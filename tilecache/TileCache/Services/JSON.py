from TileCache.Services.TMS import TMS
from TileCache.Service import Request, Capabilities
import simplejson
class JSON(TMS):
    def parse(self, fields, path, host):
        layers = {} 
        for name, layer in self.service.layers.items():
            layers[name] = {'bbox': layer.bbox, 'metadata': layer.metadata,}
        return ("application/json", simplejson.dumps(layers)) 
