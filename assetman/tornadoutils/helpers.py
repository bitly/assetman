from assetman.managers import AssetManager, JSManager, CSSManager, LessManager, SassManager
import functools

class TemplateCommands(object):
    def __init__(self, settings, local=None):
        self.include_js = functools.partial(JSManager.include, settings=settings, local=local)
        self.include_css = functools.partial(CSSManager.include, settings=settings, local=local)
        self.include_less = functools.partial(LessManager.include, settings=settings, local=local)
        self.include_sass = functools.partial(SassManager.include, settings=settings, local=local)
        self.static_url = AssetManager("", settings=settings).static_url
