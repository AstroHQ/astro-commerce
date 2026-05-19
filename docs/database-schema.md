# Astro Commerce Database Schema

`astro-commerce configure` saves the selected SQLite path in `.astro-commerce.json` as `database_path` and initializes these tables. `astro-commerce sync run` and `astro-commerce sync ingest` use that configured database unless `--db` or `ECOM_DB_PATH` overrides it.

Default path: `~/.ecom-sales.db`

## Tables

### daily_sales

One row per sale date, channel, and SKU.

| Column | Type | Notes |
|---|---|---|
| `date` | `TEXT NOT NULL` | Sale date, `YYYY-MM-DD`; primary key part |
| `channel` | `TEXT NOT NULL` | `amazon`, `shopify`, `stripe`, `fastspring`, or `appstore`; primary key part |
| `sku` | `TEXT NOT NULL` | Product SKU; primary key part |
| `units` | `INTEGER NOT NULL` | Units sold |
| `revenue` | `REAL NOT NULL` | Gross revenue amount in `currency` |
| `currency` | `TEXT DEFAULT 'USD'` | ISO currency code |
| `product_type` | `TEXT DEFAULT 'physical'` | `physical` or `software`; used by dashboard inventory views |
| `updated_at` | `TEXT NOT NULL` | UTC sync timestamp |

Primary key: `(date, channel, sku)`

Indexes:

- `idx_sales_date` on `date`
- `idx_sales_sku` on `sku`

### daily_inventory

One row per inventory snapshot date, channel, SKU, and location.

| Column | Type | Notes |
|---|---|---|
| `date` | `TEXT NOT NULL` | Snapshot date, `YYYY-MM-DD`; primary key part |
| `channel` | `TEXT NOT NULL` | `amazon` or `shopify`; primary key part |
| `sku` | `TEXT NOT NULL` | Product SKU; primary key part |
| `location` | `TEXT NOT NULL DEFAULT ''` | Warehouse/location label; primary key part |
| `on_hand` | `INTEGER NOT NULL` | Sellable units currently on hand |
| `inbound` | `INTEGER DEFAULT 0` | Units inbound to fulfillment/warehouse |
| `updated_at` | `TEXT NOT NULL` | UTC sync timestamp |

Primary key: `(date, channel, sku, location)`

Indexes:

- `idx_inventory_date` on `date`
- `idx_inventory_sku` on `sku`

### hidden_skus

Dashboard preference table for SKUs hidden from default inventory views.

| Column | Type | Notes |
|---|---|---|
| `sku` | `TEXT PRIMARY KEY` | Hidden product SKU |

## SQL

```sql
CREATE TABLE IF NOT EXISTS daily_sales (
    date         TEXT NOT NULL,
    channel      TEXT NOT NULL,
    sku          TEXT NOT NULL,
    units        INTEGER NOT NULL,
    revenue      REAL NOT NULL,
    currency     TEXT DEFAULT 'USD',
    product_type TEXT DEFAULT 'physical',
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (date, channel, sku)
);

CREATE TABLE IF NOT EXISTS daily_inventory (
    date       TEXT NOT NULL,
    channel    TEXT NOT NULL,
    sku        TEXT NOT NULL,
    location   TEXT NOT NULL DEFAULT '',
    on_hand    INTEGER NOT NULL,
    inbound    INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (date, channel, sku, location)
);

CREATE TABLE IF NOT EXISTS hidden_skus (
    sku TEXT PRIMARY KEY
);

CREATE INDEX IF NOT EXISTS idx_sales_date ON daily_sales(date);
CREATE INDEX IF NOT EXISTS idx_sales_sku ON daily_sales(sku);
CREATE INDEX IF NOT EXISTS idx_inventory_date ON daily_inventory(date);
CREATE INDEX IF NOT EXISTS idx_inventory_sku ON daily_inventory(sku);
```
