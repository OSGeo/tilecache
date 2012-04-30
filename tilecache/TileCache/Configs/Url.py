#!/usr/bin/python

# BSD Licensed, Copyright (c) 2006-2010 TileCache Contributors
from TileCache.Config import Config
import urllib2, traceback, sys, os, ConfigParser, csv, time
import TileCache.Cache, TileCache.Caches
import TileCache.Layer, TileCache.Layers
from TileCache.Service import TileCacheException
from TileCache.Configs.PG import PG
import re
import threading

class Url(Config):
    __slots__ = Config.__slots__
    
    def __init__ (self, resource, cache = None):
        #sys.stderr.write( "Url.__init__ %s\n" % resource)
        self.resource = resource
        self.cache = cache
        self.layers = {}
        self.metadata={}
    
        self.lock = threading.RLock()

    def isUrl(self):
        return True
    
    ###########################################################################
    ##
    ## @brief load method for the included config files.
    ##
    ## @param config    ConfigParser::ConfigParser object
    ## @param configs   list of config objects to add new configs to
    ## @param section   ConfigParser include section
    ## @param reload    
    ##
    ## 
    ###########################################################################
    
    def _read_include (self, config, configs, section, reload = False):
        #sys.stderr.write("URL._read_include\n")
        
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
                    #sys.stderr.write("File.read_include %s\n" % "goot")
                    mUrl = Url(url, self.cache)
                    #sys.stderr.write("File.read_include %s\n" % mUrl.resource)
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
    ## @param url    config url to parse
    ##
    ###########################################################################
    
    def read(self, configs, reload = False):
        #sys.stderr.write("url.read\n")
        self.cache = None
        self.metadata = {}
        
        config = None
        try:
            config = ConfigParser.ConfigParser()
            fp = urllib2.urlopen( self.resource )
            headers = dict(fp.info())
            config.readfp(fp)
            fp.close()
            self.layers = {}

            self._loadSections (config, configs, reload, cache = self.cache)
            
            ##### set last_mtime #####
            os.environ['TZ'] = 'UTC'
            time.tzset()
            #FIXME fixed format is probably wrong
            mytime = time.strptime( headers['last-modified'],
                                    "%a, %d %b %Y %H:%M:%S %Z" )
            self.last_mtime = time.mktime(mytime)
        
        except Exception, E:
            self.metadata['exception'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
    
    ###########################################################################
    ##
    ## @brief method to check a config for change and reload it
    ##
    ## @return True if changed, False if unchanged or error.
    ##
    ###########################################################################
    
    def checkchange (self, configs):
        
        try:
            urllib2.Request(self.resource)
            request.get_method = lambda : 'HEAD'
            response = urllib2.urlopen(request)
            headers = dict(response.info())
            
            os.environ['TZ'] = 'UTC'
            time.tzset()
            #FIXME fixed format is probably wrong
            mytime = time.strptime( headers['last-modified'],
                                    "%a, %d %b %Y %H:%M:%S %Z" )
            mtime = time.mktime(mytime)
        
            if self.last_mtime < mtime:
                
                self.read(file, configs, True)
                sys.stderr.write( "Config file %s has changed, reloading\n" %
                                  self.resource )
                self.last_mtime = mtime
                return True
        except:
            pass
        
        return False

