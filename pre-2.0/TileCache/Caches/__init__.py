import os

def caches(path):
    caches = {}
    for filename in sorted(os.listdir(path)):
        if filename.endswith(".py") and not filename.startswith("_"):
            name, ext = os.path.splitext(os.path.basename(filename))
            caches[name] = getattr(__import__('TileCache.Caches.' + name, globals(), locals(), name), name)
    return caches        
        

