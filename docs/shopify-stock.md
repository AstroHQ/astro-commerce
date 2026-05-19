# astro-commerce shopify inventory

Pull inventory levels from Shopify via the Admin REST API.

## Setup

Uses the same config as `astro-commerce shopify sales`: `~/.shopify-api.json` (or `SHOPIFY_*` env vars). See [Shopify sales docs](shopify-revenue.md) for setup details.

Requires `read_products` and `read_inventory` access scopes.

## Usage

```bash
astro-commerce shopify inventory
astro-commerce shopify inventory --match "luna"
astro-commerce shopify inventory --group total
astro-commerce shopify inventory --hide-zero --output csv
```

## Options

| Flag | Description |
|------|-------------|
| `--match PATTERN` | Filter by SKU substring, case-insensitive (alias: `--sku`) |
| `--group MODE` | `sku` (default) or `total` |
| `--output FORMAT` | `table`, `csv`, or `json` (default: `table`) |
| `--hide-zero` | Hide SKUs with 0 inventory |

## Group Modes

### `--group sku` (default)
One row per SKU.

```
SKU                                      On-Hand
--------------------------------------------------
luna-classic-black                            42
luna-classic-white                            18
--------------------------------------------------
TOTAL                                         60
```

### `--group total`
Single summary line.

```
On-Hand: 60
```

## How It Works

1. Fetches all Shopify locations
2. Fetches all products/variants (paginated) to map SKU → inventory_item_id
3. Fetches inventory levels in batches of 50, summing across all locations
4. Outputs aggregated on-hand quantities per SKU

## Output Formats

- **table** — human-readable (default)
- **csv** — pipe to `astro-commerce chart` or other tools
- **json** — structured output with `items` array and `summary`

## Composable records output

Use `--output records` to emit canonical sync-ingestable JSON instead of report-shaped JSON:

```bash
astro-commerce shopify inventory --output records
astro-commerce shopify inventory --match luna --output records | astro-commerce sync ingest
```

Schema: `astro.commerce.inventory.v1`

Records include `sku`, `location`, `on_hand`, and `inbound`.
