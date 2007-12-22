#!/usr/bin/env python
# BSD Licensed, Copyright (c) 2006-2007 MetaCarta, Inc.

import sys, urllib, urllib2, time, os, math
import httplib

# setting this to True will exchange more useful error messages
# for privacy, hiding URLs and error messages.
HIDE_ALL = False 

class WMS (object):
    fields = ("bbox", "srs", "width", "height", "format", "layers", "styles")
    defaultParams = {'version': '1.1.1', 'request': 'GetMap', 'service': 'WMS'}
    __slots__ = ("base", "params", "client", "data", "response")

    def __init__ (self, base, params):
        self.base    = base
        if self.base[-1] not in "?&":
            if "?" in self.base:
                self.base += "&"
            else:
                self.base += "?"

        self.params  = {}
        self.client  = urllib2.build_opener()
        for key, val in self.defaultParams.items():
            if self.base.lower().rfind("%s=" % key.lower()) == -1:
                self.params[key] = val
        for key in self.fields:
            if params.has_key(key):
                self.params[key] = params[key]
            elif self.base.lower().rfind("%s=" % key.lower()) == -1:
                self.params[key] = ""

    def url (self):
        return self.base + urllib.urlencode(self.params)
    
    def fetch (self):
        urlrequest = urllib2.Request(self.url())
        # urlrequest.add_header("User-Agent",
        #    "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1)" )
        response = None
        while response is None:
            try:
                response = self.client.open(urlrequest)
                data = response.read()
                # check to make sure that we have an image...
                msg = response.info()
                if msg.has_key("Content-Type"):
                    ctype = msg['Content-Type']
                    if ctype[:5].lower() != 'image':
                        if HIDE_ALL:
                            raise Exception("Did not get image data back. (Adjust HIDE_ALL for more detail.)")
                        else:
                            raise Exception("Did not get image data back. \nURL: %s\nContent-Type Header: %s\nResponse: \n%s" % (self.url(), ctype, data))
            except httplib.BadStatusLine:
                response = None # try again
        return data, response

    def setBBox (self, box):
        self.params["bbox"] = ",".join(map(str, box))

def seed (svc, base, layer, levels = (0, 5), bbox = None):
    from Layer import Tile

    if not bbox: bbox = layer.bbox

    start = time.time()
    total = 0
    
    for z in range(*levels):
        bottomleft = layer.getClosestCell(z, bbox[0:2])
        topright   = layer.getClosestCell(z, bbox[2:4])
        print >>sys.stderr, "###### %s, %s" % (bottomleft, topright)
        zcount = 0 
        metaSize = layer.getMetaSize(z)
        ztiles = int(math.ceil(float(topright[1] - bottomleft[1]) / metaSize[0]) * math.ceil(float(topright[0] - bottomleft[0]) / metaSize[1])) 
        for y in range(bottomleft[1], topright[1], metaSize[1]):
            for x in range(bottomleft[0], topright[0], metaSize[0]):
                tileStart = time.time()
                tile = Tile(layer,x,y,z)
                bounds = tile.bounds()
                svc.renderTile(tile)
                total += 1
                zcount += 1
                box = "(%.4f %.4f %.4f %.4f)" % bounds
                print "%02d (%06d, %06d) = %s [%.4fs : %.3f/s] %s/%s" \
                     % (z,x,y, box, time.time() - tileStart, total / (time.time() - start + .0001), zcount, ztiles)

def main ():
    from Service import Service, cfgfiles
    from Layer import Layer
    base  = sys.argv[1]
    svc = Service.load(*cfgfiles)
    layer = svc.layers[sys.argv[2]]
    if len(sys.argv) == 5:
        seed(svc, base, layer, map(int, sys.argv[3:]))
    elif len(sys.argv) == 6:
        seed(svc, base, layer, map(int, sys.argv[3:5]), map(float, sys.argv[5].split(",")))
    else:
        for line in sys.stdin.readlines():
            lat, lon, delta = map(float, line.split(","))
            bbox = (lon - delta, lat - delta, lon + delta, lat + delta)
            print "===> %s <===" % (bbox,)
            seed(svc, base, layer, (5, 17), bbox)

if __name__ == '__main__':
    main()
