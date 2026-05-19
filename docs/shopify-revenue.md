# astro-commerce shopify sales

Pull sales data from Shopify via the Admin REST API.

## Setup

Create `~/.shopify-api.json`:

```json
{
  "store": "your-store.myshopify.com",
  "api_key": "xxx",
  "api_secret": "xxx"
}
```

Or use a legacy access token:

```json
{
  "store": "your-store.myshopify.com",
  "access_token": "shpat_xxx"
}
```

Environment variables `SHOPIFY_STORE`, `SHOPIFY_ACCESS_TOKEN`, `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET` also work.

## Usage

```bash
astro-commerce shopify sales --days 7
astro-commerce shopify sales --start 2026-02-01 --end 2026-02-10
astro-commerce shopify sales --days 30 --match "luna" --group day
```

## Options

| Flag | Description |
|------|-------------|
| `--start DATE` | Start date (YYYY-MM-DD) |
| `--end DATE` | End date (default: today) |
| `--days N` | Look back N days from today (alternative to `--start`) |
| `--match PATTERN` | Filter by SKU substring, case-insensitive (alias: `--sku`) |
| `--group MODE` | Aggregation mode (default: `sku-day`) |
| `--output FORMAT` | `table`, `csv`, or `json` (default: `table`) |

## Group Modes

### `--group sku-day` (default)
Full detail — one row per SKU per day.

```
Date         SKU                          Units    Revenue
2026-02-03   luna-usbc-01                     1     129.99
2026-02-03   luna-hdmi-01                     2     259.98
2026-02-04   luna-usbc-01                     3     389.97
--------------------------------------------------------------
TOTAL                                        6     779.94 USD
```

### `--group day`
Totals per day, all matching SKUs merged.

```
Date         Units    Revenue
2026-02-03       3     389.97
2026-02-04       3     389.97
-------------------------------
TOTAL            6     779.94 USD
```

### `--group sku`
Totals per SKU across the entire date range.

```
SKU                          Units    Revenue
luna-usbc-01                     4     519.96
luna-hdmi-01                     2     259.98
----------------------------------------------
TOTAL                            6     779.94 USD
```

### `--group total`
Single summary line.

```
Units: 6 | Revenue: 779.94 USD
```

## Charting

```bash
astro-commerce shopify sales --days 14 --group day --output csv | astro-commerce chart -t "Shopify Daily Sales"
```

## Notes

- Fetches orders via the Admin REST API with automatic pagination.
- Rate limiting is handled automatically (respects `Retry-After` and Shopify's leaky bucket).
- Auth uses client credentials grant (api_key + api_secret) or legacy access tokens.

## Composable records output

Use `--output records` to emit canonical sync-ingestable JSON instead of report-shaped JSON:

```bash
astro-commerce shopify sales --yesterday --output records
astro-commerce shopify sales --start 2026-05-01 --end 2026-05-12 --output records | astro-commerce sync ingest
```

Schema: `astro.commerce.sales.v1`

Records are aggregated by `(date, sku)` and include `quantity`, `gross_revenue`, `currency`, and optional source details under `meta`.
