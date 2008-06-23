from TileCache.Service import Service
import TileCache.Layers

import ConfigParser

from pydoc import ispackage

import os, inspect

from StringIO import StringIO

from web_request.response import Response

from mako.lookup import TemplateLookup


template_lookup = None 

def home(service, parts=None, **kwargs):
    template = template_lookup.get_template("home_template.tmpl")
    return template.render(cache=service.cache, layers=service.layers, base=kwargs['base_path'])

def view(service, parts=None, tilecache_location = None, **kwargs):
    if not tilecache_location:
        return "No TileCache location is configured. Add tilecache_location to your config to use."

    if not parts or (not service.layers.has_key(parts[0]) and parts[0] != "cache"):
        return "Error"
    else:
        layer = service.layers[parts[0]]
        data = template_lookup.get_template("view_layer.tmpl").render(layer=layer, 
            tilecache_location=tilecache_location,
            base = kwargs['base_path'])
        return str(data)

def edit(service, parts=None, additional_keys = None, **kwargs):
    if not parts or (not service.layers.has_key(parts[0]) and parts[0] != "cache"):
        return "Error"
    else:
        layer = service.layers[parts[0]]
        data = template_lookup.get_template("edit_layer.tmpl").render(layer=layer, 
            extras = additional_keys, 
            base = kwargs['base_path'])
        return str(data)

def save(service, parts=None, params = {}, **kwargs):
    if not parts or (not service.layers.has_key(parts[0]) and parts[0] != "cache"):
        return "Error"
    else:
        name = params['name']
        for key, value in params.items():
            if key == "name": continue
            if value == "None" or value == "none" or value == "":
                service.config.remove_option(name, key)
                continue
            service.config.set(name, key, value)
        
        f = open(service.files[0], "w")
        service.config.write(f)
        f.close()
        
        f = open(service.files[0])
        data = f.read()
        f.close()
        
        r = Response("Redirecting...", headers={'Location': "%s/" % (kwargs['base_path'])}, status_code=302)

        return r

def find_packages(object):
    modnames = []
    for file in os.listdir(object.__path__[0]):
        path = os.path.join(object.__path__[0], file)
        modname = inspect.getmodulename(file)
        if modname != '__init__':
            if modname and modname not in modnames:
                modnames.append(modname)
    return modnames


def new(service, parts=None, params = {}, **kwargs):
    if params.has_key('submit'):
        name = params['name']
        type = params['type']
        
        service.config.add_section(name)
        service.config.set(name, "type", type)
        
        f = open(service.files[0], "w")
        service.config.write(f)
        f.close()
        
        r = Response("Redirecting...", headers={'Location': "%s/edit/%s" % (kwargs['base_path'], name)}, status_code=302)

        return r


    else:
        types = find_packages(TileCache.Layers)
        
        data = template_lookup.get_template("new_layer.tmpl").render(types=types, base = kwargs['base_path'])
        return ['text/html', data]

dispatch_urls = {
 '': home,
 'home': home,
 'edit': edit,
 'save': save, 
 'new': new,
 'view': view,
} 

def run(config_path = "config.cfg", path_info = None, **kwargs):
    global template_lookup
    c = ConfigParser.ConfigParser()
    c.read(config_path)

    tc_path = c.get("config", "tilecache_config")

    s = Service.load(tc_path)
    
    template_path = c.get("config", "template_path")

    tilecache_location = None
    if c.has_option('config', "tilecache_location"):
        tilecache_location = c.get("config", "tilecache_location")

    template_lookup = TemplateLookup(directories=template_path.split(","))
    
    additional_metadata = [] 
    
    try:
        additional_metadata = [i[0] for i in c.items("properties")]
    except ConfigParser.NoSectionError:
        pass

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
        data = dispatch_urls[stripped_split[0]](s, parts=stripped_split[1:], 
                                                additional_keys = additional_metadata, 
                                                tilecache_location = tilecache_location,
                                                **kwargs)
    
    if isinstance(data, list) or isinstance(data, Response):
        return data
    
    return ['text/html', str(data)]
