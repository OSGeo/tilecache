from TileCache.Layer import MetaLayer
import TileCache.Client as WMSClient

class WMS(MetaLayer):
    def __init__ (self, name, url = None, **kwargs):
        MetaLayer.__init__(self, name, **kwargs) 
        self.url = url

    def renderTile(self, tile):
        wms = WMSClient.WMS( self.url, {
          "bbox": tile.bbox(),
          "width": tile.size()[0],
          "height": tile.size()[1],
          "srs": self.srs,
          "format": self.format(),
          "layers": self.layers,
        } )
        tile.data, response = wms.fetch()
        return tile.data 
