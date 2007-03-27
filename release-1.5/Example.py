#!/usr/bin/python

from TileCache.Service import Service, modPythonHandler, cgiHandler
from TileCache.Layer import MapServerLayer, WMSLayer
from TileCache.Cache import DiskCache

myService = Service (
  DiskCache("/www/wms-c/cache"), 
  { 
    "basic"     : MapServerLayer( "basic", "/www/wms-c/basic.map" ),
    "satellite" : MapServerLayer( "satellite", "/www/wms-c/basic.map",
                                extension = "jpeg" ),
    "cascade"   : WMSLayer( "basic", "http://labs.metacarta.com/wms/vmap0?",
                                extension = "jpeg" ),
    "DRG"       : WMSLayer( "DRG", "http://terraservice.net/ogcmap.ashx?",
                                extension = "jpeg"  ),
    "OSM"       : WMSLayer( "roads", 
                    "http://aesis.metacarta.com/cgi-bin/mapserv?FORMAT=png8&" +
                    "map=/home/crschmidt/osm.map&TRANSPARENT=TRUE&",
                    extension = "png"  ),
    "Boston"    : WMSLayer( 
                    "border,water,openspace,roads,buildings,rapid_transit",
                    "http://nyc.freemap.in/cgi-bin/mapserv?" + 
                    "map=/www/freemap.in/boston/map/gmaps.map&" ),
    "hfoot"     : WMSLayer( "hfoot", 
                    "http://beta.sedac.ciesin.columbia.edu/mapserver/wms/hfoot?",
                    levels = 20, extension = "jpeg")
  }
) 

def handler (req):
    return modPythonHandler(req, myService)

if __name__ == '__main__':
    cgiHandler(myService)
