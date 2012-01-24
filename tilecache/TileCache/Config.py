#!/usr/bin/python

# BSD Licensed, Copyright (c) 2006-2010 TileCache Contributors

import urllib2, traceback, sys, os, ConfigParser, csv, time
import TileCache.Layer, TileCache.Layers
import TileCache.Cache, TileCache.Caches

def import_module(name):
    """Helper module to import any module based on a name, and return the module."""
    mod = __import__(name)
    components = name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod
    
    def isFile(self):
        return False
    def isUrl(self):
        return False
    def isPG(self):
        return False
    
###############################################################################
##
## @brief base config class handles file configs
##
###############################################################################

class Config (object):
    __slots__ = ( "resource", "last_mtime", "cache", "metadata" , "layers", "s_sections")
    
    def __init__ (self, resource):
        self.s_sections = [ "cache", "metadata", "tilecache_options", "include" ]
    
    def isequal(self, resource):
        if self.resource == arg:
            return True
        return False
    
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
        #sys.stderr.write( "_loadSections\n")
        for section in config.sections():
            sys.stderr.write( "_loadSections %s\n" % section)
            ##### include sections #####
            
            if section == "include" and reload == False:
                self._read_include( config, configs, section, reload )
                
            ##### if its not a standard section load the section #####
            
            #sys.stderr.write( "_loadSections %s s_sections %s\n" % (section, [ "cache", "metadata", "tilecache_options", "include" ]))
            if section not in [ "cache", "metadata", "tilecache_options", "include" ]:
                self.layers[section] = self._loadFromSection ( config, section,
                                                               TileCache.Layer,
                                                               cache = self.cache)
    
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
    #FIXME this does not work in the parent class for some reason
    def _ddread_include (self, config, configs, section, reload = False):
        sys.stderr.write("File._read_include\n")
        ##### url? #####

        if config.has_option(section, "urls"):
            urls = config.get(section, "urls")
            
            for url in csv.reader([urls], delimiter=',', quotechar='"').next():
                
                have = False
                
                ##### test if its a new include ? #####
                
                if reload:
                    for conf in configs:
                        if conf.isUrl() and conf.isequal(url):
                            have = True
                            break
                
                
                if not reload or not have:
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
                    mPG = PG(dsn, self.cache)
                    configs.append(mPG)
                    mPG.read(configs)
                
                
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



