#!/bin/sh
set -eu
umask 077
# The official entrypoint updates its keystore. Keep config writable while
# keeping the container root filesystem read-only.
cp -R /usr/share/elasticsearch/config/. /work-config/
cp /settings/elasticsearch.yml /work-config/elasticsearch.yml
