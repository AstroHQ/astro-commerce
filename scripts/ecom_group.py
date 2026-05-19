"""Shared grouping/aggregation helpers for astro-commerce sales rows."""

from __future__ import annotations

import csv
import io
import json

SALES_GROUPS = ("day", "sku", "sku-day", "total")


def aggregate_sales(rows: list[dict], group: str = "sku-day") -> list[dict]:
    """Aggregate normalized sales rows by sku-day, day, sku, or total.

    Input rows should have date, sku, quantity, amount, and optional currency.
    """
    if group == "sku-day":
        agg: dict[tuple[str, str], dict] = {}
        for r in rows:
            key = (r["date"], r["sku"])
            if key not in agg:
                agg[key] = {"date": r["date"], "sku": r["sku"], "quantity": 0, "amount": 0.0, "currency": r.get("currency", "USD")}
            agg[key]["quantity"] += int(r.get("quantity", 0) or 0)
            agg[key]["amount"] += float(r.get("amount", 0) or 0)
        return sorted(agg.values(), key=lambda x: (x["date"], x["sku"]))

    if group == "day":
        agg: dict[str, dict] = {}
        for r in rows:
            key = r["date"]
            if key not in agg:
                agg[key] = {"date": key, "quantity": 0, "amount": 0.0, "currency": r.get("currency", "USD")}
            agg[key]["quantity"] += int(r.get("quantity", 0) or 0)
            agg[key]["amount"] += float(r.get("amount", 0) or 0)
        return sorted(agg.values(), key=lambda x: x["date"])

    if group == "sku":
        agg: dict[str, dict] = {}
        for r in rows:
            key = r["sku"]
            if key not in agg:
                agg[key] = {"sku": key, "quantity": 0, "amount": 0.0, "currency": r.get("currency", "USD")}
            agg[key]["quantity"] += int(r.get("quantity", 0) or 0)
            agg[key]["amount"] += float(r.get("amount", 0) or 0)
        return sorted(agg.values(), key=lambda x: x["amount"], reverse=True)

    if group == "total":
        if not rows:
            return []
        total = {"sku": "ALL", "quantity": 0, "amount": 0.0, "currency": rows[0].get("currency", "USD")}
        for r in rows:
            total["quantity"] += int(r.get("quantity", 0) or 0)
            total["amount"] += float(r.get("amount", 0) or 0)
        return [total]

    raise ValueError(f"unknown sales group: {group}")


# Backwards-compatible function names used by older scripts/tests.
def aggregate_by_sku_day(rows: list[dict]) -> list[dict]:
    return aggregate_sales(rows, "sku-day")


def aggregate_by_day(rows: list[dict]) -> list[dict]:
    return aggregate_sales(rows, "day")


def aggregate_by_sku(rows: list[dict]) -> list[dict]:
    return aggregate_sales(rows, "sku")


def aggregate_total(rows: list[dict]) -> list[dict]:
    return aggregate_sales(rows, "total")


def sales_summary(rows: list[dict]) -> dict:
    return {
        "total_units": sum(int(r.get("quantity", 0) or 0) for r in rows),
        "total_revenue": round(sum(float(r.get("amount", 0) or 0) for r in rows), 2),
    }


def format_sales_csv(rows: list[dict], group: str = "sku-day") -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    summary = sales_summary(rows)
    total_qty = summary["total_units"]
    total_amt = summary["total_revenue"]

    if group == "total":
        writer.writerow(["Units", "Revenue"])
        writer.writerow([total_qty, f"{total_amt:.2f}"])
    elif group == "sku":
        writer.writerow(["SKU", "Units", "Revenue"])
        for r in rows:
            writer.writerow([r["sku"], r["quantity"], f"{r['amount']:.2f}"])
        writer.writerow(["TOTAL", total_qty, f"{total_amt:.2f}"])
    elif group == "day":
        writer.writerow(["Date", "Units", "Revenue"])
        for r in rows:
            writer.writerow([r["date"], r["quantity"], f"{r['amount']:.2f}"])
        writer.writerow(["TOTAL", total_qty, f"{total_amt:.2f}"])
    else:
        writer.writerow(["Date", "SKU", "Units", "Revenue"])
        for r in rows:
            writer.writerow([r["date"], r["sku"], r["quantity"], f"{r['amount']:.2f}"])
        writer.writerow(["TOTAL", "", total_qty, f"{total_amt:.2f}"])
    return out.getvalue()


def format_sales_json(rows: list[dict], group: str = "sku-day") -> str:
    return json.dumps({"group": group, "rows": rows, "summary": sales_summary(rows)}, indent=2)
