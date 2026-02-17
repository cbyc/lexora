#!/bin/sh
set -e

: "${FEED_API_BASE:=http://localhost:9001}"
: "${MIND_API_BASE:=http://localhost:9002}"

envsubst '${FEED_API_BASE} ${MIND_API_BASE}' \
  < /usr/share/nginx/html/index.html.template \
  > /usr/share/nginx/html/index.html

exec nginx -g 'daemon off;'
