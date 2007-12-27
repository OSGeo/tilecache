# BSD Licensed, Copyright (c) 2006-2007 MetaCarta, Inc.

import os, sys
from warnings import warn
from Client import WMS
from Service import TileCacheException

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
    def actualSize (self):
        metaCols, metaRows = self.layer.getMetaSize(self.z)
        return ( self.layer.size[0] * metaCols,
                 self.layer.size[1] * metaRows )

    def size (self):
        actual = self.actualSize()
        return ( actual[0] + self.layer.metaBuffer[0] * 2, 
                 actual[1] + self.layer.metaBuffer[1] * 2 )

    def bounds (self):
        tilesize   = self.actualSize()
        res        = self.layer.resolutions[self.z]
        buffer     = (res * self.layer.metaBuffer[0], res * self.layer.metaBuffer[1])
        metaWidth  = res * tilesize[0]
        metaHeight = res * tilesize[1]
        minx = self.layer.bbox[0] + self.x * metaWidth  - buffer[0]
        miny = self.layer.bbox[1] + self.y * metaHeight - buffer[1]
        maxx = minx + metaWidth  + 2 * buffer[0]
        maxy = miny + metaHeight + 2 * buffer[1]
        return (minx, miny, maxx, maxy)

class Layer (object):
    __slots__ = ( "name", "layers", "bbox", 
                  "size", "resolutions", "extension", "srs",
                  "cache", "debug", "description", 
                  "watermarkimage", "watermarkopacity",
                  "extent_type", "tms_type", "units", "mime_type")
    
    def __init__ (self, name, layers = None, bbox = (-180, -90, 180, 90),
                        srs  = "EPSG:4326", description = "", maxresolution = None,
                        size = (256, 256), levels = 20, resolutions = None,
                        extension = "png", mime_type = None, cache = None,  debug = True, 
                        watermarkimage = None, watermarkopacity = 0.2,
                        extent_type = "strict", units = None, tms_type = "" ):
        self.name   = name
        self.description = description
        self.layers = layers or name
        if isinstance(bbox, str): bbox = map(float,bbox.split(","))
        self.bbox = bbox
        if isinstance(size, str): size = map(int,size.split(","))
        self.size = size
        self.units = units
        self.srs  = srs
        if extension.lower() == 'jpg': extension = 'jpeg' # MIME
        self.extension = extension.lower()
        self.mime_type = mime_type or self.format() 
        if isinstance(debug, str):
            debug = debug.lower() not in ("false", "off", "no", "0")
        self.cache = cache
        self.debug = debug
        self.extent_type = extent_type
        self.tms_type = tms_type
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
        self.watermarkimage = watermarkimage
        self.watermarkopacity = float(watermarkopacity)

    def getResolution (self, (minx, miny, maxx, maxy)):
        return max( (maxx - minx) / self.size[0],
                    (maxy - miny) / self.size[1] )

    def getLevel (self, res, size = [256, 256]):
        max_diff = res / max(size[0], size[1])
        z = None
        for i in range(len(self.resolutions)):
            if abs( self.resolutions[i] - res ) < max_diff:
                res = self.resolutions[i]
                z = i
                break
        if z is None:
            raise TileCacheException("can't find resolution index for %f. Available resolutions are: \n%s" % (res, self.resolutions))
        return z

    def getCell (self, (minx, miny, maxx, maxy), exact = True):
        if exact and self.extent_type == "strict" and not self.contains((minx, miny)): 
            raise TileCacheException("Lower left corner (%f, %f) is outside layer bounds %s. \nTo remove this condition, set extent_type=loose in your configuration." 
                     % (minx, miny, self.bbox))
            return None

        res = self.getResolution((minx, miny, maxx, maxy))
        x = y = None

        z = self.getLevel(res, self.size)

        res = self.resolutions[z]
        x0 = (minx - self.bbox[0]) / (res * self.size[0])
        y0 = (miny - self.bbox[1]) / (res * self.size[1])
        
        x = int(round(x0))
        y = int(round(y0))
        
        tilex = ((x * res * self.size[0]) + self.bbox[0])
        tiley = ((y * res * self.size[1]) + self.bbox[1])
        if exact:
            if (abs(minx - tilex)  / res > 1):
                raise TileCacheException("Current x value %f is too far from tile corner x %f" % (minx, tilex))  
            
            if (abs(miny - tiley)  / res > 1):
                raise TileCacheException("Current y value %f is too far from tile corner y %f" % (miny, tiley))  
        
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
    def __init__ (self, name, metatile = "", metasize = (5,5),
                              metabuffer = (10,10), **kwargs):
        Layer.__init__(self, name, **kwargs)
        self.metaTile    = metatile.lower() in ("true", "yes", "1")
        if isinstance(metasize, str):
            metasize = map(int,metasize.split(","))
        if isinstance(metabuffer, str):
            metabuffer = map(int, metabuffer.split(","))
            if len(metabuffer) == 1:
                metabuffer = (metabuffer[0], metabuffer[0])
        self.metaSize    = metasize
        self.metaBuffer  = metabuffer

    def getMetaSize (self, z):
        if not self.metaTile: return (1,1)
        maxcol, maxrow = self.grid(z)
        return ( min(self.metaSize[0], int(maxcol + 1)), 
                 min(self.metaSize[1], int(maxrow + 1)) )

    def getMetaTile (self, tile):
        x = int(tile.x / self.metaSize[0])
        y = int(tile.y / self.metaSize[1])
        return MetaTile(self, x, y, tile.z) 

    def renderMetaTile (self, metatile, tile):
        import StringIO, Image

        data = self.renderTile(metatile)
        image = Image.open( StringIO.StringIO(data) )

        metaCols, metaRows = self.getMetaSize(metatile.z)
        metaHeight = metaRows * self.size[1] + 2 * self.metaBuffer[1]
        for i in range(metaCols):
            for j in range(metaRows):
                minx = i * self.size[0] + self.metaBuffer[0]
                maxx = minx + self.size[0]
                ### this next calculation is because image origin is (top,left)
                maxy = metaHeight - (j * self.size[1] + self.metaBuffer[1])
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
                if self.watermarkimage:
                    subdata = self.watermark(subdata)
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
            if self.watermarkimage:
                return self.watermark(self.renderTile(tile))
            else:
                return self.renderTile(tile)

    def watermark (self, img):
        import StringIO, Image, ImageEnhance
        tileImage = Image.open( StringIO.StringIO(img) )
        wmark = Image.open(self.watermarkimage)
        assert self.watermarkopacity >= 0 and self.watermarkopacity <= 1
        if wmark.mode != 'RGBA':
            wmark = wmark.convert('RGBA')
        else:
            wmark = wmark.copy()
        alpha = wmark.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(self.watermarkopacity)
        wmark.putalpha(alpha)
        if tileImage.mode != 'RGBA':
            tileImage = tileImage.convert('RGBA')
        watermarkedImage = Image.new('RGBA', tileImage.size, (0,0,0,0))
        watermarkedImage.paste(wmark, (0,0))
        watermarkedImage = Image.composite(watermarkedImage, tileImage, watermarkedImage)
        buffer = StringIO.StringIO()
        if watermarkedImage.info.has_key('transparency'):
            watermarkedImage.save(buffer, self.extension, transparency=compositeImage.info['transparency'])
        else:
            watermarkedImage.save(buffer, self.extension)
        buffer.seek(0)
        return buffer.read()
