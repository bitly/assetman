import os
import sys
import logging

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
   format='%(asctime)s %(process)d %(filename)s %(lineno)d %(levelname)s #| %(message)s',
   datefmt='%H:%M:%S')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
