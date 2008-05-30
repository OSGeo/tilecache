from TileCache.Service import Service
import TileCache.Layers

from pydoc import ispackage

import os, inspect

from StringIO import StringIO
import ConfigParser

from web_request.response import Response

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
            data = template_lookup.get_template("edit_layer.tmpl").render(layer=layer, extras = service.metadata['additional_keys'])
        return str(data)

def save(service, parts=None, params = {}, **kwargs):
    if not parts or (not service.layers.has_key(parts[0]) and parts[0] != "cache"):
        return "Error"
    else:
        name = params['name']
        f = open(service.files[0], "w")
        for key, value in params.items():
            if key == "name": continue
            if value == "None" or value == "none" or value == "":
                service.config.remove_option(name, key)
                continue
            service.config.set(name, key, value)
        
        service.config.write(f)
        f.close()
        
        f = open(service.files[0])
        data = f.read()
        f.close()
        
        return ['text/plain', data]

def find_packages(object):
    modpkgs = []
    modnames = []
    for file in os.listdir(object.__path__[0]):
        path = os.path.join(object.__path__[0], file)
        modname = inspect.getmodulename(file)
        if modname != '__init__':
            if modname and modname not in modnames:
                modpkgs.append((modname, 0, 0))
                modnames.append(modname)
            elif ispackage(path):
                modpkgs.append((file, 1, 0))
    return modnames


def new(service, parts=None, params = {}, **kwargs):
    if params.has_key('submit'):
        
        f = open(service.files[0], "w")
        name = params['name']
        type = params['type']
        
        service.config.add_section(name)
        service.config.set(name, "type", type)
        
        service.config.write(f)
        f.close()
        
        r = Response("Redirecting...", headers={'Location': "%s/edit/%s" % (kwargs['base_path'], name)}, status_code=302)

        return r


    else:
        types = find_packages(TileCache.Layers)
        
        data = template_lookup.get_template("new_layer.tmpl").render(types=types)
        return ['text/html', data]

dispatch_urls = {
 '': home,
 'home': home,
 'edit': edit,
 'save': save, 
 'new': new,
} 

def run(config_path = "/etc/tilecache.cfg", path_info = None, additional_metadata = None, **kwargs):
    s = Service.load(config_path)
    
    if additional_metadata == None:
        additional_metadata = [] 
    
    s.metadata['additional_keys'] = additional_metadata

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
    
    if isinstance(data, list) or isinstance(data, Response):
        return data
    
    return ['text/html', str(data)]
