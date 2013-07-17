import assetman
import functools

class TornadoTemplateHelper(object):
    def __init__(self, settings):
        self.include_js = functools.partial(assetman.JSManager.include, settings=settings)
        self.include_css = functools.partial(assetman.CSSManager.include, settings=settings)
        self.include_less = functools.partial(assetman.LessManager.include, settings=settings)
        self.include_sass = functools.partial(assetman.SassManager.include, settings=settings)
        self.static_url = assetman.AssetManager("", settings=settings).static_url
