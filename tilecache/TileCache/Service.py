#!/usr/bin/python

# BSD Licensed, Copyright (c) 2006-2010 TileCache Contributors

class TileCacheException(Exception): pass

import sys, cgi, time, os, traceback, email, ConfigParser
import Cache, Caches, Config, Configs
import Layer, Layers
import urllib2, csv
from Configs.File import File
import threading

# Windows doesn't always do the 'working directory' check correctly.
if sys.platform == 'win32':
    workingdir = os.path.abspath(os.path.join(os.getcwd(), os.path.dirname(sys.argv[0])))
    cfgfiles = [ os.path.join(workingdir, "tilecache.cfg"),
                 os.path.join(workingdir,"..","tilecache.cfg") ]
else:
    cfgfiles = [ "/etc/tilecache.cfg",
                 os.path.join("..", "tilecache.cfg"),
                 "tilecache.cfg" ]
    

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
    __slots__ = ("files", "configs", "layers", "lastcheckchange", "cache", "thread_lock")

    def __init__ (self, configs, layers):
        self.configs = configs
        self.layers = layers
        self.lastcheckchange = time.time()
        
        ##### we need a mutex for reading the configs #####

        self.thread_lock=threading.Lock()

    ###########################################################################
    ##
    ## @brief load method to parse the config.
    ##
    ## @param files    config files to parse
    ##
    ###########################################################################
    
    def _load (cls, files):
        
        configs = []
        initconfigs = []

        print >> sys.stderr, "Loading Configs: %s" % (','.join(files),)
        for f in files:
            #sys.stderr.write( "_load f %s\n" % f )
            cfg = File(f)
            if cfg.resource != None:
                configs.append( cfg )
                initconfigs.append( cfg )

        for conf in initconfigs:
            conf.read( configs )
            if conf.cache != None:
                cls.cache = conf.cache
            
#        layers = {}
        layers = cls.LayerConfig()  
            
        for conf in configs:
#            layers.update(conf.layers)        
            layers.update(conf)

        service = cls(configs, layers)
        
        service.files = files
            
        return service

    load = classmethod(_load)

    ############################################################################
    # This subclass is used to define the config objects layerconfig object -
    # which acts like a layer dictionary, so we can make it masquerade as 
    # what *used* to be the layers dictionary, which contained configs for the
    # layers.
    # 
    # Each config is checked (in the order they appear in the config file) for 
    # the requested layer.  The first match is returned.  That means that
    # it's possible for a config to be defined more than once, but the first
    # definition will always take precedence.
    # This allows for "dynamic" configs (like memcache) where we don't know
    #    if a layer config exists in advance.
    ############################################################################

    class LayerConfig(object):

        ########################################################################
        # The constructor
        ########################################################################
        
        def __init__(self):
            self.list=[]
        
        ########################################################################
        # @brief get the number of objects in the list, Not number of config
        #        entries (since we might not know that.)
        #
        # @return the number of objects in the layerconfig
        #
        ########################################################################

        def __len__(self):

            return len(self.list)
        
        ########################################################################
        # @brief iterate over the LayerConfig list and check each item for a
        #        layer
        # 
        # @param key    the name of the layer to search for
        #
        # @return the layer object if found. or None when no config is found.
        ########################################################################

        def __getitem__(self, key):
            '''

            '''
            sys.stderr.write('Getitem for %s\n' % (key,))
            sys.stderr.write('list contains %s items\n' % (len(self),))
            for item in self.list:
                sys.stderr.write('Lookup for %s\n' % (item.resource,))
                c=item.getConfig(key)
                sys.stderr.write('Value is %s\n' % (c,))
                if c:
                    return c
            return False
        
        ########################################################################
        # @brief Get a list of (known) layers that are supported by this tilecache
        #        service.  The memcache ones won't be listed - since TileCache
        #        doesn't really know about them until they are queried.
        #
        # @return list of layers
        ########################################################################

        def keys(self):
            
            layers=[]
            for item in self.list:
                layers += item.getLayers()
            return layers
            
        ########################################################################
        # @brief Add a config, this'll update the item (maintaining the same order
        #        as in the original config.) if it's already there (such as
        #        in the case of checkchange) or add it to the end (the initial
        #        parse/load case.)
        #
        # @param configObjb the configuration object to add
        #
        ########################################################################
        
        def update(self, configObj):

            for pos, item in enumerate(self.list):
                if configObj.resource == item.resource:
                    self.list[pos]=configObj
                    break
            else:
                self.list.append(configObj)
            
        ########################################################################
        # @brief This is in case someone tries to do something like:
        #    if layer_name in LayerConfig_object ...
        #    this is the membership test.
        #
        # @param key    the 
        ########################################################################
    
        def __contains__(self, key):
            
            for item in self.list:
                if item.hasConfig(key): 
                    return True
            return False

    ###########################################################################
    ##
    ## @brief method to check the configs for change
    ##
    ##
    ###########################################################################
    
    def checkchange (self):
    
        if self.lastcheckchange < time.time() + 1:
           
            #sys.stderr.write( "service.checkchange\n" )
            configs = []
            initconfigs = []
            changes = 0;

            for conf in self.configs:

                ##### only one thread needs to check a single config #####

                if conf.lock.acquire( blocking=0 ):
                    if conf.checkchange(self.configs):
                        self.layers.update(conf)
                    conf.lock.release()

            
    
    def generate_crossdomain_xml(self):
        """Helper method for generating the XML content for a crossdomain.xml
           file, to be used to allow remote sites to access this content."""
        xml = ["""<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM
  "http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
        """]
        if self.metadata.has_key('crossdomain_sites'):
            sites = self.metadata['crossdomain_sites'].split(',')
            for site in sites:
                xml.append('  <allow-access-from domain="%s" />' % site)
        xml.append("</cross-domain-policy>")        
        return ('text/xml', "\n".join(xml))       

    def renderTile (self, tile, force = False):
        from warnings import warn
        start = time.time()

        # do more cache checking here: SRS, width, height, layers 

        layer = tile.layer
        image = None
        if not force:
            image = self.cache.get(tile)
        
        if not image:
            data = layer.render(tile, force=force)
            if (data):
                image = self.cache.set(tile, data)
            else:
                raise Exception("Zero length data returned from layer.")
            
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
                    coverage = Layer.Tile(layer,x,y,z)
                    self.cache.delete(coverage)

    def dispatchRequest (self, params, path_info="/", req_method="GET", host="http://example.com/"):

        ##### loop over the config instances and #####
        ##### check for warnings and exceptions  #####
        
        for conf in self.configs:
            if conf.metadata.has_key('exception'):
                raise TileCacheException("%s\n%s" % (conf.metadata['exception'], conf.metadata['traceback']))
            elif conf.metadata.has_key('warn'):
                sys.stderr.write("%s\n%s" % (conf.metadata['warn'], conf.metadata['traceback']))
        
        if path_info.find("crossdomain.xml") != -1:
            return self.generate_crossdomain_xml()

        if path_info.split(".")[-1] == "kml":
            from TileCache.Services.KML import KML 
            return KML(self).parse(params, path_info, host)
        
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
        elif params.has_key("tile"):
            from TileCache.Services.VETMS import VETMS 
            tile = VETMS(self).parse(params, path_info, host)
        elif params.has_key("format") and params['format'].lower() == "json":
            from TileCache.Services.JSON import JSON 
            return JSON(self).parse(params, path_info, host)
        else:
            from TileCache.Services.TMS import TMS
            tile = TMS(self).parse(params, path_info, host)
        
        #if hasattr(tile, "data"): # duck-typing for Layer.Tile
        #if isinstance(tile, Layer.Tile):
        
        ##### Capabilities object #####
        
        if hasattr(tile, "format"):
            # return ( TileCache.Service.Capabilities.format,
            #          TileCache.Service.Capabilities.data
            #        )
            return (tile.format, tile.data)
        
        ##### single tile object #####
        
        elif not isinstance(tile, list):
            
            if req_method == 'DELETE':
                self.expireTile(tile)
                return ('text/plain', 'OK')
            else:
                return self.renderTile(tile, params.has_key('FORCE'))
        
        ##### list of tile objects #####
        
        elif isinstance(tile, list):
            if req_method == 'DELETE':
                [self.expireTile(t) for t in tile]
                return ('text/plain', 'OK')
            else:
                try:
                    import PIL.Image as Image
                except ImportError:
                    raise Exception("Combining multiple layers requires Python Imaging Library.")
                try:
                    import cStringIO as StringIO
                except ImportError:
                    import StringIO
                
                
                ##### calc image size #####

                xoff=0;
                yoff=0;
                prev = None
                xmax=0
                ymax=0
                for t in tile:
                    
                    
                    xincr = t.layer.size[0]
                    yincr = t.layer.size[1]
                    if prev:
                        if t.x < prev.x:
                            xoff = 0;
                        elif  t.x > prev.x:
                            xoff += xincr
                        
                        if t.y < prev.y:
                            yoff = 0;
                        elif t.y > prev.y:
                            yoff += yincr
                    
                    xmax = max(xmax, xoff + xincr)
                    ymax = max(ymax, yoff + yincr)
                    prev=t

                ##### build an image from the tiles #####

                result = None
                xoff=0;
                yoff = ymax - yincr
                prev = None
                for t in tile:

                    xincr = t.layer.size[0]
                    yincr = t.layer.size[1]
                    if prev:
                        if t.x < prev.x:
                            xoff = 0;
                        elif  t.x > prev.x:
                            xoff += xincr

                        if t.y < prev.y:
                            yoff = ymax - yincr;
                        elif t.y > prev.y:
                            yoff -= yincr

                    (format, data) = self.renderTile(t, params.has_key('FORCE'))
                    image = Image.open(StringIO.StringIO(data))
                    if not result:
                        result = Image.new(image.mode, (xmax, ymax))
                        imformat = image.format
                    
                    try:
                        result.paste(image, (xoff, yoff) , image)
                    except Exception, E:
                        raise Exception("Could not combine images: Is it possible that some layers are not \n8-bit transparent images? \n(Error was: %s)" % E) 
                    prev=t

                buffer = StringIO.StringIO()
                result.save(buffer, imformat)
                buffer.seek(0)

                return (format, buffer.read())
        
        ##### unknown object #####
        
        else:
            raise NotImplementedError("Service instance must return a Tile or Capabilities object")
        

def modPythonHandler (apacheReq, service):
    from mod_python import apache, util
    try:
        if apacheReq.headers_in.has_key("X-Forwarded-Host"):
            host = "http://" + apacheReq.headers_in["X-Forwarded-Host"]
        else:
            host = "http://" + apacheReq.headers_in["Host"]
        #host += apacheReq.uri[:-len(apacheReq.path_info)]
        host += "/tilecache/tilecache.py"
        
        ##### test configs for changes #####
        
        service.checkchange()
        
        format, image = service.dispatchRequest( 
                                util.FieldStorage(apacheReq), 
                                apacheReq.path_info,
                                apacheReq.method,
                                host )
        apacheReq.content_type = format
        apacheReq.status = apache.HTTP_OK
        if format.startswith("image/"):
            if service.cache.sendfile:
                apacheReq.headers_out['X-SendFile'] = image
            if service.cache.expire:
                apacheReq.headers_out['Expires'] = email.Utils.formatdate(time.time() + service.cache.expire, False, True)
                
        apacheReq.set_content_length(len(image))
        apacheReq.send_http_header()
        if format.startswith("image/") and service.cache.sendfile:
            apacheReq.write("")
        else: 
            apacheReq.write(image)
    except TileCacheException, E:
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
        
        ##### test configs for changes #####
        
        service.checkchange()
        
        format, image = service.dispatchRequest( fields, path_info, req_method, host )
        headers = [( 'Content-Type', format.encode('utf-8') )]
        if format.startswith("image/"):
            if service.cache.sendfile:
                headers.append(('X-SendFile', image))
            if service.cache.expire:
                headers.append(('Expires', email.Utils.formatdate(time.time() + service.cache.expire, False, True)))

        start_response("200 OK", headers)
        if service.cache.sendfile and format.startswith("image/"):
            return []
        else:
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
        
        ##### test configs for changes #####
        
        service.checkchange()
        
        format, image = service.dispatchRequest( params, path_info, req_method, host )
        print "Content-type: %s" % format
        if format.startswith("image/"):
            if service.cache.sendfile:
                print "X-SendFile: %s" % image
            if service.cache.expire:
                print "Expires: %s" % email.Utils.formatdate(time.time() + service.cache.expire, False, True)
        print ""
        if (not service.cache.sendfile) or (not format.startswith("image/")):
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

theService = {}
lastRead = {}
def handler (apacheReq):
    global theService, lastRead
    options = apacheReq.get_options()
    print options
    fileChanged = False
    if options.has_key("TileCacheConfig"):
        configFile = options["TileCacheConfig"]
        lastRead[configFile] = time.time()
        
        if configFile not in cfgfiles:
            cfgfiles.append( configFile )
        
        try:
            cfgTime = os.stat(configFile)[8]
            fileChanged = lastRead[configFile] < cfgTime
        except:
            pass
    else:
        configFile = 'default'
        
    if not theService.has_key(configFile) or fileChanged:
        theService[configFile] = Service.load(cfgfiles)
        
    return modPythonHandler(apacheReq, theService[configFile])

def wsgiApp (environ, start_response):
    global theService
    cfgs    = cfgfiles
    if not theService:
        theService = Service.load(cfgs)
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

def paste_deploy_app(global_conf, full_stack=True, **app_conf):
    if 'tilecache_config' in app_conf:
        cfgfiles = (app_conf['tilecache_config'],)
    else:
        raise TileCacheException("No tilecache_config key found in configuration. Please specify location of tilecache config file in your ini file.")
    theService = Service.load(*cfgfiles)
    if 'exception' in theService.metadata:
        raise theService.metadata['exception']
    
    def pdWsgiApp (environ,start_response):
        return wsgiHandler(environ,start_response,theService)
    
    return pdWsgiApp

if __name__ == '__main__':
    svc = Service.load(cfgfiles)
    cgiHandler(svc)
