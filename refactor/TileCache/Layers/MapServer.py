from TileCache.Layer import MetaLayer 

class MapServer(MetaLayer):
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
