# All defaults.
import os

HERE = os.path.abspath(os.path.dirname(__file__))

INSTALLED_APPS = [
    'assetman.django_assetman',
]

TEMPLATE_DIRS = [
    HERE,
]

ASSETMAN_SETTINGS = {
    'enable_static_compilation': True,
    'static_url_prefix': 'STATIC',
    'local_cdn_url_prefix': 'CDN',
}
