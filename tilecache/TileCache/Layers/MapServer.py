from TileCache.Layer import MetaLayer 

class MapServer(MetaLayer):
    def __init__ (self, name, mapfile = None, styles = "", **kwargs):
        MetaLayer.__init__(self, name, **kwargs) 
        self.mapfile = mapfile
        self.styles = styles

    def renderTile(self, tile):
        import mapscript
        wms = mapscript.mapObj(self.mapfile) 
        if self.metaBuffer:
            try:
                # if the metadata is already set, don't override.
                wms.getMetaData("labelcache_map_edge_buffer")
            except mapscript._mapscript.MapServerError:
                # We stick an extra buffer of 5px in there because in the case
                # of shields, we want to account for when the shield could get
                # cut even though the label that the shield is on isn't.
                buffer = -self.metaBuffer - 5
                wms.setMetaData("labelcache_map_edge_buffer", str(buffer))
        req = mapscript.OWSRequest()
        req.setParameter("bbox", tile.bbox())
        req.setParameter("width", str(tile.size()[0]))
        req.setParameter("height", str(tile.size()[1]))
        req.setParameter("srs", self.srs)
        req.setParameter("format", self.format())
        req.setParameter("layers", self.layers)
        req.setParameter("styles", self.styles)
        req.setParameter("request", "GetMap")
        wms.loadOWSParameters(req)
        mapImage = wms.draw()
        tile.data = mapImage.getBytes()
        return tile.data 
