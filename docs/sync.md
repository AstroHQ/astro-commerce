# astro-commerce sync

Syncs sales and inventory data into the configured local SQLite database. `astro-commerce configure` saves the default path in `.astro-commerce.json`; top-level `astro-commerce --db PATH`, command-specific `--db`, and `ECOM_DB_PATH` override it.

## Usage

```bash
# Default: yesterday's sales + today's inventory for both channels
astro-commerce sync run

# Last 7 days of sales
astro-commerce sync run --days 7

# Specific date range, Amazon only
astro-commerce sync run --start 2026-01-01 --end 2026-01-31 --channel amazon

# Only inventory sync
astro-commerce sync run --skip-sales

# Only sales sync
astro-commerce sync run --skip-inventory

# Custom database path
astro-commerce --db /path/to/custom.db sync run --channel appstore --days 7
```

## Options

| Flag | Description |
|------|-------------|
| `--days N` | Look back N days for sales |
| `--yesterday` | Sync yesterday's sales (default) |
| `--start DATE` | Start date (YYYY-MM-DD) |
| `--end DATE` | End date (default: today) |
| `--channel` | `amazon`, `shopify`, `stripe`, `fastspring`, `appstore`, or `all` (default: `all`) |
| `--skip-sales` | Skip sales sync |
| `--skip-inventory` | Skip inventory sync |
| `--db PATH` | Override database path (default: configured `.astro-commerce.json` path or `~/.ecom-sales.db`) |

Date flags (`--days`, `--yesterday`, `--start`) are mutually exclusive.

## Database Schema

See [database-schema.md](database-schema.md) for tables, columns, indexes, and SQL.

## How It Works

1. Pulls sales with `--group sku-day --output records`
2. Pulls inventory with `--output records`
3. Sends each canonical `astro.commerce.*.v1` payload through `astro-commerce sync ingest`
4. Upserts results into SQLite using `INSERT OR REPLACE`
5. If one channel fails, continues with the others and reports the error

## Querying the Database

```bash
sqlite3 /path/to/commerce.db "SELECT date, SUM(revenue) FROM daily_sales GROUP BY date ORDER BY date"
```

## Composable Ingest

`astro-commerce sync ingest` can ingest canonical records JSON from any `astro-commerce` source command. This keeps live API connectors separate from database writes:

```bash
astro-commerce shopify sales --yesterday --output records | astro-commerce sync ingest
astro-commerce shopify inventory --output records | astro-commerce sync ingest --date 2026-05-12
astro-commerce amazon sales --yesterday --output records | astro-commerce sync ingest
astro-commerce amazon inventory --output records | astro-commerce sync ingest --date 2026-05-12
```

Supported schemas:

- `astro.commerce.sales.v1`
- `astro.commerce.inventory.v1`

Regular `astro-commerce sync run` uses this same canonical ingest path internally, so direct API sync and piped records writes follow one database contract.


## Demo Mode

Use the public CLI to sync realistic fake values into a demo database:

```bash
astro-commerce --demo sync run --days 30
```

By default demo sync writes to `~/.ecom-sales-demo.db` instead of the live DB. Use top-level `astro-commerce --db PATH` or `ECOM_DEMO_DB_PATH` to choose another demo DB. Demo mode preserves dates, SKUs, channels, locations, and metadata but replaces revenue, unit, and inventory values before SQLite writes.
