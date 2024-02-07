#!/usr/bin/python

from distutils.core import setup

setup(name='assetman',
      version='0.2.0', # also update in __init__.py
      description='AssetMan asset manager',
      url="http://github.com/bitly/assetman",
      license="Apache Software License",
      author='Will McCutchen',
      author_email="wm@bit.ly",
      maintainer="Jehiah Czebotar",
      maintainer_email="jehiah@gmail.com",
      packages=['assetman', 'assetman/parsers', 'assetman/tornadoutils'],
      classifiers = [
                     "Programming Language :: Python :: 3",
                     "Programming Language :: Python :: 3.9",
                     ],
      scripts=['scripts/assetman_compile']
)
