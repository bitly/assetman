import os
import sys
import logging

# Hack: Do this before attempting to load any django-related stuff.
# FIXME boo do not modify environ at module scope
os.environ['DJANGO_SETTINGS_MODULE'] = 'assetman.tests.django_test_settings'

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
   format='%(asctime)s %(process)d %(filename)s %(lineno)d %(levelname)s #| %(message)s',
   datefmt='%H:%M:%S')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
