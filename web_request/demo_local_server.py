from web_request.handlers import wsgi

def run(*args, **kwargs):
    return "text/plain", str(kwargs)

def wsgiApp (environ, start_response):
    return wsgi(run, environ, start_response)


from wsgiref import simple_server
httpd = simple_server.WSGIServer(('',8080), simple_server.WSGIRequestHandler,)
httpd.set_app(wsgiApp)
try:
    print "Listening on port %s" % 8080 
    httpd.serve_forever()
except KeyboardInterrupt:
    print "Shutting down."
