from __future__ import absolute_import, with_statement

import django.template
import django.template.loader
from assetman.djangoutils.templatetags.assetman_tags import AssetmanNode
from assetman.parsers import base


def get_compiler_class(node):
    return base.compiler_map[node.asset_type]

class DjangoParser(base.TemplateParser):
    """ Template parser for parsing and handling django templates """

    def load_template(self, path):
        """
        Loads a template from a full file path.
        """
        self.template = django.template.loader.get_template(path)

    def get_compilers(self):
        """
        Finds any {% assetman foo %} blocks in the given compiled
        Template object and yields insantiated AssetCompiler instances for each
        block.
        """
        for node in self.template.nodelist.get_nodes_by_type(AssetmanNode):
            compiler_cls = get_compiler_class(node)
            yield compiler_cls(node.get_all_text(),
                               src_path=self.template_path,
                               settings=self.settings)


