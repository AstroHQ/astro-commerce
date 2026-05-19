# astro-commerce chart

Generate PNG charts from CSV data. Designed to pair with `astro-commerce` CSV output but works with any CSV.

## Usage

```bash
# Pipe from sales tools
astro-commerce amazon sales --days 14 --group day --output csv | astro-commerce chart -t "Amazon Daily Sales"
astro-commerce shopify sales --days 30 --group sku --output csv | astro-commerce chart -t "Shopify by SKU" --type bar

# From a file
astro-commerce chart -f data.csv -t "Monthly Revenue" --type line

# Save to file instead of opening Preview
astro-commerce chart -f data.csv -o chart.png
```

## Options

| Flag | Description |
|------|-------------|
| `-f, --file PATH` | CSV file path (default: stdin) |
| `-t, --title TEXT` | Chart title |
| `--type TYPE` | `bar`, `line`, or `pie` (default: auto-detect) |
| `--x COLUMN` | X-axis column name (default: first column) |
| `--y COLUMNS` | Y-axis column(s), comma-separated (default: all numeric) |
| `-o PATH` | Output PNG path (default: opens in macOS Preview) |
| `--width N` | Figure width in inches (default: 12) |
| `--height N` | Figure height in inches (default: 6) |
| `--stacked` | Stacked bar/area chart |
| `--keep-total` | Keep TOTAL summary rows (stripped by default) |

## Auto-detection

- **Chart type:** If the x-axis looks like dates → line chart. Otherwise → bar chart.
- **Y columns:** Automatically picks all numeric columns (excluding the x column).
- **TOTAL rows:** Stripped by default so they don't skew the chart. Use `--keep-total` to include them.

## Examples

```bash
# Daily revenue trend (line chart, auto-detected)
astro-commerce amazon sales --days 30 --group day --output csv | astro-commerce chart -t "Daily Revenue"

# SKU comparison (bar chart)
astro-commerce amazon sales --days 7 --group sku --output csv | astro-commerce chart -t "Sales by SKU" --type bar

# Multi-series: units and revenue on same chart
astro-commerce chart -f data.csv --y "Units,Revenue" -t "Units vs Revenue"

# Stacked bar chart
astro-commerce chart -f data.csv --stacked -t "Stacked Sales"

# Save to file for sharing
astro-commerce amazon sales --days 7 --group day --output csv | astro-commerce chart -t "Weekly Sales" -o weekly.png
```

## Dependencies

- **matplotlib** — installed automatically on first run if missing.
