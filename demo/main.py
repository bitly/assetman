import tornado.web
import tornado.options
import tornado.httpserver
import tornado.ioloop
import tornado.httpclient

import logging
import os

import assetman.settings
import assetman.tornado.static

class Application(tornado.web.Application):
    def __init__(self): 

        app_settings = {
            "template_path" : os.path.join(os.path.dirname(__file__), "templates"),
        }
        
        handlers = [
                # Specialized "compiling" static handlers which must come
                # before the normal static handler
                (r'^/s/beta/(.*?\.scss)', assetman.tornado.static.SassCompilerHandler, {
                    'input_root': assetman.settings.get('static_dir'),
                }),
                (r"^/s/beta/(.*?\.less)", assetman.tornado.static.LessCompilerHandler, {
                    'input_root': assetman.settings.get('static_dir'),
                }),
                # "Regular" static handler
                (r"^/s/beta/(.*)", assetman.tornado.static.StaticFileHandler, {
                    'root': assetman.settings.get('static_dir'),
                    'expires': assetman.settings.env() != 'dev'
                }),
        ]
        
        tornado.web.Application.__init__(self, handlers, **app_settings)


if __name__ == "__main__":
    tornado.options.define("port", default=7385, help="Listen on port", type=int)
    tornado.options.parse_command_line()

    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(tornado.options.options.port, address="0.0.0.0")
    tornado.ioloop.IOLoop.instance().start()
