from assetman.managers import AssetManager, JSManager, CSSManager, LessManager, SassManager
from assetman.manifest import Manifest
import assetman.tornadoutils

# An easier interface to use in templates
include_js = JSManager.include
include_css = CSSManager.include
include_less = LessManager.include
include_sass = SassManager.include

