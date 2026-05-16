#!/bin/sh
set -eu

escape_json() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

PUBLIC_SITE_URL_ESCAPED="$(escape_json "${CLIENT_PORTAL_PUBLIC_SITE_URL:-}")"
GOOGLE_TAG_ID_ESCAPED="$(escape_json "${CLIENT_PORTAL_GOOGLE_TAG_ID:-}")"
YANDEX_METRIKA_ID_ESCAPED="$(escape_json "${CLIENT_PORTAL_YANDEX_METRIKA_ID:-}")"

cat > /usr/share/nginx/html/assets/runtime-config.js <<EOF
window.__REPIRECRM_CLIENT_CONFIG__ = {
  publicSiteUrl: "${PUBLIC_SITE_URL_ESCAPED}",
  googleTagId: "${GOOGLE_TAG_ID_ESCAPED}",
  yandexMetrikaId: "${YANDEX_METRIKA_ID_ESCAPED}"
};
EOF
