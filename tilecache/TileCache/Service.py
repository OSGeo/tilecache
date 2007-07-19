#!/usr/bin/python
# BSD Licensed, Copyright (c) 2006-2007 MetaCarta, Inc.

import sys, cgi, time, os, traceback, ConfigParser
import Cache, Layer

# Windows doesn't always do the 'working directory' check correctly.
if sys.platform == 'win32':
    workingdir = os.path.abspath(os.path.join(os.getcwd(), os.path.dirname(sys.argv[0])))
    cfgfiles = (os.path.join(workingdir, "tilecache.cfg"), os.path.join(workingdir,"..","tilecache.cfg"))
else:
    cfgfiles = ("tilecache.cfg", os.path.join("..", "tilecache.cfg"), "/etc/tilecache.cfg")

class TileCacheException(Exception): pass

class Capabilities (object):
    def __init__ (self, format, data):
        self.format = format
        self.data   = data

class Request (object):
    def __init__ (self, service):
        self.service = service

class WorldWind (Request):
    def parse (self, fields, path, host):
        param = {}

        for key in ['t', 'l', 'x', 'y', 'request']: 
            if fields.has_key(key.upper()):
                param[key] = fields[key.upper()] 
            elif fields.has_key(key):
                param[key] = fields[key]
            else:
                param[key] = ""
        
        if param["request"] == "GetCapabilities" or param["request"] == "metadata":
            return self.getCapabilities(host + path, param)
        else:
            return self.getMap(param)

    def getMap (self, param):
        layer = self.service.layers[param["t"]]
        level = int(param["l"])
        y = float(param["y"])
        x = float(param["x"])
        
        tile  = Layer.Tile(layer, x, y, level)
        return tile
    
    def getCapabilities (self, host, param):

        metadata = self.service.metadata
        if "description" in metadata:
            description = metadata["description"]
        else:
            description = ""

        formats = {}
        for layer in self.service.layers.values():
            formats[layer.format()] = 1
        formats = formats.keys()
        xml = """<?xml version="1.0" encoding="UTF-8" ?>
            <LayerSet Name="TileCache" ShowAtStartup="true" ShowOnlyOneLayers="false"> 
            """

        for name, layer in self.service.layers.items():
            if (layer.srs != "EPSG:4326"): continue
            xml += """
                <ChildLayerSet Name="%s" ShowAtStartup="false" ShowOnlyOneLayer="true">
                <QuadTileSet ShowAtStartup="true">
                  <Name>%s</Name>
                  <Description>Layer: %s</Description>
                  <DistanceAboveSurface>0</DistanceAboveSurface>
                  <BoundingBox>
                    <West><Value>%s</Value></West>
                    <South><Value>%s</Value></South>
                    <East><Value>%s</Value></East>
                    <North><Value>%s</Value></North>
                  </BoundingBox>
                  <TerrainMapped>false</TerrainMapped>
                  <!-- I have no clue what this means. -->
                  <ImageAccessor>
                    <LevelZeroTileSizeDegrees>%s</LevelZeroTileSizeDegrees>
                    <NumberLevels>%s</NumberLevels>
                    <TextureSizePixels>%s</TextureSizePixels>
                    <ImageFileExtension>%s</ImageFileExtension>
                    <ImageTileService>
                      <ServerUrl>%s</ServerUrl>
                      <DataSetName>%s</DataSetName>
                    </ImageTileService>  
                  </ImageAccessor>
                  <ExtendedInformation>
                    <Abstract>SRS:%s</Abstract>
                    <!-- WorldWind doesn't have any place to store the SRS --> 
                  </ExtendedInformation>
                </QuadTileSet>
              </ChildLayerSet>
                """ % (name, name, layer.description, float(layer.bbox[0]), float(layer.bbox[1]),
                       float(layer.bbox[2]), float(layer.bbox[3]), layer.resolutions[0] * layer.size[0], 
                       len(layer.resolutions), layer.size[0], layer.extension, host, 
                       name, layer.srs)

        xml += """
            </LayerSet>"""

        return Capabilities("text/xml", xml)

class WMS (Request):
    def parse (self, fields, path, host):
        param = {}
        for key in ['bbox', 'layers', 'request', 'version']: 
            if fields.has_key(key.upper()):
                param[key] = fields[key.upper()] 
            elif fields.has_key(key):
                param[key] = fields[key]
            else:
                param[key] = ""
        if param["request"] == "GetCapabilities":
            return self.getCapabilities(host + path, param)
        else:
            return self.getMap(param)

    def getMap (self, param):
        bbox  = map(float, param["bbox"].split(","))
        layer = self.service.layers[param["layers"]]
        tile  = layer.getTile(bbox)
        if not tile:
            raise Exception(
                "couldn't calculate tile index for layer %s from (%s)"
                % (layer.name, bbox))
        return tile

    def getCapabilities (self, host, param):
        if host[-1] not in "?&":
            if "?" in host:
                host += "&"
            else:
                host += "?"

        metadata = self.service.metadata
        if "description" in metadata:
            description = metadata["description"]
        else:
            description = ""

        formats = {}
        for layer in self.service.layers.values():
            formats[layer.format()] = 1
        formats = formats.keys()

        xml = """<?xml version='1.0' encoding="ISO-8859-1" standalone="no" ?>
        <!DOCTYPE WMT_MS_Capabilities SYSTEM 
            "http://schemas.opengeospatial.net/wms/1.1.1/WMS_MS_Capabilities.dtd" [
              <!ELEMENT VendorSpecificCapabilities (TileSet*) >
              <!ELEMENT TileSet (SRS, BoundingBox?, Resolutions,
                                 Width, Height, Format, Layers*, Styles*) >
              <!ELEMENT Resolutions (#PCDATA) >
              <!ELEMENT Width (#PCDATA) >
              <!ELEMENT Height (#PCDATA) >
              <!ELEMENT Layers (#PCDATA) >
              <!ELEMENT Styles (#PCDATA) >
        ]> 
        <WMT_MS_Capabilities version="1.1.1">
          <Service>
            <Name>OGC:WMS</Name>
            <Title>%s</Title>
            <OnlineResource xlink:href="%s"/>
          </Service>
        """ % (description, host)

        xml += """
          <Capability>
            <Request>
              <GetCapabilities>
                <Format>application/vnd.ogc.wms_xml</Format>
                <DCPType>
                  <HTTP>
                    <Get><OnlineResource xlink:href="%s"/></Get>
                  </HTTP>
                </DCPType>
              </GetCapabilities>""" % (host)
        xml += """
              <GetMap>"""
        for format in formats:
            xml += """
                <Format>%s</Format>\n""" % format
        xml += """
                <DCPType>
                  <HTTP>
                    <Get><OnlineResource xlink:href="%s"/></Get>
                  </HTTP>
                </DCPType>
              </GetMap>
            </Request>""" % (host)
        xml += """
            <Exception>
              <Format>text/plain</Format>
            </Exception>
            <VendorSpecificCapabilities>"""
        for name, layer in self.service.layers.items():
            resolutions = " ".join(["%.9f" % r for r in layer.resolutions])
            xml += """
              <TileSet>
                <SRS>%s</SRS>
                <BoundingBox SRS="%s" minx="%f" miny="%f"
                                      maxx="%f" maxy="%f" />
                <Resolutions>%s</Resolutions>
                <Width>%d</Width>
                <Height>%d</Height>
                <Format>%s</Format>
                <Layers>%s</Layers>
                <Styles></Styles>
              </TileSet>""" % (
                layer.srs, layer.srs, layer.bbox[0], layer.bbox[1],
                layer.bbox[2], layer.bbox[3], resolutions, layer.size[0],
                layer.size[1], layer.format(), name )
        xml += """
            </VendorSpecificCapabilities>
            <UserDefinedSymbolization SupportSLD="0" UserLayer="0"
                                      UserStyle="0" RemoteWFS="0"/>"""
        for name, layer in self.service.layers.items():
            xml += """
            <Layer queryable="0" opaque="0" cascaded="1">
              <Name>%s</Name>
              <Title>%s</Title>
              <SRS>%s</SRS>
              <BoundingBox srs="%s" minx="%f" miny="%f"
                                    maxx="%f" maxy="%f" />
            </Layer>""" % (
                name, layer.name, layer.srs, layer.srs,
                layer.bbox[0], layer.bbox[1], layer.bbox[2], layer.bbox[3])

        xml += """
          </Capability>
        </WMT_MS_Capabilities>"""

        return Capabilities("text/xml", xml)

class TMS (Request):
    def parse (self, fields, path, host):
        # /1.0.0/global_mosaic/0/0/0.jpg
        parts = filter( lambda x: x != "", path.split("/") )
        if not host[-1] == "/": host = host + "/"
        if len(parts) < 1:
            return self.serverCapabilities(host)
        elif len(parts) < 2:
            return self.serviceCapabilities(host, self.service.layers)
        else:
            layer = self.service.layers[parts[1]]
            if len(parts) < 3:
                return self.layerCapabilities(host, layer)
            else:
                parts[-1] = parts[-1].split(".")[0]
                tile = None
                if (fields.has_key('type') and fields['type'] == 'google'):
                    res = layer.resolutions[int(parts[2])]
                    maxY = int((layer.bbox[3] - layer.bbox[1]) / (res * layer.size[1])) - 1
                    tile  = Layer.Tile(layer, int(parts[3]), maxY - int(parts[4]), int(parts[2]))
                else: 
                    tile  = Layer.Tile(layer, int(parts[3]), int(parts[4]), int(parts[2]))
                return tile

    def serverCapabilities (self, host):
        return Capabilities("text/xml", """<?xml version="1.0" encoding="UTF-8" ?>
            <Services>
                <TileMapService version="1.0.0" href="%s1.0.0/" />
            </Services>""" % host)

    def serviceCapabilities (self, host, layers):
        xml = """<?xml version="1.0" encoding="UTF-8" ?>
            <TileMapService version="1.0.0">
              <TileMaps>"""

        for name, layer in layers.items():
            profile = "none"
            if (layer.srs == "EPSG:4326"): profile = "global-geodetic"
            elif (layer.srs == "OSGEO:41001"): profile = "global-mercator"
            xml += """
                <TileMap 
                   href="%s1.0.0/%s/" 
                   srs="%s"
                   title="%s"
                   profile="%s" />
                """ % (host, name, layer.srs, layer.name, profile)

        xml += """
              </TileMaps>
            </TileMapService>"""

        return Capabilities("text/xml", xml)

    def layerCapabilities (self, host, layer):
        xml = """<?xml version="1.0" encoding="UTF-8" ?>
            <TileMap version="1.0.0" tilemapservice="%s1.0.0/">
              <Title>%s</Title>
              <Abstract>%s</Abstract>
              <SRS>%s</SRS>
              <BoundingBox minx="%.6f" miny="%.6f" maxx="%.6f" maxy="%.6f" />
              <Origin x="%.6f" y="%.6f" />  
              <TileFormat width="%d" height="%d" mime-type="%s" extension="%s" />
              <TileSets>
            """ % (host, layer.name, layer.description, layer.srs, layer.bbox[0], layer.bbox[1],
                   layer.bbox[2], layer.bbox[3], layer.bbox[0], layer.bbox[1],
                   layer.size[0], layer.size[1], layer.format(), layer.extension)

        for z, res in enumerate(layer.resolutions):
            xml += """
                 <TileSet href="%s1.0.0/%s/%d"
                          units-per-pixel="%.9f" order="%d" />""" % (
                   host, layer.name, z, res, z)
                
        xml += """
              </TileSets>
            </TileMap>"""

        return Capabilities("text/xml", xml)

class Service (object):
    __slots__ = ("layers", "cache", "metadata")

    def __init__ (self, cache, layers, metadata = {}):
        self.cache    = cache
        self.layers   = layers
        self.metadata = metadata
    
    def _loadFromSection (cls, config, section, module, **objargs):
        type  = config.get(section, "type")
        objclass = getattr(module, type)
        for opt in config.options(section):
            if opt != "type":
                objargs[opt] = config.get(section, opt)
        if module is Layer:
            return objclass(section, **objargs)
        else:
            return objclass(**objargs)
    loadFromSection = classmethod(_loadFromSection)

    def _load (cls, *files):
        config = ConfigParser.ConfigParser()
        config.read(files)
        
        metadata = {}
        if config.has_section("metadata"):
            for key in config.section("metadata"):
                metadata[key] = config.get("metadata", key)

        cache = cls.loadFromSection(config, "cache", Cache)

        layers = {}
        for section in config.sections():
            if section in cls.__slots__: continue
            layers[section] = cls.loadFromSection(
                                    config, section, Layer, cache = cache)

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
        
        return (layer.format(), image)

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

    def dispatchRequest (self, params, path_info, req_method, host):
        if params.has_key("service") or params.has_key("SERVICE"):
            tile = WMS(self).parse(params, path_info, host)
        elif params.has_key("L") or params.has_key("l"):
            tile = WorldWind(self).parse(params, path_info, host)
        else:
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
        host += apacheReq.uri
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
