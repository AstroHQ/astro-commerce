# astro-commerce

Unified CLI for commerce sales, inventory, sync, and charting.

## Local Install

From the skill directory:

```bash
./scripts/astro-commerce install
./scripts/astro-commerce install --with-deps  # also installs requirements.txt with pip --user
```

This links only the public `astro-commerce` CLI into `~/clawd-work/bin` by default.

## Usage

```bash
astro-commerce [--db PATH] <channel> <resource> [args...]
astro-commerce [--db PATH] sync run [args...]
astro-commerce [--db PATH] sync ingest [args...]
astro-commerce chart [args...]
astro-commerce configure [--db /path/to/commerce.db]
astro-commerce [--db PATH] doctor
astro-commerce install [args...]

# Demo-safe output
astro-commerce --demo shopify sales --days 30 --group sku
astro-commerce --demo sync run --days 30
```

## Commands

| Command | Description |
|---|---|
| `astro-commerce shopify sales` | Shopify order revenue by date/SKU |
| `astro-commerce shopify inventory` | Shopify inventory by SKU/location |
| `astro-commerce amazon sales` | Amazon Seller Central sales by date/SKU |
| `astro-commerce amazon inventory` | Amazon FBA on-hand and inbound inventory |
| `astro-commerce stripe sales` | Stripe subscription sales |
| `astro-commerce fastspring sales` | FastSpring revenue |
| `astro-commerce appstore sales` | App Store Connect sales reports |
| `astro-commerce sync run` | Pull enabled channels and upsert them into SQLite |
| `astro-commerce sync ingest` | Ingest canonical records JSON into SQLite |
| `astro-commerce chart` | Render CSV data to PNG charts |
| `astro-commerce install` | Install the public CLI shim |

## Examples

```bash
astro-commerce shopify sales --yesterday --output records
astro-commerce shopify inventory --output records | astro-commerce sync ingest

astro-commerce amazon sales --days 7 --group day
astro-commerce amazon inventory --output records | astro-commerce sync ingest

astro-commerce stripe sales --days 30 --group sku
astro-commerce fastspring sales --yesterday --group sku-day
astro-commerce appstore sales --yesterday --group sku

astro-commerce sync run --channel shopify --yesterday
astro-commerce sync run --channel all --days 7
astro-commerce --db /tmp/commerce-test.db sync run --channel appstore --days 7
```

## Demo Mode

Use `--demo` to replace sales, revenue, unit, and inventory numbers with deterministic realistic-looking values.

```bash
astro-commerce --demo shopify sales --days 30 --group sku
astro-commerce --demo sync run --days 30
```

For source commands, demo mode masks terminal output. For `sync`, it writes fake values to `~/.ecom-sales-demo.db` by default so demos can be shown safely. Dates, SKUs, channels, locations, and metadata stay intact. Use top-level `--db` or `ECOM_DEMO_DB_PATH` to choose another demo DB.

## Doctor

```bash
astro-commerce doctor
```

Checks local command availability, required service credential fields, App Store private-key file presence, and Python packages. It does not call external APIs or print secret values.

## Database

`astro-commerce configure` asks where to create/use the SQLite database, saves that path in `.astro-commerce.json`, and initializes the schema. `sync` uses that configured path by default. See [database-schema.md](database-schema.md) for tables, columns, indexes, and SQL.

Override the configured database for one command with top-level `--db`:

```bash
astro-commerce --db /tmp/commerce-test.db sync run --channel shopify --days 7
astro-commerce --db /tmp/commerce-demo.db --demo sync run --days 30
astro-commerce --db /tmp/commerce-test.db doctor
```

`astro-commerce sync run --db PATH`, `astro-commerce sync ingest --db PATH`, and `ECOM_DB_PATH=/path/to/db` remain supported.

## Dependencies

See `../requirements.txt`. Package usage:

| Package | Required by |
|---|---|
| `requests` | Shopify, Amazon, Stripe, FastSpring, and App Store API CLIs |
| `PyJWT` | App Store JWT authentication |
| `cryptography` | App Store private-key signing through PyJWT |
| `matplotlib` | `astro-commerce chart` rendering |

Standard library only: the `astro-commerce` CLI and SQLite sync path.
