#!/usr/bin/python
from TileCache.Service import wsgiApp

if __name__ == '__main__':
    from wsgiref import simple_server
    print "Listening on port 8080"
    httpd = simple_server.WSGIServer(('',8080), simple_server.WSGIRequestHandler,)
    httpd.set_app(wsgiApp)
    httpd.serve_forever()
