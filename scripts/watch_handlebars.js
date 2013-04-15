var Handlebars = require('handlebars')
var watcher = require('watch-tree')
var path = require('path')
var fs = require('fs')
var exec = require('child_process').exec
var jsDir = path.join(__dirname, '..', 'static/js')
var templates = path.join(__dirname, '..', 'static/templates')


var recompile = function recompile(file) {
    if (path.extname(file) !== '.handlebars')
        return;
    console.log('change: ', file)
    exec('handlebars --output ' + jsDir + '/templates.js ' + templates + '/{,**/}*.handlebars', function(err, stdout, stderr) {
            if (err) {
                console.error(err);
            }
            else {
                console.log('compiled all templates')
            }
    })
}

// Initialize watchTree utility
var watch = watcher.watchTree(templates);

watch.on('fileModified', recompile);
watch.on('fileCreated', recompile);
watch.on('fileDeleted', recompile);
console.log('Watching for changes in Handlebars Templates...')
