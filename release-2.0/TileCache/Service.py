#!/usr/bin/python
# BSD Licensed, Copyright (c) 2006-2007 MetaCarta, Inc.

class TileCacheException(Exception): pass

import sys, cgi, time, os, traceback, ConfigParser
import Cache, Caches
import Layer, Layers

# Windows doesn't always do the 'working directory' check correctly.
if sys.platform == 'win32':
    workingdir = os.path.abspath(os.path.join(os.getcwd(), os.path.dirname(sys.argv[0])))
    cfgfiles = (os.path.join(workingdir, "tilecache.cfg"), os.path.join(workingdir,"..","tilecache.cfg"))
else:
    cfgfiles = ("/etc/tilecache.cfg", os.path.join("..", "tilecache.cfg"), "tilecache.cfg")


class Capabilities (object):
    def __init__ (self, format, data):
        self.format = format
        self.data   = data

class Request (object):
    def __init__ (self, service):
        self.service = service
    def getLayer(self, layername):    
        try:
            return self.service.layers[layername]
        except:
            raise TileCacheException("The requested layer (%s) does not exist. Available layers are: \n * %s" % (layername, "\n * ".join(self.service.layers.keys()))) 

    
def import_module(name):
    """Helper module to import any module based on a name, and return the module."""
    mod = __import__(name)
    components = name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod

class Service (object):
    __slots__ = ("layers", "cache", "metadata", "tilecache_options")

    def __init__ (self, cache, layers, metadata = {}):
        self.cache    = cache
        self.layers   = layers
        self.metadata = metadata
 
    def _loadFromSection (cls, config, section, module, **objargs):
        type  = config.get(section, "type")
        for opt in config.options(section):
            if opt not in ["type", "module"]:
                objargs[opt] = config.get(section, opt)
        
        object_module = None
        
        if config.has_option(section, "module"):
            object_module = import_module(config.get(section, "module"))
        else: 
            if module is Layer:
                type = type.replace("Layer", "")
                object_module = import_module("TileCache.Layers.%s" % type)
            else:
                type = type.replace("Cache", "")
                object_module = import_module("TileCache.Caches.%s" % type)
        if object_module == None:
            raise TileCacheException("Attempt to load %s failed." % type)
        
        section_object = getattr(object_module, type)
        
        if module is Layer:
            return section_object(section, **objargs)
        else:
            return section_object(**objargs)
    loadFromSection = classmethod(_loadFromSection)

    def _load (cls, *files):
        config = ConfigParser.ConfigParser()
        config.read(files)
        
        metadata = {}
        if config.has_section("metadata"):
            for key in config.options("metadata"):
                metadata[key] = config.get("metadata", key)
        
        if config.has_section("tilecache_options"):
            if 'path' in config.options("tilecache_options"): 
                for path in config.get("tilecache_options", "path").split(","):
                    sys.path.insert(0, path)
        
        cache = cls.loadFromSection(config, "cache", Cache)

        layers = {}
        for section in config.sections():
            if section in cls.__slots__: continue
            layers[section] = cls.loadFromSection(
                                    config, section, Layer, 
                                    cache = cache)

        return cls(cache, layers, metadata)
    load = classmethod(_load)

    def renderTile (self, tile, force = False):
        from warnings import warn
        start = time.time()

        # do more cache checking here: SRS, width, height, layers 

        layer = tile.layer
        image = None
        if not force: image = self.cache.get(tile)
        if not image:
            data = layer.render(tile)
            if (data): image = self.cache.set(tile, data)
            else: raise Exception("Zero length data returned from layer.")
            if layer.debug:
                sys.stderr.write(
                "Cache miss: %s, Tile: x: %s, y: %s, z: %s, time: %s\n" % (
                    tile.bbox(), tile.x, tile.y, tile.z, (time.time() - start)) )
        else:
            if layer.debug:
                sys.stderr.write(
                "Cache hit: %s, Tile: x: %s, y: %s, z: %s, time: %s, debug: %s\n" % (
                    tile.bbox(), tile.x, tile.y, tile.z, (time.time() - start), layer.debug) )
        
        return (layer.mime_type, image)

    def expireTile (self, tile):
        bbox  = tile.bounds()
        layer = tile.layer 
        for z in range(len(layer.resolutions)):
            bottomleft = layer.getClosestCell(z, bbox[0:2])
            topright   = layer.getClosestCell(z, bbox[2:4])
            for y in range(bottomleft[1], topright[1] + 1):
                for x in range(bottomleft[0], topright[0] + 1):
                    coverage = Tile(layer,x,y,z)
                    self.cache.delete(coverage)

    def dispatchRequest (self, params, path_info="/", req_method="GET", host="http://example.com/"):
        if path_info.split(".")[-1] == "kml":
            from TileCache.Services.KML import KML 
            return KML(self).parse(params, path_info, host)
            raise TileCacheException("What, you think we do KML?")
        
        if params.has_key("scale") or params.has_key("SCALE"): 
            from TileCache.Services.WMTS import WMTS
            tile = WMTS(self).parse(params, path_info, host)
        elif params.has_key("service") or params.has_key("SERVICE") or \
           params.has_key("REQUEST") and params['REQUEST'] == "GetMap" or \
           params.has_key("request") and params['request'] == "GetMap": 
            from TileCache.Services.WMS import WMS
            tile = WMS(self).parse(params, path_info, host)
        elif params.has_key("L") or params.has_key("l") or \
             params.has_key("request") and params['request'] == "metadata":
            from TileCache.Services.WorldWind import WorldWind
            tile = WorldWind(self).parse(params, path_info, host)
        elif params.has_key("interface"):
            from TileCache.Services.TileService import TileService
            tile = TileService(self).parse(params, path_info, host)
        elif params.has_key("v") and \
             (params['v'] == "mgm" or params['v'] == "mgmaps"):
            from TileCache.Services.MGMaps import MGMaps 
            tile = MGMaps(self).parse(params, path_info, host)
        else:
            from TileCache.Services.TMS import TMS
            tile = TMS(self).parse(params, path_info, host)
        
        if isinstance(tile, Layer.Tile):
            if req_method == 'DELETE':
                self.expireTile(tile)
                return ('text/plain', 'OK')
            else:
                return self.renderTile(tile, params.has_key('FORCE'))
        else:
            return (tile.format, tile.data)

def modPythonHandler (apacheReq, service):
    from mod_python import apache, util
    try:
        if apacheReq.headers_in.has_key("X-Forwarded-Host"):
            host = "http://" + apacheReq.headers_in["X-Forwarded-Host"]
        else:
            host = "http://" + apacheReq.headers_in["Host"]
        host += apacheReq.uri[:-len(apacheReq.path_info)]
        format, image = service.dispatchRequest( 
                                util.FieldStorage(apacheReq), 
                                apacheReq.path_info,
                                apacheReq.method,
                                host )
        apacheReq.content_type = format
        apacheReq.send_http_header()
        apacheReq.write(image)
    except Layer.TileCacheException, E:
        apacheReq.content_type = "text/plain"
        apacheReq.status = apache.HTTP_NOT_FOUND
        apacheReq.send_http_header()
        apacheReq.write("An error occurred: %s\n" % (str(E)))
    except Exception, E:
        apacheReq.content_type = "text/plain"
        apacheReq.status = apache.HTTP_INTERNAL_SERVER_ERROR
        apacheReq.send_http_header()
        apacheReq.write("An error occurred: %s\n%s\n" % (
            str(E), 
            "".join(traceback.format_tb(sys.exc_traceback))))
    return apache.OK

def wsgiHandler (environ, start_response, service):
    from paste.request import parse_formvars
    try:
        path_info = host = ""


        if "PATH_INFO" in environ: 
            path_info = environ["PATH_INFO"]

        if "HTTP_X_FORWARDED_HOST" in environ:
            host      = "http://" + environ["HTTP_X_FORWARDED_HOST"]
        elif "HTTP_HOST" in environ:
            host      = "http://" + environ["HTTP_HOST"]

        host += environ["SCRIPT_NAME"]
        req_method = environ["REQUEST_METHOD"]
        fields = parse_formvars(environ)

        format, image = service.dispatchRequest( fields, path_info, req_method, host )
        start_response("200 OK", [('Content-Type',format)])
        return [image]

    except TileCacheException, E:
        start_response("404 Tile Not Found", [('Content-Type','text/plain')])
        return ["An error occurred: %s" % (str(E))]
    except Exception, E:
        start_response("500 Internal Server Error", [('Content-Type','text/plain')])
        return ["An error occurred: %s\n%s\n" % (
            str(E), 
            "".join(traceback.format_tb(sys.exc_traceback)))]

def cgiHandler (service):
    try:
        params = {}
        input = cgi.FieldStorage()
        for key in input.keys(): params[key] = input[key].value
        path_info = host = ""

        if "PATH_INFO" in os.environ: 
            path_info = os.environ["PATH_INFO"]

        if "HTTP_X_FORWARDED_HOST" in os.environ:
            host      = "http://" + os.environ["HTTP_X_FORWARDED_HOST"]
        elif "HTTP_HOST" in os.environ:
            host      = "http://" + os.environ["HTTP_HOST"]

        host += os.environ["SCRIPT_NAME"]
        req_method = os.environ["REQUEST_METHOD"]
        format, image = service.dispatchRequest( params, path_info, req_method, host )
        print "Content-type: %s\n" % format

        if sys.platform == "win32":
            binaryPrint(image)
        else:    
            print image
    except TileCacheException, E:
        print "Cache-Control: max-age=10, must-revalidate" # make the client reload        
        print "Content-type: text/plain\n"
        print "An error occurred: %s\n" % (str(E))
    except Exception, E:
        print "Cache-Control: max-age=10, must-revalidate" # make the client reload        
        print "Content-type: text/plain\n"
        print "An error occurred: %s\n%s\n" % (
            str(E), 
            "".join(traceback.format_tb(sys.exc_traceback)))

theService = None

def handler (apacheReq):
    global theService
    options = apacheReq.get_options()
    cfgs    = cfgfiles
    if options.has_key("TileCacheConfig"):
        cfgs = (options["TileCacheConfig"],) + cfgs
    if not theService:
        theService = Service.load(*cfgs)
    return modPythonHandler(apacheReq, theService)

def wsgiApp (environ, start_response):
    global theService
    cfgs    = cfgfiles
    if not theService:
        theService = Service.load(*cfgs)
    return wsgiHandler(environ, start_response, theService)

def binaryPrint(binary_data):
    """This function is designed to work around the fact that Python
       in Windows does not handle binary output correctly. This function
       will set the output to binary, and then write to stdout directly
       rather than using print."""
    try:
        import msvcrt
        msvcrt.setmode(sys.__stdout__.fileno(), os.O_BINARY)
    except:
        pass
    sys.stdout.write(binary_data)    

if __name__ == '__main__':
    svc = Service.load(*cfgfiles)
    cgiHandler(svc)
