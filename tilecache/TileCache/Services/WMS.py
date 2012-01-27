# BSD Licensed, Copyright (c) 2006-2010 TileCache Contributors

from TileCache.Service import Request, Capabilities
import TileCache.Layer as Layer
import sys

class WMS (Request):
    def parse (self, fields, path, host):
        param = {}
        for key in ['bbox', 'layers', 'request', 'version', 'height', 'width']: 
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
        layers = param["layers"].split(",")
        height = min( 4096, int(param["height"]) )
        width  = min( 4096, int(param["width"]) )
        tiles =  []

        ##### loop over the layers #####

        for name in layers:

            ##### calc the increment for each of the tiles in the bbox #####

            xincr = ( bbox[2] - bbox[0] ) / (width  / self.getLayer(name).size[0])
            yincr = ( bbox[3] - bbox[1] ) / (height / self.getLayer(name).size[1])
            
            ##### loop over the bbox  and build a list of tiles #####
            
            x = bbox[0]
            while x < bbox[2] - xincr / 2: #### cant use the exact bbox value because of floating point errors
                y = bbox[1]
                while y < bbox[3] - yincr / 2:
                    tile  = self.getLayer(name).getTile((x, y, x+xincr, y+yincr))
                    if not tile:
                        raise Exception(
                            "couldn't calculate tile index for layer %s from (%s)"
                            % (layer.name, bbox))
                    tiles.append(tile)
                    y += yincr
                x += xincr

        if len(tiles) > 1:
            return tiles
        else:
            return tiles[0]

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
            <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="%s"/>
          </Service>
        """ % (description, host)

        xml += """
          <Capability>
            <Request>
              <GetCapabilities>
                <Format>application/vnd.ogc.wms_xml</Format>
                <DCPType>
                  <HTTP>
                    <Get><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="%s"/></Get>
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
                    <Get><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="%s"/></Get>
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
            resolutions = " ".join(["%.20f" % r for r in layer.resolutions])
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
                                      UserStyle="0" RemoteWFS="0"/>
            <Layer>
              <Title>TileCache Layers</Title>"""
        for name, layer in self.service.layers.items():
            xml += """
            <Layer queryable="0" opaque="0" cascaded="1">
              <Name>%s</Name>
              <Title>%s</Title>
              <SRS>%s</SRS>
              <BoundingBox SRS="%s" minx="%f" miny="%f"
                                    maxx="%f" maxy="%f" />
            </Layer>""" % (
                name, layer.name, layer.srs, layer.srs,
                layer.bbox[0], layer.bbox[1], layer.bbox[2], layer.bbox[3])

        xml += """
            </Layer>
          </Capability>
        </WMT_MS_Capabilities>"""

        return Capabilities("text/xml", xml)


