
from . import test_shunt # pyflakes.ignore

import contextlib

from assetman.settings import Settings
from assetman.compile import NeedsCompilation
from assetman.S3UploadThread import upload_assets_to_s3
import assetman.compile
import tempfile
import logging

COMPILED_ASSET_DIR=tempfile.mkdtemp(suffix='.assetman_tests')

def get_settings(**opts):
    logging.info('temp dir %s', COMPILED_ASSET_DIR)
    assetman_settings = Settings(
                    compiled_asset_root=COMPILED_ASSET_DIR,
                    static_dir="./assetman/tests/static_dir",
                    static_url_prefix="/static/",
                    tornado_template_dirs=["./assetman/tests/tornado_templates"],
                    template_extension="html",
                    test_needs_compile=opts.get("test_needs_compile", True),
                    skip_s3_upload=True,
                    force_recompile=False,
                    skip_inline_images=True,
                    closure_compiler=opts.get("closure_compiler", "/bitly/local/bin/closure-compiler.jar"),
                    minify_compressor_path=opts.get("minify_compressor_path", "/bitly/local/bin/minify"),
                    sass_compiler=opts.get("sass_compiler", "/bitly/local/bin/sass"),
                    lessc_path=opts.get("lessc_path", "/bitly/local/hamburger/node_modules/.bin/lessc"), # lessc is included as a node module in hamburger. Does not exist in /bitly/local/bin/
                    aws_username=None,
                    java_bin="/usr/bin/java",
                    )
    return assetman_settings
    

def run_compiler(test_needs_compile=True, **opts):
    """Runs the assetman compiler and returns a 2-tuple of

        (manifest, exit code)

    If test_needs_compile is True, the assets will not be compiled. This will
    always cause skip_upload to be True, so that we don't upload test assets
    to our CDN.
    """

    manifest = assetman.compile.run(get_settings(test_needs_compile=test_needs_compile, **opts))
    logging.debug(manifest)
    return manifest

def test_needs_compile():
    main_files = ["test.css", "test.less", "test.js"]
    dependency_files = ["dependency.png"]
    try:
        manifest = run_compiler()
        raise Exception("should need compile")
    except NeedsCompilation:
        pass

    # This time, we should not need a recompile
    manifest = run_compiler(test_needs_compile=False)
    
    for key in main_files + dependency_files:
        assert key in manifest.assets
    assert len(manifest.blocks) == len(main_files)

    # But if any of the dependencies are modified, a recompile is needed
    for filename in main_files + dependency_files:
        with temporarily_alter_contents('static_dir/%s' % filename, '\n\n\n'):
            try:
                manifest = run_compiler()
                raise Exception("should need compile")
            except NeedsCompilation:
                pass

    # Sanity check that we still don't need a compile (since we should have
    # undone the changes above after the with block)
    manifest = run_compiler()
    
    files_to_upload = upload_assets_to_s3(manifest, get_settings(), skip_s3_upload=True)
    logging.debug(files_to_upload)
    assert len(files_to_upload) == 4
    

@contextlib.contextmanager
def temporarily_alter_contents(path, data):
    """When used in a with block, temporarily changes the contents of a file
    before restoring the original contents when the with block is exited.
    """
    assert isinstance(data, str)
    contents = open(path).read()
    open(path, 'a').write(data)
    yield
    print('undoing alter contents! %d' % len(contents))
    open(path, 'w').write(contents)

# 
# 
# @mock.patch.object(tornado.options.options, 'environment', 'testing')
# def test_dependency_graph():
#     manifest, code = run_compiler()
# 
#     # Gather up the relative paths to all of the static assets in our static
#     # dir, each of which we'll expect to see in the manifest
#     static_assets = []
#     for dirpath, dirnames, filenames in os.walk(settings.get('static_path_prefix')):
#         dirpath = dirpath.lstrip('./')
#         static_assets.extend(os.path.join(dirpath, f) for f in filenames)
# 
#     # Ensure that each static asset is accounted for
#     expected_assets = set(manifest['assets'].keys())
#     for asset in static_assets:
#         assert asset in expected_assets

# 
# @mock.patch.object(tornado.options.options, 'environment', 'testing')
# def test_dev_rendering():
#     manifest, code = run_compiler()
# 
#     # Pretend like the manifest was successfully compiled
#     write_manifest_and_stubs(manifest)
# 
#     # Since we're not in production, we expect assets to be rendered
#     # individually, pointing to local asset locations
#     expected_urls = [
#         '/s/test/js/test.js',
#         '/s/test/less/test.less',
#         '/s/test/css/test.css',
#         '/s/test/js/page.js',
#         '/s/test/js/page2.js',
#         '/s/test/js/page3.js',
#         '/s/test/css/page.css',
#         '/s/test/img/test-logo.png',
#         '/s/test/img/standalone.png',
#     ]
#     with mock.patch('lib.assetman.settings.env', new=lambda: 'dev'):
#         result = render('page.html')
#     for url in expected_urls:
#         assert url in result
# 
# 
# @mock.patch.object(tornado.options.options, 'environment', 'testing')
# def test_prod_rendering():
#     manifest, code = run_compiler()
# 
#     # Pretend like the manifest was successfully compiled
#     write_manifest_and_stubs(manifest)
# 
#     # When we simulate production, we expect all CDN urls and no local urls
#     expected_urls = [
#         '//cdn.bitly.org/e589a70e11f41b3cc122068e9bc3aea2.js',
#         '//cdn.bitly.org/87d66f3c2ae98037731415839c206e0a.css',
#         '//cdn.bitly.org/366868c90da4511dbde3ad14267b2c95.js',
#         '//cdn.bitly.org/a75d0b4e0fd99db15865c44fee810b95.css',
#         '//cdn.bitly.org/c2051d9195fa263c5339d288962b73f4.png',
#         '//cdn.bitly.org/c2051d9195fa263c5339d288962b73f4.png',
#         '//cdn.bitly.org/b2cbc6ee206d4eb6cef58d12f0da7670.png',
#     ]
#     with mock.patch('lib.assetman.settings.env', new=lambda: 'del'):
#         result = render('page.html')
# 
#     for url in expected_urls:
#         assert url in result
# 
#     # as a sanity check, make sure no local URLs are present
#     assert settings.get('static_url_prefix') not in result
# 
# 
# @mock.patch.object(tornado.options.options, 'environment', 'testing')
# def test_special_rendering():
#     manifest, code = run_compiler()
# 
#     # Pretend like the manifest was successfully compiled
#     write_manifest_and_stubs(manifest)
# 
#     with mock.patch('lib.assetman.settings.env', new=lambda: 'dev'):
#         result = render('manifest.html')
# 
#     # make sure one of our URLs has no tag around it
#     assert re.search(r'(?m)^/s/test/js/mobile\.js$', result)
# 
#     # and the other one does have a tag
#     assert '<script src="/s/test/js/mobile2.js" type="text/javascript"></script>' in result
# 
#     # now fake rendering in production
#     with mock.patch('lib.assetman.settings.env', new=lambda: 'del'):
#         result = render('manifest.html')
# 
#     # these blocks use the 'local' cdn url prefix, not the real one
#     assert re.search(r'(?m)^/cdn/76445780cfa7095a8e65a3d730688760\.js$', result)
#     assert '<script src="/cdn/f022be20475cb50d7050f1a45a715795.js" type="text/javascript"></script>' in result
#     assert settings.get('cdn_url_prefix')[0] not in result
