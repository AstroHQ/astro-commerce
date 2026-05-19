"""Inventory alert calculations backed by the commerce SQLite database."""

from __future__ import annotations

import csv
from datetime import date, timedelta
import io
import json
import sqlite3


PHYSICAL_PRODUCT_TYPE = "physical"
NON_PHYSICAL_SKUS = {"(no sku)", "rock-planner", "rock-planner-50-off", "rock-planner-yearly"}
DEFAULT_ALERT_DAYS = 30
DEFAULT_BASIS_DAYS = 30
RECENT_INVENTORY_DAYS = 7

LATEST_PHYSICAL_SKUS_SQL = """
    SELECT sku
    FROM (
        SELECT sku, product_type,
               ROW_NUMBER() OVER (PARTITION BY sku ORDER BY date DESC, updated_at DESC) as rn
        FROM daily_sales
    )
    WHERE rn=1 AND product_type=?
"""


def get_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _latest_physical_skus(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(LATEST_PHYSICAL_SKUS_SQL, (PHYSICAL_PRODUCT_TYPE,)).fetchall()
    return {row["sku"] for row in rows if row["sku"] not in NON_PHYSICAL_SKUS}


def hidden_skus(db_path: str) -> list[str]:
    conn = get_db(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS hidden_skus (sku TEXT PRIMARY KEY)")
        rows = conn.execute("SELECT sku FROM hidden_skus ORDER BY sku").fetchall()
        return [row["sku"] for row in rows]
    finally:
        conn.close()


def _ensure_hidden_alerts_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hidden_inventory_alerts (
            channel TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT '',
            sku TEXT NOT NULL,
            PRIMARY KEY (channel, location, sku)
        )
        """
    )


def hidden_alerts(db_path: str) -> list[dict]:
    conn = get_db(db_path)
    try:
        _ensure_hidden_alerts_table(conn)
        rows = conn.execute(
            "SELECT channel, location, sku FROM hidden_inventory_alerts ORDER BY channel, location, sku"
        ).fetchall()
        return [{"channel": row["channel"], "location": row["location"], "sku": row["sku"]} for row in rows]
    finally:
        conn.close()


def add_hidden_alert(db_path: str, channel: str, location: str, sku: str) -> None:
    channel = channel.strip()
    location = location.strip()
    sku = sku.strip()
    if not channel or not sku:
        raise ValueError("channel and sku are required")
    conn = get_db(db_path)
    try:
        _ensure_hidden_alerts_table(conn)
        conn.execute(
            "INSERT OR IGNORE INTO hidden_inventory_alerts (channel, location, sku) VALUES (?, ?, ?)",
            (channel, location, sku),
        )
        conn.commit()
    finally:
        conn.close()


def remove_hidden_alert(db_path: str, channel: str, location: str, sku: str) -> None:
    conn = get_db(db_path)
    try:
        _ensure_hidden_alerts_table(conn)
        conn.execute(
            "DELETE FROM hidden_inventory_alerts WHERE channel=? AND location=? AND sku=?",
            (channel, location, sku),
        )
        conn.commit()
    finally:
        conn.close()


def add_hidden_sku(db_path: str, sku: str) -> None:
    sku = sku.strip()
    if not sku:
        raise ValueError("sku is required")
    conn = get_db(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS hidden_skus (sku TEXT PRIMARY KEY)")
        conn.execute("INSERT OR IGNORE INTO hidden_skus (sku) VALUES (?)", (sku,))
        conn.commit()
    finally:
        conn.close()


def remove_hidden_sku(db_path: str, sku: str) -> None:
    conn = get_db(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS hidden_skus (sku TEXT PRIMARY KEY)")
        conn.execute("DELETE FROM hidden_skus WHERE sku=?", (sku,))
        conn.commit()
    finally:
        conn.close()


def _avg_inventory_daily(
    conn: sqlite3.Connection,
    sku: str,
    channel: str | None,
    location: str | None,
    days: int,
) -> float | None:
    filters = ["sku=?"]
    params: list = [sku]
    if channel and channel != "all":
        filters.append("channel=?")
        params.append(channel)
    if location and location != "all":
        filters.append("location=?")
        params.append(location)

    where_sql = " AND ".join(filters)
    latest = conn.execute(f"SELECT MAX(date) as date FROM daily_inventory WHERE {where_sql}", tuple(params)).fetchone()
    if not latest or not latest["date"]:
        return None

    latest_date = date.fromisoformat(latest["date"])
    start = (latest_date - timedelta(days=days)).isoformat()
    rows = conn.execute(
        f"""
        SELECT date, SUM(on_hand) as on_hand
        FROM daily_inventory
        WHERE {where_sql} AND date>=?
        GROUP BY date
        ORDER BY date
        """,
        tuple([*params, start]),
    ).fetchall()
    if len(rows) < 2:
        return None

    consumed = 0
    previous = rows[0]["on_hand"]
    for row in rows[1:]:
        current = row["on_hand"]
        if previous is not None and current is not None and current < previous:
            consumed += previous - current
        previous = current
    if consumed <= 0:
        return None
    return consumed / days


def _latest_inventory_rows(conn: sqlite3.Connection, channel: str = "all", location: str = "all") -> list[sqlite3.Row]:
    filters = []
    params = []
    if channel != "all":
        filters.append("di.channel=?")
        params.append(channel)
    if location != "all":
        filters.append("di.location=?")
        params.append(location)
    where_sql = " AND ".join(filters)
    where_clause = f"AND {where_sql}" if where_sql else ""
    return conn.execute(
        f"""
        WITH channel_latest AS (
            SELECT channel, MAX(date) as latest_date
            FROM daily_inventory
            GROUP BY channel
        ),
        ranked AS (
            SELECT di.sku, di.channel, di.location, di.on_hand, di.inbound, di.date, di.updated_at,
                   cl.latest_date,
                   ROW_NUMBER() OVER (
                       PARTITION BY di.sku, di.channel, di.location
                       ORDER BY di.date DESC, di.updated_at DESC
                   ) as rn
            FROM daily_inventory di
            JOIN channel_latest cl ON cl.channel=di.channel
            WHERE TRIM(di.sku) != ''
              {where_clause}
              AND di.date >= date(cl.latest_date, ?)
              AND di.sku IN (""" + LATEST_PHYSICAL_SKUS_SQL + """)
        )
        SELECT sku, channel, location, on_hand, inbound, date
        FROM ranked
        WHERE rn=1
        ORDER BY location, channel, sku
        """,
        tuple([*params, f"-{RECENT_INVENTORY_DAYS} days", PHYSICAL_PRODUCT_TYPE]),
    ).fetchall()


def _inventory_rows(conn: sqlite3.Connection, channel: str = "all", location: str = "all") -> list[dict]:
    physical_skus = _latest_physical_skus(conn)
    rows = []
    for row in _latest_inventory_rows(conn, channel, location):
        sku = row["sku"]
        if sku not in physical_skus or sku in NON_PHYSICAL_SKUS:
            continue
        avg7 = _avg_inventory_daily(conn, sku, row["channel"], row["location"] or "", 7)
        avg30 = _avg_inventory_daily(conn, sku, row["channel"], row["location"] or "", DEFAULT_BASIS_DAYS)
        on_hand = row["on_hand"] or 0
        inbound = row["inbound"] or 0
        available = on_hand + inbound
        days_remaining_7d = int(on_hand / avg7) if avg7 and avg7 > 0 else None
        days_remaining = int(available / avg30) if avg30 and avg30 > 0 else None
        if avg7 is None and avg30 is None:
            status = "no-sales"
        elif days_remaining_7d is not None and days_remaining_7d < 14:
            status = "critical"
        elif days_remaining_7d is not None and days_remaining_7d < 30:
            status = "warning"
        else:
            status = "ok"
        rows.append(
            {
                "sku": sku,
                "channel": row["channel"],
                "location": row["location"] or "",
                "on_hand": on_hand,
                "inbound": inbound,
                "available_with_inbound": available,
                "avg_daily_7d": round(avg7, 2) if avg7 else None,
                "avg_daily_30d": round(avg30, 2) if avg30 else None,
                "days_remaining_7d": days_remaining_7d,
                "days_remaining_30d": days_remaining,
                "stockout_date_7d": (date.today() + timedelta(days=days_remaining_7d)).isoformat() if days_remaining_7d is not None else None,
                "stockout_date_30d": (date.today() + timedelta(days=days_remaining)).isoformat() if days_remaining is not None else None,
                "status": status,
            }
        )
    return rows


def _revenue_per_unit(conn: sqlite3.Connection, days: int) -> dict[str, float]:
    latest = conn.execute("SELECT MAX(date) as latest_date FROM daily_sales").fetchone()
    if not latest or not latest["latest_date"]:
        return {}
    end = date.fromisoformat(latest["latest_date"])
    start = end - timedelta(days=days - 1)
    rows = conn.execute(
        """
        SELECT sku, SUM(revenue) as revenue, SUM(units) as units
        FROM daily_sales
        WHERE date BETWEEN ? AND ?
          AND product_type=?
          AND sku NOT IN ({excluded})
        GROUP BY sku
        """.format(excluded=", ".join("?" for _ in NON_PHYSICAL_SKUS)),
        tuple([start.isoformat(), end.isoformat(), PHYSICAL_PRODUCT_TYPE, *sorted(NON_PHYSICAL_SKUS)]),
    ).fetchall()
    out = {}
    for row in rows:
        units = row["units"] or 0
        out[row["sku"]] = (row["revenue"] or 0) / units if units else 0
    return out


def _freshness(conn: sqlite3.Connection) -> list[dict]:
    global_row = conn.execute("SELECT MAX(date) as latest_date FROM daily_sales").fetchone()
    latest = global_row["latest_date"] if global_row else None
    rows = conn.execute(
        "SELECT channel, MAX(date) as latest_date FROM daily_sales GROUP BY channel ORDER BY channel"
    ).fetchall()
    out = []
    for row in rows:
        days_lag = None
        if latest and row["latest_date"]:
            days_lag = (date.fromisoformat(latest) - date.fromisoformat(row["latest_date"])).days
        out.append(
            {
                "channel": row["channel"],
                "latest_date": row["latest_date"],
                "days_lag": days_lag,
                "status": "stale" if days_lag is not None and days_lag > 0 else "current",
            }
        )
    return out


def _stockout_action(row: dict, days: int) -> tuple[str, str]:
    status = row.get("status")
    days_remaining = row.get("days_remaining_30d")
    reorder_units = row.get("reorder_units") or 0
    inbound = row.get("inbound") or 0
    if status == "critical":
        return "critical", "Reorder now" if reorder_units > 0 else "Monitor critical inventory"
    if days_remaining is not None and days_remaining <= 14 and reorder_units > 0:
        return "critical", "Reorder now"
    if status == "warning":
        if inbound > 0:
            return "warning", "Expedite inbound"
        if reorder_units > 0:
            return "warning", "Plan reorder"
        return "warning", "Monitor warning inventory"
    if days_remaining is not None and days_remaining <= days and inbound > 0:
        return "warning", "Expedite inbound"
    if reorder_units > 0:
        return "warning", "Plan reorder"
    return "watch", "Monitor"


def api_inventory_alerts(db_path: str, days: int = DEFAULT_ALERT_DAYS, show_hidden: bool = False) -> dict:
    days = max(1, min(int(days), 366))
    conn = get_db(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS hidden_skus (sku TEXT PRIMARY KEY)")
        _ensure_hidden_alerts_table(conn)
        hidden_alert_set = {
            (row["channel"], row["location"], row["sku"])
            for row in conn.execute("SELECT channel, location, sku FROM hidden_inventory_alerts")
        }
        revenue_per_unit = _revenue_per_unit(conn, DEFAULT_BASIS_DAYS)
        rows = _inventory_rows(conn)
        action_items = []
        for row in rows:
            alert_key = (row["channel"], row["location"], row["sku"])
            hidden = alert_key in hidden_alert_set
            if hidden and not show_hidden:
                continue
            avg = row.get("avg_daily_30d")
            days_remaining = row.get("days_remaining_30d")
            is_warning_level = row.get("status") in {"critical", "warning"}
            is_in_alert_window = bool(avg and days_remaining is not None and days_remaining <= days)
            if not is_warning_level and not is_in_alert_window:
                continue
            projected_demand = (avg or 0) * days
            shortage = max(0, round(projected_demand - (row.get("on_hand") or 0) - (row.get("inbound") or 0)))
            if (row.get("inbound") or 0) > 0 and shortage <= 0:
                continue
            reorder_units = max(0, round(projected_demand))
            lost_revenue = round(shortage * revenue_per_unit.get(row["sku"], 0), 2)
            item = {
                **row,
                "product_type": PHYSICAL_PRODUCT_TYPE,
                "sales_rate_source": "location_inventory",
                "hidden": hidden,
                "reorder_units": reorder_units,
                "lost_revenue": lost_revenue,
            }
            priority, action = _stockout_action(item, days)
            action_items.append({**item, "priority": priority, "action": action})

        priority_order = {"critical": 0, "warning": 1, "watch": 2}
        action_items.sort(key=lambda row: (priority_order.get(row["priority"], 9), row["days_remaining_30d"], row["channel"], row["location"], row["sku"]))
        stockout_risks = [{key: row[key] for key in row if key not in {"priority", "action"}} for row in action_items]
        basis = _basis_range(conn, DEFAULT_BASIS_DAYS)
        return {
            "period_days": days,
            "basis_days": DEFAULT_BASIS_DAYS,
            "basis_start_date": basis[0],
            "basis_end_date": basis[1],
            "currency": _currency(conn),
            "show_hidden": show_hidden,
            "hidden_alerts": [
                {"channel": channel, "location": location, "sku": sku}
                for channel, location, sku in sorted(hidden_alert_set)
            ],
            "freshness": _freshness(conn),
            "stockout_risks": stockout_risks,
            "action_items": action_items,
            "stockout_risk_count": len(stockout_risks),
            "reorder_units": sum(row["reorder_units"] for row in stockout_risks),
            "lost_revenue": round(sum(row["lost_revenue"] for row in stockout_risks), 2),
        }
    finally:
        conn.close()


def _basis_range(conn: sqlite3.Connection, days: int) -> tuple[str | None, str | None]:
    row = conn.execute("SELECT MAX(date) as latest_date FROM daily_sales").fetchone()
    if not row or not row["latest_date"]:
        return None, None
    end = date.fromisoformat(row["latest_date"])
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _currency(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT DISTINCT currency FROM daily_sales WHERE currency IS NOT NULL AND currency != '' ORDER BY currency"
    ).fetchall()
    currencies = [row["currency"] for row in rows]
    return currencies[0] if len(currencies) == 1 else ("mixed" if currencies else "USD")


def format_alerts_json(data: dict) -> str:
    return json.dumps(data, indent=2) + "\n"


def format_alerts_csv(data: dict) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["priority", "action", "channel", "location", "sku", "on_hand", "inbound", "available_with_inbound", "avg_daily_30d", "days_left", "reorder_units", "stockout_date", "lost_revenue"])
    for row in data.get("action_items", []):
        writer.writerow([
            row["priority"],
            row["action"],
            row["channel"],
            row["location"],
            row["sku"],
            row["on_hand"],
            row["inbound"],
            row["available_with_inbound"],
            row["avg_daily_30d"],
            row["days_remaining_30d"],
            row["reorder_units"],
            row["stockout_date_30d"],
            row["lost_revenue"],
        ])
    return out.getvalue()


def format_alerts_slack(data: dict) -> str:
    rows = data.get("action_items", [])
    days = data.get("period_days", DEFAULT_ALERT_DAYS)
    basis_start = data.get("basis_start_date") or "unknown"
    basis_end = data.get("basis_end_date") or "unknown"
    lines = [
        f"*Inventory Alerts* ({days}-day window)",
        f"_Sales basis: {basis_start} to {basis_end}_",
        "",
    ]
    if not rows:
        lines.append("No active inventory alerts.")
        return "\n".join(lines) + "\n"

    reorder_units = data.get("reorder_units", 0)
    lines.append(f"*{len(rows)} active alerts* | 30-day reorder {reorder_units:,} units")
    lines.append("")
    for row in rows:
        channel = str(row["channel"]).title()
        location = row["location"] or "-"
        lines.append(
            f"- *{row['sku']}* ({channel} / {location}) - "
            f"{row['days_remaining_30d']} days left, {row['on_hand']:,} on hand, "
            f"{row['inbound']:,} inbound, 30-day reorder {row['reorder_units']:,}"
        )
    return "\n".join(lines) + "\n"


def format_alerts_table(data: dict) -> str:
    rows = data.get("action_items", [])
    if not rows:
        return "No inventory alerts found.\n"
    headers = ["Priority", "Action", "Channel", "Location", "SKU", "On Hand", "Inbound", "Available", "Avg/Day", "Days", "Reorder", "Stockout", "Lost Rev"]
    body = [
        [
            row["priority"],
            row["action"],
            row["channel"],
            row["location"] or "-",
            row["sku"],
            row["on_hand"],
            row["inbound"],
            row["available_with_inbound"],
            row["avg_daily_30d"],
            row["days_remaining_30d"],
            row["reorder_units"],
            row["stockout_date_30d"],
            f"{row['lost_revenue']:.2f}",
        ]
        for row in rows
    ]
    widths = [len(header) for header in headers]
    for row in body:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(str(value)))
    lines = []
    lines.append("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    lines.append("  ".join("-" * width for width in widths))
    for row in body:
        lines.append("  ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))
    return "\n".join(lines) + "\n"
