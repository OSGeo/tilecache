#!/usr/bin/python

# BSD Licensed, Copyright (c) 2006-2010 TileCache Contributors

import urllib2, traceback, sys, os, ConfigParser, csv, time
import TileCache.Layer, TileCache.Layers
import TileCache.Cache, TileCache.Caches
import threading

################################################################################
# These are the supported configuration lines for includes.
# The key is the name of the config reference as it will appear in
# the tilecache.cfg file, the value is a two-tuple containing
# the module name for this config, and the object name supporting it.
################################################################################

supported_configs={'file': ('TileCache.Config.File','File',),
                   'url': ('TileCache.Config.Url','Url',),
                   'pg': ('TileCache.Configs.PG', 'PG',),
                   'memcache': ('TileCache.Configs.Memcache', 'Memcache',),
                   }

################################################################################
# Helper module to import any module based on a name, and return the module
################################################################################

def import_module(name):
    """."""
    mod = __import__(name)
    components = name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod
    
###############################################################################
##
## @brief base config class handles file configs
##
###############################################################################

class Config (object):
    __slots__ = ( "resource", "last_mtime", "cache", "metadata" , "layers", "s_sections", "lock", "loadedConfigs")
    
    def __init__ (self, resource, cache = None):
        self.s_sections = [ "cache", "metadata", "tilecache_options", "include" ]
        self.resource = resource     
        self.cache=cache   
        self.loadedConfigs={}
        self.lock = threading.RLock() 


    def isFile(self):
        return False
    def isUrl(self):
        return False
    def isPG(self):
        return False
    def isMemcache(self):
        return False

    def getLayers(self):
        if not self.isMemcache():
            return self.layers.keys()
        return []
    
    def hasConfig(self, item):
        return self.layer.has_key(item)
        
    def getConfig(self, item):
        sys.stderr.write('Getting config for %s' % (item,))
        return self.layers.get(item)

    def isequal(self, resource):
        if self.resource == arg:
            return True
        return False

    def _getConfig(self, configtype):
        if configtype in self.loadedConfigs:
            return self.loadedConfigs[configtype]
        else:
            if not configtype in supported_configs:
                raise TileCacheException("Configuration include of " \
                                         "type %s not supported" % configtype)
            try:
                module_name, class_name=supported_configs[configtype]
                config_mod=import_module(module_name)
                self.loadedConfigs[configtype]=getattr(config_mod, 
                                                       class_name)
                return self.loadedConfigs[configtype]
            except Exception, e:
                raise TileCacheException("Configuration include of " \
                                         "type %s supported, but import failed" \
                                         " (%s)"
                                         % (configtype, e,))
            
    
    def _load_layer ( self, **objargs):
        
        try:
            type = objargs['type']
        except:
            return None
        
        type = type.replace("Layer", "")
        module = import_module("TileCache.Layers.%s" % type)
               
        if module == None:
            raise TileCacheException("Attempt to load %s failed." % type)
        
        sobject = getattr(module, type)
        return sobject( **objargs)
    
    ###########################################################################
    ##
    ## @brief load method for a config section.
    ##
    ## @param config    ConfigParser::ConfigParser object
    ## @param section   include section list item
    ## @param module    module to load, typically "Layer"
    ## @param objargs   section objects
    ## 
    ## @return section object
    ##
    ###########################################################################
    
    def _loadFromSection (self, config, section, module, **objargs):
        type  = config.get(section, "type")
        for opt in config.options(section):
            if opt not in ["type", "module"]:
                objargs[opt] = config.get(section, opt)
        
        object_module = None
        
        if config.has_option(section, "module"):
            object_module = import_module(config.get(section, "module"))
        else: 
            if module is TileCache.Layer:
                type = type.replace("Layer", "")
                object_module = import_module("TileCache.Layers.%s" % type)
               
            else:
                type = type.replace("Cache", "")
                object_module = import_module("TileCache.Caches.%s" % type)
        if object_module == None:
            raise TileCacheException("Attempt to load %s failed." % type)
        
        section_object = getattr(object_module, type)
        
        if module is TileCache.Layer:
        
            return section_object(section, **objargs)
        else:
            return section_object(**objargs)
    
    def _loadSections (self, config, configs, reload = False, **objargs):
        layers = {}
        #sys.stderr.write( "_loadSections\n")
        for section in config.sections():
            #sys.stderr.write( "_loadSections %s\n" % section)
            ##### include sections #####
            
            if section == "include" and reload == False:
                self._read_include( config, configs, section, reload )
                
            ##### if its not a standard section load the section #####
            
            #sys.stderr.write( "_loadSections %s s_sections %s\n" % (section, [ "cache", "metadata", "tilecache_options", "include" ]))
            if section not in [ "cache", "metadata", "tilecache_options", "include" ]:
                
                layers[section] = self._loadFromSection ( config, section,
                                                               TileCache.Layer,
                                                               cache = self.cache)
        
        self.layers = layers
    
    ###########################################################################
    ##
    ## @brief load method for the included config files.
    ##
    ## @param config     ConfigParser::ConfigParser object
    ## @param section    include section list item
    ## @param objargs    section objects
    ##
    ## 
    ###########################################################################

    def _read_include (self, config, configs, section, reload = False):
        # This should really just load the config type and 
        # the type should have it's own parser, but this is legacy code
        # and I don't want to re-write it at this point.

        #sys.stderr.write("File._read_include\n")
        ##### url? #####

        if config.has_option(section, "urls"):
            urls = config.get(section, "urls")
            
            for url in csv.reader([re.sub(r'\s', '', urls)], delimiter=',', quotechar='"').next():
                
                have = False
                
                ##### test if its a new include ? #####
                
                if reload:
                    for conf in configs:
                        if conf.isUrl() and conf.isequal(url):
                            have = True
                            break
                
                
                if not reload or not have:
                    Url = self._getConfig("urls")
                    mUrl = Url(url, self.cache)
                    configs.append(mUrl)
                    mUrl.read(configs)

        ##### postgres? #####

        if config.has_option(section, "pg"):
            
            pg = config.get(section, "pg")
            
            ##### multiple dsn's seperated by , with "" quotes #####
            
            for dsn in csv.reader([pg], delimiter=',', quotechar='"').next():
                dsndict = {}
                
                have = False
                
                ##### test if its a new include ? #####
                
                if reload:
                    for conf in configs:
                        if conf.isPG() and conf.isequal(dsn):
                            have = True
                            break
                
                if not reload or not have:
                    PG = self._getConfig("pg")
                    mPG = PG(dsn, self.cache)
                    if mPG.conn != None:
                        configs.append(mPG)
                        mPG.read(configs)

        ##### Memcache? #####
        
        if config.has_option(section, "memcache"):
            
            memcache = config.get(section, "memcache")
            sys.stderr.write('Got Memcache Section (%s)\n' % (memcache,))

            ##### Iterate over the entries in the section  #####
            for mcsettings in csv.reader([memcache], delimiter=',', quotechar='"'):
                # Memcache entries should be of the form:
                # memcache="name,Cache_prefix,host1:port1,host2:port2,host3:port3, ..."


                ##### settings is a list #####
                #sys.stderr.write('%s\n' % ','.join(mcsettings))
    
                cache_name=mcsettings.pop(0)
                cache_prefix=mcsettings.pop(0)
                # The remainder are the host/port combinations
                cache_array=mcsettings
                
                
                ##### test if its a new include ? #####
                
                if reload:
                    for conf in configs:
                        if conf.isMemcache() and conf.isequal(cache_name):
                            have = True
                            break
                
                if not reload or not have:
                    Memcache = self._getConfig("memcache")
                    sys.stderr.write('Loading the memcache config and appending to configs\n')
                    mMemcache = Memcache(cache_name, cache_prefix, cache_array, cache=self.cache)
                    configs.append(mMemcache)

        ##### insert new config types here ie: sqlite #####
    
    def read(self, configs, reload = None):
        raise NotImplementedError()
    
    def create (self):
        raise NotImplementedError()
    
    def add (self):
        raise NotImplementedError()
    
    def update (self):
        raise NotImplementedError()

    def delete (self):
        raise NotImplementedError()
    
    def checkchange (self, configs):
        raise NotImplementedError()



