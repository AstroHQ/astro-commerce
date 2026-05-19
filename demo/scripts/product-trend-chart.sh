#!/usr/bin/env bash
set -euo pipefail

ASTRO_COMMERCE="${ASTRO_COMMERCE:-astro-commerce}"
PRODUCT_MATCH="${PRODUCT_MATCH:-luna}"
CHANNEL="${CHANNEL:-shopify}"
OUT="${OUT:-product-trend-30d.png}"

"$ASTRO_COMMERCE" "$CHANNEL" sales --days 30 --match "$PRODUCT_MATCH" --group day --output csv \
  | "$ASTRO_COMMERCE" chart \
      --title "$PRODUCT_MATCH $CHANNEL revenue - last 30 days" \
      --type line \
      -o "$OUT"

echo "Wrote $OUT"
