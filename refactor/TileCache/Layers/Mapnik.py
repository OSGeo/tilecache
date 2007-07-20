from TileCache.Layer import MetaLayer

class Mapnik(MetaLayer):
    def __init__ (self, name, mapfile = None, **kwargs):
        MetaLayer.__init__(self, name, **kwargs) 
        self.mapfile = mapfile
        self.mapnik  = None

    def renderTile(self, tile):
        import mapnik, Image, StringIO
        
        if self.mapnik:
            m = self.mapnik
        else:
            # Init it as 0,0
            m = mapnik.Map( 0, 0 )
            mapnik.load_map(m,self.mapfile)
            # this will insure that it gets cached in mod_python
            self.mapnik = m
        
        # Set the mapnik size to match the size of the current tile 
        m.width = tile.size()[0]
        m.height = tile.size()[1]
        
        bbox = tile.bounds()
        bbox = mapnik.Envelope(bbox[0], bbox[1], bbox[2], bbox[3])
        m.zoom_to_box(bbox)
                    
        im = mapnik.Image( *tile.size() )
        mapnik.render(m, im)
        im = Image.fromstring('RGBA', tile.size(), mapnik.rawdata(im))
        buffer = StringIO.StringIO()
        im.save(buffer, self.extension)
        buffer.seek(0)
        tile.data = buffer.read()
        return tile.data 
