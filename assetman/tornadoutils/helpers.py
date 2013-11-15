from assetman.managers import AssetManager, JSManager, CSSManager, LessManager, SassManager
import functools

class TemplateCommands(object):
    def __init__(self, settings):
        self.include_js = functools.partial(JSManager.include, settings=settings)
        self.include_css = functools.partial(CSSManager.include, settings=settings)
        self.include_less = functools.partial(LessManager.include, settings=settings)
        self.include_sass = functools.partial(SassManager.include, settings=settings)
        self.static_url = AssetManager("", settings=settings).static_url
