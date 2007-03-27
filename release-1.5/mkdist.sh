#!/bin/sh

VERSION=$1

DIR="tilecache-$VERSION"

rm -rf $DIR 
rm -rf $DIR.tar.gz 
mkdir $DIR
cp README $DIR
cp CHANGELOG $DIR
cp CONTRIBUTORS $DIR
cp LICENSE $DIR
cp HACKING $DIR
cp -r TileCache $DIR
cp tilecache.cfg $DIR
cp tilecache.cgi $DIR
cp tilecache.fcgi $DIR
cp tilecache_http_server.py $DIR
cp index.html $DIR/index.html
find $DIR -name .svn | xargs rm -rf
find $DIR -name *.pyc | xargs rm -rf
rm -rf $DIR/TileCache/Swarm.py
rm -rf $DIR/TileCache/Peer
tar -cvzf $DIR.tar.gz $DIR
zip -r $DIR.zip $DIR
