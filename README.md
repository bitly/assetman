Drop-in static asset compilation

### In templates

Assetman can be used by grouping your static assets into "asset
blocks" to be compiled together.  These asset blocks look like this:

    {% apply assetman.include_js %}
    path/to/utils.js
    path/to/lib.js
    path/to/main.js
    {% end %}

The given paths are relative to the `static_url_prefix` setting. There are
comparable `include_css` and `include_less` helpers available in every 
template. There is no limit on the number of assetman blocks that can be 
included in a template.

When a template with asset blocks is rendered, Assetman decides what static
includes to render in the template.

Assetman also provides a replacement for the built in tornado `static_url` 
helper that is used the same way:

    {{ assetman.static_url('path/to/asset.jpg') }}

If you use the built in `static_url` function, an error will be raised.

### The compiler

The Assetman compiler can be called via commandline using the `assetman_compile`
script.

The compiler starts by building a manifest file which describes the
dependencies of each asset block and their versions.  The manifest is built by
using Tornado's template parser to parse each template file in the template
dir(s) given to the compiler and recursively extracting dependencies from each
template.

In addition to the "current" manifest built for every compile, a "cached"
manifest from the previous compile is loaded from a configured path. 
These two manifests are used to determine what asset blocks need
to be recompiled (or compiled for the first time).

If any asset blocks needed to be compiled, the compiled files are written to
that same `/data/` directory along with the updated manifest file.

As a part of the compilation process, references to static assets rooted under
the `static_url_prefix` will be rewritten to include version information
specific to each asset. Likewise, calls to `assetman.static_url` will result
in asset-specific versioned URLs.

### The manifest

The manifest built as part of the compilation process and used during the
template rendering and static asset serving processes is a JSON object divided
into three parts:

    { 'blocks': {},
      'assets': {},
      'lookups': {} }

The `blocks` section contains mappings from asset blocks (which are identified
by a "name hash", the `md5` hash of their constituent paths) to a version
string, which is an `md5` hash representing the versions of each of its
dependencies (calculated recursively). An entry in the `blocks` section might
look like this:

    "c5f7fa59d1d2e25521e936869f8fbb7c": {
      "version": "89328b33de18bd42a3782d44b7316541"
    }

The `assets` section contains mappings from individual assets to a "depencency
spec", which is composed of a version (`md5` hash) and a list of that asset's
dependencies. As above, the version is a hash representing the version of that
asset and the versions of each of its dependencies, calculated recursively.
An entry in the `assets` section might look like this:

    "www/static/css/components/notice_box.less": {
      "version": "1f170c977b473f6f009bc1adb078efc5",
      "deps": [
        "www/static/graphics/vis/x-blue.png"
      ]
    }

An single asset's version, with no dependencies, is the `md5` hash of its file
name and its file modification time.

Every single dependency at any point in the manifest must have an entry at the
top level of the manifest.

The `lookups` block contains a mapping from an "asset abbreviation" (the first
few letters of the `md5` hash of an asset's file name) to the full path to
that asset. This lookup table is generated at compile time and used at run
time to request compiled assets while also including a list of individual
fallbacks to include if the compiled asset isn't found or if its version
doesn't match. This is just an optimization to keep URL sizes manageable.

### Serving static assets

Static assets are served by a special `StaticFileHandler`. It knows how to 
handle three types of URLs (assume `static_url_prefix` is `/s/beta/` for 
these examples):

 1. Unversioned URLs: `/s/{path}`

    This is used to serve unversioned, uncompiled assets during development.

 2. Versioned URLs: `/s/v:{version}/{path}`

    This is used to serve static assets referenced directly or via
    `assetman.static_url`, where no fallbacks are necessary.

 3. Versioned URLs with fallbacks: `/s/v:{version}/f:{a:b:c}/{hash}`

    This is used to request compiled asset blocks while also providing the
    ability for the server to respond with as many of the constituent assets
    as possible in the case where the compiled asset is not yet available or
    out of date.

Assetman takes care of generating the appropriate URLs at compile time (for
the second kind of URL) or template render time (for the 3rd).

### Running the Assetman compiler

    assetman_compile \
        --output_dir=/data/assets \
        --static_url_prefix=/s/ \
        --template_dir=templates \
        --template_dir=../other/templates
