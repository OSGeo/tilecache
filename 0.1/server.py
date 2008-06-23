from web_request.handlers import wsgi, mod_python

from tilecacheconfig.Server import run

def run_app(*args, **kwargs):
    return run("config.cfg", *args, **kwargs) 

def wsgiApp (environ, start_response):
    return wsgi(run_app, environ, start_response)

def handler(apache_request):
    options = apache_request.get_options() 
    config = options.get("ConfigFile", "/etc/tilecacheconfig.cfg")
    def run_mod_python(*args, **kwargs):
         return run(config, *args, **kwargs)
    return mod_python(run_mod_python, apache_request)   

if __name__ == "__main__":

    from wsgiref import simple_server
    httpd = simple_server.WSGIServer(('',8080), simple_server.WSGIRequestHandler,)
    httpd.set_app(wsgiApp)
    try:
        print "Listening on port %s" % 8080 
        httpd.serve_forever()
    except KeyboardInterrupt:
        print "Shutting down."
