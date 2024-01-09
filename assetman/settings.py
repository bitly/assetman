

import os
import json

example_settings = {   
    # Assetman needs to be able to point at assets to be served by us and by a
    # CDN. We have to serve our own mobile assets in production because of
    # restrictions in offline app caching.

    # Assetman needs to know how to point at assets in three different places:
    # the "normal" static URL (during dev), a "cdn proxy" URL on our own hosts
    # (for, e.g., mobile site or non-CDN fallback), and a set of cdn hosts.
    "static_url_prefix": "/s/",
    "local_cdn_url_prefix": "/cdn/",
    "cdn_url_prefix": [
        '//1.example.net/',
        '//2.example.net/',
        '//3.example.net/',
    ],
    # If we need to fall back to serving all static assets ourselves
    # 'cdn_url_prefix': ['/cdn/'],

    # Where are static files found in the filesystem for this project?
    "static_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), "static")),
    # And where are compiled static assets found?
    "compiled_asset_root": "/data/compiled_assets",
}
default_settings = {
    "closure_compiler":"/bin/closure-compiler.jar",
    "minify_compressor_path": "/bin/minify",
    "sass_compiler": "/bin/sass",
    "lessc_path": "/bin/lessc",
    "java_bin": "java"
}

class Settings(dict):
    """
    A custom dictionary object representing an Assetman configuration.
    Settings may be loaded from a configuration file or initialized through
    the object's creation. If a file is provided, additional arguments will
    serve as overrides to any values found in the file.
    """
    def __init__(self, configuration_file=None, *args, **kwargs):
        self._config_path = configuration_file
        self.update(default_settings)
        self.update(dict(*args, **kwargs))

    @classmethod
    def load(cls, path):
        """
        Loads a settings configuration file, overwriting any existing setting
        values.
        """ 

        with open(path, 'r') as config:
            return Settings(configuration_file=path, **json.loads(config.read()))

    def save(self, path=None):
        """
        Saves the current settings object to its source configuration file. If
        a path is provided, it will save to the path instead.
        """

        usepath = path if path else self._path 

        if not usepath:
            raise Exception("No destination file specified to save.")

        with open(usepath, 'w') as outfile:
            outfile.write(json.dumps(self))
