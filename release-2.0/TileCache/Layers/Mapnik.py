from TileCache.Layer import MetaLayer

class Mapnik(MetaLayer):
    def __init__ (self, name, mapfile = None, projection = None, fonts = None, **kwargs):
        MetaLayer.__init__(self, name, **kwargs) 
        self.mapfile = mapfile
        self.mapnik  = None
        self.projection = projection
        if fonts:
            self.fonts = fonts.split(",")
        else:
            self.fonts = []
            
    def renderTile(self, tile):
        import mapnik, StringIO
        import PIL.Image 
        
        if self.mapnik:
            m = self.mapnik
        else:
            if self.fonts:
                engine = mapnik.FontEngine.instance()
                for font in self.fonts:
                    engine.register_font(font)
            
            # Init it as 0,0
            m = mapnik.Map( 0, 0 )
            mapnik.load_map(m,self.mapfile)
             
            if self.projection:
                m.srs = self.projection
            
            # Restrict layer list, if requested
            if self.layers and self.layers != self.name:
                layers = self.layers.split(",")
                for layer_num in range(len(m.layers)-1, -1, -1):
                    l = m.layers[layer_num]
                    if l.name not in layers:
                        del m.layers[layer_num]
                    if self.debug:
                        print >>sys.stderr, "Removed layer %s loaded from %s, not in list: %s" % (l.name, self.mapfile, layers)
                        
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
        im = PIL.Image.fromstring('RGBA', tile.size(), mapnik.rawdata(im))
        buffer = StringIO.StringIO()
        im.save(buffer, self.extension)
        buffer.seek(0)
        tile.data = buffer.read()
        return tile.data 
