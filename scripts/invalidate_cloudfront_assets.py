#!/bin/env python2.7

import os
import sys

# Find our project root, assuming this file lives in ./scripts/. We add that
# root dir to sys.path and use it as our working directory.
project_root = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import tornado.options
from boto.cloudfront import CloudFrontConnection
import settings

tornado.options.define('url', type=str, multiple=True, help='A URL to invalidate (may be full URL or just path fragment)')

def invalidate_paths(paths):
    cx = CloudFrontConnection(
        settings.get('aws_access_key'), settings.get('aws_secret_key'))
    distros = cx.get_all_distributions()
    return [cx.create_invalidation_request(d.id, paths) for d in distros]

def main(urls):
    if not urls:
        choice = raw_input('No URLs given. Invalidate all URLs? (y/n) ')
        if choice.lower() != 'y':
            return 1
        urls = ['/*']
    paths = ['/' + url.rsplit('/')[-1] for url in urls]
    reqs = invalidate_paths(paths)
    if urls == ['/*']:
        what = 'all URLs'
    else:
        what = '%d URLs' % len(urls)
    print 'May or may not have invalidated cache for %s on %s CloudFront distributions' % (what, len(reqs))
    return 0


if __name__ == '__main__':
    tornado.options.parse_command_line()
    sys.exit(main(tornado.options.options.url or []))