from __future__ import absolute_import, with_statement

import django.template
import django.template.loader
from assetman.django_assetman.templatetags.assetman_tags import AssetmanNode
from assetman.parsers import base
import logging
from django.conf import settings


def get_compiler_class(node):
    return base.compiler_map[node.asset_type]

class DjangoParser(base.TemplateParser):
    """ Template parser for parsing and handling django templates """

    def load_template(self, path):
        """
        Loads a template from a full file path.
        """
        logging.info('django template path %s (templates %s)', path, settings.TEMPLATE_DIRS)
        for p in settings.TEMPLATE_DIRS:
            if path.startswith(p):
                logging.debug('scoping path to django template %s -> %s', path, path[len(p)+1])
                path = path[len(p)+1:]
                break
        self.template = django.template.loader.get_template(path)
        self.path = path
    
    def get_compilers(self):
        """
        Finds any {% assetman foo %} blocks in the given compiled
        Template object and yields insantiated AssetCompiler instances for each
        block.
        """
        logging.debug("djangoparser.get_compilers %s", self.path)
        for node in self.template.nodelist.get_nodes_by_type(AssetmanNode):
            compiler_cls = get_compiler_class(node)
            logging.debug('node %r %r', node, compiler_cls)
            if self.settings.get('verbose'):
                print self.path, node, compiler_cls, node.get_all_text()
            yield compiler_cls(node.get_all_text(),
                               self.template_path,
                               src_path=self.template_path,
                               settings=self.settings)


