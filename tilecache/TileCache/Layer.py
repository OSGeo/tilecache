# BSD Licensed, Copyright (c) 2006-2007 MetaCarta, Inc.
import os, sys
from warnings import warn
from Client import WMS

DEBUG = True

class Tile (object):
    __slots__ = ( "layer", "x", "y", "z", "data" )
    def __init__ (self, layer, x, y, z):
        self.layer = layer
        self.x = x
        self.y = y
        self.z = z
        self.data = None

    def size (self):
        return self.layer.size

    def bounds (self):
        res  = self.layer.resolutions[self.z]
        minx = self.layer.bbox[0] + (res * self.x * self.layer.size[0])
        miny = self.layer.bbox[1] + (res * self.y * self.layer.size[1])
        maxx = self.layer.bbox[0] + (res * (self.x + 1) * self.layer.size[0])
        maxy = self.layer.bbox[1] + (res * (self.y + 1) * self.layer.size[1])
        return (minx, miny, maxx, maxy)

    def bbox (self):
        return ",".join(map(str, self.bounds()))

class MetaTile (Tile):
    def actualSize (self) :
        metaCols, metaRows = self.layer.getMetaSize(self.z)
        return ( self.layer.size[0] * metaCols,
                 self.layer.size[1] * metaRows )

    def size (self):
        actual = self.actualSize()
        return ( actual[0] + self.layer.metaBuffer * 2, 
                 actual[1] + self.layer.metaBuffer * 2 )

    def bounds (self):
        tilesize   = self.actualSize()
        res        = self.layer.resolutions[self.z]
        buffer     = res * self.layer.metaBuffer
        metaWidth  = res * tilesize[0]
        metaHeight = res * tilesize[1]
        minx = self.layer.bbox[0] + self.x * metaWidth  - buffer
        miny = self.layer.bbox[1] + self.y * metaHeight - buffer
        maxx = minx + metaWidth  + 2 * buffer
        maxy = miny + metaHeight + 2 * buffer
        return (minx, miny, maxx, maxy)

class Layer (object):
    __slots__ = ( "name", "layers", "bbox", 
                  "size", "resolutions", "extension", "srs",
                  "cache", "debug", "description" )
    threshold = 0.001
    
    def __init__ (self, name, layers = None, bbox = (-180, -90, 180, 90),
                        srs  = "EPSG:4326", description = "", maxresolution = None,
                        size = (256, 256), levels = 20, resolutions = None,
                        extension = "png", cache = None,  debug = True):
        self.name   = name
        self.description = description
        self.layers = layers or name
        if isinstance(bbox, str): bbox = map(float,bbox.split(","))
        self.bbox = bbox
        if isinstance(size, str): size = map(int,size.split(","))
        self.size = size
        self.srs  = srs
        if extension.lower() == 'jpg': extension = 'jpeg' # MIME
        self.extension = extension.lower()
        if isinstance(debug, str):
            debug = debug.lower() not in ("false", "off", "no", "0")
        self.cache = cache
        self.debug = debug
        if resolutions:
            if isinstance(resolutions, str):
                resolutions = map(float,resolutions.split(","))
            self.resolutions = resolutions
        else:
            maxRes = None
            if not maxresolution:
                width  = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                if width >= height:
                    aspect = int( float(width) / height + .5 ) # round up
                    maxRes = float(width) / (size[0] * aspect)
                else:
                    aspect = int( float(height) / width + .5 ) # round up
                    maxRes = float(height) / (size[1] * aspect)
            else:
                maxRes = float(maxresolution)
            self.resolutions = [maxRes / 2 ** i for i in range(int(levels))]

    def getResolution (self, (minx, miny, maxx, maxy)):
        return max( (maxx - minx) / self.size[0],
                    (maxy - miny) / self.size[1] )

    def getLevel (self, res):
        z = None
        for i in range(len(self.resolutions)):
            if abs( self.resolutions[i] - res ) < 0.00000001:
                res = self.resolutions[i]
                z = i
                break
        if z is None and self.debug:
            warn("can't find resolution index for %f" % res)
        return z

    def getClosestLevel (self, res):
        for i in range(1, len(self.resolutions)):
            if res > self.resolutions[i]:
                return i - 1 
        return len(self.resolutions) - 1

    def getCell (self, (minx, miny, maxx, maxy), exact = True):
        if exact and not self.contains((minx, miny)): 
            if self.debug: warn(
                "Lower left (%f, %f) is outside layer bounds" % (minx, miny))
            return None

        res = self.getResolution((minx, miny, maxx, maxy))
        x = y = None

        if exact:
            z = self.getLevel(res)
            if z is None: return None # oops
        else:
            z = self.getClosestLevel(res)

        res = self.resolutions[z]
        x0 = (minx - self.bbox[0]) / (res * self.size[0])
        y0 = (miny - self.bbox[1]) / (res * self.size[1])
        
        x = int(x0 + self.threshold / 2)
        y = int(y0 + self.threshold / 2)

        if exact:
            if abs(x - x0) > self.threshold:
                if self.debug:
                    warn("x (%f) - x0 (%f) = %f" % (x, x0, abs(x - x0)))
                return None
            if abs(y - y0) > self.threshold:
                if self.debug:
                    warn("y (%f) - y0 (%f) = %f" % (y, y0, abs(y - y0)))
                return None

        return (x, y, z)

    def getClosestCell (self, z, (minx, miny)):
        res = self.resolutions[z]
        maxx = minx + self.size[0] * res
        maxy = miny + self.size[1] * res
        return self.getCell((minx, miny, maxx, maxy), False)

    def getTile (self, bbox):
        coord = self.getCell(bbox)
        if not coord: return None
        return Tile(self, *coord)

    def contains (self, (x, y)):
        return x >= self.bbox[0] and x <= self.bbox[2] \
           and y >= self.bbox[1] and y <= self.bbox[3]

    def grid (self, z):
        width  = (self.bbox[2] - self.bbox[0]) / (self.resolutions[z] * self.size[0])
        height = (self.bbox[3] - self.bbox[1]) / (self.resolutions[z] * self.size[1])
        return (width, height)

    def format (self):
        return "image/" + self.extension
    
    def renderTile (self, tile):
        # To be implemented by subclasses
        pass 

    def render (self, tile):
        return self.renderTile(tile)

class MetaLayer (Layer):
    __slots__ = ('metaTile', 'metaSize', 'metaBuffer')
    def __init__ (self, name, metatile = False, metasize = (5,5),
                              metabuffer = 10, **kwargs):
        Layer.__init__(self, name, **kwargs)
        self.metaTile    = metatile
        if isinstance(metasize, str):
            metasize = map(int,metasize.split(","))
        if isinstance(metabuffer, str):
            metabuffer = int(metabuffer)
        self.metaSize    = metasize
        self.metaBuffer  = metabuffer

    def getMetaSize (self, z):
        maxcol, maxrow = self.grid(z)
        return ( min(self.metaSize[0], int(maxcol)), 
                 min(self.metaSize[1], int(maxrow)) )

    def getMetaTile (self, tile):
        x = int(tile.x / self.metaSize[0])
        y = int(tile.y / self.metaSize[1])
        return MetaTile(self, x, y, tile.z) 

    def renderMetaTile (self, metatile, tile):
        import StringIO, Image

        data = self.renderTile(metatile)
        image = Image.open( StringIO.StringIO(data) )

        metaCols, metaRows = self.getMetaSize(metatile.z)
        metaHeight = metaRows * self.size[1] + 2 * self.metaBuffer
        for i in range(metaCols):
            for j in range(metaRows):
                minx = i * self.size[0] + self.metaBuffer
                maxx = minx + self.size[0]
                ### this next calculation is because image origin is (top,left)
                maxy = metaHeight - (j * self.size[1] + self.metaBuffer)
                miny = maxy - self.size[1]
                subimage = image.crop((minx, miny, maxx, maxy))
                buffer = StringIO.StringIO()
                if image.info.has_key('transparency'): 
                    subimage.save(buffer, self.extension, transparency=image.info['transparency'])
                else:
                    subimage.save(buffer, self.extension)
                buffer.seek(0)
                subdata = buffer.read()
                x = metatile.x * self.metaSize[0] + i
                y = metatile.y * self.metaSize[1] + j
                subtile = Tile( self, x, y, metatile.z )
                self.cache.set( subtile, subdata )
                if x == tile.x and y == tile.y:
                    tile.data = subdata

        return tile.data

    def render (self, tile):
        if self.metaTile:
            metatile = self.getMetaTile(tile)
            try:
                self.cache.lock(metatile)
                image = self.cache.get(tile)
                if not image:
                    image = self.renderMetaTile(metatile, tile)
            finally:
                self.cache.unlock(metatile)
            return image
        else:
            return self.renderTile(tile)

class WMSLayer(MetaLayer):
    def __init__ (self, name, url = None, **kwargs):
        MetaLayer.__init__(self, name, **kwargs) 
        self.url = url

    def renderTile(self, tile):
        wms = WMS( self.url, {
          "bbox": tile.bbox(),
          "width": tile.size()[0],
          "height": tile.size()[1],
          "srs": self.srs,
          "format": self.format(),
          "layers": self.layers,
        } )
        tile.data, response = wms.fetch()
        return tile.data 

class ImageLayer(MetaLayer):
    """The ImageLayer allows you to set up any image file in TileCache.
       All you need is an image, and a geographic bounds (filebounds),
       Which is passed in as a single, comma seperated string in the form 
       minx,miny,maxx,maxy."""
    
    def __init__ (self, name, file = None, filebounds = "-180,-90,180,90", **kwargs):
        import Image
        
        MetaLayer.__init__(self, name, **kwargs) 
        
        self.file = file
        self.filebounds  = map(float,filebounds.split(","))
        self.image = Image.open(self.file)
        self.image_size = self.image.size
        self.image_res = [(self.filebounds[2] - self.filebounds[0]) / self.image_size[0], 
                    (self.filebounds[3] - self.filebounds[1]) / self.image_size[1]
                   ]
    
    def renderTile(self, tile):
        import Image, StringIO
        bounds = tile.bounds()
        size = tile.size()
        min_x = (bounds[0] - self.filebounds[0]) / self.image_res[0]   
        min_y = (self.filebounds[3] - bounds[3]) / self.image_res[1]
        max_x = (bounds[2] - self.filebounds[0]) / self.image_res[0]   
        max_y = (self.filebounds[3] - bounds[1]) / self.image_res[1]
        sub = self.image.transform(size, Image.EXTENT, (min_x, min_y, max_x, max_y))
        buffer = StringIO.StringIO()
        if self.image.info.has_key('transparency'):
            sub.save(buffer, self.extension, transparency=self.image.info['transparency'])
        else:
            sub.save(buffer, self.extension)

        buffer.seek(0)
        tile.data = buffer.read()
        return tile.data 

class MapnikLayer(MetaLayer):
    def __init__ (self, name, mapfile = None, **kwargs):
        MetaLayer.__init__(self, name, **kwargs) 
        self.mapfile = mapfile
        self.mapnik  = None

    def renderTile(self, tile):
        import mapnik, Image, StringIO
        
        if self.mapnik:
            m = self.mapnik
        else:
            # Init it as 0,0
            m = mapnik.Map( 0, 0 )
            mapnik.load_map(m,self.mapfile)
            # this will insure that it gets cached in mod_python
            self.mapnik = m
        
        # Set the mapnik size to match the size of the current tile 
        m.width = tile.size()[0]
        m.height = tile.size()[1]
        
        bbox = tile.bounds()
        bbox = mapnik.Envelope(bbox[0], bbox[1], bbox[2], bbox[3])
        m.zoom_to_box(bbox)
                    
        im = mapnik.Image( *tile.size() )
        mapnik.render(m, im)
        im = Image.fromstring('RGBA', tile.size(), mapnik.rawdata(im))
        buffer = StringIO.StringIO()
        im.save(buffer, self.extension)
        buffer.seek(0)
        tile.data = buffer.read()
        return tile.data 

class MapServerLayer(MetaLayer):
    def __init__ (self, name, mapfile = None, **kwargs):
        MetaLayer.__init__(self, name, **kwargs) 
        self.mapfile = mapfile

    def renderTile(self, tile):
        import mapscript
        wms = mapscript.mapObj(self.mapfile) 
        req = mapscript.OWSRequest()
        req.setParameter("bbox", tile.bbox())
        req.setParameter("width", str(tile.size()[0]))
        req.setParameter("height", str(tile.size()[1]))
        req.setParameter("srs", self.srs)
        req.setParameter("format", self.format())
        req.setParameter("layers", self.layers)
        wms.loadOWSParameters(req)
        mapImage = wms.draw()
        tile.data = mapImage.getBytes()
        return tile.data 
