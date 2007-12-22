from TileCache.Cache import Cache
import time

class AWSS3(Cache):
    def __init__ (self, access_key, secret_access_key, **kwargs):
        import TileCache.Caches.S3
        Cache.__init__(self, **kwargs)
        self.s3 = S3
        self.cache = self.s3.AWSAuthConnection(access_key, secret_access_key)
        self.bucket_name = "%s-tilecache" % access_key.lower() 
        self.cache.create_bucket(self.bucket_name)
   
    def getKey(self, tile):
         return "-".join(map(str, [tile.layer.name, tile.z , tile.x, tile.y]))
    
    def get(self, tile):
        key = self.getKey(tile)
        response = self.cache.get(self.bucket_name, key)
        if not response.object.data.startswith("<?xml"):
            tile.data = response.object.data
        return tile.data
    
    def set(self, tile, data):
        if self.readonly: return data
        key = self.getKey(tile)
        obj = self.cache.put(self.bucket_name, key, self.s3.S3Object(data))
        return data
    
    def delete(self, tile):
        key = self.getKey(tile)
        self.deleteObject(key) 
    
    def deleteObject(self, key):
        self.cache.delete(self.bucket_name, key)
    
    def getLockName (self, tile):
        return "lock-" % self.getKey(tile)
    
    def attemptLock (self, tile):
        return self.cache.put( self.bucket_name, self.getLockName(tile), 
                               time.time() + self.timeout)
    
    def unlock (self, tile):
        self.cache.delete( self.bucket_name, self.getLockName() )
    
    def keys (self, options = {}):
        return map(lambda x: x.key, 
            self.cache.list_bucket(self.bucket_name, options).entries)

if __name__ == "__main__":
    import sys
    from optparse import OptionParser
    parser = OptionParser(usage="""%prog [options] action    
    action is one of: 
      list_locks
      count_tiles
      show_tiles
      delete <object_key> or <list>,<of>,<keys>
      delete_tiles""")
    parser.add_option('-z', dest='zoom', help='zoom level for count_tiles (requires layer name)')  
    parser.add_option('-l', dest='layer', help='layer name for count_tiles')  
    parser.add_option('-k', dest='key', help='access key for S3')  
    parser.add_option('-s', dest='secret', help='secret access key for S3') 
    
    (options, args) = parser.parse_args()
    if not options.key or not options.secret or not args:
        parser.print_help()
        sys.exit()
    
    def create_prefix(options):
        prefix = "" 
        if options.layer:
            prefix = "%s-" % options.layer 
            if options.zoom:
                prefix = "%s%s-" % (prefix, options.zoom)
        return prefix        
    
    # Debug mode. 
    a = AWSS3(options.key, 
              options.secret)
    if args[0] == "list_locks":           
        print ','.join(a.keys({'prefix':'lock-'}))
    elif args[0] == "list_keys":
        print ','.join(a.keys())
    elif args[0] == "count_tiles" or args[0] == "show_tiles":
        opts = { 
            'prefix': create_prefix(options)
        }
        if args[0] == "show_tiles":
            print ",".join(a.keys(opts))
        else:
            print len(a.keys(opts))
    elif args[0] == "delete":
        for key in args[1].split(","):
            a.deleteObject(key)
    elif args[0] == "delete_tiles":
        opts = { 
            'prefix': create_prefix(options)
        }
        keys = a.keys(opts)
        val = raw_input("Are you sure you want to delete %s tiles? (y/n) " % len(keys))
        if val.lower() in ['y', 'yes']:
            for key in keys:
                a.deleteObject(key)
            
    else:
        parser.print_help() 
        
