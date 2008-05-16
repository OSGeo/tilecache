from TileCache.Service import Service

from Cheetah.Template import Template

def home(service, parts=None):
    data = Template(open("templates/home_template.tmpl").read(), searchList=[{'layers':service.layers, 'cache':service.cache}])
    return data

def edit(service, parts=None):
    if not parts or not service.layers.has_key(parts[0]):
        return "Error"
    else:
        layer = service.layers[parts[0]]
        data = Template(open("templates/edit_layer.tmpl").read(), searchList=[{'layer':layer}])
        return str(data)

dispatch_urls = {
 '': home,
 'home': home,
 'edit': edit,
} 

def run(path_info = None, **kwargs):
    s = Service.load("/Users/crschmidt/tilecache/tilecache.cfg")
    data = ""
    stripped = path_info.strip("/")
    stripped_split = stripped.split("/")
    if dispatch_urls.has_key(stripped_split[0]):
        data = dispatch_urls[stripped_split[0]](s, parts=stripped_split[1:])
     
    return ['text/html', str(data)]

