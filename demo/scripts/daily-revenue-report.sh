#!/usr/bin/env bash
set -euo pipefail

ASTRO_COMMERCE="${ASTRO_COMMERCE:-astro-commerce}"
DB="${ECOM_DB_PATH:-$HOME/.ecom-sales.db}"

"$ASTRO_COMMERCE" --db "$DB" sync run --channel all --yesterday

sqlite3 "$DB" '
  SELECT channel, printf("$%.2f", SUM(revenue)) AS revenue, SUM(units) AS units
  FROM daily_sales
  WHERE date = date("now", "-1 day")
  GROUP BY channel
  ORDER BY SUM(revenue) DESC;
'
