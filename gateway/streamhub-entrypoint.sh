#!/bin/sh
set -eu

base_config=/etc/nginx/nginx.base.conf
runtime_config=/etc/nginx/nginx.conf
app_version=${APP_VERSION:-dev}

case "$app_version" in
    *[!A-Za-z0-9._-]*)
        echo "APP_VERSION contains unsupported characters" >&2
        exit 2
        ;;
esac

if [ "${NGINX_STATIC_UPSTREAMS:-false}" = "true" ]; then
    sed \
        -e '/resolver 127\.0\.0\.11 ipv6=off/d' \
        -e 's/ resolve;/;/' \
        -e "s/__APP_VERSION__/$app_version/g" \
        "$base_config" > "$runtime_config"
else
    sed -e "s/__APP_VERSION__/$app_version/g" \
        "$base_config" > "$runtime_config"
fi

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec /docker-entrypoint.sh nginx -g 'daemon off;'
