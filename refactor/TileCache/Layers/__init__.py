import os

def layers():
    layers = {}
    for filename in sorted(os.listdir(os.path.join(".", "TileCache", "Layers"))):
        if filename.endswith(".py") and not filename.startswith("_"):
            name, ext = os.path.splitext(os.path.basename(filename))
            layers[name] = getattr(__import__('TileCache.Layers.' + name, globals(), locals(), name), name)
    return layers        
        
