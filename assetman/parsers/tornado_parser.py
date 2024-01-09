

import os
import tornado.template
from assetman.tools import include_expr_matcher
from assetman.parsers import base


class TornadoParser(base.TemplateParser):
    """ Template parser for parsing and handling tornado templates """

    def load_template(self, path):
        """ loads a template from a full file path """
        dirpath, template_file = path.split(os.path.sep, 1)
        # logging.debug('loading template %r %r', dirpath, template_file)
        loader = tornado.template.Loader(dirpath)
        self.template = loader.load(template_file)
        self.path = path

    def get_compilers(self):
        """Finds any {% apply assetman.foo %} blocks in the given compiled
        Template object and yields insantiated AssetCompiler instances for each
        block.
        """
        # Map from template-side assetman manager calls to the corresponding
        # compiler classes
        for asset_block in self.__iter_child_nodes(self.template.file, self.__is_assetman_block):
            include_expr = include_expr_matcher(asset_block.method).group(1)
            assert include_expr in base.compiler_map, 'No compiler for %s' % asset_block.method
            compiler_cls = base.compiler_map[include_expr]
            yield compiler_cls(self.__extract_text(asset_block), self.template_path, settings=self.settings, src_path=self.path) 

    def __is_assetman_block(self, node):
        """Returns a bool indicating whether the given template node is an
        assetman {% apply %} block.
        """
        return isinstance(node, tornado.template._ApplyBlock) \
            and include_expr_matcher(node.method)

    def __iter_child_nodes(self, parent, pred):
        """Yields any child nodes of the given parent that match given predicate
        function.
        """

        for child in parent.each_child():
            if pred(child):
                yield child
            for grandchild in self.__iter_child_nodes(child, pred):
                yield grandchild

    def __extract_text(self, parent):
        """Concatenates the value of each _Text node under the given parent.
        The parent must contain only _Text nodes.
        """
        is_text = lambda node: isinstance(node, tornado.template._Text)
        return ''.join(child.value for child in self.__iter_child_nodes(parent, is_text))
