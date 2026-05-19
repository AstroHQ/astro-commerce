# astro-commerce amazon inventory

Pull FBA inventory levels from Amazon Seller Central via the SP-API.

## Setup

Uses the same config as `astro-commerce amazon sales`: `~/.amazon-sp-api.json` (or `SP_API_*` env vars). See [Amazon sales docs](amazon-revenue.md) for setup details.

## Usage

```bash
astro-commerce amazon inventory
astro-commerce amazon inventory --match "fresh-coat"
astro-commerce amazon inventory --group total
astro-commerce amazon inventory --hide-zero --output csv
```

## Options

| Flag | Description |
|------|-------------|
| `--match PATTERN` | Filter by SKU substring, case-insensitive (alias: `--sku`) |
| `--group MODE` | `sku` (default) or `total` |
| `--output FORMAT` | `table`, `csv`, or `json` (default: `table`) |
| `--hide-zero` | Hide SKUs where both on-hand and inbound are 0 |

## Group Modes

### `--group sku` (default)
One row per SKU.

```
SKU                                      On-Hand  Inbound
----------------------------------------------------------
fresh-coat-v1-f4                             120       50
fresh-coat-v1-f5                              85        0
----------------------------------------------------------
TOTAL                                        205       50
```

### `--group total`
Single summary line.

```
On-Hand: 205 | Inbound: 50
```

## Output Formats

- **table** — human-readable (default)
- **csv** — pipe to `astro-commerce chart` or other tools
- **json** — structured output with `items` array and `summary`

## Composable records output

Use `--output records` to emit canonical sync-ingestable JSON instead of report-shaped JSON:

```bash
astro-commerce amazon inventory --output records
astro-commerce amazon inventory --match fresh-coat --output records | astro-commerce sync ingest
```

Schema: `astro.commerce.inventory.v1`

Records include `sku`, `location`, `on_hand`, `inbound`, and optional source details under `meta`.
