#!/usr/bin/python
from TileCache.Service import wsgiApp
from optparse import OptionParser

def run(port=8080, config=None):
    if config:
        TileCache.Service.cfgfiles += config  
    from wsgiref import simple_server
    httpd = simple_server.WSGIServer(('',port), simple_server.WSGIRequestHandler,)
    httpd.set_app(wsgiApp)
    try:
        httpd.serve_forever()
        print "Listening on port %s" % port
    except KeyboardInterrupt:
        print "Shutting down."

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-p", "--port", help="port to run webserver on. Default is 8080", dest="port", action='store', type="int", default=8080)
    parser.add_option("-c", "--conf", help="config file to use.", dest="config")
    (options, args) = parser.parse_args()
    run(options.port, options.config)
