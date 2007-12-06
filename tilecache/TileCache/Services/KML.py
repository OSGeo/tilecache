from TileCache.Service import Request, Capabilities
from TileCache.Services.TMS import TMS
import TileCache.Layer as Layer

class KML(TMS):
    def parse (self, fields, path, host):
        tile = TMS.parse(self,fields, path, host) 
        tiles = [
          Layer.Tile(tile.layer, tile.x << 1, tile.y << 1, tile.z + 1),
          Layer.Tile(tile.layer, (tile.x << 1) + 1, tile.y << 1, tile.z + 1),
          Layer.Tile(tile.layer, (tile.x << 1) + 1, (tile.y << 1) + 1, tile.z + 1),
          Layer.Tile(tile.layer, tile.x << 1 , (tile.y << 1) + 1, tile.z + 1)
        ]
        
        network_links = []
        
        for single_tile in tiles:
            b = single_tile.bounds()
            network_links.append("""<NetworkLink>
      <name>tile</name>
      <Region>
        <Lod>
          <minLodPixels>128</minLodPixels><maxLodPixels>-1</maxLodPixels>
        </Lod>
        <LatLonAltBox>
          <north>%s</north><south>%s</south>
          <east>%s</east><west>%s</west>
        </LatLonAltBox>
      </Region>
      <Link>
        <href>%s/1.0.0/%s/%s/%s/%s.kml</href>
        <viewRefreshMode>onRegion</viewRefreshMode>
      </Link>
    </NetworkLink>""" % (b[3], b[1], b[2], b[0], host, single_tile.layer.name, single_tile.z, single_tile.x, single_tile.y))
        
        b = tile.bounds()
            
        kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://earth.google.com/kml/2.1">
  <Document>
    <Region>
      <Lod>
        <minLodPixels>128</minLodPixels><maxLodPixels>512</maxLodPixels>
      </Lod>
      <LatLonAltBox>
        <north>%s</north><south>%s</south>
        <east>%s</east><west>%s</west>
      </LatLonAltBox>
    </Region>
    <GroundOverlay>
      <drawOrder>%s</drawOrder>
      <Icon>
        <href>%s/1.0.0/%s/%s/%s/%s</href>
      </Icon>
      <LatLonBox>
        <north>%s</north><south>%s</south>
        <east>%s</east><west>%s</west>
      </LatLonBox>
    </GroundOverlay>
    %s
  </Document>
</kml>""" % (b[3], b[1], b[2], b[0], tile.z, host, tile.layer.name, tile.z, tile.x, tile.y, b[3], b[1], b[2], b[0], "\n".join(network_links))

        return ("application/vnd.google-earth.kml+xml", kml)
