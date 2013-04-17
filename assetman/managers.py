from __future__ import absolute_import, with_statement

import os
import logging
import functools
import hashlib

from assetman.settings import Settings
import assetman.tools as tools
from assetman.manifest import Manifest

class AssetManager(object):
    """AssetManager attempts to provide easy-to-use asset management and
    compilation for Tornado (or other?) templates.

    On the template side, assuming this `assetman` module is available in the
    template context, use in Tornado should be as easy as:

        {% apply assetman.include_js %}
        js/utils.js
        js/lib.js
        js/main.js
        {% end %}

    (Variations can/should be created for other frameworks.)

    With this block in place, each individual JavaScript file will be included
    in the resulting document in development. In production, a single,
    compiled JavaScript will be included instead.
    """

    def __init__(self, rel_url_text, local=False, include_tag=True, src_path=None, settings=None, **attrs):
        """Creates an asset manager from `rel_url_text`, a string which should
        contain space (or newline) separated asset URLs.

        Optional params:

          * local - if True, URLs in rendered output will point at our own
            hosts instead of our CDN.

          * include_tag - if False, the only rendered output will be URLs,
            without full HTML elements (useful, e.g., for mobile app manifests)

          * src_path - an optional annotation for recording where this asset
            manager originated.

        Any extra kwargs will be interpreted as extra HTML params to include
        on the rendered element.
        """
        self.rel_urls = filter(None, tools._utf8(rel_url_text).split())
        self.local = local
        self.include_tag = include_tag
        self.src_path = src_path
        self.attrs = attrs
        self._manifest = None
        self.settings = settings or Settings()
        logging.debug('%s URLs: %r', self.__class__.__name__, self.rel_urls)

    # Lazy-load the manifest attribute
    def get_manifest(self):
        if not self._manifest:
            self._manifest = Manifest(self.settings).load()
        return self._manifest

    def set_manifest(self, manifest):
        self._manifest = manifest

    manifest = property(get_manifest, set_manifest)

    def get_hash(self):
        """Gets the md5 hash for the URLs in this block of assets, which will
        be used to refer to the compiled assets in production.
        """
        return hashlib.md5('\n'.join(self.rel_urls)).hexdigest()

    def get_ext(self):
        """Returns the file extension (without leading period) to use for the
        compiled version of these assets.
        """
        raise NotImplementedError

    def get_compiled_name(self):
        """Returns the filename for the compiled version of this asset bundle,
        which is composed of its version hash and a filed extension.
        """
        name_hash = self.get_hash()
        return self.manifest['blocks'][name_hash]['versioned_path']

    def make_asset_url(self, rel_url, static_url_prefix=None, local_cdn_url_prefix=None):
        """Builds a full URL based the given relative URL."""
        if self.settings['enable_static_compilation']:
            prefix = static_url_prefix or self.settings.get('static_url_prefix')
        elif self.local:
            prefix = local_cdn_url_prefix or self.settings.get('local_cdn_url_prefix')
        return prefix.rstrip('/') + '/' + rel_url.lstrip('/')

    def render_attrs(self):
        """Returns this asset block's attrs as an HTML string. Includes a
        leading space.
        """
        attrs = ' '.join('%s=%r' % (attr, tools._utf8(val))
                         for attr, val in self.attrs.iteritems())
        return ' ' + attrs if attrs else ''

    def render_asset(self, url):
        """Renders an individual asset at the given URL. The given URL should
        be the full URL to of the asset.
        """
        if self.include_tag:
            return self.render_asset_element(url)
        else:
            return url

    def render_asset_element(self, url):
        raise NotImplementedError

    def render(self, static_url_prefix=None, local_cdn_url_prefix=None):
        """Renders these assets. If static compilation is enabled, each asset is
        rendered individually. In a production environment, this should be disabled and
        just the compiled asset should rendered.
        """
        static_url_prefix = static_url_prefix or self.settings.get("static_url_prefix")
        local_cdn_url_prefix = local_cdn_url_prefix or self.settings.get("local_cdn_url_prefix")

        make_url = functools.partial(self.make_asset_url,
                                     static_url_prefix=static_url_prefix,
                                     local_cdn_url_prefix=local_cdn_url_prefix)
        if self.settings['enable_static_compilation']:
            urls = map(make_url, self.rel_urls)
            return '\n'.join(map(self.render_asset, urls))
        else:
            return self.render_asset(make_url(self.get_compiled_name()))

    @classmethod
    def include(cls, s=None, **kwargs):
        """A shortcut for creating and rendering an AssetManager, which needs
        to support two styles of invocation in templates:

            {% apply assetman.include_js %}path/to/lib.js{% end %}

        and

            {% apply assetman.include_js(local=True) %}path/to/lib.js{% end %}

        Ie, a "bare" application without any args and one with args. In the
        latter case, we need to return a partial function that can be applied
        to a string.
        """
        if s is None:
            return functools.partial(cls.include, **kwargs)
        return cls(s, **kwargs).render()

    def static_url(self, url, static_url_prefix=None, local_cdn_url_prefix=None):
        """A shortcut for ensuring that the given URL is versioned in
        production.
        """
        if self.settings['enable_static_compilation']:
            return self.make_asset_url(url, static_url_prefix, local_cdn_url_prefix)
        else:
            path = os.path.join(static_url_prefix or self.settings.get('static_path_prefix'), url)
            assert path in self.manifest['assets'], path
            return self.make_asset_url(self.manifest['assets'][path]['versioned_path'], static_url_prefix, local_cdn_url_prefix)

    def __str__(self):
        return '<%s src:%s assets:%s>' % (
            self.__class__.__name__,
            self.src_path or '<template>',
            len(self.rel_urls))


class JSManager(AssetManager):
    def get_ext(self):
        return 'js'
    def render_asset_element(self, url):
        return '<script src="%s" type="text/javascript"%s></script>' % (
            url, self.render_attrs())


class CSSManager(AssetManager):
    def get_ext(self):
        return 'css'
    def render_asset_element(self, url):
        return '<link href="%s" rel="stylesheet" type="text/css"%s>' % (
            url, self.render_attrs())


class LessManager(CSSManager):
    # No customization needed because the custom static asset compiler handler
    # will take the *.less URL and return the CSS output.
    pass


class SassManager(CSSManager):
    # No customization needed because the custom static asset compiler handler
    # will take the *.scss URL and return the CSS output.
    pass

