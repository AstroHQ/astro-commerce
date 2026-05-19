#!/usr/bin/env bash
set -euo pipefail

ASTRO_COMMERCE="${ASTRO_COMMERCE:-astro-commerce}"
DB="${ECOM_DB_PATH:-$HOME/.ecom-sales.db}"
CHANNEL="${CHANNEL:-stripe}"
OUT="${OUT:-$CHANNEL-yesterday.json}"

"$ASTRO_COMMERCE" "$CHANNEL" sales --yesterday --output records > "$OUT"
python3 -m json.tool "$OUT" | head -40
"$ASTRO_COMMERCE" --db "$DB" sync ingest < "$OUT"
