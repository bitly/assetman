from __future__ import absolute_import, with_statement

import os
import simplejson as json
import logging

from assetman.settings import Settings

class Manifest(object):
    """
    Represents the asset manifest. 
    TODO: Currently this only handles the utility reading and writing to file functions. 
    Long-term goal is to create a complete model representation of the manifest.
    """

    _manifest = None

    def __init__(self, settings=None):
        self.settings = settings or Settings()

    def get_path(self, compiled_asset_path=None):
        compiled_asset_path = compiled_asset_path or self.settings["compiled_asset_root"]
        return os.path.join(compiled_asset_path, 'manifest.json')

    def load(self, compiled_asset_path=None):
        if self._manifest is None:
            try:
                self._manifest = json.load(open(self.get_path(compiled_asset_path)))
                assert isinstance(self._manifest['assets'], dict)
                assert isinstance(self._manifest['blocks'], dict)
            except (AssertionError, KeyError, IOError, json.JSONDecodeError), e:
                logging.warn('Missing/invalid manifest file: %s', e)
                self._manifest = self.make_empty_manifest()

            return self._manifest

    def write(self, manifest=None, compiled_asset_path=None, **kwargs):
        manifest = manifest or self._manifest
        manifest_path = self.get_path(compiled_asset_path)
        logging.info('Writing manifest to %s', manifest_path)
        json.dump(manifest, open(manifest_path, 'w'), indent=2, **kwargs)

    def make_empty_manifest(self):
        return {
            'blocks': {},
            'assets': {},
        }
