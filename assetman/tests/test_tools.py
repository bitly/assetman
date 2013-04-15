import unittest

import assetman.tools
from assetman.settings import Settings

class ToolsTest(unittest.TestCase):

    TEST_TORNADO_TEMPLATE = "assetman/tests/tornado_test_template.html"

    def test_get_parser_returns_tornado_template_parser(self):
        settings = Settings(static_dir="assetman/tests/")
        parser = assetman.tools.get_parser(self.TEST_TORNADO_TEMPLATE, settings)

        assert parser is not None

if __name__ == "__main__":
    unittest.main()
