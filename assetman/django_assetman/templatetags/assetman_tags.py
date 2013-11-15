from django import template
from django.conf import settings

register = template.Library()


class AssetmanNode(template.Node):
    """
    A template node that treats text content as paths to feed to asssetman
    compilers.
    """
    
    def __init__(self, asset_type, nodelist, settings):
        self.asset_type = asset_type
        for node in nodelist:
            if not isinstance(node, template.TextNode):
                raise template.TemplateSyntaxError("only text allowed inside assetman tags")
        self.nodelist = nodelist
        self.settings = settings

    def render(self, context):
        # Avoid circular import. TODO: code smell, re-organize.
        from assetman.parsers.django_parser import get_compiler_class
        compiler = get_compiler_class(self)(self.get_all_text(),
                                            settings=self.settings)
        return compiler.render()

    def get_all_text(self):
        return '\n'.join(child.s.strip() for child in self.get_nodes_by_type(template.TextNode))



@register.tag(name="assetman")
def do_assetman(parser, token):
    """
    Syntax::

        {% load assetman_tags %}
        {% assetman include_js %}
          path/to/asset.js
          another/path/to/another_asset.js
        {% endassetman %}

        {% assetman include_css %}
          path/to/asset.css
        {% endassetman %}

        {% assetman include_sass %}
          path/to/asset.less
        {% endassetman %}

        {% assetman include_less %}
          path/to/asset.less
        {% endassetman %}

    """
    args = token.split_contents()
    allowed_args = ('include_js', 'include_css', 'include_sass', 'include_less')
    if not (len(args) == 2 and args[1] in allowed_args):
        raise template.TemplateSyntaxError(
            'assetman requires exactly 2 args and second must be one of %s'
            % allowed_args)

    nodelist = parser.parse(('endassetman',))
    parser.delete_first_token()
    return AssetmanNode(args[1], nodelist, settings.ASSETMAN_SETTINGS)
