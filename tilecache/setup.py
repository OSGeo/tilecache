#!/usr/bin/env python

try:
    from setuptools import setup
except:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

readme = file('docs/README.txt','rb').read()

classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: GIS',
]

setup(name='TileCache',
      version='2.0',
      description='a web map tile caching system',
      author='MetaCarta Labs',
      author_email='tilecache@openlayers.org',
      url='http://tilecache.org/',
      long_description=readme,
      packages=['TileCache', 'TileCache.Caches', 'TileCache.Services', 'TileCache.Layers'],
      scripts=['tilecache.cgi', 'tilecache.fcgi',
               'tilecache_seed.py',
               'tilecache_clean.py', 'tilecache_http_server.py'],
      data_files=[('/etc', ['tilecache.cfg'])],
      zip_safe=False,
      test_suite = 'tests.run_doc_tests',
      license="BSD"
     )
