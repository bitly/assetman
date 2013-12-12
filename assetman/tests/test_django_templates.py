import unittest
import test_shunt # pyflakes.ignore

import django.template
from assetman.compilers import JSCompiler, LessCompiler, CSSCompiler
from assetman.parsers.django_parser import DjangoParser
import assetman.tools
from assetman.settings import Settings

class TestDjangoTemplateParser(unittest.TestCase):

    TEST_TEMPLATE_PATH = 'django_test_template.html'

    def test_get_parser_returns_django_template_parser(self):
        settings = Settings(static_dir="assetman/tests/")
        parser = assetman.tools.get_parser(self.TEST_TEMPLATE_PATH, 'django_template', settings)
        assert parser is not None

    def test_loads_template_from_path(self):
        parser = DjangoParser(self.TEST_TEMPLATE_PATH) 
        assert parser.template

    def test_returns_asset_blocks_from_template(self):
        parser = DjangoParser(self.TEST_TEMPLATE_PATH)
        compilers = list(parser.get_compilers())

        assert compilers

        compiler_types = [type(t) for t in compilers]

        assert JSCompiler in compiler_types, compilers
        assert LessCompiler in compiler_types, compilers
        assert CSSCompiler in compiler_types, compilers

    def test_template_rendering_without_cdn(self):
        parser = DjangoParser(self.TEST_TEMPLATE_PATH)
        template = parser.template
        context = django.template.context.Context({})
        result = template.render(context)
        self.assertIn('<link href="STATIC/assets/test.css"', result)
        self.assertIn('<link href="STATIC/assets/test.less"', result)
        self.assertIn('<script src="STATIC/assets/test.js"', result)

    def test_template_rendering_with_cdn(self):
        from django.conf import settings
        old_am_settings = dict(settings.ASSETMAN_SETTINGS)
        settings.ASSETMAN_SETTINGS['enable_static_compilation'] = False
        try:
            parser = DjangoParser(self.TEST_TEMPLATE_PATH, settings=settings)
            template = parser.template
            context = django.template.context.Context({})
            result = template.render(context)
            self.assertEqual(result, "")
            self.assertNotIn('<link href="STATIC/assets/css/test.css"', result)
            self.assertNotIn('<link href="STATIC/assets/less/test.less"', result)
            self.assertNotIn('<script src="STATIC/assets/js/test.js"', result)
        finally:
            settings.ASSETMAN_SETTINGS = old_am_settings


if __name__ == "__main__":
    unittest.main()
