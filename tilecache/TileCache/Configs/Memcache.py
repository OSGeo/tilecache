#!/usr/bin/python

# BSD Licensed, Copyright (c) 2006-2010 TileCache Contributors
from TileCache.Config import Config
import sys, select, traceback, csv, time
import TileCache.Cache, TileCache.Caches
import TileCache.Layer, TileCache.Layers
from TileCache.Service import TileCacheException
import json


try:
    import memcache
except:
    Memcache=False

    ###########################################################################
    ##
    ## @brief method to parse the config.
    ##
    ## @param url    config url to parse
    ##
    ###########################################################################

class Memcache(Config):
    __slots__ = Config.__slots__ + ('mc','memcache_prefix',)
    
    def __init__(self, memcache_name, memcache_prefix, memcache_array, cache):
        super(Memcache, self).__init__(resource=memcache_name, cache=cache)
        self.memcache_prefix=memcache_prefix
        self.mc = memcache.Client(memcache_array, debug=0)
        sys.stderr.write('Loading memcache config!')
        self.layers={}
        self.metadata={}
        
    def isMemcache(self):
        return True
    
    def checkchange (self, configs):
        return False
    
    def _getLayerConfig(self, name):
        key = self._getKey(name)
        sys.stderr.write('Memcache lookup for %s\n' % (key,))
        data=self.mc.get(key)
        sys.stderr.write('Got "%s" (type: %s)\n' % (data, type(data)))
        if data:
            try:
                return json.loads(data)
            except Exception, e:
                sys.stderr.write('Unable to parse config for layer %s (%s)\n' % (key, e,))
                return None
        return None
    
    def _loadConfig(self, layer_config):
        defaults={}
        config=defaults.copy()
        config.update(layer_config)
        return config

    def _getKey(self, name):
        key = "%s%s" % (self.memcache_prefix, name)
        return key

    def getConfig(self, item):
        return self[item]
    
    #
    # This sucks 'cause it has to do a get twice, it's usage is 
    # good to avoid.
    #
    def hasConfig(self, item):
        return any(self._getLayerConfig(item))
    
    #
    # So this will get the config entry if it exists and
    # return it back to the caller.
    #
    def __getitem__(self, layer):
        sys.stderr.write('Memcache lookup for %s\n' % (layer,))
        pconfig=self._getLayerConfig(layer)
        if not pconfig:
            raise KeyError('Item does not exist in Memcache config')
        else:
            pconfig.update({'cache': self.cache})
            sys.stderr.write('Loading config for %s' % (layer,))
            return self._load_layer(**pconfig)

    
    ###########################################################################
    ##
    ## @brief method to add a layer to the config.
    ##
    ## @param objargs   the settings to add
    ##
    ## @return True on success, False on failure
    ## @details
    ## objargs must contain a name key. all other keys are added,
    ## this method will replace a layer if it already exists
    ##
    ###########################################################################

    def add (self):
        if objargs.has_key('name'):
            key = self._getKey(name)
            sys.stderr.write('Memcache add for %s\n' % (key,))

            try:
                config = {}
                config.update(objargs)
                
                data = json.dumps(config)
                self.mc.put(key, data)
                
                return True

            except Exception, e:
                raise Exception("Update failed.\n".join(traceback.format_tb(sys.exc_traceback)))
                
        return False
    
    ###########################################################################
    ##
    ## @brief method to update a layer in the config.
    ##
    ## @param objargs   the settings to update
    ##
    ## @return True on success, False on failure
    ## @details
    ## objargs must contain a name key. all other keys are added or replaced,
    ## use the add to remove options from the layer
    ###########################################################################

    def update (self, **objargs ):
        
        if objargs.has_key('name'):
            key = self._getKey(name)
            sys.stderr.write('Memcache update for %s\n' % (key,))

            try:
                data=self.mc.get(key)
                
                if data:

                    config = json.loads(data)
                    config.update(objargs)
                    
                    data = json.dumps(config)
                    self.mc.put(key, data)
                    
                    return True

            except Exception, e:
                raise Exception("Update failed.\n".join(traceback.format_tb(sys.exc_traceback)))
                
        return False

    ###########################################################################
    ##
    ## @brief method to delete a layer from the config.
    ##
    ## @param name  name of the layer to delete
    ##
    ## @return True on success, False on failure
    ##
    ###########################################################################

    def delete (self, name = None):
        if name != None:
            key = self._getKey(name)
            sys.stderr.write('Memcache delete for %s\n' % (key,))
            
            try:
                self.mc.delete(key)
                return True

            except:
                raise Exception("Delete failed.\n".join(traceback.format_tb(sys.exc_traceback)))

        return False
    

