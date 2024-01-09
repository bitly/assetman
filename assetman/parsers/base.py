
from assetman.settings import Settings
from assetman.compilers import JSCompiler, LessCompiler, CSSCompiler, SassCompiler

# Map from template-side assetman manager calls to the corresponding
# compiler classes
compiler_classes = [JSCompiler, LessCompiler, CSSCompiler, SassCompiler]
compiler_map = dict((c.include_expr, c) for c in compiler_classes)


class TemplateParser(object):
    """ Base template parsing class, to serve as a drop in template wrapper for
    template agnosticism.
    """

    def __init__(self, template_path, settings=None, **kwargs):
        self.settings = settings or Settings()
        self.template_path = template_path
        self.load_template(template_path)

    def load_template(self, path):
        """
        This method must be defined to load template-language specific loading
        mechanism on init.
        """
        raise NotImplementedError

    def get_compilers(self):
        """
        Define this method to return all compilers required for the assetman blocks
        contained by this template.
        """
        raise NotImplementedError
