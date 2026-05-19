# Astro Commerce Test Cases

Run the automated suite from this directory with:

\`\`\`bash
python3 -m unittest discover -s tests
\`\`\`

The tests are written with Python's standard \`unittest\` module so they do not require pytest.

## Live API Smoke Tests

Live smoke tests are kept separate from the offline suite and are skipped by default. They call the real vendor APIs through the public \`astro-commerce\` CLI with a narrow \`--yesterday\` sales range and \`--output records\`, then verify each command authenticates and returns a canonical JSON payload.

Run all configured live smoke tests with:

\`\`\`bash
python3 tests/test_astro_commerce_smoke.py --live
\`\`\`

Run only selected channels with:

\`\`\`bash
python3 tests/test_astro_commerce_smoke.py --live --channels shopify,stripe
\`\`\`

If you pass smoke-test flags to \`tests/test_astro_commerce.py\` by mistake, it delegates to the smoke-test runner:

\`\`\`bash
python3 tests/test_astro_commerce.py --live --channels shopify
\`\`\`

Optional knobs:

- \`--timeout SECONDS\` changes the per-command timeout; default is 240 seconds.
- \`--channels all|shopify,amazon,stripe,fastspring,appstore\` limits which vendor APIs are called.

The same controls are also available as env vars for CI: \`ASTRO_COMMERCE_LIVE_SMOKE=1\`, \`ASTRO_COMMERCE_SMOKE_TIMEOUT=SECONDS\`, and \`ASTRO_COMMERCE_SMOKE_CHANNELS=...\`.

Each smoke case is skipped if that channel's credential config is not present. These tests intentionally make live API calls and may be affected by vendor outages, rate limits, report-generation delays, or missing data availability.

For App Store Connect, the smoke runner normalizes a relative \`ASC_PRIVATE_KEY_PATH\` against the App Store config location before calling the CLI, so running tests from the refactor directory still finds the \`.p8\` key.

## Coverage Matrix

| Area | Test cases |
| --- | --- |
| \`astro-commerce\` router | help/commands output, channel/resource dispatch, \`--demo\` passthrough, invalid \`--channel all\` JSON output |
| Demo masking | JSON numeric masking preserves dates/SKUs and recomputes summary totals |
| Shared helpers | sales aggregation by day/SKU/SKU-day/total, CSV totals, empty table output |
| Shopify sales | order line extraction, store-timezone date handling, SKU filtering, records payload summary |
| Amazon sales | Sales & Traffic JSON parsing, TSV fallback parsing, aggregate \`ALL\` rows excluded from sync records |
| Stripe sales | price map matching, metadata fallback, refunded/failed charges ignored, records payload summary |
| FastSpring sales | exact and partial product-path SKU mapping, SKU filtering |
| App Store sales | gzipped TSV parsing, Apple SKU normalization, unknown products ignored |
| Shopify inventory | sync-ingestable inventory records and totals |
| Amazon inventory | sync-ingestable inventory records, inbound totals, source metadata |
| SQLite sync | schema creation plus sales/inventory upserts from mocked source CLIs |
| Charting | date/numeric detection and PNG output generation from CSV |
| Install | copy install into a temporary bin directory |
| Live API smoke | opt-in real API calls for Shopify sales/inventory, Amazon sales/inventory, Stripe sales, FastSpring sales, and App Store sales |

## Not Covered By The Offline Suite

These tests intentionally do not call live Shopify, Amazon SP-API, Stripe, FastSpring, or App Store Connect APIs. Live credential/API tests should be separate smoke tests because they depend on secrets, network reliability, rate limits, and vendor data availability.
