# BSD Licensed, Copyright (c) 2006-2007 MetaCarta, Inc.

from TileCache.Layer import MetaLayer
from TileCache.Service import TileCacheException

import urllib
import xml.dom.minidom as m

class ArcXML(MetaLayer):
    def __init__ (self, name, url = None, off_layers = "", **kwargs):
        MetaLayer.__init__(self, name, **kwargs) 
        self.url = url
        self.off_layers = off_layers

    def renderTile(self, tile):
        layers = []
        off_layers = []
        for id in self.layers.split(","):
            if id.strip():
                layers.append('<LAYERDEF id="%s" visible="true" />' % id)
        for id in self.off_layers.split(","):
            if id.strip():
                off_layers.append('<LAYERDEF id="%s" visible="false" />' % id)
        bbox = tile.bounds()
        xml = """<?xml version="1.0" encoding="UTF-8" ?>
<ARCXML version="1.1">
<REQUEST>
<GET_IMAGE>
<PROPERTIES>
<ENVELOPE minx="%s" miny="%s" maxx="%s" maxy="%s" />
<IMAGESIZE height="%s" width="%s" />
<LAYERLIST >
%s
%s
</LAYERLIST>
</PROPERTIES>
</GET_IMAGE>
</REQUEST>
</ARCXML>""" % (bbox[0], bbox[1], bbox[2], bbox[3], tile.size()[0], tile.size()[1], "\n".join(layers), "\n".join(off_layers))
        try:
            xmldata = urllib.urlopen(self.url, xml).read()
        except Exception, E:
            raise TileCacheException("Error fetching URL. Exception was: %s\n Input XML:\n %s " % (E, xml))
            
        try:
            doc = m.parseString(xmldata)
            imgURL = doc.getElementsByTagName("OUTPUT")[0].attributes['url'].value
        except Exception, E:
            raise TileCacheException("Error fetching URL. Exception was: %s\n Output XML: \n%s\n\nInput XML:\n %s " % (E, xmldata, xml))
        tile.data = urllib.urlopen(imgURL).read()
        return tile.data 
