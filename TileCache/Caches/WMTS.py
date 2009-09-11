# BSD Licensed, Copyright (c) 2008 MetaCartas, Inc.

"""
Disk cache using the WMTS structure
"""

from TileCache.Cache import Cache
from TileCache.Caches.Disk import Disk
from TileCache.Service import TileCacheException
from TileCache.Layers.WMTS import WMTSTile


import os

class WMTS(Disk):
    def getKey (self, tile):
        
        if not isinstance(tile, WMTSTile):
            raise TileCacheException("Can't request tiles using TMS from a WMTS type Cache.")
        
        components = [self.basedir,
                      tile.layer.wmts_layer]
        if tile.layer.style:
            components.append(tile.layer.style[0])            
            
        if tile.layer.dimensions:
            components += [x[1] for x in tile.layer.dimensions]
    
        components += [tile.layer.tile_matrix_set,					   
                      tile.tile_matrix.identifier,
                      ("%s" % tile.y),
                      ("%s.%s" % (tile.x , tile.layer.extension))]

        filename = os.path.join( *components )
        return filename

