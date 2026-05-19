"""Shared readable table formatting for astro-commerce CLI tools."""

from __future__ import annotations


def fmt_int(value) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def fmt_money(value, currency: str | None = None) -> str:
    try:
        text = f"{float(value):,.2f}"
    except Exception:
        text = str(value)
    return f"{text} {currency}" if currency else text


def _width(text: object) -> int:
    return len(str(text))


def render_table(headers: list[str], rows: list[list[object]], align: list[str] | None = None, divider_before_last: bool = False) -> str:
    """Render a compact boxed table. align values: 'left' or 'right'."""
    if align is None:
        align = ["left"] * len(headers)
    str_rows = [[str(cell) for cell in row] for row in rows]
    widths = []
    for col, header in enumerate(headers):
        widths.append(max([_width(header), *(_width(row[col]) for row in str_rows)] or [_width(header)]))

    def border(left: str, mid: str, right: str) -> str:
        return left + mid.join("─" * (w + 2) for w in widths) + right

    def row(cells: list[str]) -> str:
        parts = []
        for i, cell in enumerate(cells):
            if align[i] == "right":
                parts.append(" " + cell.rjust(widths[i]) + " ")
            else:
                parts.append(" " + cell.ljust(widths[i]) + " ")
        return "│" + "│".join(parts) + "│"

    lines = [border("┌", "┬", "┐"), row(headers), border("├", "┼", "┤")]
    for i, cells in enumerate(str_rows):
        if divider_before_last and i == len(str_rows) - 1 and i > 0:
            lines.append(border("├", "┼", "┤"))
        lines.append(row(cells))
    lines.append(border("└", "┴", "┘"))
    return "\n".join(lines)


def format_sales_table(rows: list[dict], group: str = "sku-day") -> str:
    if not rows:
        return "No data found."
    currency = rows[0].get("currency", "USD")
    total_qty = sum(int(r.get("quantity", 0) or 0) for r in rows)
    total_amt = sum(float(r.get("amount", 0) or 0) for r in rows)

    if group == "total":
        return render_table(
            ["Metric", "Value"],
            [["Units", fmt_int(total_qty)], ["Revenue", fmt_money(total_amt, currency)]],
            ["left", "right"],
        )

    revenue_header = f"Revenue ({currency})" if currency else "Revenue"

    if group == "sku":
        table_rows = [[r.get("sku", ""), fmt_int(r.get("quantity", 0)), fmt_money(r.get("amount", 0))] for r in rows]
        table_rows.append(["TOTAL", fmt_int(total_qty), fmt_money(total_amt)])
        return render_table(["SKU", "Units", revenue_header], table_rows, ["left", "right", "right"], divider_before_last=True)

    if group == "day":
        table_rows = [[r.get("date", ""), fmt_int(r.get("quantity", 0)), fmt_money(r.get("amount", 0))] for r in rows]
        table_rows.append(["TOTAL", fmt_int(total_qty), fmt_money(total_amt)])
        return render_table(["Date", "Units", revenue_header], table_rows, ["left", "right", "right"], divider_before_last=True)

    table_rows = [[r.get("date", ""), r.get("sku", ""), fmt_int(r.get("quantity", 0)), fmt_money(r.get("amount", 0))] for r in rows]
    table_rows.append(["TOTAL", "", fmt_int(total_qty), fmt_money(total_amt)])
    return render_table(["Date", "SKU", "Units", revenue_header], table_rows, ["left", "left", "right", "right"], divider_before_last=True)


def format_inventory_table(rows: list[dict], group: str = "sku", include_location: bool = False, include_inbound: bool = False) -> str:
    if not rows:
        return "No inventory data found."
    total_on_hand = sum(int(r.get("on_hand", 0) or 0) for r in rows)
    total_inbound = sum(int(r.get("inbound", 0) or 0) for r in rows)

    if group == "total":
        metric_rows = [["On-Hand", fmt_int(total_on_hand)]]
        if include_inbound:
            metric_rows.append(["Inbound", fmt_int(total_inbound)])
        return render_table(["Metric", "Value"], metric_rows, ["left", "right"])

    headers = ["SKU"]
    align = ["left"]
    if include_location:
        headers.append("Location")
        align.append("left")
    headers.append("On-Hand")
    align.append("right")
    if include_inbound:
        headers.append("Inbound")
        align.append("right")

    table_rows = []
    for r in rows:
        row = [r.get("sku", "")]
        if include_location:
            row.append(r.get("location", ""))
        row.append(fmt_int(r.get("on_hand", 0)))
        if include_inbound:
            row.append(fmt_int(r.get("inbound", 0)))
        table_rows.append(row)

    total_row = ["TOTAL"]
    if include_location:
        total_row.append("")
    total_row.append(fmt_int(total_on_hand))
    if include_inbound:
        total_row.append(fmt_int(total_inbound))
    table_rows.append(total_row)
    return render_table(headers, table_rows, align, divider_before_last=True)
