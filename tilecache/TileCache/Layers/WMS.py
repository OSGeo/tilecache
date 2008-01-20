# BSD Licensed, Copyright (c) 2006-2008 MetaCarta, Inc.

from TileCache.Layer import MetaLayer
import TileCache.Client as WMSClient

class WMS(MetaLayer):
    def __init__ (self, name, url = None, user = None, password = None, **kwargs):
        MetaLayer.__init__(self, name, **kwargs) 
        self.url = url
        self.user = user
        self.password = password

    def renderTile(self, tile):
        wms = WMSClient.WMS( self.url, {
          "bbox": tile.bbox(),
          "width": tile.size()[0],
          "height": tile.size()[1],
          "srs": self.srs,
          "format": self.format(),
          "layers": self.layers,
        }, self.user, self.password)
        tile.data, response = wms.fetch()
        return tile.data 
