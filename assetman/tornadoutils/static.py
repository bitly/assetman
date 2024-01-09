

import calendar
import datetime
import email
import logging
import mimetypes
import os
import stat
import subprocess

import tornado.web
import assetman


class AssetmanMixin(object):
    def __init__(self, *args, **kwargs):
        super(AssetmanMixin, self).__init__(*args, **kwargs)
        assert hasattr(self.application, 'assetman_template_helper')
        assert isinstance(self.application.assetman_template_helper, 
            assetman.tornadoutils.helpers.TemplateCommands) 

    def render_string(self, template_name, **kwargs):
        return super(AssetmanMixin, self).render_string(template_name, 
            assetman=self.application.assetman_template_helper, **kwargs)



class StaticFileHandler(tornado.web.RequestHandler):

    def initialize(self, root, expires=True):
        assert isinstance(expires, bool)
        self.root = root
        self.expires = expires

    def head(self, path):
        return self.get(path, include_body=False)

    def get(self, path, include_body=True):
        abs_path = os.path.normpath(os.path.join(self.root, path))

        if not os.path.isfile(abs_path) or not abs_path.startswith(self.root):
            raise tornado.web.HTTPError(404, 'File %s not found', path)

        stat_result = os.stat(abs_path)
        modified = datetime.datetime.utcfromtimestamp(stat_result[stat.ST_MTIME])
        self.set_header("Last-Modified", modified)
        self.set_expires_header()
        self.set_mime_type(abs_path)

        # Check the If-Modified-Since, and don't send the result if the
        # content has not been modified
        ims_value = self.request.headers.get("If-Modified-Since")
        if ims_value is not None:
            date_tuple = email.utils.parsedate(ims_value)
            if_since = datetime.datetime.utcfromtimestamp(calendar.timegm(date_tuple))
            if if_since >= modified:
                logging.debug('Not modified since %s', if_since)
                self.set_status(304)
                return

        if not include_body:
            return

        self.set_header("Content-Length", stat_result[stat.ST_SIZE])
        with open(abs_path, 'rb') as f:
            logging.debug('Response headers: %r', self._headers)
            self.write(f.read())

    def set_expires_header(self):
        if self.expires:
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=365*10)
            max_age = 86400 * 365 * 10
            self.set_header("Expires", expires_at)
            self.set_header("Cache-Control", "public, max-age=%s" % max_age)
        else:
            # no-cache == revalidate before serving from cache; different from
            # no-store
            self.set_header("Cache-Control", "no-cache")

    def set_mime_type(self, url):
        mime_type, encoding = mimetypes.guess_type(url)
        if not mime_type and url.endswith('.otf'):
            mime_type = 'application/octet-stream'
        if not mime_type and url.endswith('.ttf'):
            mime_type = 'font/ttf'
        if not mime_type and url.endswith('.eot'):
            mime_type = 'application/vnd.ms-fontobject'
        if not mime_type and url.endswith('.woff'):
            mime_type = 'application/x-font-woff'
        if not mime_type and url.endswith('.json'):
            mime_type = 'application/json'
        if not mime_type and url.endswith('.svg'):
            mime_type = 'image/svg+xml'
        if not mime_type and url.endswith('.csv'):
            mime_type = 'text/csv'
        if mime_type:
            self.set_header("Content-Type", mime_type)
            if mime_type == 'text/csv':
                filename = os.path.basename(url)
                disposition = "attachment; filename=%s" % filename
                self.set_header("Content-Disposition", disposition)
        else:
            logging.warning('Unable to guess mime type for %r', url)


class CompilingStaticHandler(tornado.web.RequestHandler):

    content_type = None

    def initialize(self, input_root, output_root=None):
        """Input root is where we will look for source files and output root
        is where we will put compiled/intermediate files (if necessary).
        """
        assert self.content_type, 'content_type must be set on %s' % self
        assert os.path.isdir(input_root), 'Input root %r must be a directory' % input_root
        if output_root is not None:
            assert os.path.isdir(output_root), 'Output root %r must be a directory' % output_root
        self.input_root = input_root
        self.output_root = output_root

    def get(self, path):
        if not self.settings['assetman_settings']['enable_static_compilation']:
            logging.error('Static compiler handler not enabled')
            raise tornado.web.HTTPError(404)

        abs_path = os.path.normpath(os.path.join(self.input_root, path))
        if not os.path.isfile(abs_path) or not abs_path.startswith(self.input_root):
            raise tornado.web.HTTPError(404, 'File %s not found', path)

        logging.debug('Compiling %s', abs_path)
        output = self.do_compile(abs_path, path)
        self.set_header('Content-Type', self.content_type)
        self.set_header('Cache-Control', 'no-cache')
        self.write(output)

    def do_compile(self, abs_path, url_path):
        raise NotImplementedError

    def run_proc(self, cmd, stdin=None, env=None):
        """Runs the given cmd as a subprocess, where cmd is a list suitable
        for passing to subprocess.call. Returns a 3-tuple of

            (exit code, stdout, stderr)
        """
        assert isinstance(cmd, (list, tuple))
        popen_args = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if stdin is not None:
            popen_args['stdin'] = subprocess.PIPE
        if env is not None:
            new_env = os.environ.copy()
            new_env.update(env)
            popen_args['env'] = new_env
        proc = subprocess.Popen(cmd, **popen_args)
        out, err = proc.communicate(input=stdin)

        if proc.returncode == 0:
            return out
        logging.error('Error in %r %r', ' '.join(cmd), err)
        raise tornado.web.HTTPError(500)


class LessCompilerHandler(CompilingStaticHandler):

    content_type = 'text/css'

    def do_compile(self, abs_path, url_path):
        cmd = [self.settings['assetman_settings']['lessc_path'], abs_path]
        env = {
            'PATH': os.environ.get('PATH', '') 
        }
        return self.run_proc(cmd, env=env)


class SassCompilerHandler(CompilingStaticHandler):

    content_type = 'text/css'

    def do_compile(self, abs_path, url_path):
        # We need to change into our input_root directory, which is where the
        # special config.rb file lives, which tells Compass how to compile
        # things.
        old_cwd = os.getcwd()
        os.chdir(self.input_root)
        cmd = [
            self.settings['assetman_settings']['sass_compiler_path'],
            '--compass', '--trace', '-l', '--stop-on-error',
            abs_path,
        ]
        try:
            out = self.run_proc(cmd)
            return out
        finally:
            os.chdir(old_cwd)
