from __future__ import absolute_import, with_statement

import os
import tornado.template
from assetman.tools import include_expr_matcher 
from assetman.compilers import JSCompiler, LessCompiler, CSSCompiler
from assetman.settings import Settings

class TemplateParser(object):
    """ Base template parsing class, to serve as a drop in template wrapper for
    template agnosticism.
    """

    def __init__(self, template_path, settings=None, **kwargs):
        self.settings = settings or Settings()
        self.template_path = template_path
        self.load_template(template_path)

    def load_template(self, path):
        """ This method must be defined to load template-language specific loading 
        mechanism on init. """
        pass

    def get_compilers(self):
        """ Define this method to return all compilers required for the assetman blocks
        contained by this template """ 
        raise Exception("Not implemented")

class TornadoParser(TemplateParser):
    """ Template parser for parsing and handling tornado templates """

    def load_template(self, path):
        """ loads a template from a full file path """
        dirpath, template_file = os.path.split(path) 
        loader = tornado.template.Loader(dirpath)
        self.template = loader.load(template_file)

    def get_compilers(self):
        """Finds any {% apply assetman.foo %} blocks in the given compiled
        Template object and yields insantiated AssetCompiler instances for each
        block.
        """
        # Map from template-side assetman manager calls to the corresponding
        # compiler classes
        compiler_classes = [JSCompiler, LessCompiler, CSSCompiler]
        compiler_map = dict((c.include_expr, c) for c in compiler_classes)

        for asset_block in self.__iter_child_nodes(self.template.file, self.__is_assetman_block):
            include_expr = include_expr_matcher(asset_block.method).group(1)
            assert include_expr in compiler_map, 'No compiler for %s' % asset_block.method
            compiler_cls = compiler_map[include_expr]
            yield compiler_cls(self.__extract_text(asset_block), self.template_path, settings=self.settings) 

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
