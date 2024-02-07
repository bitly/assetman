

import os
import json
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
        self._manifest = self.make_empty_manifest()

    def data(self):
        return self._manifest

    @property
    def assets(self):
        return self._manifest['assets']
    @property
    def blocks(self):
        return self._manifest['blocks']
    
    def __str__(self):
        return '<Manifest %s assets:%s blocks:%s>' % (self.get_path(), self.assets, self.blocks)

    @classmethod
    def wrap(cls, data):
        assert isinstance(data, dict)
        assert 'assets' in data
        assert 'blocks'in data
        m = cls()
        m._manifest = data
        return m

    def get_path(self, compiled_asset_path=None):
        compiled_asset_path = compiled_asset_path or self.settings["compiled_asset_root"]
        return os.path.join(compiled_asset_path, 'manifest.json')

    def load(self, compiled_asset_path=None):
        try:
            filename = self.get_path(compiled_asset_path)
            self._manifest = json.load(open(filename))
            assert isinstance(self.assets, dict)
            assert isinstance(self.blocks, dict)
        except (AssertionError, KeyError, IOError, json.JSONDecodeError) as e:
            logging.warning('error opening manifest file: %s', e)
            self._manifest = self.make_empty_manifest()

        return self

    def write(self, compiled_asset_path=None, settings=None, **kwargs):
        if settings is not None:
            self.settings = settings
        manifest_path = self.get_path(compiled_asset_path)
        logging.info('Writing manifest to %s', manifest_path)
        json.dump(self._manifest, open(manifest_path, 'w'), indent=2, **kwargs)

    def make_empty_manifest(self):
        return {
            'blocks': {},
            'assets': {},
        }

    def normalize(self):
        """Normalizes and sanity-checks the given dependency manifest by first
        ensuring that all deps are expressed as lists instead of sets (as they are
        when the manifest is built) and then by ensuring that every dependency has
        its own entry and version in the top level of the manifest.
        """
        for parent, depspec in self.assets.items():
            depspec['deps'] = list(depspec['deps'])
            for dep in depspec['deps']:
                assert dep in self.assets, (parent, dep)
                assert depspec['version'], (parent, dep)
        for name_hash, depspec in self.blocks.items():
            assert depspec['version'], name_hash

    def union(self, newer_manifest):
        # add an age entry to the old side so we can know how many merge
        # generations ago an entry was created
        def age(entry):
            entry['age'] = entry.get('age', 0) + 1
        list(map(age, list(self.blocks.values())))
        list(map(age, list(self.assets.values())))
        self.blocks.update(newer_manifest.blocks)
        self.assets.update(newer_manifest.assets)
    
    def needs_recompile(self, newer_manifest):
        # Figure out if any static assets referenced in the new manifest are
        # missing from the cached manifest.
        def assets_in_sync(asset):
            if asset not in self.assets:
                logging.info('new asset %s (not in current manifest)', asset)
                return False
            if self.assets[asset]['version'] != newer_manifest.assets[asset]['version']:
                logging.warning('Static asset %s version mismatch', asset)
                return False
            return True
        assets_out_of_sync = not all(map(assets_in_sync, newer_manifest.assets))
        if assets_out_of_sync:
            logging.warning('Static assets out of sync')
        return assets_out_of_sync

