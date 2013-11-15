from __future__ import absolute_import, with_statement

import os
import re
import itertools 

# What to calls to assetman look like in {% apply %} blocks?
include_expr_matcher = re.compile(r'^assetman\.(include_\w+)').match

def _utf8(instr):
    return instr.encode("utf-8")

def iter_template_paths(template_dirs, template_ext):
    """Walks each directory in the given list of template directories,
    yielding the path to each template found.
    """
    # We only try to parse files that match this pattern as Tornado templates
    template_file_matcher = re.compile(r'\.' + re.escape(template_ext) + '$').search

    for template_dir in template_dirs:
        for root, dirs, files in os.walk(template_dir):
            for f in itertools.ifilter(template_file_matcher, files):
                yield os.path.join(root, f)

# Shortcuts for creating paths relative to some other path
def make_static_path(static_dir, p):
    return os.path.join(static_dir, p)

def make_output_path(compiled_asset_root, p):
    return os.path.join(compiled_asset_root, p)

def get_static_pattern(static_url_prefix):
    """Builds a regular expression we can use to find static asset references
    that start with the given static URL prefix.

    Used for finding static dependencies inside JS and CSS files and for
    rewriting static references in compiled assets.
    """
    return r'(%s)(.*?\.\w+)' % re.escape(static_url_prefix)

def get_parser(template_path, template_type, settings):
    """ Factory method to return appropriate parser class """
    #TODO: dynamic import / return based on settings / config
    #avoids circular dep
    assert template_type in ["tornado_template", "django_template"]
    if template_type == "tornado_type":
        from assetman.parsers.tornado_parser import TornadoParser
        return TornadoParser(template_path, settings)
    else:
        from assetman.parsers.django_parser import DjangoParser
        return DjangoParser(template_path, settings)
