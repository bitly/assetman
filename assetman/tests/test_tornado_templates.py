import unittest

from assetman.compilers import JSCompiler, LessCompiler, CSSCompiler
from assetman.parsers.tornado_parser import TornadoParser
import assetman.tools
from assetman.settings import Settings

class TestTornadoTemplateParser(unittest.TestCase):

    TEST_TEMPLATE_PATH = "assetman/tests/tornado_templates/tornado_test_template.html"

    def test_get_parser_returns_tornado_template_parser(self):
        settings = Settings(static_dir="assetman/tests/")

        parser = assetman.tools.get_parser(self.TEST_TEMPLATE_PATH, 'tornado_template', settings)
        assert parser is not None

    def test_loads_template_from_path(self):
        parser = TornadoParser(self.TEST_TEMPLATE_PATH) 

        assert parser.template

    def test_returns_asset_blocks_from_template(self):
        parser = TornadoParser(self.TEST_TEMPLATE_PATH)

        compilers = list(parser.get_compilers())

        assert compilers

        compiler_types = [type(t) for t in compilers]

        assert JSCompiler in compiler_types, compilers
        assert LessCompiler in compiler_types, compilers
        assert CSSCompiler in compiler_types, compilers

if __name__ == "__main__":
    unittest.main()
