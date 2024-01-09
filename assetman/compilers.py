

import base64
from collections import defaultdict
import hashlib
import logging
import mimetypes
import subprocess
import functools
import os
import re

import assetman.managers
from assetman.tools import make_absolute_static_path, make_relative_static_path, get_static_pattern, make_output_path

def run_proc(cmd, stdin=None):
    """Runs the given cmd as a subprocess. If the exit code is non-zero, calls
    sys.exit with the exit code (aborting program). If stdin is given, it will
    be piped to the subprocess's stdin.

    The cmd should be a command suitable for passing to subprocess.call (ie, a
    list, usually).
    """
    popen_args = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if stdin is not None:
        popen_args['stdin'] = subprocess.PIPE
        stdin = stdin.encode()
    proc = subprocess.Popen(cmd, **popen_args)
    out, err = proc.communicate(input=stdin)
    if proc.returncode != 0:
        raise CompileError(cmd, err)
    elif err:
        logging.warning('%s stderr:\n%s', cmd[0], err)
    return out.decode()

class CompileError(Exception):
    """Error encountered while compiling assets."""

class ParseError(Exception):
    """Error encountered while parsing templates."""

class DependencyError(Exception):
    """Invalid or missing dependency."""

class AssetCompiler(object):
    """A base class meant to be mixed in with `assetman.AssetManager`
    subclasses to provide support for compiling asset blocks.
    """

    # What do this compiler's {% assetman.include_* %} expressions look like?
    include_expr = None

    def __init__(self, *args, **kwargs): 
        super(AssetCompiler, self).__init__(*args, **kwargs)

    def required_setting_file(self, key):
        """
        Get the named setting from self.settings and give an informative
        error if it's missing.

        This is helpful because when run under multiprocessing, we get only
        the exception name and message without a useful traceback,
        so it's hard to know how/where to fix the problem.
        http://bugs.python.org/issue13831
        """
        path = self.settings[key]
        assert os.path.exists(path), "missing file %s (settings key %s)" % (path, key)
        return path
        

    def compile(self, **kwargs):
        """Compiles the assets in this Assetman block. Returns compiled source code as a string."""
        logging.info("Compiling %s", self)
        result =  self.do_compile(**kwargs)
        return result

    def do_compile(self, **kwargs):
        raise NotImplementedError

    def needs_compile(self, cached_manifest, current_manifest):
        """Determines whether or not this asset block needs compilation by
        comparing the versions in the given manifests and checking the version
        on disk.
        """
        name_hash = self.get_hash()
        assert name_hash in current_manifest.blocks, self
        content_hash = current_manifest.blocks[name_hash]['version']
        if name_hash in cached_manifest.blocks:
            if cached_manifest.blocks[name_hash]['version'] == content_hash:
                compiled_path = self.get_compiled_path()
                if not os.path.exists(compiled_path):
                    logging.warning('Missing compiled asset %s from %s',
                                 compiled_path, self)
                    return True
                return False
            else:
                logging.warning('Contents of %s changed', self)
        else:
            compiled_path = self.get_compiled_path()
            if not os.path.exists(compiled_path):
                logging.warning('New/unknown hash %s from %s', name_hash, self)
            else:
                logging.info('new hash %s from %s but already exists on file %s', name_hash, self, compiled_path)
                return False
        return True

    def get_current_content_hash(self, manifest):
        """Gets the md5 hash for each of the files in this manager's list of assets."""
        h = hashlib.md5()
        for path in self.get_paths():
            relative_path = make_relative_static_path(self.settings['static_dir'], path)
            assert relative_path in manifest.assets, relative_path
            h.update(manifest.assets[relative_path]['version'].encode())
        return h.hexdigest()

    def get_paths(self):
        """Returns a list of absolute paths to the assets contained in this manager."""
        paths = list(map(functools.partial(make_absolute_static_path, self.settings['static_dir']), self.rel_urls))
        try:
            assert all(map(os.path.isfile, paths))
        except AssertionError:
            missing = [path for path in paths if not os.path.isfile(path)]
            raise DependencyError(self.src_path, ','.join(missing))
        return paths

    def get_compiled_path(self):
        """Creates the output filename for the compiled assets of the given manager."""
        return make_output_path(self.settings['compiled_asset_root'], self.get_compiled_name())


class JSCompiler(AssetCompiler, assetman.managers.JSManager):

    include_expr = 'include_js'

    def do_compile(self, **kwargs):
        """We just hand each of the input paths to the closure compiler and
        let it go to work.
        """
        cmd = [
            self.required_setting_file("java_bin"), '-Xss16m', '-jar', self.required_setting_file("closure_compiler"),
            '--compilation_level', 'SIMPLE_OPTIMIZATIONS',
            '--language_in', 'ECMASCRIPT5',
            ]
        for path in self.get_paths():
            cmd.extend(('--js', path))
        return run_proc(cmd)


class CSSCompiler(AssetCompiler, assetman.managers.CSSManager):

    include_expr = 'include_css'

    def do_compile(self, **kwargs): 
        """Compiles CSS files using the minify compressor. Since the compressor
        will only accept a single input file argument, we have to manually
        concat the CSS files in the batch and pipe them into the compressor.

        https://github.com/tdewolff/minify/tree/master/cmd/minify

        This also allows us to accept a css_input argument, so this function
        can be used by the compile_less function as well.
        """
        css_input = kwargs.get("css_input")
        if css_input is None:
            css_input = '\n'.join(
                open(path).read() for path in self.get_paths())
        if not kwargs.get("skip_inline_images"):
            css_input = self.inline_images(css_input)
        cmd = [
           self.required_setting_file("minify_compressor_path"),
           '--type=css'
        ]
        return run_proc(cmd, stdin=css_input)

    def inline_images(self, css_src):
        """Here we will "inline" any images under a certain size threshold
        into the CSS in the form of "data:" URIs.

        IE 8 can't handle URLs longer than 32KB, so any image whose data URI
        is larger than that is skipped.
        """
        KB = 1024.0
        MAX_FILE_SIZE = 24 * KB # Largest size we consider for inlining
        MAX_DATA_URI_SIZE = 32 * KB # IE8's maximum URL size

        # We only want to replace asset references that show up inside of
        # `url()` rules (this avoids weird constructs like IE-specific filters
        # for transparent PNG support).
        base_pattern = get_static_pattern(self.settings.get('static_url_prefix'))
        pattern = r"""(url\(["']?)%s(["']?\))""" % base_pattern

        # Track duplicate images so that we can warn about them
        seen_assets = defaultdict(int)

        def replacer(match):
            before, url_prefix, rel_path, after = match.groups()
            path = make_absolute_static_path(self.settings['static_dir'], rel_path)
            assert os.path.isfile(path), (path, str(self))
            if os.stat(path).st_size > MAX_FILE_SIZE:
                logging.debug('Not inlining %s (%.2fKB)', path, os.stat(path).st_size / KB)
                return match.group(0)
            else:
                encoded = base64.b64encode(open(path).read())
                mime_type, _ = mimetypes.guess_type(path)
                if not mime_type and path.endswith('.otf'):
                    mime_type = 'application/octet-stream'
                if not mime_type and path.endswith('.ttf'):
                    mime_type = 'font/ttf'
                if not mime_type and path.endswith('.eot'):
                    mime_type = 'application/vnd.ms-fontobject'
                if not mime_type and path.endswith('.woff'):
                    mime_type = 'application/x-font-woff'
                if not mime_type and path.endswith('.json'):
                    mime_type = 'application/json'
                if not mime_type and path.endswith('.svg'):
                    mime_type = 'image/svg+xml'
                data_uri = 'data:%s;base64,%s' % (mime_type, encoded)
                if len(data_uri) >= MAX_DATA_URI_SIZE:
                    logging.debug('Not inlining %s (%.2fKB encoded)', path, len(data_uri) / KB)
                    return match.group(0)
                seen_assets['%s%s' % (url_prefix, rel_path)] += 1
                return ''.join([before, data_uri, after])

        result = re.sub(pattern, replacer, css_src)

        for url, count in seen_assets.items():
            if count > 1:
                logging.warning('inline asset duplicated %dx: %s', count, url)

        return result


class LessCompiler(CSSCompiler, assetman.managers.LessManager):

    include_expr = 'include_less'

    def do_compile(self, **kwargs):
        """Compiling less files is an ugly 2-step process, because the lessc
        compiler sucks.

        First, we have to run each of the given paths through lessc
        separately, capturing and concatenating the output. Then, we send all
        of the compiled CSS to the YUI compressor.
        """
        # First we "compile" the less files into CSS
        lessc = self.required_setting_file("lessc_path")
        outputs = [run_proc([lessc, path]) for path in self.get_paths()]
        return super(LessCompiler, self).do_compile(css_input='\n'.join(outputs))


class SassCompiler(CSSCompiler, assetman.managers.SassManager):

    include_expr = 'include_sass'

    def do_compile(self, **kwargs):
        cmd = [
            self.required_setting_file("sass_compiler_path"),
            '--compass', '--trace', '--no-cache', '--stop-on-error', '-l'
        ] + self.rel_urls
        output = run_proc(cmd)
        return super(SassCompiler, self).do_compile(css_input=output)

