from __future__ import with_statement

import unittest
import simplejson as json

from assetman.settings import Settings

class TestSettings(unittest.TestCase):
    def test_settings_can_load_from_file(self):
        settings_stub = {
            'testkey1': "testvalue1",
            'testkey2': "testvalue2",
        }

        savepath = "./test_settings"

        with open(savepath, 'w') as saved_file:
            saved_file.write(json.dumps(settings_stub))

        s = Settings.load(savepath)

        assert s is not None
        for k, v in s.items():
            assert settings_stub[k] == v

    def test_settings_can_write_to_file(self):
        s = Settings()
        s['testkey1'] = "testvalue1"
        s['testkey2'] = "testvalue2"

        savepath = "./test_settings"
        s.save(path=savepath)

        try:
            with open(savepath, 'r') as saved_file:
                assert saved_file, "file not found, save failed"

                settings_dict = json.loads(saved_file.read())
                for k, v in settings_dict.items():
                    assert s[k] == v

        except Exception, ex:
            self.fail(str(ex))

if __name__ == "__main__":
    unittest.main()
