#!/usr/bin/python

from distutils.core import setup

setup(name='assetman',
      version='0.1.3',
      description='AssetMan asset manager',
      url="http://github.com/bitly/assetman",
      license="Apache Software License",
      author='Will McCutchen',
      author_email="wm@bit.ly",
      maintainer="Anton Fritsch",
      maintainer_email="anton@bit.ly",
      packages=['assetman', 'assetman/tornadoutils'],
      install_requires=['simplejson',
                        'multiprocessing',
                       ],

      scripts=['scripts/compile']
)
