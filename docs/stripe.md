# astro-commerce stripe sales

Pull subscription sales data from Stripe REST API.

## Usage

```bash
astro-commerce stripe sales --days 30 --group sku
astro-commerce stripe sales --yesterday --output records | astro-commerce sync ingest
```

## Records output

Use `--output records` to emit canonical sync-ingestable JSON.

Schema: `astro.commerce.sales.v1`

Records are aggregated by `(date, sku)` and include `quantity`, `gross_revenue`, and `currency`.
