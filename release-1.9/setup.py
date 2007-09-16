#!/usr/bin/env python

from distutils.core import setup

setup(name='TileCache',
      version='1.9',
      description='a web map tile caching system',
      author='MetaCarta Labs',
      author_email='labs+tilecache@metacarta.com',
      url='http://tilecache.org/',
      packages=['TileCache'],
      scripts=['tilecache.cgi', 'tilecache.fcgi',
               'tilecache_seed.py',
               'tilecache_clean.py', 'tilecache_http_server.py'],
      data_files=[('/etc', ['tilecache.cfg'])]
     )
