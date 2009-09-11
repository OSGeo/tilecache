# BSD Licensed, Copyright (c) 2006-2008 MetaCarta, Inc.

from TileCache.Service import Request, Capabilities, TileCacheException
import TileCache.Layer as Layer
from TileCache.Layers.TileMatrixSet import TileMatrixSet, TileMatrix, XML_NAMESPACES, WMTS_VERSION 
from TileCache.Layers.WMTS import WMTSTile

def pluralize(condition_val, text_val, plural_form = None):
    if condition_val == 1:
        return "%d %s" % (condition_val, text_val)
    else:
        if plural_form:
            return "%d %s" % (condition_val, plural_form)
        else:
            return "%d %ss" % (condition_val, text_val)
        

class FeatureInfo (object):
    def __init__ (self, format, data):
        self.format = format
        self.data   = data

# http://localhost/tilecache-2.04/tilecache.py/1.0.0/basic/3/14/2.png
# is the same tile as 
# http://localhost/tilecache-2.04/wmts.py/basic/thickblue/basicMatrixSet/34879630.5804/14/5.png
# 
# other examples:
# http://localhost/tilecache-2.04/wmts.py/basic/thickblue/TestMtx1/2.5e6/75/75.gif
# Zoom level 3 is at scale 34879630.5804
# In both cases it's tile column 14
# WMTS tile rows are flipped, so instead of row 2 in range 0-7 it's 7 - 2 = 5
class WMTS(Request):
    service_details = None
    
    def parse (self, fields, path, host):
        # Full Query: {HTTPServer}/{WMTSServerPath}/{layer}/{style}/{firstDimension}/{...}/{lastDimension}/{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.{format_extension}
        
        parts = filter( lambda x: x != "", path.split("/") )
        if not host[-1] == "/": host = host + "/"
        if len(parts) == 0:
            # detected get capabilities request
            return self.serviceCapabilities(host, self.service.layers)
        else:
            # to interpret the resource requested we need to know 
            # which layer it was request for. For instance if a 
            # layer has none or one style associated with it then 
            # the REST request won't specify any style. The same 
            # goes for dimensions. Note that there is a change 
			# request to make style mandatory, with a default 
			# value instead of no value.
            
            # use a mapping of a sequence of WMTS specific request 
            # components to a single layer of tilecache
            
            # determine the layer
            
            if(len(parts) == 1):
                raise TileCacheException("Malformed WMTS request. If you were after capabilities remember the version number (%s).\nFor WMTS capabilities try /%s/WMTSCapabilities" % (WMTS_VERSION, WMTS_VERSION));
            if(len(parts) == 2):
                ver = parts[0]
                
                if ver != WMTS_VERSION:
                    raise TileCacheException("WMTS Version '%s' not supported. Try '%s', or check your request structure." % (ver, WMTS_VERSION));
                
                requested = parts[1]
                if requested == "WMTSCapabilities.xml":
                    return self.serviceCapabilities(host, self.service.layers)
                else:
                    # does the layer exist?
                    for layer in self.service.layers.values():
                        if layer.wmts_layer == requested:
                            return Capabilities("text/xml", self.layerCapabilities(requested, True))
                    
                    # was it a tile matrix set instead?
                    if self.service.tile_matrix_sets.has_key(requested):
                        return Capabilities("text/xml", self.service.tile_matrix_sets[requested].getCapabilities(is_root_node=True))
                
                raise TileCacheException("No capabilities could be generated for '%s'. It is not a WMTS layer or Tile Matrix Set. Try 'WMTSCapabilities.xml' for a complete capabilities document." % requested);

            wmts_layer_name = parts[0]
            
            if parts[-1].find(".") == -1:
                raise TileCacheException("Malformed GetTile request. Expecting a file extension.")
                
            # split off the format extension
            parts.append(parts[-1].split(".")[1])
            parts[-2] = parts[-2].split(".")[0]
            
            # we have a WMTS layer name, from this we can find out
            # what styles / dimensions are supported for the layer
            styles_expected, dimensions_expected = self.getWMTSLayerDetails(wmts_layer_name)
            
            # now we know exactly what structure the URL needs to be 
            # we can validate it
            parts_in_get_tile = 6 + styles_expected + dimensions_expected
            parts_in_get_feature = 8 + styles_expected + dimensions_expected
            tile_details_offset = len(parts) - parts_in_get_tile
            if(len(parts) in [parts_in_get_tile, parts_in_get_feature]):
                is_get_tile = len(parts) == parts_in_get_tile
                style = None
                
                if styles_expected > 0:
                    style = parts[1]
                    
                dimensions = None
                
                if dimensions_expected > 0:
                    dimensions = parts[1 + styles_expected : 1 + styles_expected + dimensions_expected]
                    
                tile_matrix_set_name = parts[-(tile_details_offset + 5)]
                tile_matrix_identifier = parts[-(tile_details_offset + 4)]
                tile_row = int(parts[-(tile_details_offset + 3)])
                tile_col = int(parts[-(tile_details_offset + 2)])
                    
                if(is_get_tile):
                    format_extension = parts[-1]
                else:
                    j = int(parts[-3])
                    i = int(parts[-2])
                    format_extension = parts[-1]
    
                layer = self.getWMTSLayer(wmts_layer_name, style, dimensions, tile_matrix_set_name)
                tile_matrix = self.getTileMatrix(tile_matrix_set_name, tile_matrix_identifier)
                     
                self.checkTileCoords(tile_matrix, tile_row, tile_col)
                    
                scale = tile_matrix.scale_denominator; 
                res = .00028 * float(scale) / layer.meters_per_unit
                z = layer.getLevel(res, layer.size)
                    
                tile = WMTSTile(layer, tile_col, tile_row, z, tile_matrix)
                tile.tile_matrix = tile_matrix
                
                if(is_get_tile):
                    return tile
                else:
                    self.checkInfoFormat(layer, format_extension)
                    self.checkIJCoords(tile_matrix, i, j)
                 
                    response = layer.getFeatureInfo(tile, i, j, format_extension)
                    return FeatureInfo(layer.info_formats[format_extension], response)

            else:
                raise TileCacheException("Invalid WMTS Request. Layer '%s' expects %s and %s" % (wmts_layer_name, pluralize(styles_expected, "style"), pluralize(dimensions_expected, "dimension")))


    # Given a WMTS layer name, find out how many styles and dimensions are 
    # expected in the request
    def getWMTSLayerDetails(self, layer_name):
        wmts_layers = []

        styles_expected = 0
        dimensions_expected = 0
        
        for name, layer in self.service.layers.items():
            if not layer.wmts_layer in wmts_layers: 
                wmts_layers.append(layer.wmts_layer)

            if layer.wmts_layer == layer_name:
                
                if layer.style:
                    # either 0 or 1 style can be expected
                    # if any WMTS layer has style set 
                    # then all of them have to have it set 
                    styles_expected = 1
                    
                if layer.dimensions:
                    dimensions_expected = len(layer.dimensions)
                
                return styles_expected, dimensions_expected

        # if we got to this point in the code then the layer wasn't found. 
        if layer_name == WMTS_VERSION:
            raise TileCacheException("Invalid WMTS Request. Try removing the version number from the request, it's only needed for capability requests.")
        else:
            raise TileCacheException("The requested WMTS layer (%s) does not map to any WMTS layer known to this tilecache. Available WMTS layers are: \n * %s" % (layer_name, "\n * ".join(wmts_layers))) 

    # validates the WMTS layer request is OK
    # layer_name: the WMTS layer name as a String
    # style_name: the style name as a String or None
    # dimensions: the dimensions as a list of Strings or none
    # tile_matrix_set_name: the tile matrix set name as a string or None
    def getWMTSLayer(self, layer_name, style_name, dimensions, tile_matrix_set_name):
        wmts_layers = []
        wmts_styles = []
        wmts_tile_matrix_sets = []
        
        layer_ok = False
        style_ok = False
        tile_matrix_set_ok = False

        for name, layer in self.service.layers.items():
            if not layer.wmts_layer in wmts_layers: 
                wmts_layers.append(layer.wmts_layer)

            if layer.wmts_layer == layer_name:
                layer_ok = True
                
                # style may not be required for this layer
                if layer.style:
                    if not layer.style[0] in wmts_styles: 
                        wmts_styles.append(layer.style[0])

                if ((layer.style == None and style_name == None) or 
                    (layer.style and layer.style[0] == style_name)):
                    style_ok = True
                
                    if not layer.tile_matrix_set in wmts_tile_matrix_sets: 
                        wmts_tile_matrix_sets.append(layer.tile_matrix_set)
    
                    if layer.tile_matrix_set == tile_matrix_set_name:
                        tile_matrix_set_ok = True
                
                        if dimensions and layer.dimensions:
                            if [x[1] for x in layer.dimensions] == dimensions:
                                return layer
                        elif not (dimensions or layer.dimensions):
                            # no dimensions
                            return layer 

        # if we got to this point in the code then the layer wasn't found. 
        # give a nice exception explaining what went wrong with the request.
        
        if layer_ok:
            if style_ok:
                if tile_matrix_set_ok:
                    raise TileCacheException("There is no combination of dimensions that match (%s) for WMTS layer %s. Check the WMTS capabilities document for that layer." % (dimensions, layer_name))
                else:
                    raise TileCacheException("The requested WMTS tile matrix set (%s) is not used for the WMTS layer %s. Available tile matrix sets for the WMTS layer %s are: \n * %s" % (tile_matrix_set_name, layer_name, layer_name, "\n * ".join(wmts_tile_matrix_sets)))
            else:
                raise TileCacheException("The requested WMTS style (%s) is not used for the WMTS layer %s. Available styles for the WMTS layer %s are: \n * %s" % (style_name, layer_name, layer_name, "\n * ".join(wmts_styles)))
        else:
            raise TileCacheException("The requested WMTS layer (%s) does not map to any WMTS layer known to this tilecache. Available WMTS layers are: \n * %s" % (layer_name, "\n * ".join(wmts_layers))) 

    # Get the scale of a given a tile matrix using the tile matrix set name and tile matrix identifier.
    # tile_matrix_set_name: the tile matrix set name as a string
    # layer_name: the WMTS layer name as a String
    def getTileMatrix(self, tile_matrix_set_name, tile_matrix_ident):
        tile_matrices = []
        
        tile_matrix_set = self.service.tile_matrix_sets[tile_matrix_set_name]
        for tile_matrix in tile_matrix_set.tile_matrices:
            tile_matrices.append(tile_matrix.identifier)
            
            if tile_matrix.identifier == tile_matrix_ident:
                return tile_matrix
            
        raise TileCacheException("The requested WMTS tile matrix set (%s) does not contain a tile matrix with the identifier %s. Available tile matrixes for this tile matrix set are: \n * %s" % (tile_matrix_set_name, tile_matrix_ident, "\n * ".join(tile_matrices)))

    def checkTileCoords(self, tile_matrix, tile_row, tile_col):

        if tile_row < 0 or tile_matrix.matrix_size[1] <= tile_row:
            raise TileCacheException(
"""The requested WMTS tile row (%s) is outside the bounds of tile matrix %s.  
Bounds are rows: 0 to %s and columns: 0 to %s. 
Order expected in query is row first then column.""" % 
                    (tile_row, tile_matrix.identifier, 
                     tile_matrix.matrix_size[1] - 1, 
                     tile_matrix.matrix_size[0] - 1))

        if tile_col < 0 or tile_matrix.matrix_size[0] <= tile_col:
            raise TileCacheException(
"""The requested WMTS tile column (%s) is outside the bounds of tile matrix %s.  
Bounds are rows: 0 to %s and columns: 0 to %s. 
Order expected in query is row first then column.""" % 
                    (tile_col, tile_matrix.identifier, 
                     tile_matrix.matrix_size[1] - 1, 
                     tile_matrix.matrix_size[0] - 1))
            
    def checkIJCoords(self, tile_matrix, i, j):
        # i is pixel column, j is pixel row

        if i < 0 or tile_matrix.tile_size[0] <= i:
            raise TileCacheException(
"""The requested pixel column (%s) is outside the bounds of a tile in tile matrix %s.  
Bounds are pixel row (j): 0 to %s and pixel column (i): 0 to %s. 
Order expected in query is row (j) first then column (i).""" % 
                    (i, tile_matrix.identifier, 
                     tile_matrix.tile_size[0] - 1, 
                     tile_matrix.tile_size[1] - 1))

        if j < 0 or tile_matrix.tile_size[1] <= j:
            raise TileCacheException(
"""The requested pixel row (%s) is outside the bounds of a tile in tile matrix %s.  
Bounds are pixel row (j): 0 to %s and pixel column (i): 0 to %s. 
Order expected in query is row (j) first then column (i).""" % 
                    (j, tile_matrix.identifier, 
                     tile_matrix.tile_size[0] - 1, 
                     tile_matrix.tile_size[1] - 1))

    def checkInfoFormat(self, layer, file_extension):
        if layer.info_formats:
            if not layer.info_formats.has_key(file_extension):
                formats = []
                for name, value in layer.info_formats.items():
                    formats.append("%s (%s)" % (name, value))
                    
                raise TileCacheException("Invalid WMTS Request. Layer '%s' does not support the info format %s. Supported formats are\n * %s" % (layer.wmts_layer, file_extension, "\n * ".join(formats)))
        else:
            raise TileCacheException("Invalid WMTS Request. Layer '%s' is not queryable." % (layer.wmts_layer))

    def serviceCapabilities (self, host, layers):
        if not self.service_details:
            self.loadServiceDetails()
        
        xml = """<?xml version="1.0" encoding="UTF-8" ?>
<Capabilities %sversion="%s">""" % (XML_NAMESPACES, WMTS_VERSION)

        xml += self.service_details % {"host": host, "version": WMTS_VERSION }

        xml += """
    <ows:OperationsMetadata>
        <ows:Operation name="GetCapabilities">
            <ows:DCP>
                <ows:HTTP>
                    <ows:Get xlink:href="%(host)s">
                        <ows:Constraint name="GetEncoding">
                            <ows:AllowedValues>
                                <ows:Value>RESTFul</ows:Value>
                            </ows:AllowedValues>
                        </ows:Constraint>
                    </ows:Get>
                </ows:HTTP>
            </ows:DCP>
        </ows:Operation>
        <ows:Operation name="GetTile">
            <ows:DCP>
                <ows:HTTP>
                    <ows:Get xlink:href="%(host)s">
                        <ows:Constraint name="GetEncoding">
                            <ows:AllowedValues>
                                <ows:Value>RESTFul</ows:Value>
                            </ows:AllowedValues>
                        </ows:Constraint>
                    </ows:Get>
                </ows:HTTP>
            </ows:DCP>
        </ows:Operation>
        <ows:Operation name="GetFeatureInfo">
            <ows:DCP>
                <ows:HTTP>
                    <ows:Get xlink:href="%(host)s">
                        <ows:Constraint name="GetEncoding">
                            <ows:AllowedValues>
                                <ows:Value>RESTFul</ows:Value>
                            </ows:AllowedValues>
                        </ows:Constraint>
                    </ows:Get>
                </ows:HTTP>
            </ows:DCP>
        </ows:Operation>
    </ows:OperationsMetadata>
    <Contents>
""" % {"host": host }
        
        wmts_layers = []

        for name, layer in layers.items():
            if layer.wmts_layer and not layer.wmts_layer in wmts_layers:
                wmts_layers.append(layer.wmts_layer)
                xml += self.layerCapabilities(layer.wmts_layer)

        # you might want to do this the old way (calc tile matrix sets based on 
        # resolutions) if you want to check how the resolutions of the layers 
        # convert to tile matrix sets.
        if True:
            # Generate tile matrix sets based on the tile matrix set records 
            for name, tile_matrix_set in self.service.tile_matrix_sets.items():
                xml += tile_matrix_set.getCapabilities()
        else:
            # Generate tile matrix sets based on the layers resolutions
            wmts_layers = []
            for name, layer in layers.items():
                if layer.wmts_layer and not layer.wmts_layer in wmts_layers:
                    wmts_layers.append(layer.wmts_layer)
                    xml += self.tileMatrixSetCapabilities(layer=layer)
            

        xml += """
    </Contents>
</Capabilities>"""

        return Capabilities("text/xml", xml)

    def layerCapabilities (self, layer_name, is_root_node = False):
        keyword_xml = ""

        styles = []
        style_xml = ""
        
        # a dictionary of dimensions and their possible values
        dimensions = {}
        dimension_xml = ""

        tile_matrix_sets = []
        tile_matrix_set_xml = ""

        info_format_xml = ""
        
        reference_layer = None
        
        for name, layer in self.service.layers.items():
            if layer.wmts_layer == layer_name:
                # we'll just grab the first layer for things like bbox and description
                if not reference_layer:
                    reference_layer = layer
                    
                if layer.style and not layer.style[0] in styles:
                    styles.append(layer.style[0])
                
                if layer.dimensions:
                    for dimension in layer.dimensions:
                        if dimension[0] in dimensions:
                            if not dimension[1] in dimensions[dimension[0]]:
                                dimensions[dimension[0]].append(dimension[1])
                        else:
                            dimensions[dimension[0]] = [dimension[1]]

                if layer.tile_matrix_set and not layer.tile_matrix_set in tile_matrix_sets:
                    tile_matrix_sets.append(layer.tile_matrix_set)

        if reference_layer.keywords:
            for keyword in reference_layer.keywords:
                keyword_xml += """
                <ows:Keyword>%s</ows:Keyword>""" % keyword

            if keyword_xml != "":
                keyword_xml = """<ows:Keywords>%s
            </ows:Keywords>""" % keyword_xml
              
        if styles:
            for style in styles:
                style_xml += """
                <Style>
                    <ows:Identifier>%s</ows:Identifier>
                </Style>""" % style
        else:
            style_xml += """
                <Style isDefault="true">
                    <ows:Title>default</ows:Title>
                    <ows:Identifier>default</ows:Identifier>
                </Style>"""            
              
        if reference_layer.info_formats:
            for ext, mime in reference_layer.info_formats.iteritems():
                info_format_xml += """
                <InfoFormat>
                    <MIME>%s</MIME>
                    <FileExtension>%s</FileExtension>
                </InfoFormat>""" % (mime, ext)
                
        # use the reference layer to order the dimensions
        if reference_layer.dimensions:        
            for dimension in reference_layer.dimensions:
                if dimension[0].startswith("dim_"):
                    name = dimension[0][4:]
                else:
                    name = dimension[0]
                    
                dimension_xml += """
                <Dimension>
                    <ows:Identifier>%s</ows:Identifier>
                    %s
                </Dimension>""" % (name, "\n                ".join(map( lambda x : "<Value>%s</Value>" % x, dimensions[dimension[0]])))

        for tile_matrix_set in tile_matrix_sets:
            tile_matrix_set_xml += """
            <TileMatrixSet>%s</TileMatrixSet>""" % tile_matrix_set

        root_node_xml = ""
        if is_root_node:
            root_node_xml = " %s version=\"%s\"" % (XML_NAMESPACES, WMTS_VERSION)
                
        xml = """
        <Layer%s>
            <ows:Title>%s</ows:Title>
            <ows:Abstract>%s</ows:Abstract>
            %s
            <ows:WGS84BoundingBox>
                <ows:LowerCorner>%.6f %.6f</ows:LowerCorner>
                <ows:UpperCorner>%.6f %.6f</ows:UpperCorner>
            </ows:WGS84BoundingBox>
            <ows:Identifier>%s</ows:Identifier>
            %s
            <Format>
                <MIME>%s</MIME>
                <FileExtension>%s</FileExtension>
            </Format>
            %s
            %s
            %s
        </Layer>""" % (root_node_xml, reference_layer.title or layer_name, 
                   reference_layer.description, keyword_xml,  
                   reference_layer.bbox[0], reference_layer.bbox[1],
                   reference_layer.bbox[2], reference_layer.bbox[3], 
                   layer_name, style_xml, reference_layer.format(),
                   reference_layer.extension, info_format_xml, 
                   dimension_xml, tile_matrix_set_xml)
        
        if is_root_node:
            xml = """<?xml version="1.0" encoding="UTF-8" ?>\n""" + xml

        return xml
    
    def loadServiceDetails(self):
        file_paths = self.configPaths("wmts_service_details.xml")
        
        exceptions = []
        
        for file_path in file_paths:
            try:
                self.service_details = open(file_path).read()
                break
            except Exception, E:
                exceptions.append(E)
            
        if len(exceptions) >= len(file_paths):
            raise TileCacheException("Couldn't load WMTS service details. Attempted locations: %s\n\nExceptions: %s" % (file_paths, exceptions))
    
    # find the service details template file by looking in the same locations 
    # the tilecache config file can be found in.
    def configPaths(self, filename):
        filelist = self.service.files
        cfgfiles = []
        
        for fileitem in filelist:
            if fileitem.rfind("/") != -1:
                this_file = fileitem[0:fileitem.rfind("/") + 1] + filename
            elif fileitem.rfind("\\") != -1:
                this_file = fileitem[0:fileitem.rfind("\\") + 1] + filename
            else:
                this_file = fileitem.replace("tilecache.cfg", filename)
                
            cfgfiles.append(this_file)
            
        return cfgfiles
            
        
        

