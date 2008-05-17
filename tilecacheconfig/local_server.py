from web_request.handlers import wsgi

from tilecacheconfig.Server import run

def run_app(*args, **kwargs):
    return run("/Users/crschmidt/tilecache/tilecache.cfg", *args, **kwargs) 

def wsgiApp (environ, start_response):
    return wsgi(run_app, environ, start_response)


from wsgiref import simple_server
httpd = simple_server.WSGIServer(('',8080), simple_server.WSGIRequestHandler,)
httpd.set_app(wsgiApp)
try:
    print "Listening on port %s" % 8080 
    httpd.serve_forever()
except KeyboardInterrupt:
    print "Shutting down."
