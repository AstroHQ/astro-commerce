# astro-commerce appstore sales

Pull daily sales report data from the App Store Connect API.

## Setup

1. Create an API key in [App Store Connect → Users and Access → Keys](https://appstoreconnect.apple.com/access/api)
2. Download the `.p8` private key file
3. Create `~/.appstore-api.json`:

```json
{
  "issuer_id": "your-issuer-id",
  "key_id": "YOUR_KEY_ID",
  "private_key_path": "/path/to/AuthKey_YOURKEYID.p8",
  "vendor_number": "YOUR_VENDOR_NUMBER"
}
```

Or set environment variables:
- `ASC_ISSUER_ID` — Issuer ID from App Store Connect
- `ASC_KEY_ID` — Key ID for your API key
- `ASC_PRIVATE_KEY_PATH` — Path to the .p8 private key file
- `ASC_VENDOR_NUMBER` — Your vendor number

## Usage

```bash
# Yesterday's sales
astro-commerce appstore sales --yesterday

# Last 7 days by SKU
astro-commerce appstore sales --days 7 --group sku

# Date range, daily totals
astro-commerce appstore sales --start 2026-03-01 --end 2026-03-25 --group day

# Filter by SKU pattern
astro-commerce appstore sales --days 30 --match "luna" --group sku

# Canonical records output
astro-commerce appstore sales --yesterday --output records

# Specific vendor number
astro-commerce appstore sales --yesterday --vendor 12345678
```

## Flags

| Flag | Description |
|------|-------------|
| `--start DATE` | Start date (YYYY-MM-DD) |
| `--end DATE` | End date (default: yesterday — Apple has 1-day delay) |
| `--days N` | Look back N days |
| `--yesterday` | Shortcut for yesterday only |
| `--vendor NUMBER` | Apple vendor number (overrides config) |
| `--match PATTERN` | Filter by SKU substring (alias: `--sku`) |
| `--group MODE` | `sku-day` (default), `day`, `sku`, or `total` |
| `--output FORMAT` | `table` (default), `csv`, or `json` |

## Notes

- Apple sales reports have a **1-day delay** — yesterday is the latest available date
- Reports are fetched one day at a time (Apple API limitation)
- The tool automatically clamps the end date to yesterday if today is requested
- Apple returns gzip-compressed TSV data; the tool handles decompression automatically
- SKU names are normalized: lowercased with spaces/underscores converted to dashes
- Revenue = Developer Proceeds × Units (per-unit amount multiplied by quantity)

## Dependencies

```bash
pip install requests PyJWT cryptography
```


## Records output

Use `--output records` to emit canonical sync-ingestable JSON.

```bash
astro-commerce appstore sales --yesterday --output records | astro-commerce sync ingest
```

Schema: `astro.commerce.sales.v1`

Records are aggregated by `(date, sku)` and include `quantity`, `gross_revenue`, and `currency`.
