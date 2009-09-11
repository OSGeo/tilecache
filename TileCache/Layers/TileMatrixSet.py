# BSD Licensed, Copyright (c) 2006-2008 MetaCarta, Inc.

METERS_PER_UNIT = { 'degrees': 111118.752,
                    'meters': 1,
                    'feet': 0.3048,
                    'GlobalCRS84Pixel': 111319.49079327355
                    }

XML_NAMESPACES = """
xmlns:xlink="http://www.w3.org/1999/xlink" 
xmlns="http://www.opengis.net/wmts/1.0" 
xmlns:gml="http://www.opengis.net/gml" 
xmlns:ows="http://www.opengis.net/ows/1.1" 
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
xsi:schemaLocation="http://www.opengis.net/wmts/1.0 http://www.miramon.uab.es/ogc/schemas/wmts/1.0.0/wmtsGetCapabilities_response.xsd" """

WMTS_VERSION = "1.0.0"

class TileMatrix (object):
    __slots__ = ( "identifier", "scale_denominator", 
                  "top_left", "tile_size", "matrix_size")
    
    def __init__ (self, identifier, scale_denominator, top_left, tile_size, matrix_size):
        
        self.identifier = identifier
        self.scale_denominator = float(scale_denominator)
        self.top_left = map( lambda x: float(x), top_left.split(","))
        self.tile_size = map( lambda x: int(x), tile_size.split(","))
        self.matrix_size = map( lambda x: int(x), matrix_size.split(","))


class TileMatrixSet (object):
    __slots__ = ("name", "crs", "wellknown_scale_set", "identifier", "tile_matrices")
    
    config_properties = [
      {'name':'crs', 'description':'SRS (or CRS?) understood by source WMS'},
      {'name':'wellknown_scale_set', 'description': 'Identifier of a well known scale set this tile matrix set should advertise it supports.'},
      {'name':'identifiers', 'description': 'Comma separated list of tile matrix identifiers.'},
      {'name':'scale_denominator', 'description': 'Scale denominator for a tile matrix. Always preceeded with <identifier>__, as it pertains to a specific matrix set.'},
      {'name':'top_left', 'description': 'Top left spatial coordinate of a tile matrix. If preceeded with <identifier>__, it pertains to a specific matrix set only.'},
      {'name':'tile_size', 'description': 'Width and height of a tile in pixels. If preceeded with <identifier>__, it pertains to a specific matrix set only.'},
      {'name':'matrix_size', 'description': 'Width and height of a tile matrix in tiles. Always preceeded with <identifier>__, as it pertains to a specific matrix set.'},
    ]  
    
    def __init__ (self, name, wellknown_scale_set=None, crs="EPSG:4326", identifiers=None, top_left=None, tile_size=None, **kwargs ):
        """Take in parameters, usually from a config file, and create a TileMatrixSet.
        """
        
        self.name = name
        self.wellknown_scale_set = wellknown_scale_set        
        self.crs = crs        

        tile_matrices = []
        
        if identifiers:
            identifiers = identifiers.split(",")
            
            for identifier in identifiers:
                args = { "identifier": identifier }

                args["scale_denominator"] = kwargs["%s__scale_denominator" % identifier] 
                args["matrix_size"] = kwargs["%s__matrix_size" % identifier]
                
                if kwargs.has_key("%s__top_left" % identifier):
                    args["top_left"] = kwargs["%s__top_left" % identifier]
                else:
                    args["top_left"] = top_left
                    
                if kwargs.has_key("%s__tile_size" % identifier):
                    args["tile_size"] = kwargs["%s__tile_size" % identifier]
                else:
                    args["tile_size"] = tile_size
                
                tile_matrices.append(TileMatrix(**args))

                # ensure order is from largest scale denominator to smallest.
                tile_matrices.sort(key=lambda x: x.scale_denominator, reverse=True)
            
        self.tile_matrices = tile_matrices

    def getCapabilities(self, is_root_node=False):
        
        xml = ""
        
        # generate the capabilities document based on the 
        # defined tile matrix sets.
        for tile_matrix in self.tile_matrices:
            xml += """
            <TileMatrix>
                <ows:Identifier>%s</ows:Identifier>
                <ScaleDenominator>%f</ScaleDenominator>
                <TopLeftCorner>%f %f</TopLeftCorner>
                <TileWidth>%d</TileWidth>
                <TileHeight>%d</TileHeight>
                <MatrixWidth>%d</MatrixWidth>
                <MatrixHeight>%d</MatrixHeight>
            </TileMatrix>""" % (tile_matrix.identifier, 
                       tile_matrix.scale_denominator,  
                       tile_matrix.top_left[0], 
                       tile_matrix.top_left[1], 
                       tile_matrix.tile_size[0], 
                       tile_matrix.tile_size[1], 
                       tile_matrix.matrix_size[0], 
                       tile_matrix.matrix_size[1])
                
        root_node_xml = ""
        if is_root_node:
            root_node_xml = " %s version=\"%s\"" % (XML_NAMESPACES, WMTS_VERSION)
            
        well_known_scale_set_xml = ""
        if self.wellknown_scale_set:
            well_known_scale_set_xml = "<WellKnownScaleSet>%s</WellKnownScaleSet>\n            " % self.wellknown_scale_set

        xml = """
        <TileMatrixSet%s>
            <ows:Identifier>%s</ows:Identifier>
            <ows:SupportedCRS>%s</ows:SupportedCRS>
            %s%s
        </TileMatrixSet>
            """ % (root_node_xml, 
                   self.name, 
                   self.crs,  
                   well_known_scale_set_xml,  
                   xml)

        if is_root_node:
            xml = """<?xml version="1.0" encoding="UTF-8" ?>\n""" + xml

        return xml

if __name__ == "__main__":
    import doctest
    doctest.testmod()
