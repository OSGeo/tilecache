# BSD Licensed, Copyright (c) 2006-2008 MetaCarta, Inc.

import os, sys
from warnings import warn
from TileCache.Layer import MetaLayer, MetaTile
from TileCache.Layers.WMS import WMS
import TileCache.Client as WMSClient
from TileCache.Layers.TileMatrixSet import TileMatrixSet, TileMatrix, METERS_PER_UNIT, XML_NAMESPACES, WMTS_VERSION 
from TileCache.Service import TileCacheException

def cartesian_product(lists, previous_elements = []):
    """
    Returns a generator of cartesian products of the lists provided.
    """ 
    if len(lists) == 1:
        for elem in lists[0]:
            yield previous_elements + [elem, ]
    else:
        for elem in lists[0]:
            for x in cartesian_product(lists[1:], previous_elements + [elem, ]):
                yield x

def load_wmts_layer(name, title=None, keywords=None, styles=None, stylevals=None, dimensions=None, dimensionvals=None, tile_matrix_sets=None, **kwargs):
    """
    Interprets a WMTS section in to a list of layers.
    styles, dimensions, tilematrixsets etc should be as they appear in the configuration file.    
    """
    if styles:
        styles = styles.split(",")
        
        if stylevals:
            stylevals = eval(stylevals)
        else:
            # duplicate the styles list for style values
            stylevals = styles[:]
            
        styles = zip(styles, stylevals)
    else:
        styles = [None]
        
    if not (dimensions or dimensionvals):
        dimensions = [None]
    else:
        # we need to rearrange the dimensions list into 
        # somethine we can use in a list comprehension to
        # generate all the WMTS layers.
        # Example of how it should look in config:
        #
        # dimensions=Elevation,Time
        # dimensionvals=[["5", "10"], ["2008-01", "2008-03"]]
        #
        # We need to expand this into a cartesian product of the 
        # values in a tuple with the dimension name like this:
        # [
        #   [("Elevation", "5"),("Time", "2008-01")],
        #   [("Elevation", "5"),("Time", "2008-03")],
        #   [("Elevation", "10"),("Time", "2008-01")],
        #   [("Elevation", "10"),("Time", "2008-03")],
        # ]
        dimensions = dimensions.split(",")
        dimensionvals = eval(dimensionvals)
        
        temp_dimensions = [] 
        for value_combination in cartesian_product(dimensionvals):
            temp_dimensions.append(zip(dimensions, value_combination))
            
        dimensions = temp_dimensions
    
    if tile_matrix_sets:
        tile_matrix_sets = tile_matrix_sets.split(",")
    else:
        tile_matrix_sets = [None]
        
    return [WMTS(name, title, keywords, s, d, t, **kwargs)
            for s in styles
            for d in dimensions
            for t in tile_matrix_sets]

def check_tile_matrix_set(layer, tile_matrix_sets):
    """
    Ensures the layer adheres to it's assigned tile matrix set.
    
    If the tile matrix set for the layer provided doesn't exist we will 
    define one based on the list of resolutions Tilecache came up with 
    by default.
    
    If the WMTS Layer references a tile matrix set that has already  
    been defined we will update the the resolutions list of the layer 
    to adhere to it.
    
    If a new tile matrix set is generated it will be returned for 
    addition to the list of tile matrix sets the service knows about.    
    """

    if layer.tile_matrix_set in tile_matrix_sets:
        tile_matrix_set = tile_matrix_sets[layer.tile_matrix_set]
        
        resolutions = []
        
        for tile_matrix in tile_matrix_set.tile_matrices:
            res = .00028 * tile_matrix.scale_denominator / layer.meters_per_unit
            
            resolutions.append(res)

        layer.resolutions = resolutions
        
    else:
        tile_matrix_set = TileMatrixSet("%s_TileMatrixSet" % layer.wmts_layer, 
                                        crs=layer.srs)
        
        for z, res in enumerate(layer.resolutions):
            # convert the resolution to a scale.
            # The scale denominator is defined as a "standardised rendering pixel size" of 0.28mm 
            scale = res * layer.meters_per_unit / .00028
            
            tile_span_x = layer.size[0] * res
            tile_span_y = layer.size[1] * res
            
            matrix_width = (layer.bbox[2] - layer.bbox[0]) / tile_span_x
            matrix_height = (layer.bbox[3] - layer.bbox[1]) / tile_span_y
            
            tile_matrix_set.tile_matrices.append(TileMatrix(
                                   "%f" % scale, 
                                   "%f" % scale, 
                                   "%f,%f" % (layer.bbox[1], layer.bbox[2]), 
                                   "%d,%d" % (layer.size[0], layer.size[1]), 
                                   "%d,%d" % (matrix_width, matrix_height)))
            
        return tile_matrix_set
    
class WMTSTile (MetaTile):
    tile_matrix = None
    
    def __init__ (self, layer, x, y, z, tile_matrix):
        self.layer = layer
        self.x = x
        self.y = y
        self.z = z
        self.data = None
        self.tile_matrix = tile_matrix

    def actualSize (self):
        if self.layer.metaTile:
            metaCols = min(self.tile_matrix.matrix_size[0], self.layer.metaSize[0])
            metaRows = min(self.tile_matrix.matrix_size[1], self.layer.metaSize[1])
        else:
            metaCols = 1
            metaRows = 1
        
        return ( self.tile_matrix.tile_size[0] * metaCols,
                 self.tile_matrix.tile_size[1] * metaRows )

    def size (self):
        actual = self.actualSize()
        
        if self.layer.metaTile:
            return ( actual[0] + self.layer.metaBuffer[0] * 2, 
                     actual[1] + self.layer.metaBuffer[1] * 2 )
        else:
            return actual

    def bounds (self):
        tilesize   = self.actualSize()
        res        = self.layer.resolutions[self.z]
        if self.layer.metaTile:
            buffer = (res * self.layer.metaBuffer[0], res * self.layer.metaBuffer[1])
        else:
            buffer = (0, 0)
            
        metaWidth  = res * tilesize[0]
        metaHeight = res * tilesize[1]
        
        minx = self.tile_matrix.top_left[0] + self.x * metaWidth - buffer[0]
        maxy = self.tile_matrix.top_left[1] - self.y * metaHeight + buffer[1]
        maxx = minx + metaWidth + 2 * buffer[0]
        miny = maxy - (metaHeight + 2 * buffer[1])

        return (minx, miny, maxx, maxy)
    
class WMTS(WMS):
    """
        Represents one Tilecache layer that supports WMTS style REST requests.
        One WMTS layer is actually going to be many Tilecache layers. The 
        formula is styles * dimension value combinations * tilematrixsets = number of Tilecache 
        layers it takes to represent one WMTS layer. This class represents one 
        of those Tilecache layers. It will be told of one style, one combination of 
        dimension values and one tilematrix set. 
    """
    config_properties = [
      {'name':'wmts_layer', 'description': 'WMTS Layer name. Unique in WMTS configuration of layers - Not set in the .cfg file, automatically determined.'},
      {'name':'title', 'description': 'A title to include in the capabilities document for this layer.'},
      {'name':'keywords', 'description': 'A comma separated list of keywords to include in the capabilities document for this layer.'},
      {'name':'style', 'description': 'Tuple of a name, value pair of the style for this WMTS layer. Name is the name of the WMTS style where value is the list of styles to pass on to the WMS for tile render.'},
      {'name':'dimensions', 'description': 'This must evaluate to an array of tuples with the dimension name as the first value of the tuple and a list of dimension values as the second value of the tuple. EG: [("Elevation", "5"), ("Wavelength", "a"), ("Time", "2008-01")].'},
      {'name':'units', 'description': 'A string that matches a key of the METERS_PER_UNIT dict, or the number of meters per unit to use for this layer.'},
      {'name':'tile_matrix_set', 'description': 'The tile matrix set this layer uses.'},
      {'name':'query_layers', 'description': 'If a get feature info request is made, use this setting to control which layers to query. This is fixed for the layer. Defaults to the layer list.'},
      {'name':'feature_count', 'description': 'Optional. Maximum number of features to return from a get feature info request.'},
      {'name':'info_formats', 'description': 'Optional. What info formats are supported by the layer. By default this is set to html and xml if query_layers is set. Otherwise it is blank.'},
      {'name':'pixel_coord_params', 'description': 'Some implementations of GetFeatureInfo use x,y instead of i,j. Set this parameter to a comma separated list of parameter names to use instead of i,j.'},
    ] + WMS.config_properties
    
    def __init__ (self, name, title=None, keywords=None, style=None, 
                  dimensions=None, tile_matrix_set=None, units="degrees",
                  query_layers=None, feature_count=None, info_formats=None, 
                  pixel_coord_params=None, 
                  **kwargs):
        WMS.__init__(self, name, **kwargs) 

        self.style = style
        
        self.wmts_layer = name
        self.title = title
        if keywords:
            self.keywords = keywords.split(",")
        else:
            self.keywords = None
            
        if METERS_PER_UNIT.has_key(units):
            self.meters_per_unit = METERS_PER_UNIT[units]
        else:
            self.meters_per_unit = float(units)
        
        if tile_matrix_set:
            self.tile_matrix_set = tile_matrix_set
        else:
            self.tile_matrix_set = "%s_TileMatrixSet" % name
        
        # If no query layers were specified in the config then make 
        # sure no info formats are configured as this is whats used 
        # to enable a layer as queryable.
        if query_layers:
            if info_formats:
                self.info_formats = eval(info_formats)
            else:
                self.info_formats = {"gml":"application/vnd.ogc.gml","htm":"text/html","html":"text/html","xml":"text/xml"}
        else:
            self.info_formats = None

        # get feature info options
        self.query_layers = query_layers or self.layers
        self.feature_count = feature_count
        
        self.pixel_coord_params = pixel_coord_params or 'i,j'
        self.pixel_coord_params = tuple(self.pixel_coord_params.split(','))  

        self.dimensions = dimensions
        if self.dimensions:
            # Ensure all dimensions besides 'time' 
            # and 'elevation' are prefixed with 
            # 'dim_'.
            for i in range(len(self.dimensions)):
                if not (self.dimensions[i][0].lower() == "time" or 
                        self.dimensions[i][0].lower() == "elevation" or
                        self.dimensions[i][0].lower().startswith("dim_")):
                    self.dimensions[i] = ("dim_%s" % self.dimensions[i][0], self.dimensions[i][1]) 
                 
        # Calculate what name this Tilecache layer should 
        # have. This name identifies the layer according to 
        # tilecache.
        namelist = [self.wmts_layer]
        
        if self.style:
            namelist.append(self.style[0])
        if self.dimensions:
            for dimension in self.dimensions:
                namelist.append(dimension[1])
        namelist.append(self.tile_matrix_set)

        self.name = "_".join(namelist)

    def renderTile(self, tile):
        # 'time' and 'elevation' are special dimensions.
        # All other dimensions are named 'dim_<dimension name>' 
        # in the KVP.
        params = self.prepareGetTileParams(tile)
            
        wms = WMSClient.WMS( self.url, params, self.user, self.password)
        
        tile.data, response = wms.fetch()

        return tile.data 

    def getTile (self, bbox):
        """Returns a WMTS tile that most closely matches the provided bbox"""
        raise TileCacheException("getTile(bbox) not supported in WMTS at the moment")

    def getMetaTile (self, tile):
        """Generates a metatile based on the supplied WMTS tile.
        Override the getMetaTile method to ensure that a WMTSTile is returned."""
        
        x = int(tile.x / self.metaSize[0])
        y = int(tile.y / self.metaSize[1])
        return WMTSTile(self, x, y, tile.z, tile.tile_matrix)

    def getMetaSize (self, tile_matrix):
        if not self.metaTile: return (1,1)
        maxcol, maxrow = tile_matrix.matrix_size
        return ( min(self.metaSize[0], int(maxcol + 1)), 
                 min(self.metaSize[1], int(maxrow + 1)) )

    def renderMetaTile (self, metatile, tile):
        import StringIO
        import PIL.Image as PILImage

        data = self.renderTile(metatile)
        image = PILImage.open( StringIO.StringIO(data) )

        metaCols, metaRows = self.getMetaSize(metatile.tile_matrix) 
        metaHeight = metaRows * metatile.tile_matrix.tile_size[1] + 2 * self.metaBuffer[1]
        
        for i in range(metaCols):
            for j in range(metaRows):
                minx = i * metatile.tile_matrix.tile_size[0] + self.metaBuffer[0]
                maxx = minx + metatile.tile_matrix.tile_size[0]

                miny = j * metatile.tile_matrix.tile_size[1] + self.metaBuffer[1]
                maxy = miny + metatile.tile_matrix.tile_size[1]
                
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
                subtile = WMTSTile(self, x, y, tile.z, tile.tile_matrix)
                if self.watermarkimage:
                    subdata = self.watermark(subdata)
                self.cache.set( subtile, subdata )
                if x == tile.x and y == tile.y:
                    tile.data = subdata

        return tile.data

    def getFeatureInfo(self, tile, i, j, format):
        # 'time' and 'elevation' are special dimensions.
        # All other dimensions are named 'dim_<dimension name>' 
        # in the KVP.
        params = self.prepareGetTileParams(tile)
            
        wms = WMSClient.WMS( self.url, params, self.user, self.password)

        # Correct the GetMap to a GetFeatureInfo
        wms.params["request"] = "GetFeatureInfo"

        wms.params["query_layers"] = self.query_layers
        if self.feature_count:
            wms.params["feature_count"] = self.feature_count
        
        wms.params["info_format"] = self.info_formats[format]
        wms.params[self.pixel_coord_params[0]] = i
        wms.params[self.pixel_coord_params[1]] = j
        
        # raise TileCacheException(wms.url())
        
        result, response = wms.fetch(self.info_formats[format])

        return result 

    def prepareGetTileParams(self, tile):
        params = {
          "bbox": tile.bbox(),
          "width": tile.size()[0],
          "height": tile.size()[1],
          "srs": self.srs,
          "format": self.mime_type,
          "layers": self.layers,
        }
        
        if self.style:
            params["styles"] = self.style[1]

        if self.dimensions:
            # Python 3 is going to support dictionary comprehension :D
            for key, val in self.dimensions:
                params[key] = val
        
        return params