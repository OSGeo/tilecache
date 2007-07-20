from TileCache.Cache import Cache
import sys, os

class Disk (Cache):
    def __init__ (self, base = None, perms = 0777, **kwargs):
        Cache.__init__(self, **kwargs)
        self.basedir = base
        
        if sys.platform.startswith("java"):
            from java.io import File
            self.file_module = File
            self.platform = "jython"
        else:
            self.platform = "cpython"
        
        if not self.access(base, 'read'):
            os.makedirs(base, perms)
        
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

    def get (self, tile):
        filename = self.getKey(tile)
        if self.access(filename, 'read'):
            tile.data = file(filename, "rb").read()
            return tile.data
        else:
            return None

    def set (self, tile, data):
        if self.readonly: return data
        filename = self.getKey(tile)
        dirname  = os.path.dirname(filename)
        if not self.access(dirname, 'write'):
            os.makedirs(dirname)
        tmpfile = filename + ".%d.tmp" % os.getpid()
        output = file(tmpfile, "wb")
        output.write(data)
        output.close()
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
            os.makedirs(name)
            return True
        except OSError:
            pass
        try:
            st = os.stat(name)
            if st.st_ctime + self.stale < time.time():
                warnings.warn("removing stale lock %s" % name)
                # remove stale lock
                self.unlock()
                os.makedirs(name)
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
