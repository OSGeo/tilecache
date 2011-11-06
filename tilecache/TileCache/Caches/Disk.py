# BSD Licensed, Copyright (c) 2006-2010 TileCache Contributors

from TileCache.Cache import Cache
import sys, os, time, warnings

class Disk (Cache):
    def __init__ (self, base = None, umask = '002', **kwargs):
        Cache.__init__(self, **kwargs)
        self.basedir = base
        self.umask = int(umask, 0)
        if sys.platform.startswith("java"):
            from java.io import File
            self.file_module = File
            self.platform = "jython"
        else:
            self.platform = "cpython"
        
        if not self.access(base, 'read'):
            self.makedirs(base)
        
    def makedirs(self, path, hide_dir_exists=True):
        if hasattr(os, "umask"):
            old_umask = os.umask(self.umask)
        try:
            os.makedirs(path)
        except OSError, E:
            # os.makedirs can suffer a race condition because it doesn't check
            # that the directory  doesn't exist at each step, nor does it
            # catch errors. This lets 'directory exists' errors pass through,
            # since they mean that as far as we're concerned, os.makedirs
            # has 'worked'
            if E.errno != 17 or not hide_dir_exists:
                raise E
        if hasattr(os, "umask"):
            os.umask(old_umask)
        
    def access(self, path, type='read'):
        if self.platform == "jython":
            if type == "read":
                return self.file_module(path).canRead()
            else:
                return self.file_module(path).canWrite()
        else:
            if type =="read":
                return os.access(path, os.R_OK)
            else:
                return os.access(path, os.W_OK)

    ###########################################################################
    ##
    ## @brief test a tile to see if it has expired
    ##
    ## @param path              the full path to the tile to test
    ## @param TileCache::Layer  the layer
    ##
    ## @return true if expire time on the layer is less than the tiles mtime,
    ##         or false in any other case
    ##
    ###########################################################################
    
    def isExpired(self, path, layer):
        
        if layer.expired != None:
            
            try:
                mtime = os.stat(path).st_mtime
            except Exception, E:
                raise Exception( "isExpired %s %s\n", (path, E) )
                return False
            
            if mtime < layer.expired:
                return True
        
        return False
        
    def getKey (self, tile):
        components = ( self.basedir,
                       tile.layer.name,
                       "%02d" % tile.z,
                       "%03d" % int(tile.x / 1000000),
                       "%03d" % (int(tile.x / 1000) % 1000),
                       "%03d" % (int(tile.x) % 1000),
                       "%03d" % int(tile.y / 1000000),
                       "%03d" % (int(tile.y / 1000) % 1000),
                       "%03d.%s" % (int(tile.y) % 1000, tile.layer.extension)
                    )
        filename = os.path.join( *components )
        return filename

    ###########################################################################
    ##
    ## @brief get cached tile
    ##
    ## @param TileCache::Layer::Tile  the tile to get from the cache
    ##
    ## @return filename for the X-SendFile header, TileCache::Layer::Tile::data,
    ##  or None if the there is no cached tile
    ##
    ###########################################################################
    
    def get (self, tile):
        
        filename = self.getKey(tile)
        if self.access(filename, 'read'):
            
            ##### test if the tile has expired #####
            
            if self.isExpired(filename, tile.layer) and not self.readonly:
                os.unlink(filename)
                return None
            
            if self.sendfile:
                return filename
            else:
                tile.data = file(filename, "rb").read()
                return tile.data
        else:
            return None

    def set (self, tile, data):
        if self.readonly: return data
        filename = self.getKey(tile)
        dirname  = os.path.dirname(filename)
        if not self.access(dirname, 'write'):
            self.makedirs(dirname)
        tmpfile = filename + ".%d.tmp" % os.getpid()
        if hasattr(os, "umask"):
            old_umask = os.umask(self.umask)
        output = file(tmpfile, "wb")
        output.write(data)
        output.close()
        if hasattr(os, "umask"):
            os.umask( old_umask );
        try:
            os.rename(tmpfile, filename)
        except OSError:
            os.unlink(filename)
            os.rename(tmpfile, filename)
        tile.data = data
        return data
    
    def delete (self, tile):
        filename = self.getKey(tile)
        if self.access(filename, 'read'):
            os.unlink(filename)
            
    def attemptLock (self, tile):
        name = self.getLockName(tile)
        try: 
            self.makedirs(name, hide_dir_exists=False)
            return True
        except OSError:
            pass
        try:
            st = os.stat(name)
            if st.st_ctime + self.stale < time.time():
                warnings.warn("removing stale lock %s" % name)
                # remove stale lock
                self.unlock(tile)
                self.makedirs(name)
                return True
        except OSError:
            pass
        return False 
     
    def unlock (self, tile):
        name = self.getLockName(tile)
        try:
            os.rmdir(name)
        except OSError, E:
            print >>sys.stderr, "unlock %s failed: %s" % (name, str(E))
