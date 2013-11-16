# All defaults.
import os

HERE = os.path.abspath(os.path.dirname(__file__))

INSTALLED_APPS = [
    'assetman.django_assetman',
]

TEMPLATE_DIRS = [
    os.path.join(HERE,"django_templates")
]

ASSETMAN_SETTINGS = {
    'enable_static_compilation': True,
    'static_url_prefix': 'STATIC',
    'local_cdn_url_prefix': 'CDN',
    'compiled_asset_root': '/tmp',
}

# Logging configuration.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        'django': {
            'handlers': [],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

