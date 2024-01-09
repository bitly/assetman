

import os
import re
import binascii
import itertools
import logging

# What to calls to assetman look like in {% apply %} blocks?
include_expr_matcher = re.compile(r'^assetman\.(include_\w+)').match
def get_shard_from_list(settings_list, shard_id):
    assert isinstance(settings_list, (list, tuple)), "must be a list not %r" % settings_list
    shard_id = _crc(shard_id)
    bucket = shard_id % len(settings_list)
    return settings_list[bucket]

def _crc(key):
    """crc32 hash a string"""
    return binascii.crc32(_utf8(key)) & 0xffffffff

def _utf8(s):
    """encode a unicode string as utf-8"""
    if isinstance(s, str):
        return s.encode("utf-8").decode()
    if isinstance(s, bytes):
        return s.decode("utf-8")
    assert isinstance(s, str), "_utf8 expected a str, not %r" % type(s)
    return s

def iter_template_paths(template_dirs, template_ext):
    """Walks each directory in the given list of template directories,
    yielding the path to each template found.
    """
    # We only try to parse files that match this pattern as Tornado templates
    template_file_matcher = re.compile(r'\.' + re.escape(template_ext) + '$').search

    for template_dir in template_dirs:
        for root, dirs, files in os.walk(template_dir):
            for f in filter(template_file_matcher, files):
                yield os.path.join(root, f)

# Shortcuts for creating paths relative to some other path
def make_absolute_static_path(static_dir, p):
    if os.path.exists(p):
        return p
    return os.path.normpath(os.path.abspath(os.path.join(static_dir, p)))

def make_relative_static_path(static_dir, p):
    base = os.path.normpath(os.path.abspath(static_dir))
    if p.startswith(base):
        return p[len(base)+1:]
    return p

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
    assert template_type in ["tornado_template"]
    assert isinstance(template_path, str)
    logging.info('parsing for %s %s', template_type, template_path)
    if settings.get('verbose'):
        print(template_type, template_path)
    from assetman.parsers.tornado_parser import TornadoParser
    return TornadoParser(template_path, settings)
