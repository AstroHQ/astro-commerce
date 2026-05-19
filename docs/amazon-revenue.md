# astro-commerce amazon sales

Pull sales data from Amazon Seller Central via the SP-API Reports API.

## Setup

Create `~/.amazon-sp-api.json`:

```json
{
  "refresh_token": "Atzr|...",
  "lwa_app_id": "amzn1.application-oa2-client.xxx",
  "lwa_client_secret": "xxx",
  "marketplace_id": "ATVPDKIKX0DER",
  "seller_id": "YOUR_SELLER_ID"
}
```

Or set equivalent `SP_API_*` environment variables.

## Usage

```bash
astro-commerce amazon sales --days 7
astro-commerce amazon sales --start 2026-02-01 --end 2026-02-10
astro-commerce amazon sales --days 30 --match "fresh-coat" --group day
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
2026-02-03   fresh-coat-v1-f4                 1      29.99
2026-02-03   fresh-coat-v1-f5                 2      59.98
2026-02-04   fresh-coat-v1-f4                 3      89.97
--------------------------------------------------------------
TOTAL                                        6     179.94 USD
```

### `--group day`
Totals per day, all matching SKUs merged.

```
Date         Units    Revenue
2026-02-03       4     119.96
2026-02-04       7     209.93
-------------------------------
TOTAL           11     329.89 USD
```

### `--group sku`
Totals per SKU across the entire date range.

```
SKU                          Units    Revenue
fresh-coat-v1-f4                 9     269.91
fresh-coat-v1-f5                12     359.88
----------------------------------------------
TOTAL                           21     629.79 USD
```

### `--group total`
Single summary line.

```
Units: 21 | Revenue: 629.79 USD
```

## Charting

```bash
astro-commerce amazon sales --days 14 --match fresh-coat --group day --output csv | astro-commerce chart -t "Fresh Coat Daily Sales"
```

## Notes

- When `--match` is used with `--group day` or `--group sku-day`, the tool fetches one report per day (parallel) to get SKU-level granularity. This is slower but necessary due to SP-API report structure.
- Marketplace defaults to US (`ATVPDKIKX0DER`).

## Composable records output

Use `--output records` to emit canonical sync-ingestable JSON instead of report-shaped JSON:

```bash
astro-commerce amazon sales --yesterday --output records
astro-commerce amazon sales --start 2026-05-01 --end 2026-05-12 --output records | astro-commerce sync ingest
```

Schema: `astro.commerce.sales.v1`

Records are aggregated by `(date, sku)` and include `quantity`, `gross_revenue`, `currency`, and optional source details under `meta`.

Note: `--output records` forces SKU/day-style output so the database receives real SKU rows, not date-only `ALL` aggregate rows.
