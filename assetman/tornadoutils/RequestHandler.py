import tornado.web
from assetman import static_url

class RequestHandler(tornado.web.RequestHandler):
    def static_url(self, path, include_host=None):
        return static_url(path, include_host=include_host)
