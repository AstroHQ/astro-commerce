# Astro Commerce Demo Scripts

These examples show how to use `astro-commerce` as a reporting and automation building block.

Set `ASTRO_COMMERCE` if the CLI is not installed globally:

```bash
export ASTRO_COMMERCE="$PWD/scripts/astro-commerce"
```

Most scripts use `ECOM_DB_PATH` when set, otherwise `~/.ecom-sales.db`.

## Scripts

| Script | Purpose |
| --- | --- |
| `scripts/daily-revenue-report.sh` | Sync yesterday's data and print a channel revenue summary |
| `scripts/slack-daily-report.sh` | Sync yesterday's data and post a Slack webhook summary |
| `scripts/inventory-alerts-slack.sh` | Generate inventory alerts and post them to Slack |
| `scripts/product-trend-chart.sh` | Build a 30-day product revenue PNG chart |
| `scripts/composable-etl.sh` | Pull `records` JSON from one channel and ingest it into SQLite |

## Slack Webhooks

Slack examples expect the webhook URL in an environment variable:

```bash
export SLACK_WEBHOOK_URL="<your Slack incoming webhook URL>"
demo/scripts/slack-daily-report.sh
```

Do not commit webhook URLs or bot tokens.

## Demo-Safe Output

Use `--demo` directly on `astro-commerce` when you want masked sales, revenue, units, and inventory values:

```bash
astro-commerce --demo shopify sales --days 30 --group sku
astro-commerce --demo sync run --days 30
```

Demo mode preserves dates, SKUs, channels, and locations while replacing sensitive numeric values.
