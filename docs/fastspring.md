# astro-commerce fastspring sales

Pull revenue data from FastSpring Data API.

## Usage

```bash
astro-commerce fastspring sales --days 30 --group sku
astro-commerce fastspring sales --yesterday --output records | astro-commerce sync ingest
```

## Records output

Use `--output records` to emit canonical sync-ingestable JSON.

Schema: `astro.commerce.sales.v1`

Records are aggregated by `(date, sku)` and include `quantity`, `gross_revenue`, and `currency`.
