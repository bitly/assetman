from assetman.managers import AssetManager, JSManager, CSSManager, LessManager, SassManager
from assetman.manifest import Manifest

# An easier interface to use in templates
include_js = JSManager.include
include_css = CSSManager.include
include_less = LessManager.include
include_sass = SassManager.include

__version__ = "0.1.9"
version_info = (0, 1, 9)