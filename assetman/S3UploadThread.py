#!/bin/python
from __future__ import with_statement
import re
import os
import os.path
import sys
import threading
import datetime
import Queue
import mimetypes
import logging
import boto3
from assetman.tools import make_output_path, make_absolute_static_path, make_relative_static_path, get_static_pattern, get_shard_from_list

class S3UploadThread(threading.Thread):
    """Thread that knows how to read asset file names from a queue and upload
    them to S3. Any exceptions encountered will be added to a shared errors
    list.

    Each asset will be uploaded twice:  Once with a special "/cdn/" prefix for
    assets to be served by a proxy on our own domain, and again without the
    prefix for assets to be served via CloudFront.  For the second upload,
    static URLs inside each asset will have to be rewritten *again* to point
    at CloudFront instead of our local CDN proxy.
    """

    def __init__(self, queue, errors, manifest, settings):
        threading.Thread.__init__(self)
        self.client = boto3.client('s3',
            aws_access_key_id=settings.get('aws_access_key'),
            aws_secret_access_key=settings.get('aws_secret_key'))
        self.bucket = boto3.resource('s3',
            aws_access_key_id=settings.get('aws_access_key'),
            aws_secret_access_key=settings.get('aws_secret_key')).Bucket(settings.get('s3_assets_bucket'))
        self.queue = queue
        self.errors = errors
        self.manifest = manifest
        self.settings = settings

    def run(self):
        while True:
            file_name, file_path = self.queue.get()
            try:
                self.start_upload_file(file_name, file_path)
            except Exception, e:
                logging.error('Error uploading %s: %s', file_name, e)
                self.errors.append((sys.exc_info(), self))
            finally:
                self.queue.task_done()

    def start_upload_file(self, file_name, file_path):
        """Starts the procecss of uploading a file to S3. Each file will be
        uploaded twice (once for CDN and once for our local CDN proxy).
        """
        assert isinstance(file_name, (str, unicode))
        assert isinstance(file_path, (str, unicode))
        assert os.path.isfile(file_path)

        content_type, content_encoding = mimetypes.guess_type(file_name)
        if not content_type:
            ext = os.path.splitext(file_name)[-1]
            content_type = {
                '.woff': 'application/font-woff',
                '.ttf': 'font/ttf',
                '.otf': 'font/opentype',
                '.eot': 'application/vnd.ms-fontobject',
                '.svg': 'image/svg+xml',
            }.get(ext, 'application/octet-stream')
        headers = {
            'Content-Type': content_type,
            'Cache-Control': self.get_cache_control(),
        }

        with open(file_path, 'rb') as f:
            file_data = f.read()
            # First we will upload the asset for serving via CloudFront CDN,
            # so its S3 key will not have a prefix.
            key = self.bucket.Object(file_name)
            self.upload_file(key, file_data, headers, for_cdn=True)

            # Next we will upload the same file with a prefixed key, to be
            # served by our "local CDN proxy".
            key_prefix = self.settings.get('local_cdn_url_prefix').lstrip('/').rstrip('/')
            key = self.bucket.Object(key_prefix + '/' + file_name)
            self.upload_file(key, file_data, headers, for_cdn=False)

    def exists(self, obj):
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.head_object
        try:
            self.client.head_object(Bucket=obj.bucket_name, Key=obj.key)
        except Exception, e:
            logging.error('got %s', e)
            return False
        return True

    def upload_file(self, key, file_data, headers, for_cdn):
        """Uploads the given file_data to the given S3 key. If the file is a
        compiled asset (ie, JS or CSS file), any static URL references it
        contains will be rewritten before upload.

        If use_cdn is True, static URL references will be updated to point to
        our CloudFront CDN domains. Otherwise, they will be updated to point
        to our local CDN proxy.
        """
        if self.settings.get('force_s3_upload') or not self.exists(key):
            # Do we need to do URL replacement?
            if re.search(r'\.(css|js)$', key.key):
                if for_cdn:
                    logging.info('Rewriting URLs => CDN in %s', key.key)
                    replacement_prefix = self.settings.get('cdn_url_prefix')
                else:
                    logging.info('Rewriting URLs => local proxy in %s', key.key)
                    replacement_prefix = self.settings.get('local_cdn_url_prefix')
                file_data = sub_static_version(
                    file_data,
                    self.manifest,
                    replacement_prefix,
                    self.settings['static_dir'],
                    self.settings.get('static_url_prefix'))
            key.put(Body=file_data, CacheControl=headers.get('Cache-Control'), ContentType=headers.get('Content-Type'), ACL="public-read", Expires=self.get_expires())
            logging.info('Uploaded s3://%s/%s', key.bucket_name, key.key)
            logging.debug('Headers: %r', headers)
        else:
            logging.info('Skipping upload of %s; already exists (use force_s3_upload to override)', key.key)

    def get_expires(self):
        # Get a properly formatted date and time, via Tornado's set_header()
        dt = datetime.datetime.utcnow() + datetime.timedelta(days=365*10)
        return dt


    def get_cache_control(self):
        return 'public, max-age=%s' % (86400 * 365 * 10)


def upload_assets_to_s3(manifest, settings, skip_s3_upload=False):
    """Uploads any assets that are in the given manifest and in our compiled
    output dir but missing from our static assets bucket to that bucket on S3.
    """

    # We will gather a set of (file_name, file_path) tuples to be uploaded
    to_upload = set()

    # We know we want to upload each asset block (these correspond to the
    # assetman.include_* blocks in each template)
    for depspec in manifest.blocks.itervalues():
        file_name = depspec['versioned_path']
        file_path = make_output_path(settings['compiled_asset_root'], file_name)
        assert os.path.isfile(file_path), 'Missing compiled asset %s' % file_path
        to_upload.add((file_name, file_path))

    # And we know that we'll want to upload any statically-referenced assets
    # (from assetman.static_url calls or referenced in any compiled assets),
    # but we'll need to filter out other entries in the complete 'assets'
    # block of the manifest.
    should_skip = re.compile(r'\.(scss|less|css|js|html)$', re.I).search
    for rel_path, depspec in manifest.assets.iteritems():
        if should_skip(rel_path):
            continue
        file_path = make_absolute_static_path(settings['static_dir'], rel_path)
        assert os.path.isfile(file_path), 'Missing static asset %s' % file_path
        file_name = depspec['versioned_path']
        to_upload.add((file_name, file_path))

    logging.info('Found %d assets to upload to S3', len(to_upload))
    if skip_s3_upload:
        logging.info('Skipping asset upload to S3 %s', to_upload)
        return to_upload

    # Upload assets to S3 using 5 threads
    queue = Queue.Queue()
    errors = []
    for i in xrange(5):
        uploader = S3UploadThread(queue, errors, manifest, settings)
        uploader.setDaemon(True)
        uploader.start()
    map(queue.put, to_upload)
    queue.join()
    if errors:
        raise Exception(errors)
    return to_upload


def sub_static_version(src, manifest, replacement_prefix, static_dir, static_url_prefix):
    """Adjusts any static URLs in the given source to point to a different
    location.

    Static URLs are determined based on the the 'static_url_prefix' setting.
    They will be updated to point to the given replacement_prefix, which can
    be a string or a list of strings (in which case the actual replacement
    prefix will be chosen by sharding each asset's base name).
    """
    def replacer(match):
        prefix, rel_path = match.groups()
        path = make_relative_static_path(static_dir, rel_path)
        if path in manifest.assets:
            versioned_path = manifest.assets[path]['versioned_path']
            if isinstance(replacement_prefix, (list, tuple)):
                prefix = get_shard_from_list(replacement_prefix, versioned_path)
            else:
                prefix = replacement_prefix
            replacement_link = prefix.rstrip('/') + '/' + versioned_path.lstrip('/')
            logging.info('replacing %s -> %s', path, replacement_link)
            return replacement_link
        logging.warn('Missing path %s in manifest, using %s', path, match.group(0))
        return match.group(0)
    pattern = get_static_pattern(static_url_prefix)
    return re.sub(pattern, replacer, src)
