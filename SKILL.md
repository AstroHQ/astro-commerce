---
name: astro-commerce
description: Pull, sync, chart, and inspect Astropad commerce sales/inventory data from Shopify, Amazon Seller Central, Stripe, FastSpring, and App Store Connect. Use for revenue, order quantities, SKU performance, inventory, commerce database sync, and CLI charting workflows.
homepage: https://github.com/AstroHQ/astro-commerce
metadata: {"openclaw":{"emoji":"🛰️","requires":{"bins":["python3"]},"install":[{"id":"python3-brew","kind":"brew","formula":"python","bins":["python3"],"label":"Install Python 3 (Homebrew)"}]}}
---
# Astro Commerce Skill

Pull, sync, chart, and inspect commerce sales/inventory data from Amazon Seller Central (SP-API), Shopify (Admin REST API), Stripe (REST API), App Store Connect API, and FastSpring Data API. Includes `astro-commerce chart` for quick chart generation.

## Tools

| Command | Description |
|---------|-------------|
| `astro-commerce` | Unified CLI for all commerce channels, sync, and charting |

## Quick Reference

When using this skill from an agent, prefer the bundled CLI path:

```bash
{baseDir}/scripts/astro-commerce doctor  # validates commands, credential fields, key files, database schema, and Python packages
{baseDir}/scripts/astro-commerce shopify sales --yesterday --output records | {baseDir}/scripts/astro-commerce sync ingest
{baseDir}/scripts/astro-commerce amazon inventory --output records | {baseDir}/scripts/astro-commerce sync ingest
{baseDir}/scripts/astro-commerce sync run --channel all --days 7
```

After local install/symlink, users can run the shorter commands:

```bash
astro-commerce doctor
astro-commerce --demo shopify sales --days 30 --match "luna" --group sku
astro-commerce shopify sales --days 30 --match "luna" --group sku
astro-commerce amazon sales --days 7 --group day
astro-commerce stripe sales --days 30 --group sku
astro-commerce appstore sales --yesterday --group sku
astro-commerce fastspring sales --yesterday --group sku-day
astro-commerce --db /tmp/commerce-test.db sync run --channel appstore --days 7
astro-commerce inventory-alerts --output json
astro-commerce configure --db ~/.ecom-sales.db
```

Dashboard implementation lives in the separate `ecom-dashboard` skill.

## Demo Mode

Use `--demo` on the public CLI to replace sales, revenue, unit, and inventory numbers with deterministic realistic-looking values. For source commands it masks terminal output. For `sync`, it writes fake values into a separate demo SQLite DB by default (`~/.ecom-sales-demo.db`) so demos can be shown safely.

```bash
astro-commerce --demo shopify sales --days 30 --group sku
astro-commerce --demo sync run --days 30
astro-commerce --demo amazon inventory --output records
astro-commerce --demo stripe sales --yesterday --output records
```

Dates, SKUs, channels, locations, and metadata stay intact so output still looks realistic for demos. Use top-level `--db` or `ECOM_DEMO_DB_PATH` to choose a specific demo DB.

## Database Selection

`astro-commerce configure` saves the default database in `.astro-commerce.json`. Override it per command with top-level `--db`:

```bash
astro-commerce --db /tmp/commerce-test.db sync run --channel shopify --days 7
astro-commerce --db /tmp/commerce-demo.db --demo sync run --days 30
astro-commerce --db /tmp/commerce-test.db doctor
```

Command-specific `--db PATH` on `astro-commerce sync run` and `astro-commerce sync ingest` also works.

## Common Flags (inventory tools)

| Flag | Description |
|------|-------------|
| `--match PATTERN` | Filter by SKU substring (alias: `--sku`) |
| `--group MODE` | `sku` (default) or `total` |
| `--output FORMAT` | `table` (default), `csv`, `json`, or `records` |
| `--hide-zero` | Hide zero-quantity SKUs |

## Inventory Alerts

`astro-commerce inventory-alerts` calculates location-specific inventory actions from synced SQLite data. This is the shared source used by dashboard/web UI code and can also feed Slack automation.

```bash
astro-commerce inventory-alerts
astro-commerce inventory-alerts --days 30 --output json
astro-commerce inventory-alerts --output csv
astro-commerce inventory-alerts --output slack
astro-commerce inventory-alerts --channel shopify --location "ITB" --hide-sku old-sku
astro-commerce inventory-alerts --list-hidden
```

The JSON payload includes `action_items` with `priority`, `action`, `channel`, `location`, `sku`, `on_hand`, `inbound`, `available_with_inbound`, `avg_daily_30d`, `days_remaining_30d`, `reorder_units`, `lost_revenue`, and `sales_rate_source`.
`days_remaining_30d` uses `on_hand + inbound`, because inbound means the replenishment is already handled and on the way.
For active alerts, `reorder_units` is the full 30-day projected demand and does not subtract current on-hand or inbound inventory.
Hidden alerts are stored as `channel + location + sku` tuples in the shared SQLite database and are excluded from alerts by default; pass `--show-hidden` to include them.
Use `--output slack` for Slack posts instead of the raw table.

## Common Flags (sales commands)

| Flag | Description |
|------|-------------|
| `--start DATE` | Start date (YYYY-MM-DD) |
| `--end DATE` | End date (default: today) |
| `--days N` | Look back N days (alternative to `--start`) |
| `--match PATTERN` | Filter by SKU substring (alias: `--sku`) |
| `--group MODE` | `sku-day` (default), `day`, `sku`, or `total` |
| `--output FORMAT` | `table` (default), `csv`, `json`, or `records` |

## Detailed Docs

See `docs/` folder:
- [astro-commerce.md](docs/astro-commerce.md)
- [Amazon sales](docs/amazon-revenue.md)
- [Shopify sales](docs/shopify-revenue.md)
- [Amazon inventory](docs/amazon-stock.md)
- [Shopify inventory](docs/shopify-stock.md)
- [Charts](docs/chart.md)
- [Sync](docs/sync.md)
- [database-schema.md](docs/database-schema.md)
- [Stripe sales](docs/stripe.md)
- [App Store sales](docs/app-store.md)
- [FastSpring sales](docs/fastspring.md)

## Local Install

Install command shims into `~/clawd-work/bin`:

```bash
{baseDir}/scripts/astro-commerce install
```

Install Python package dependencies too:

```bash
{baseDir}/scripts/astro-commerce install --with-deps
```

This installs the public `astro-commerce` CLI.

## Setup

- **Amazon:** `~/.amazon-sp-api.json` — see [Amazon sales docs](docs/amazon-revenue.md)
- **Shopify:** `~/.shopify-api.json` — see [Shopify sales docs](docs/shopify-revenue.md)
- **Stripe:** `~/.stripe-api.json` or `STRIPE_API_KEY` env var — see [Stripe sales docs](docs/stripe.md)
- **App Store:** `~/.appstore-api.json` or `ASC_ISSUER_ID`/`ASC_KEY_ID`/`ASC_PRIVATE_KEY_PATH` env vars — see [App Store sales docs](docs/app-store.md)
- **FastSpring:** `.fastspring-api.json` in workspace or `~/.fastspring-api.json` with `{"username": "...", "password": "..."}` — see [FastSpring sales docs](docs/fastspring.md)

## Dependencies

Python package dependencies are listed in `requirements.txt`.

| Package | Required by |
|---|---|
| `requests` | Shopify, Amazon, Stripe, FastSpring, and App Store API CLIs |
| `PyJWT` | App Store JWT authentication |
| `cryptography` | App Store private-key signing through PyJWT |
| `matplotlib` | `astro-commerce chart` rendering |

Standard library only: the `astro-commerce` CLI and SQLite sync path.

Install with:

```bash
python3 -m pip install --user -r {baseDir}/requirements.txt
```
