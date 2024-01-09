#!/bin/python



import os
import re
import logging
import multiprocessing
import hashlib

from optparse import OptionParser

from assetman.manifest import Manifest 
from assetman.tools import iter_template_paths, get_static_pattern, make_relative_static_path, make_absolute_static_path, get_parser
from assetman.compilers import DependencyError, ParseError, CompileError
from assetman.S3UploadThread import upload_assets_to_s3

from assetman.settings import Settings

class NeedsCompilation(Exception):
    pass

parser = OptionParser(description='Compiles assets for AssetMan')

parser.add_option(
    '--tornado_template_dirs', type="string", action='append', 
    help='Directory to crawl looking for static assets to compile.')

parser.add_option(
    '--template-ext', type="string", default="html",
    help='File extension of compilable templates.')

parser.add_option(
    '--static-dir', type="string", default='static',
    help='Directory where static assets are located in this project.')

parser.add_option(
    '--output-dir', type="string", default='assets',
    help='Directory where compiled assets are to be placed.')

parser.add_option(
    '--static-path-prefix', type="string", default="",
    help="Directory prefix to access static assets (matching url prefix)")

parser.add_option(
    '--static-url-path', type="string", default="/",
    help="Static asset base url path")

parser.add_option(
    '--compiled-manifest-path', type="string", default="/",
    help="Location to read/write the compiled asset manifest")

parser.add_option(
    '-t', '--test-needs-compile', action="store_true",
    help='Check whether a compile is needed. Exits 1 if so.')

parser.add_option(
    '-f', '--force-recompile', action="store_true",
    help='Force a recompile of everything.')

parser.add_option(
    '-i', '--skip-inline-images', action="store_true",
    help='Do not sub data URIs for small images in CSS.')

parser.add_option(
    '--skip-s3-upload', action="store_true",
    help='Skip uploading anything to s3')

parser.add_option(
    '--aws_username', type="string", 
    help="AWS username, required for uploading to s3 (no upload if ommited)")

parser.add_option(
    '--aws_access_key', type="string",
    help="AWS access key, required for uploading to s3")

parser.add_option(
    '--aws_secret_key', type="string",
    help="AWS secret key, required for uplaoding to s3")

parser.add_option(
    '--s3_assets_bucket', type="string",
    help="AWS s3 bucket to store assets, required for uploading to s3")


# Static calls are like {{ assetman.static_url('path.jpg') }} or include
# an extra arg: {{ assteman.static_url('path.jpg', local=True) }}
static_url_call_finder = re.compile(r'assetman\.static_url\((.*?)(,.*?)?\)').finditer

##############################################################################
# Multiprocessing workers
##############################################################################
class ParserWorker(object):
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, template_info):
        """Takes a template path and returns a list of AssetCompiler instances
        extracted from that template. Helper function to be called by each process
        in the process pool created by find_assetman_compilers, above.
        """
        assert isinstance(template_info, (list, tuple))
        template_path, template_type = template_info
        template = get_parser(template_path, template_type, self.settings)
        return list(template.get_compilers())

class CompileWorker(object):
    """Takes an AssetCompiler and, based on the manifest, compiles the assets,
    writing the results to disk. Used as a helper function when compiling
    assets in parallel.
    """
    def __init__(self, skip_inline_images, manifest):
        self.manifest = manifest
        self.skip_inline_images = skip_inline_images

    def __call__(self, compiler):
        with open(compiler.get_compiled_path(), 'w') as outfile:
            outfile.write(compiler.compile(skip_inline_images=self.skip_inline_images))


##############################################################################
# Compiler support functions
##############################################################################
def get_file_hash(path, block_size=8192):
    """Calculates the content hash for the file at the given path."""
    md5 = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            block = f.read(block_size)
            if not block:
                break
            md5.update(block)
    return md5.hexdigest()

##############################################################################
# Build and compare dependency manifests
##############################################################################
def static_finder(s, static_url_prefix):
    pattern = get_static_pattern(static_url_prefix)
    return re.compile(pattern).finditer(s)

def import_finder(s):
    return re.compile(r"""@import (url\()?(["'])(.*?)(\2)""").finditer(s)

def empty_asset_entry():
    """This is the form of each 'assets' entry in the manifest as we're
    building it.
    """
    return {
        'version': None,
        'versioned_path': None,
        'deps': set()
    }

def build_compilers(path_infos, settings):
    """Parse each template and return a list of AssetCompiler instances for
    any assetman.include_* blocks in each template.
    """
    # pool.map will not ordinarily handle KeyboardInterrupts cleanly,
    # but if you give them a timeout they will. More info:
    # http://bugs.python.org/issue8296
    # http://stackoverflow.com/a/1408476/151221

    parser_worker = ParserWorker(settings)
    # a sync version for easier debugging (to see exceptions)
    compiler_lists = [parser_worker(x) for x in path_infos]
    output = [item for sublist in compiler_lists for item in sublist]
    return output
    # pool = multiprocessing.Pool()
    # return [x for xs in pool.map_async(parser_worker, path_infos).get(1e100) for x in xs]


def iter_template_deps(static_dir, src_path, static_url_prefix):
    """Yields static resources included as {{assetman.static_url()}} calls
    in the given source path, which should be a Tornado template.

    TODO: need one of these for every supported template language?
    """
    src = open(src_path).read()
    for match in static_url_call_finder(src):
        arg = match.group(1)
        quotes = '\'"'
        if arg[0] not in quotes or arg[-1] not in quotes:
            msg = 'Vars not allowed in static_url calls: %s' % match.group(0)
            raise ParseError(src_path, msg)
        else:
            dep_path = make_absolute_static_path(static_dir, arg.strip(quotes))
            if os.path.isfile(dep_path):
                yield dep_path
            else:
                logging.warning('Missing dep %s (src: %s)', dep_path, src_path)

###############################################################################

def version_dependency(path, manifest):
    """A dependency's version is calculated using this recursive formula:

        version = md5(md5(path_contents) + version(deps))

    So, the version of a path is based on the hash of its own file contents as
    well as those of each of its dependencies.
    """
    assert path in manifest.assets, path
    if manifest.assets[path]['version']:
        return manifest.assets[path]['version']
    h = hashlib.md5()
    h.update(get_file_hash(make_absolute_static_path(manifest.settings['static_dir'], path)).encode())
    for dep_path in manifest.assets[path]['deps']:
        h.update(version_dependency(dep_path, manifest).encode())
    version = h.hexdigest()
    _, ext = os.path.splitext(path)
    manifest.assets[path]['version'] = version
    manifest.assets[path]['versioned_path'] = version + ext
    return manifest.assets[path]['version']


def iter_deps(static_dir, src_path, static_url_prefix):
    """Yields first-level dependencies from the given source path."""
    assert os.path.isfile(src_path), src_path
    dep_iter = {
        '.js': iter_js_deps,
        '.css': iter_css_deps,
        '.less': iter_css_deps,
        '.scss': iter_scss_deps,
        '.html': iter_template_deps,
        }.get(os.path.splitext(src_path)[1])
    if dep_iter:
        for path in dep_iter(static_dir, src_path, static_url_prefix):
            yield path

def iter_css_deps(static_dir, src_path, static_url_prefix):
    """Yields first-level dependencies from the given source path, which
    should be a CSS, Less, or Sass file. Dependencies will either be more
    CSS/Less/Sass files or static image resources.
    """
    assert os.path.isfile(src_path), src_path
    root = os.path.dirname(src_path)
    src = open(src_path).read()

    # First look for CSS/Less imports and recursively descend into them
    for match in import_finder(src):
        path = match.group(3)
        if src_path.endswith('.less') and os.path.splitext(path)[1] == '':
            path = path + '.less'
        # normpath will take care of '../' path components
        new_root = os.path.normpath(os.path.join(root, os.path.dirname(path)))
        full_path = os.path.join(new_root, os.path.basename(path))
        assert os.path.isdir(new_root), new_root
        assert os.path.isfile(full_path), full_path
        yield full_path

    # Then look for static assets (images, basically)
    for dep in iter_static_deps(static_dir, src_path, static_url_prefix):
        yield dep

def iter_scss_deps(src_path):
    """Yields first-level dependencies from the given source path, which
    should be a Sass file. Dependencies will either be more
    Sass files or static image resources.
    """
    assert os.path.isfile(src_path), src_path
    root = os.path.dirname(src_path)
    src = open(src_path).read()

    # First look for CSS/Less imports and recursively descend into them
    for match in import_finder(src):
        path = match.group(3)
        if path.startswith('compass/'):
            continue
        # normpath will take care of '../' path components
        new_root = os.path.normpath(os.path.join(root, os.path.dirname(path)))
        full_path = os.path.join(new_root, os.path.basename(path))
        assert os.path.isdir(new_root), new_root
        assert os.path.isfile(full_path), full_path
        yield full_path

    # Then look for static assets (images, basically)
    for dep in iter_static_deps(src_path):
        yield dep


def iter_js_deps(static_dir, src_path, static_url_prefix):
    """Yields first-level dependencies from the given source path, which
    should be a JavaScript file. Dependencies will be static image resources.
    """
    return iter_static_deps(static_dir, src_path, static_url_prefix)

def iter_static_deps(static_dir, src_path, static_url_prefix):
    """Yields static resources (ie, image files) from the given source path.
    """
    assert os.path.isfile(src_path), src_path
    for match in static_finder(open(src_path).read(), static_url_prefix):
        dep_path = make_absolute_static_path(static_dir, match.group(2))
        if os.path.isfile(dep_path):
            yield dep_path
        else:
            logging.warning('Missing dep %s (src: %s)', dep_path, src_path)


def _build_manifest_helper(static_dir, src_paths, static_url_prefix, manifest):
    assert isinstance(src_paths, (list, tuple))
    for src_path in src_paths:
        # Make sure every source path at least has the skeleton entry
        rel_src_path = make_relative_static_path(static_dir, src_path)
        logging.info('_build_manifest_helper %s (crrent %s)', src_path, manifest.assets.get(rel_src_path))
        manifest.assets.setdefault(rel_src_path, empty_asset_entry())
        for dep_path in iter_deps(static_dir, src_path, static_url_prefix):
            logging.info('%s > dependency %s', src_path, dep_path)
            rel_path = make_relative_static_path(static_dir, dep_path)
            manifest.assets[rel_src_path]['deps'].add(rel_path)
            _build_manifest_helper(static_dir, [dep_path], static_url_prefix, manifest)


def build_manifest(tornado_paths, settings):
    """Recursively builds the dependency manifest for the given list of source
    paths.
    """
    assert isinstance(tornado_paths, (list, tuple))

    paths = list(set(tornado_paths))
    # First, parse each template to build a list of AssetCompiler instances
    path_infos = [(x, 'tornado_template') for x in tornado_paths]
    compilers = build_compilers(path_infos, settings)

    # Add each AssetCompiler's paths to our set of paths to search for deps
    paths = set(paths)
    for compiler in compilers:
        new_paths = compiler.get_paths()
        if settings.get('verbose'):
            print(compiler, new_paths)
        paths.update(new_paths)
    paths = list(paths)

    # Start building the new manifest
    manifest = Manifest(settings)
    _build_manifest_helper(settings['static_dir'], paths, settings['static_url_prefix'], manifest)
    assert all(make_relative_static_path(settings['static_dir'], path) in manifest.assets for path in paths)

    # Next, calculate the version hash for each entry in the manifest
    for src_path in manifest.assets:
        version_dependency(src_path, manifest)

    # Normalize and validate the manifest
    manifest.normalize()

    # Update the 'blocks' section of the manifest for each asset block
    for compiler in compilers:
        name_hash = compiler.get_hash()
        content_hash = compiler.get_current_content_hash(manifest)
        manifest.blocks[name_hash] = {
            'version': content_hash,
            'versioned_path': content_hash + '.' + compiler.get_ext(),
        }
        
    return manifest, compilers

def _create_settings(options):
    return Settings(compiled_asset_root=options.output_dir,
                    static_dir=options.static_dir,
                    static_url_prefix=options.static_url_path,
                    tornado_template_dirs=options.tornado_template_dirs,
                    template_extension=options.template_ext,
                    test_needs_compile=options.test_needs_compile,
                    skip_s3_upload=options.skip_s3_upload,
                    force_s3_upload=False,
                    force_recompile=options.force_recompile,
                    skip_inline_images=options.skip_inline_images,
                    aws_username=options.aws_username,
                    aws_access_key=options.aws_access_key,
                    aws_secret_key=options.aws_secret_key,
                    verbose=False,
                    s3_assets_bucket=options.s3_assets_bucket)

def run(settings):
    if not re.match(r'^/.*?/$', settings.get('static_url_prefix')):
        raise Exception('static_url_prefix setting must begin and end with a slash')

    if not os.path.isdir(settings['compiled_asset_root']) and not settings['test_needs_compile']:
        logging.info('Creating output directory: %s', settings['compiled_asset_root'])
        os.makedirs(settings['compiled_asset_root'])

    for d in settings['tornado_template_dirs']:
        if not os.path.isdir(d):
            raise Exception('Template directory not found: %r', d)

    if not os.path.isdir(settings['static_dir']):
        raise Exception('Static directory not found: %r', settings['static_dir'])

    # Find all the templates we need to parse
    tornado_paths = list(iter_template_paths(settings['tornado_template_dirs'], settings['template_extension']))

    if not tornado_paths:
        logging.warning("No templates found")

    # Load the current manifest and generate a new one
    cached_manifest = Manifest(settings).load()
    try:
        current_manifest, compilers = build_manifest(tornado_paths, settings)
    except ParseError as e:
        src_path, msg = e.args
        logging.error('Error parsing template %s', src_path)
        logging.error(msg)
        raise Exception
    except DependencyError as e:
        src_path, missing_deps = e.args
        logging.error('Dependency error in source %s!', src_path)
        logging.error('Missing paths: %s', missing_deps)
        raise Exception("dependency error in %s. missing %s" % (src_path, missing_deps))

    # Remove duplicates from our list of compilers. This de-duplication must
    # happen after the current manifest is built, because each non-unique
    # compiler's source path figures into the dependency tracking. But we only
    # need to actually compile each block once.
    logging.debug('Found %d assetman block compilers', len(compilers))
    compilers = list(dict((c.get_hash(), c) for c in compilers).values())
    logging.debug('%d unique assetman block compilers', len(compilers))

    # update the manifest on each our compilers to reflect the new manifest,
    # which is needed to know the output path for each compiler.
    for compiler in compilers:
        compiler.manifest = current_manifest

    # Figure out which asset blocks need to be (re)compiled, if any.
    def needs_compile(compiler):
        return compiler.needs_compile(cached_manifest, current_manifest)

    if settings['force_recompile']:
        to_compile = compilers
    else:
        to_compile = list(filter(needs_compile, compilers))

    if to_compile or cached_manifest.needs_recompile(current_manifest):
        # If we're only testing whether a compile is needed, we're done
        if settings['test_needs_compile']:
            raise NeedsCompilation()

        pool = multiprocessing.Pool()
        try:
            # See note above about bug in pool.map w/r/t KeyboardInterrupt.
            _compile_worker = CompileWorker(settings.get('skip_inline_images', False), current_manifest)
            pool.map_async(_compile_worker, to_compile).get(1e9) # previously set to 1e100 which caused overflow of C _PyTime_t_
        except CompileError as e:
            cmd, msg = e.args
            logging.error('Compile error!')
            logging.error('Command: %s', ' '.join(cmd))
            logging.error('Error:   %s', msg)
            raise Exception('Compilation Failed')

        #TODO: refactor to some chain of command for plugins
        if settings['aws_username']:
            upload_assets_to_s3(current_manifest, settings, skip_s3_upload=settings['skip_s3_upload'])
        

        if settings.get('merge_manifest_updates', True):
            cached_manifest.union(current_manifest)
        else:
            cached_manifest = current_manifest
        cached_manifest.write(settings=settings)
        return cached_manifest
    return current_manifest

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    options, args = parser.parse_args()
    settings = _create_settings(options) 
    run(settings)
