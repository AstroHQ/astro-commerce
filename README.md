# Astro Commerce

Astro Commerce is a Codex/OpenClaw skill and Python CLI for pulling, syncing, charting, and inspecting commerce data across Astropad sales channels.

It supports:

- Shopify sales and inventory
- Amazon Seller Central sales and inventory through SP-API
- Stripe sales
- App Store Connect sales
- FastSpring sales
- SQLite sync for unified reporting
- CSV/table/JSON/records output
- Demo-safe masked output
- Inventory alert calculations

## Quick Start

Clone the repo and install Python dependencies:

```bash
git clone https://github.com/AstroHQ/astro-commerce.git
cd astro-commerce
python3 -m pip install --user -r requirements.txt
```

Run the CLI directly from the repo:

```bash
scripts/astro-commerce doctor
scripts/astro-commerce --demo shopify sales --days 30 --group sku
scripts/astro-commerce --demo sync run --days 30
```

To install command shims into your local workspace:

```bash
scripts/astro-commerce install --with-deps
```

After installation:

```bash
astro-commerce doctor
astro-commerce --demo amazon inventory --output records
```

## Common Commands

```bash
astro-commerce shopify sales --days 30 --match "luna" --group sku
astro-commerce amazon sales --days 7 --group day
astro-commerce stripe sales --days 30 --group sku
astro-commerce appstore sales --yesterday --group sku
astro-commerce fastspring sales --yesterday --group sku-day
astro-commerce sync run --channel all --days 7
astro-commerce inventory-alerts --output json
```

## Example Workflows

### Daily Revenue Snapshot

Sync all configured channels, then print yesterday's revenue by channel from SQLite:

```bash
astro-commerce sync run --channel all --yesterday

sqlite3 ~/.ecom-sales.db '
  SELECT channel, printf("$%.2f", SUM(revenue)) AS revenue, SUM(units) AS units
  FROM daily_sales
  WHERE date = date("now", "-1 day")
  GROUP BY channel
  ORDER BY SUM(revenue) DESC;
'
```

### Post a Slack Daily Report

Use an incoming webhook and keep the webhook URL in the environment:

```bash
export SLACK_WEBHOOK_URL="<your Slack incoming webhook URL>"

astro-commerce sync run --channel all --yesterday

export REPORT=$(
  sqlite3 ~/.ecom-sales.db '
    SELECT "- " || channel || ": $" || printf("%.2f", SUM(revenue)) || " / " || SUM(units) || " units"
    FROM daily_sales
    WHERE date = date("now", "-1 day")
    GROUP BY channel
    ORDER BY SUM(revenue) DESC;
  '
)

python3 - <<'PY'
import json
import os
import urllib.request

title = "Daily commerce report"
report = os.environ["REPORT"]
payload = json.dumps({"text": f"*{title}*\n{report}"}).encode()
req = urllib.request.Request(
    os.environ["SLACK_WEBHOOK_URL"],
    data=payload,
    headers={"Content-Type": "application/json"},
)
urllib.request.urlopen(req, timeout=15).read()
PY
```

### Product Trend Chart

Generate a PNG chart from live channel data:

```bash
astro-commerce shopify sales --days 30 --match "luna" --group day --output csv \
  | astro-commerce chart --title "Luna Shopify Revenue - Last 30 Days" --type line -o luna-shopify-30d.png
```

### Inventory Alert Digest

Sync sales and inventory, then produce action items for stock planning:

```bash
astro-commerce sync run --channel all --days 30
astro-commerce inventory-alerts --days 30 --output slack
```

To post those alerts to Slack:

```bash
export ALERTS=$(astro-commerce inventory-alerts --days 30 --output slack)
curl -X POST -H "Content-Type: application/json" \
  --data "$(python3 -c 'import json, os; print(json.dumps({"text": os.environ["ALERTS"]}))')" \
  "$SLACK_WEBHOOK_URL"
```

### Composable ETL

Pull from one source, inspect the records payload, then ingest it into the shared database:

```bash
astro-commerce stripe sales --yesterday --output records > stripe-yesterday.json
python3 -m json.tool stripe-yesterday.json | head -40
astro-commerce sync ingest < stripe-yesterday.json
```

### Demo Without Exposing Real Numbers

Keep real SKUs, channels, dates, and locations while masking revenue, units, and stock counts:

```bash
astro-commerce --db /tmp/commerce-demo.db --demo sync run --days 45
astro-commerce --db /tmp/commerce-demo.db --demo shopify sales --days 30 --group sku
astro-commerce --db /tmp/commerce-demo.db inventory-alerts --output json
```

Use `--demo` to mask sales, revenue, unit, and inventory numbers with deterministic demo values:

```bash
astro-commerce --demo shopify sales --days 30 --group sku
astro-commerce --demo sync run --days 30
```

Demo sync writes to `~/.ecom-sales-demo.db` by default. Use `--db PATH` or `ECOM_DEMO_DB_PATH` to choose another database.

## Configuration

Configure the default SQLite database:

```bash
astro-commerce configure --db ~/.ecom-sales.db
```

Credential files and environment variables are intentionally not committed. Channel setup is documented here:

- [Shopify sales](docs/shopify-revenue.md)
- [Shopify inventory](docs/shopify-stock.md)
- [Amazon sales](docs/amazon-revenue.md)
- [Amazon inventory](docs/amazon-stock.md)
- [Stripe](docs/stripe.md)
- [App Store Connect](docs/app-store.md)
- [FastSpring](docs/fastspring.md)

## Output Formats

Most source commands support:

- `table` for terminal output
- `csv` for spreadsheets and charting
- `json` for structured inspection
- `records` for piping into `astro-commerce sync ingest`

Example:

```bash
astro-commerce shopify sales --yesterday --output records | astro-commerce sync ingest
```

## Inventory Alerts

`astro-commerce inventory-alerts` calculates action items from synced sales and inventory data:

```bash
astro-commerce inventory-alerts
astro-commerce inventory-alerts --days 30 --output slack
astro-commerce inventory-alerts --channel shopify --location "ITB" --hide-sku old-sku
```

See [database-schema.md](docs/database-schema.md) and [sync.md](docs/sync.md) for how synced data is stored.

## Tests

Run the offline test suite:

```bash
python3 -m unittest discover -s tests
```

Live API smoke tests are opt-in and skip channels without credentials:

```bash
python3 tests/test_astro_commerce_smoke.py --live
python3 tests/test_astro_commerce_smoke.py --live --channels shopify,stripe
```

## Skill Usage

For Codex/OpenClaw skill installation, this repository root is the skill directory. The skill manifest and agent instructions live in [SKILL.md](SKILL.md).

When calling from an agent without installing shims, prefer repo-relative commands:

```bash
{baseDir}/scripts/astro-commerce doctor
{baseDir}/scripts/astro-commerce sync run --channel all --days 7
```
