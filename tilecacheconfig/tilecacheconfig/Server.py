from TileCache.Service import Service

from StringIO import StringIO
import ConfigParser

from Cheetah.Template import Template

from mako.lookup import TemplateLookup

template_lookup = TemplateLookup(directories=['templates'])

def home(service, parts=None, **kwargs):
    template = template_lookup.get_template("home_template.tmpl")
    return template.render(cache=service.cache, layers=service.layers)
    #data = Template(open("templates/home_template.tmpl").read(), searchList=[{'layers':service.layers, 'cache':service.cache}])
    #return data

def edit(service, parts=None, **kwargs):
    if not parts or (not service.layers.has_key(parts[0]) and parts[0] != "cache"):
        return "Error"
    else:
        if parts[0] == "cache": 
            data = Template(open("templates/edit_cache.tmpl").read(), searchList=[{'cache':cache}])
        else:
            layer = service.layers[parts[0]]
            data = template_lookup.get_template("edit_layer.tmpl").render(layer=layer)
        return str(data)

def save(service, parts=None, params = {}, **kwargs):
    if not parts or (not service.layers.has_key(parts[0]) and parts[0] != "cache"):
        return "Error"
    else:
        name = params['name']
        f = open(service.files[0], "w")
        for key, value in params.items():
            if key == "name": continue
            service.config.set(name, key, value)
        service.config.write(f)
        f.close()
        
        f = open(service.files[0])
        data = f.read()
        f.close()
        
        return ['text/plain', data]

dispatch_urls = {
 '': home,
 'home': home,
 'edit': edit,
 'save': save, 
} 

def run(config_path = "/etc/tilecache.cfg", path_info = None, **kwargs):
    s = Service.load(config_path)
    if s.metadata.has_key('exception'):
        data = [
          "Current TileCache config is invalid.", 
          "Exception: %s" % s.metadata['exception'],
          "Traceback: \n %s" % s.metadata['traceback']
        ]
        return ['text/plain', "\n".join(data)]
    data = ""
    stripped = path_info.strip("/")
    stripped_split = stripped.split("/")
    if dispatch_urls.has_key(stripped_split[0]):
        data = dispatch_urls[stripped_split[0]](s, parts=stripped_split[1:], **kwargs)
    
    if isinstance(data, list):
        return data
    
    return ['text/html', str(data)]
