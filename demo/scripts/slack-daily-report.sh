#!/usr/bin/env bash
set -euo pipefail

ASTRO_COMMERCE="${ASTRO_COMMERCE:-astro-commerce}"
DB="${ECOM_DB_PATH:-$HOME/.ecom-sales.db}"

if [[ -z "${SLACK_WEBHOOK_URL:-}" ]]; then
  echo "Set SLACK_WEBHOOK_URL to a Slack incoming webhook URL." >&2
  exit 1
fi

"$ASTRO_COMMERCE" --db "$DB" sync run --channel all --yesterday

REPORT=$(
  sqlite3 "$DB" '
    SELECT "- " || channel || ": $" || printf("%.2f", SUM(revenue)) || " / " || SUM(units) || " units"
    FROM daily_sales
    WHERE date = date("now", "-1 day")
    GROUP BY channel
    ORDER BY SUM(revenue) DESC;
  '
)

export REPORT
python3 - <<'PY'
import json
import os
import urllib.request

payload = json.dumps({
    "text": "*Daily commerce report*\n" + os.environ["REPORT"],
}).encode()
req = urllib.request.Request(
    os.environ["SLACK_WEBHOOK_URL"],
    data=payload,
    headers={"Content-Type": "application/json"},
)
urllib.request.urlopen(req, timeout=15).read()
PY
