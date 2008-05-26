from TileCache.Services.TMS import TMS
from TileCache.Service import Request, Capabilities
import simplejson
class JSON(TMS):
    def parse(self, fields, path, host):
        layers = {} 
        for name, layer in self.service.layers.items():
            layers[name] = {'bbox': layer.bbox, 'metadata': layer.metadata,}
        
        obj = {'layers': layers}
        data = simplejson.dumps(obj)
        if 'callback' in fields:
            data = "%s(%s)" % (fields['callback'], data)
        return ("application/json", data) 
