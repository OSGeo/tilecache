#!/usr/bin/python
from TileCache.Service import wsgiApp
from optparse import OptionParser

def run(port=8080, config=None):
    from wsgiref import simple_server
    httpd = simple_server.WSGIServer(('',port), simple_server.WSGIRequestHandler,)
    httpd.set_app(wsgiApp)
    try:
        print "Listening on port %s" % port
        httpd.serve_forever()
    except KeyboardInterrupt:
        print "Shutting down."

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-p", "--port", help="port to run webserver on. Default is 8080", dest="port", action='store', type="int", default=8080)
    (options, args) = parser.parse_args()
    run(options.port)
