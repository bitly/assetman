
import os
import unittest
import json

from assetman.manifest import Manifest
from assetman.settings import Settings

class TestManifest(unittest.TestCase):

    TEST_MANIFEST_PATH = "assetman/tests/"

    def setUp(self):
        with open(self.TEST_MANIFEST_PATH + "manifest.json", 'w') as manifest_file:
            manifest_file.write(json.dumps(dict(blocks=dict(a='a'), assets=dict(a='a')))) 

    def tearDown(self):
        os.remove(self.TEST_MANIFEST_PATH + "manifest.json")
 
    def test_can_open_manifest_path_from_settings(self):
        settings = Settings(compiled_asset_root=self.TEST_MANIFEST_PATH)

        manifest = Manifest(settings)
        path = manifest.get_path()
        assert "tests/manifest.json" in path

    def test_can_get_manifest_path_from_asset_path(self):
        manifest = Manifest()
        path = manifest.get_path(self.TEST_MANIFEST_PATH)
        assert "tests/manifest.json" in path

    def test_can_load_manifest_from_asset_path(self):
        manifest = Manifest().load(self.TEST_MANIFEST_PATH)
        assert manifest
        assert list(manifest.blocks.keys())

    def test_can_load_manifest_from_settings(self):
        settings = Settings(compiled_asset_root=self.TEST_MANIFEST_PATH)

        manifest = Manifest(settings).load()
        assert manifest
        assert list(manifest.blocks.keys())

    def test_can_write_manifest_to_path(self):
        manifest = Manifest()
        manifest.load(compiled_asset_path=self.TEST_MANIFEST_PATH)

        #spoof a field update for now
        manifest.assets['test_field'] = "hello"

        manifest.write(compiled_asset_path=self.TEST_MANIFEST_PATH)

        with open(self.TEST_MANIFEST_PATH + '/manifest.json', 'r') as manifest_file:
            manifest_json = json.loads(manifest_file.read())
            for k, v in list(manifest_json.items()):
                assert manifest._manifest.get(k) == v

if __name__ == "__main__":
    unittest.main()
