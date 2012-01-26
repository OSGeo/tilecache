#!/usr/bin/python

# BSD Licensed, Copyright (c) 2006-2010 TileCache Contributors
from TileCache.Config import Config
import traceback, sys, os, ConfigParser, csv
import TileCache.Cache, TileCache.Caches
import TileCache.Layer, TileCache.Layers
from TileCache.Service import TileCacheException
from TileCache.Configs.Url import Url
from TileCache.Configs.PG import PG
import re

###############################################################################
##
## @brief base config class handles file configs
##
###############################################################################

class File (Config):
    __slots__ = Config.__slots__
    
    def __init__ (self, resource, cache = None):
        
        self.resource = resource
        self.cache = cache
        #sys.stderr.write( "File.__init__ %s\n" % resource)
        self.layers = {}
        self.metadata={}

        try:
            os.stat(self.resource)
        except:
            self.resource = None

    def isFile(self):
        return True
    
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
                    if mPG.conn != None:
                        configs.append(mPG)
                        mPG.read(configs)
                
                
        ##### insert new config types here ie: sqlite #####
    
    ###########################################################################
    ##
    ## @brief method to parse the config.
    ##
    ## @param file    config file to parse
    ##
    ###########################################################################
    
    def read(self, configs, reload = False):
        #sys.stderr.write("File.read\n")
        self.cache = None
        self.metadata = {}
        self.layers = {}
        
        ##### set last_mtime #####
        
        try:
            mtime = os.stat(self.resource)[8]
            self.last_mtime = mtime
        except Exception, E:
            self.metadata['warn'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
            
            return None        
        
        config = None
        try:
            config = ConfigParser.ConfigParser()
            config.read(self.resource)
            
            if reload == False:
                if config.has_section("metadata"):
                    for key in config.options("metadata"):
                        self.metadata[key] = config.get("metadata", key)
                
                if config.has_section("tilecache_options"):
                    if 'path' in config.options("tilecache_options"): 
                        for path in config.get("tilecache_options", "path").split(","):
                            sys.path.insert(0, path)
                
                self.cache = self._loadFromSection(config, "cache", TileCache.Cache)
            
            self._loadSections (config, configs, reload, cache = self.cache)
            
        except Exception, E:
            self.metadata['exception'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
    
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
            
            try:
                config = ConfigParser.ConfigParser()
                config.read(self.resource)
                
                if config.has_section(name):
                    remove_section(name)
                
                    config.write(self.resource)
                    return True
            except:
                raise Exception("Delete failed.\n".join(traceback.format_tb(sys.exc_traceback)))
        
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
    
    def update (self, objargs ):
        
        if objargs.has_key('name'):
            try:
                config = ConfigParser.ConfigParser()
                config.read(self.resource)
                
                if config.has_section(name):
                    options = config.options(name)
                
                    config.set(name, option, objargs[option])
                        
                    config.write(self.resource)
                    return True
            except:
                raise Exception("Update failed.\n".join(traceback.format_tb(sys.exc_traceback)))
        
        return False

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
        
    def add (self, objargs ):
        
        if objargs.has_key('name'):
            name = objargs[name]
            try:
                config = ConfigParser.ConfigParser()
                config.read(self.resource)
                
                if config.has_section(name):
                    remove_section(name)
                    
                config.add_section(name)
                for option in objargs:
                    if option != 'name':
                        config.set(name, option, objargs[option])
                
                config.write(self.resource)
                return True
            except:
                raise Exception("Add failed.\n".join(traceback.format_tb(sys.exc_traceback)))
        return False
    
    ###########################################################################
    ##
    ## @brief method to check a config for change and reload it
    ##
    ## @return True if changed, False if unchanged or error.
    ##
    ###########################################################################
    
    def checkchange (self, configs):
        
        try:
            mtime = os.stat(self.resource)[8]
        
            if self.last_mtime < mtime:
                self.read(file, True)
                #sys.stderr.write( "Config file %s has changed, reloading\n" %
                #                  self.resource )
                self.read(self.file, configs, reload = True)
                self.last_mtime = mtime
                return True
        
        except:
            pass
        
        return False
    
