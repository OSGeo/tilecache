#!/usr/bin/env python

from web_request.handlers import cgi

def run(*args, **kwargs):
    return "text/plain", str(kwargs)

cgi(run)    
