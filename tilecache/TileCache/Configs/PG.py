#!/usr/bin/python

# BSD Licensed, Copyright (c) 2006-2010 TileCache Contributors
from TileCache.Config import Config
try:
    import psycopg2
    import psycopg2.extensions
    import psycopg2.extras

except ImportError:
    Psycopg2 = False;

import sys, select, traceback, csv, time
import TileCache.Cache, TileCache.Caches
import TileCache.Layer, TileCache.Layers
from TileCache.Service import TileCacheException
import threading

###############################################################################
##
## @brief class for the postgres server version
##
###############################################################################

class PGVersion (object):
    __slots__ = ( "major", "minor", "build", "rev" )
    
    def __init__ (self, version):

        split = version.split('.')
        
        self.major = int(split[0])
        self.minor = int(split[1])
        try:
            split2 = split[2].split('.')
            self.build = int(split2[0])
            self.rev = int(split2[1])
        except:
            self.build = int(split[2])
            self.rev = None


###############################################################################
##
## @brief tilecache class for configuration in postgres
##
###############################################################################
            
class PG(Config):
    __slots__ = Config.__slots__ + ( "dsn", "tname", "pgversion", "pool", "conn", "lcur")
    
    def __init__ (self, resource, cache = None):
        #sys.stderr.write( "PG.__init__ %s\n" % resource)
        super(PG,self).__init__(resource, cache)

        ##### multiple vars seperated by " " with '' quotes #####
        
        dsndict = {}
        
        for item in csv.reader([resource], delimiter=' ', quotechar="'").next():
            ldict = csv.reader([item], delimiter='=', quotechar="'").next()
            dsndict[ldict[0]] = ldict[1]
        
        if not dsndict.has_key('database') or dsndict['database'] == None or dsndict['database'] == "":
            self.metadata['warn'] = "error: must have database specified\n"
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
            return None
        
        if not dsndict.has_key('tname') or dsndict['tname'] == None or dsndict['tname'] == "":
            self.metadata['warn'] = "error: must have table name specified\n"
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
            return None
        
        self.dsn = { 'database': dsndict['database'] }
        if dsndict.has_key('host'):
            self.dsn['host'] = dsndict['host']
        if dsndict.has_key('port'):
            self.dsn['port'] = dsndict['port']
        if dsndict.has_key('user'):
            self.dsn['user'] = dsndict['user']
        if dsndict.has_key('password'):
            self.dsn['password'] = dsndict['password']
        
        self.tname = dsndict['tname'];
        self.cache = cache
        self.layers = {}
        self.metadata={}
        
        ##### connect to the server #####

        self._connect()
        
        ##### get the server version #####
        
        self.pgversion = PGVersion(self._get_server_version())
        
        ##### set autocommit mode if atleast pg 9 #####

        if self.pgversion.major >= 9:
            self.conn.set_isolation_level(
                psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        
        ##### setup the listen for config changes #####

        self.start_listen()
        
    def isPG(self):
        return True
    
    ###########################################################################
    ##
    ## @brief method to setup the connection pool to the database
    ## 
    ###########################################################################
    
    def _connect (self):
        
        while True:
            try:
                self.conn = psycopg2.connect(**self.dsn)
                break
            except psycopg2.DatabaseError, e:
                time.sleep(1)
        
        return True
    
    ###########################################################################
    ##
    ## @brief a complete list of config options
    ##
    ## @details
    ## make sure the table is the same order
    ###########################################################################
    
    options = [ 'name', 'type', 'mapfile', 'file', 'url', 'username',
                'password', 'off_layers', 'projection', 'layers', 'bbox',
                'data_extent', 'size', 'resolutions', 'levels', 'extension',
                'srs', 'cache', 'debug', 'description', 'watermarkimage',
                'watermarkopacity', 'extent_type', 'tms_type', 'units',
                'mime_type', 'paletted', 'spherical_mercator', 'metadata',
                'expired', 'metaTile', 'metaSize' , 'metaBuffer' ]
        
    ###########################################################################
    ##
    ## @brief a method to perform a simple sql with a commit
    ##
    ## @param sql   the sql to perform
    ## 
    ###########################################################################
    
    def _simplesql (self, sql, args = None):
        
        try:
            cur = self.conn.cursor()
            if args != None:
                cur.execute(sql, args)
            cur.execute(sql)    
            if self.pgversion.major >= 9:
                self.conn.commit()
            cur.close()
            
        except Exception, E:
            self.metadata['warn'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
            if self.pgversion.major >= 9:
                self.conn.rollback()
                return False
        
        return True
    
    ###########################################################################
    ##
    ## @brief method to create a tilecache postgres config table
    ##
    ###########################################################################
    
    def create_table (self):
        
        sql='''
CREATE TABLE "%s"
    (
        lid                 serial      PRIMARY KEY                     ,
        name                text        UNIQUE NOT NULL                 ,
        type                text        NOT NULL                        ,
        mapfile             text                                        ,
        file                text                                        ,
        url                 text                                        ,
        username            text                                        ,
        password            text                                        ,
        off_layers          text                                        ,
        projection          text                                        ,
        layers              text[]                                      ,
        bbox                numeric[4]  DEFAULT '{ -180, -90, 180, 90 }',
        data_extent         numeric[4]                                  ,
        size                INT[2]      DEFAULT '{ 256, 256 }'          ,
        resolutions         numeric[]                                   ,
        levels              INT         DEFAULT 20                      ,
        extension           text        DEFAULT 'png'                   ,
        srs                 text        DEFAULT 'EPSG:4326'             ,
        debug               BOOLEAN     DEFAULT FALSE                   ,
        description         text                                        ,
        watermarkimage      text                                        ,
        watermarkopacity    numeric                                     ,
        extent_type         text                                        ,   
        tms_type            text                                        ,
        units               text                                        ,
        mime_type           text                                        ,
        paletted            BOOLEAN                                     ,
        spherical_mercator  BOOLEAN                                     ,
        metadata            text                                        ,
        expired             TIMESTAMP                                   ,
        metaTile            BOOLEAN     DEFAULT FALSE                   ,
        metaSize            INT[2]      DEFAULT '{ 5, 5 }'              ,
        metaBuffer          INT[2]      DEFAULT '{10,10 }'              ,
        
        CHECK( type = ANY( ARRAY [ 'ArcXML', 'GDAL', 'Image', 'Mapserver',
                                   'Mapnik', 'WMS' ] ) )                                ,
        CHECK( mapfile      IS NULL OR type = ANY(ARRAY[ 'ArcXML', 'Mapserver' ] ) )    ,
        CHECK( file         IS NULL OR type = ANY(ARRAY[ 'GDAL', 'Image' ] ) )          ,
        CHECK( username     IS NULL OR type = 'WMS' )                                   ,
        CHECK( password     IS NULL OR type = 'WMS' )                                   ,
        CHECK( off_layers   IS NULL OR type = 'ArcXML' )                                ,
        CHECK( projection   IS NULL OR type = 'ArcXML' )
    );
    ''' % self.tname


        self._simplesql (sql)

        self._remove_triggers()
        self._create_trigger_functions()
        self._create_triggers()

    ###########################################################################
    ##
    ## @brief method to get the pg server version
    ##
    ###########################################################################
    
    def _get_server_version(self):
        sql='''
SELECT current_setting('server_version')::text;
    '''
        try:
            cur = self.conn.cursor()
            cur.execute(sql)
            version = cur.fetchone()
            self.conn.rollback()
            cur.close()
            
            return version[0]
        
        except Exception, E:
            self.metadata['warn'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
            return "0.0.0"
        
    ###########################################################################
    ##
    ## @brief method to create the pg trigger functions
    ##
    ###########################################################################
    
    def _create_trigger_functions(self):
        
        ###### test if the server supports a notify payload #####
        
        if self.pgversion.major < 9:
            
            self.metadata['warn'] = "%s\n" % ''' 
warning: server does not support notify payloads,
deletion of layers not supported'''
            
            sql = '''
CREATE OR REPLACE FUNCTION tilecache_config_insert_notify_trigger()
RETURNS trigger AS $$
DECLARE
BEGIN
    EXECUTE 'NOTIFY "%s_insert"';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION tilecache_config_update_notify_trigger()
RETURNS trigger AS $$
DECLARE
BEGIN
    EXECUTE 'NOTIFY "%s_update"';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
''' % ( self.tname, self.tname, self.tname )

        else:
            sql='''
CREATE OR REPLACE FUNCTION tilecache_config_insert_notify_trigger()
RETURNS trigger AS $$
DECLARE
BEGIN
    EXECUTE 'NOTIFY "%s_insert" , \'\'' || NEW.name || '\'\'';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION tilecache_config_delete_notify_trigger()
RETURNS trigger AS $$
DECLARE
BEGIN
    EXECUTE 'NOTIFY "%s_delete" , \'\'' || OLD.name || '\'\'';
    RETURN OLD;
END;

$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION tilecache_config_update_notify_trigger()
RETURNS trigger AS $$
DECLARE
BEGIN
    EXECUTE 'NOTIFY "%s_update" , \'\'' || NEW.name || '\'\'';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
''' % ( self.tname, self.tname, self.tname, self.tname )

        self._simplesql (sql)
        
    ###########################################################################
    ##
    ## @brief method to create the pg triggers
    ##
    ###########################################################################
    
    def _create_triggers(self):
        
        ###### test if the server supports a notify payload #####
        
        if self.pgversion.major < 9:
        
            sql='''
CREATE TRIGGER "%s_tilecache_config_insert_notify_trigger"
AFTER insert
ON %s
FOR EACH ROW
    EXECUTE PROCEDURE tilecache_config_insert_notify_trigger();

CREATE TRIGGER "%s_tilecache_config_update_notify_trigger"
AFTER update
ON %s
FOR EACH ROW
    EXECUTE PROCEDURE tilecache_config_update_notify_trigger();

''' % ( self.tname, self.tname, self.tname, self.tname )
        
        else:
        
            sql='''
CREATE TRIGGER "%s_tilecache_config_insert_notify_trigger"
AFTER insert
ON %s
FOR EACH ROW
    EXECUTE PROCEDURE tilecache_config_insert_notify_trigger();

CREATE TRIGGER "%s_tilecache_config_delete_notify_trigger"
AFTER delete
ON %s
FOR EACH ROW
    EXECUTE PROCEDURE tilecache_config_delete_notify_trigger();

CREATE TRIGGER "%s_tilecache_config_update_notify_trigger"
AFTER update
ON %s
FOR EACH ROW
    EXECUTE PROCEDURE tilecache_config_update_notify_trigger();

''' % ( self.tname, self.tname, self.tname, self.tname, self.tname, self.tname )

        self._simplesql (sql)
        
    ###########################################################################
    ##
    ## @brief method to remove the pg triggers
    ##
    ###########################################################################
    
    def _remove_triggers(self):
        
        ###### test if the server supports a notify payload #####
        
        if self.pgversion.major < 9:
        
            sql='''
DROP TRIGGER IF EXISTS "%s_tilecache_config_insert_notify_trigger"
ON %s;

DROP TRIGGER IF EXISTS "%s_tilecache_config_update_notify_trigger"
ON %s;

''' % ( self.tname, self.tname, self.tname, self.tname )
        
        else:
        
            sql='''
DROP TRIGGER IF EXISTS "%s_tilecache_config_insert_notify_trigger"
ON %s;

DROP TRIGGER IF EXISTS "%s_tilecache_config_delete_notify_trigger"
ON %s;

DROP TRIGGER IF EXISTS "%s_tilecache_config_update_notify_trigger"
ON %s;

''' % ( self.tname, self.tname, self.tname, self.tname, self.tname, self.tname )

        self._simplesql (sql)
            
    ###########################################################################
    ##
    ## @brief method to start listens
    ##
    ###########################################################################
    
    def start_listen (self):
        

                
        sql = '''
LISTEN "%s_insert";
LISTEN "%s_delete";
LISTEN "%s_update";
''' % ( self.tname, self.tname, self.tname )
        
        try:
            
            self.lcur = self.conn.cursor()
            self.lcur.execute(sql)
            if self.pgversion.major < 9:
                self.conn.commit();
            
        except Exception, E:
            self.metadata['warn'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
            if self.pgversion.major < 9:
               self.conn.rollback()
    
    ###########################################################################
    ##
    ## @brief method to start listens
    ##
    ###########################################################################
    
    def stop_listen (self):
        
        try:
            cur.close()
            
        except Exception, E:
            self.metadata['warn'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
        
        sql = '''
UNLISTEN %s_insert;
UNLISTEN %s_delete;
UNLISTEN %s_update;
''' % ( self.tname, self.tname, self.tname )

        self._simplesql (sql)
        
    ###########################################################################
    ##
    ## @brief method to poll the notifys just once
    ##
    ###########################################################################
    
    ###########################################################################
    ##
    ## @brief method to read the config from the pg db
    ##
    ###########################################################################
    
    def read(self, configs, reload = None, name = None):
        
        #sys.stderr.write( "PG.read\n" )
        if name == None:
            sql = '''
SELECT
        lid                 ,
        name                ,
        type                ,
        mapfile             ,
        file                ,
        url                 ,
        username            ,
        password            ,
        off_layers          ,
        projection          ,
        layers              ,
        bbox                ,
        data_extent         ,
        size                ,
        resolutions         ,
        levels              ,
        extension           ,
        srs                 ,
        debug               ,
        description         ,
        watermarkimage      ,
        watermarkopacity    ,
        extent_type         ,
        tms_type            ,
        units               ,
        mime_type           ,
        paletted            ,
        spherical_mercator  ,
        metadata            ,
        to_char(expired, 'YYYY-MM-DDT' ) ||  to_char(expired, 'HH24:MI:SSZ') as expired,
        metaTile            ,
        metaSize            ,
        metaBuffer          
FROM %s;
''' % self.tname
        else:
            sql = '''
SELECT
        lid                 ,
        name                ,
        type                ,
        mapfile             ,
        file                ,
        url                 ,
        username            ,
        password            ,
        off_layers          ,
        projection          ,
        layers              ,
        bbox                ,
        data_extent         ,
        size                ,
        resolutions         ,
        levels              ,
        extension           ,
        srs                 ,
        debug               ,
        description         ,
        watermarkimage      ,
        watermarkopacity    ,
        extent_type         ,
        tms_type            ,
        units               ,
        mime_type           ,
        paletted            ,
        spherical_mercator  ,
        metadata            ,
        to_char(expired, 'YYYY-MM-DDT' ) ||  to_char(expired, 'HH24:MI:SSZ') as expired,
        metaTile            ,
        metaSize            ,
        metaBuffer          
FROM %s
WHERE name = '%s';
''' % ( self.tname, name )
        
        try:

            cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql)
            
            returnlist = []
            while True:
                row = cur.fetchone()
                if row == None:
                    break;
                
                rowdict = self._convert_row(row)
                rowdict['cache'] = self.cache
                self.layers[ rowdict['name'] ] = self._load_layer ( **rowdict )
            if self.pgversion.major < 9:
                self.conn.commit()
            cur.close()
            
        except Exception, E:
            self.metadata['warn'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
        
        if reload == None:
            self.start_listen()
        
        return returnlist
    
    ###########################################################################
    ##
    ## @brief method to convert a python list to a string for a Tilcache Layer
    ##        dictionary
    ##
    ###########################################################################
    
    def _list2str(self, mylist):
        string = ""
        needcomma = False
        for item in mylist:
            if needcomma:
                string += ", " + str(item)
            else:
                string += str(item)
                needcomma = True
        
        return string

    ###########################################################################
    ##
    ## @brief method to convert a row to Tilcache Layer dictionary
    ##
    ###########################################################################
    
    def _convert_row (self, row):
        
        config = {}
        
        for key in row:
            if row[key] == None:
                continue
                
            if not isinstance(row[key], list):
                config[key] = row[key]
                
            else:
                config[key] = self._list2str( row[key] )
        
        return config
    
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
            
            sql = '''
DELETE
FROM "%s"
WHERE name = '%s';
''' % ( self.tname )
            
            if self._simplesql (sql, name):
                return True
            
        return False
    
    ###########################################################################
    ##
    ## @brief method to update a layer in the config.
    ##
    ## @param objargs   the settings to update
    ##
    ## @return True on success, False on failure
    ## @details
    ## objargs must contain a name key. all other keys are replaced,
    ##
    ###########################################################################
    
    def update (self, objargs ):
        
        if not objargs.has_key('name'):
            return False
        
        sublist = []
        sql = '''
UPDATE "%s"
SET (
''' % self.tname
        
        #FIXME need quotes for strings, and build arrays when nessasary
        # ppossibly detect this from the schema?
        needcomma = False
        for option in objargs:
            if option != 'name':
                if needcomma:
                    sql = sql + ','
                sql = sql + '''
        "%s" = %s '''
                sublist.extend( [ option, objargs[option] ] )
        sql = sql + '''
    );
'''
        
        try:
            
            cur = self.conn.cursor()
            cur.execute(sql, sublist)
            if self.pgversion.major < 9:
                  self.conn.commit()
            cur.close()

        except Exception, E:
            self.metadata['exception'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
            return False
        
        return True

    ###########################################################################
    ##
    ## @brief method to add a layer to the config.
    ##
    ## @param objargs   the settings to add
    ##
    ## @return True on success, False on failure
    ## @details
    ## objargs must contain a name key. all other keys are added,
    ##
    ##
    ###########################################################################
        
    def add (self, objargs ):
        
        if not objargs.has_key('name'):
            return False

        sublist = []
        sql = '''
INSERT INTO "%s"
    (
''' % self.tname

        needcomma = False
        for option in objargs:
            if needcomma:
                sql = sql + ','
            sql = sql + '''
        "%s"'''
            sublist.append( option )
        sql = sql + '''
    )
VALUES (
'''
        #FIXME need quotes for strings, and build arrays when nessasary 
        # ppossibly detect this from the schema?
        needcomma = False
        for option in objargs:
            if needcomma:
                sql = sql + ','
            sql = sql + '''
        %s'''
            sublist.append( objargs[option] )
        sql = sql + '''
    );'
'''
    
        try:
            cur = self.conn.cursor()
            cur.execute(sql, sublist)
            if self.pgversion.major < 9:
                  self.conn.commit()
            cur.close()
            
        except Exception, E:
            self.metadata['warn'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
            return False
        
        return True
   
    ###########################################################################
    ##
    ## @brief method to reconnect to the db when its the connection drops
    ##
    ## @return True if succcessfull, False if error.
    ##
    ###########################################################################

    def _reconnect (self):

        try:
            self.conn = psycopg2.connect(**self.dsn)

            ##### set autocommit mode if atleast pg 9 #####

            if self.pgversion.major >= 9:
               self.conn.set_isolation_level(
                  psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

            ##### setup the listen for config changes #####

            self.start_listen()
                    
            ##### if the connection errors out return false #####

        except psycopg2.DatabaseError, e:
            return False

        return True

    ###########################################################################
    ##
    ## @brief method to check a config for change and reload it
    ##
    ## @return True if changed, False if unchanged or error.
    ##
    ###########################################################################
    
    def checkchange (self, configs):
        #FIXME test if the connection has dropped
        try:

            
            ##### older versions of Psycopg had the fileno method in the cursor #####
            
            if hasattr(self.conn,"fileno"):
                fd = self.conn
            else:
                fd = self.lcur
 
            if select.select([fd],[],[],0)==([],[],[]):
                pass
            else:

                ##### do we need to reconnect? #####

                if self.conn.closed or not hasattr(self.conn, 'poll'):

                    ##### if reconnect reread the config #####

                    if self._reconnect():
                        self.read(None, True)
                        return True

                    ##### if we cant reconnect return false like theres no changes #####

                    else:
                        return False

                ##### we didnt loose connection so check for the notifies #####

                self.conn.poll()
                while self.conn.notifies:
                    notify = self.conn.notifies.pop()
                    
                    ##### pg server not support notify payload? #####
                    
                    if self.pgversion.major < 9:
                        if notify.channel == "%s_insert" % self.tname:
                            self.read(None, True)
                            
                        elif notify.channel == "%s_update" % self.tname:
                            self.read(None, True)
                            
                        else:
                            sys.stderr.write( "Got Unhandled NOTIFY: %s %s %s\n",
                                              notify.pid, notify.channel )
                            
                    ##### has payload #####
                    
                    else:
                    
                        if notify.channel == "%s_insert" % self.tname:
                            self.read(None, True, name = notify.payload)
                        
                        elif notify.channel == "%s_update" % self.tname:
                            self.read(None, True, name = notify.payload)
                        
                        elif notify.channel == "%s_delete" % self.tname:
                            try:
                                del self.layers[notify.payload]
                            except:
                                pass
                        
                        else:
                            sys.stderr.write( "Got Unhandled NOTIFY: %s %s %s\n",
                                              notify.pid, notify.channel,
                                              notify.payload )
                
                return True            

        except Exception, E:
            self.metadata['warn'] = E
            self.metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
        
        return False

