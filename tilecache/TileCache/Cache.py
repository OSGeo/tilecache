# BSD Licensed, Copyright (c) 2006-2007 MetaCarta, Inc.
import os, sys, time
from warnings import warn

class Cache (object):
    def __init__ (self, timeout = 30.0, stale_interval = 300.0, readonly = False, **kwargs):
        self.stale    = float(stale_interval)
        self.timeout = float(timeout)
        self.readonly = readonly
                
    def lock (self, tile, blocking = True):
        start_time = time.time()
        result = self.attemptLock(tile)
        if result:
            return True
        elif not blocking:
            return False
        while result is not True:
            if time.time() - start_time > self.timeout:
                raise Exception("You appear to have a stuck lock. You may wish to remove the lock named:\n%s" % self.getLockName(tile)) 
            time.sleep(0.25)
            result = self.attemptLock(tile)
        return True

    def getLockName (self, tile):
        return self.getKey(tile) + ".lck"

    def getKey (self, tile):
        raise NotImplementedError()

    def attemptLock (self, tile):
        raise NotImplementedError()

    def unlock (self, tile):
        raise NotImplementedError()

    def get (self, tile):
        raise NotImplementedError()

    def set (self, tile, data):
        raise NotImplementedError()
    
    def delete(self, tile):
        raise NotImplementedError()

class MemoryCache (Cache):
    def __init__ (self, servers = ['127.0.0.1:11211'], **kwargs):
        Cache.__init__(self, **kwargs)
        import memcache
        if type(servers) is str: servers = map(str.strip, servers.split(","))
        self.cache = memcache.Client(servers, debug=0)
   
    def getKey(self, tile):
         return "/".join(map(str, [tile.layer.name, tile.x, tile.y, tile.z]))
        
    def get(self, tile):
        key = self.getKey(tile)
        tile.data = self.cache.get(key)
        return tile.data
    
    def set(self, tile, data):
        if self.readonly: return data
        key = self.getKey(tile)
        self.cache.set(key, data)
        return data
    
    def delete(self, tile):
        key = self.getKey(tile)
        self.cache.delete(key)

    def attemptLock (self, tile):
        return self.cache.add( self.getLockName(tile), "0", 
                               time.time() + self.timeout)
    
    def unlock (self, tile):
        self.cache.delete( self.getLockName() )

class DiskCache (Cache):
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
                warn("removing stale lock %s" % name)
                # remove stale lock
                self.unlock(tile)
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
