from assetman import AssetManager 

class AssetmanMixin(object):
    def __init__(self, *args, **kwargs):
        self.asset_manager = AssetManager("", settings=self.settings['assetman_settings'],**kwargs)

    def static_url(self, path, include_host=None):
        return self.asset_manager.static_url(path, include_host=include_host)
