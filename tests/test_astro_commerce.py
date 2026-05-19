import gzip
import io
import importlib.machinery
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name):
    path = SCRIPTS / name
    module_name = name.replace("-", "_") + "_under_test"
    loader = importlib.machinery.SourceFileLoader(module_name, str(path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Response:
    def __init__(self, status_code=200, payload=None, text="", content=b"", headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self._payload


class SharedHelperTests(unittest.TestCase):
    def test_sales_aggregation_and_csv_totals(self):
        group = load_script("ecom_group.py")
        rows = [
            {"date": "2026-05-13", "sku": "luna-usb-c", "quantity": 2, "amount": 199.98, "currency": "USD"},
            {"date": "2026-05-13", "sku": "luna-usb-c", "quantity": 1, "amount": 99.99, "currency": "USD"},
            {"date": "2026-05-14", "sku": "studio-yearly", "quantity": 3, "amount": 239.97, "currency": "USD"},
        ]

        by_sku_day = group.aggregate_sales(rows, "sku-day")
        self.assertEqual(by_sku_day[0]["quantity"], 3)
        self.assertAlmostEqual(by_sku_day[0]["amount"], 299.97)

        by_sku = group.aggregate_sales(rows, "sku")
        self.assertEqual([r["sku"] for r in by_sku], ["luna-usb-c", "studio-yearly"])

        csv_text = group.format_sales_csv(by_sku_day, "sku-day")
        self.assertIn("TOTAL,,6,539.94", csv_text)

    def test_table_formatters_handle_empty_sales_and_inventory(self):
        table = load_script("ecom_table.py")
        self.assertEqual(table.format_sales_table([]), "No data found.")
        self.assertEqual(table.format_inventory_table([]), "No inventory data found.")


class AstroCommerceCliTests(unittest.TestCase):
    def test_global_db_override_sets_db_for_command(self):
        astro = load_script("astro-commerce")
        old_run_command = astro.run_command
        old_db = os.environ.get("ECOM_DB_PATH")
        old_marker = os.environ.get("ASTRO_COMMERCE_DB_OVERRIDE")
        captured = {}

        def fake_run_command(command, args, demo=False):
            captured["command"] = command
            captured["args"] = args
            captured["demo"] = demo
            captured["db"] = os.environ.get("ECOM_DB_PATH")
            captured["marker"] = os.environ.get("ASTRO_COMMERCE_DB_OVERRIDE")
            return 0

        try:
            astro.run_command = fake_run_command
            rc = astro.main(["--db", "/tmp/astro-commerce-test.db", "sync", "run", "--days", "1"])
        finally:
            astro.run_command = old_run_command
            if old_db is None:
                os.environ.pop("ECOM_DB_PATH", None)
            else:
                os.environ["ECOM_DB_PATH"] = old_db
            if old_marker is None:
                os.environ.pop("ASTRO_COMMERCE_DB_OVERRIDE", None)
            else:
                os.environ["ASTRO_COMMERCE_DB_OVERRIDE"] = old_marker

        self.assertEqual(rc, 0)
        self.assertEqual(captured["command"], "sync-sales-db")
        self.assertEqual(captured["args"], ["--days", "1"])
        self.assertEqual(captured["db"], "/tmp/astro-commerce-test.db")
        self.assertEqual(captured["marker"], "1")

    def test_demo_sync_respects_explicit_global_db_override(self):
        astro = load_script("astro-commerce")
        old_subprocess_run = astro.subprocess.run
        old_db = os.environ.get("ECOM_DB_PATH")
        old_marker = os.environ.get("ASTRO_COMMERCE_DB_OVERRIDE")
        captured = {}

        class Proc:
            returncode = 0
            stdout = ""

        def fake_subprocess_run(argv, *args, **kwargs):
            captured["argv"] = argv
            return Proc()

        try:
            os.environ["ECOM_DB_PATH"] = "/tmp/astro-commerce-demo-test.db"
            os.environ["ASTRO_COMMERCE_DB_OVERRIDE"] = "1"
            astro.subprocess.run = fake_subprocess_run
            rc = astro.run_command("sync-sales-db", ["--days", "1"], demo=True)
        finally:
            astro.subprocess.run = old_subprocess_run
            if old_db is None:
                os.environ.pop("ECOM_DB_PATH", None)
            else:
                os.environ["ECOM_DB_PATH"] = old_db
            if old_marker is None:
                os.environ.pop("ASTRO_COMMERCE_DB_OVERRIDE", None)
            else:
                os.environ["ASTRO_COMMERCE_DB_OVERRIDE"] = old_marker

        self.assertEqual(rc, 0)
        self.assertIn("--demo", captured["argv"])
        self.assertNotIn("--db", captured["argv"][1:])

    def test_inventory_alerts_cli_outputs_location_calculated_actions(self):
        astro = load_script("astro-commerce")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sales.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.executescript("""
                    CREATE TABLE daily_sales (
                        date TEXT, channel TEXT, sku TEXT, units INTEGER, revenue REAL, currency TEXT,
                        product_type TEXT DEFAULT 'physical', updated_at TEXT,
                        PRIMARY KEY (date, channel, sku)
                    );
                    CREATE TABLE daily_inventory (
                        date TEXT, channel TEXT, sku TEXT, location TEXT DEFAULT '', on_hand INTEGER,
                        inbound INTEGER DEFAULT 0, updated_at TEXT,
                        PRIMARY KEY (date, channel, sku, location)
                    );
                    CREATE TABLE hidden_skus (sku TEXT PRIMARY KEY);
                """)
                latest = date.today() - timedelta(days=1)
                for offset in range(0, 30):
                    dt = (latest - timedelta(days=offset)).isoformat()
                    conn.execute(
                        "INSERT INTO daily_sales VALUES (?, 'shopify', 'location-risk-sku', 3, 150.0, 'USD', 'physical', ?)",
                        (dt, dt),
                    )
                conn.execute(
                    "INSERT INTO daily_inventory VALUES (?, 'shopify', 'location-risk-sku', 'ITB', 60, 0, ?)",
                    ((latest - timedelta(days=30)).isoformat(), (latest - timedelta(days=30)).isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_inventory VALUES (?, 'shopify', 'location-risk-sku', 'ITB', 10, 0, ?)",
                    (latest.isoformat(), latest.isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_inventory VALUES (?, 'shopify', 'location-risk-sku', 'Huboo UK', 60, 0, ?)",
                    ((latest - timedelta(days=30)).isoformat(), (latest - timedelta(days=30)).isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_inventory VALUES (?, 'shopify', 'location-risk-sku', 'Huboo UK', 10, 0, ?)",
                    (latest.isoformat(), latest.isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_sales VALUES (?, 'shopify', 'inbound-covered-sku', 3, 150.0, 'USD', 'physical', ?)",
                    (latest.isoformat(), latest.isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_inventory VALUES (?, 'shopify', 'inbound-covered-sku', 'ITB', 60, 0, ?)",
                    ((latest - timedelta(days=30)).isoformat(), (latest - timedelta(days=30)).isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_inventory VALUES (?, 'shopify', 'inbound-covered-sku', 'ITB', 10, 50, ?)",
                    (latest.isoformat(), latest.isoformat()),
                )
                conn.commit()
            finally:
                conn.close()

            result = subprocess.run(
                [str(SCRIPTS / "astro-commerce"), "--db", str(db_path), "inventory-alerts", "--output", "json"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["stockout_risk_count"], 2)
            self.assertNotIn("inbound-covered-sku", {row["sku"] for row in data["action_items"]})
            row = next(row for row in data["action_items"] if row["location"] == "ITB")
            self.assertEqual(row["sales_rate_source"], "location_inventory")
            self.assertEqual(row["avg_daily_30d"], 1.67)
            self.assertEqual(row["days_remaining_30d"], 6)
            self.assertEqual(row["reorder_units"], 50)

            table_result = subprocess.run(
                [str(SCRIPTS / "astro-commerce"), "--db", str(db_path), "inventory-alerts"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            self.assertEqual(table_result.returncode, 0, table_result.stderr)
            self.assertNotIn("inbound-covered-sku", table_result.stdout)
            self.assertIn("location-risk-sku", table_result.stdout)

            slack_result = subprocess.run(
                [str(SCRIPTS / "astro-commerce"), "--db", str(db_path), "inventory-alerts", "--output", "slack"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            self.assertEqual(slack_result.returncode, 0, slack_result.stderr)
            self.assertIn("*Inventory Alerts* (30-day window)", slack_result.stdout)
            self.assertIn("*2 active alerts*", slack_result.stdout)
            self.assertIn("30-day reorder", slack_result.stdout)
            self.assertIn("30-day reorder 100 units", slack_result.stdout)
            self.assertNotIn("lost revenue", slack_result.stdout.lower())
            self.assertIn("location-risk-sku", slack_result.stdout)
            self.assertNotIn("inbound-covered-sku", slack_result.stdout)

            hidden_result = subprocess.run(
                [
                    str(SCRIPTS / "astro-commerce"),
                    "--db",
                    str(db_path),
                    "inventory-alerts",
                    "--channel",
                    "shopify",
                    "--location",
                    "ITB",
                    "--hide-sku",
                    "location-risk-sku",
                    "--output",
                    "json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            self.assertEqual(hidden_result.returncode, 0, hidden_result.stderr)
            hidden_data = json.loads(hidden_result.stdout)
            self.assertEqual(hidden_data["stockout_risk_count"], 1)
            self.assertEqual(hidden_data["action_items"][0]["location"], "Huboo UK")
            self.assertEqual(hidden_data["hidden_alerts"], [{"channel": "shopify", "location": "ITB", "sku": "location-risk-sku"}])

            show_hidden_result = subprocess.run(
                [str(SCRIPTS / "astro-commerce"), "--db", str(db_path), "inventory-alerts", "--show-hidden", "--output", "json"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            self.assertEqual(show_hidden_result.returncode, 0, show_hidden_result.stderr)
            show_hidden_data = json.loads(show_hidden_result.stdout)
            self.assertEqual(show_hidden_data["stockout_risk_count"], 2)
            self.assertTrue(next(row for row in show_hidden_data["action_items"] if row["location"] == "ITB")["hidden"])
            self.assertFalse(next(row for row in show_hidden_data["action_items"] if row["location"] == "Huboo UK")["hidden"])

    def test_inventory_alerts_cli_includes_warning_level_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sales.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.executescript("""
                    CREATE TABLE daily_sales (
                        date TEXT, channel TEXT, sku TEXT, units INTEGER, revenue REAL, currency TEXT,
                        product_type TEXT DEFAULT 'physical', updated_at TEXT,
                        PRIMARY KEY (date, channel, sku)
                    );
                    CREATE TABLE daily_inventory (
                        date TEXT, channel TEXT, sku TEXT, location TEXT DEFAULT '', on_hand INTEGER,
                        inbound INTEGER DEFAULT 0, updated_at TEXT,
                        PRIMARY KEY (date, channel, sku, location)
                    );
                """)
                latest = date.today() - timedelta(days=1)
                conn.execute(
                    "INSERT INTO daily_sales VALUES (?, 'shopify', 'warning-sku', 1, 50.0, 'USD', 'physical', ?)",
                    (latest.isoformat(), latest.isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_inventory VALUES (?, 'shopify', 'warning-sku', 'ITB', 54, 0, ?)",
                    ((latest - timedelta(days=7)).isoformat(), (latest - timedelta(days=7)).isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_inventory VALUES (?, 'shopify', 'warning-sku', 'ITB', 40, 0, ?)",
                    (latest.isoformat(), latest.isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_sales VALUES (?, 'shopify', 'inbound-covered-warning-sku', 1, 50.0, 'USD', 'physical', ?)",
                    (latest.isoformat(), latest.isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_inventory VALUES (?, 'shopify', 'inbound-covered-warning-sku', 'ITB', 54, 0, ?)",
                    ((latest - timedelta(days=7)).isoformat(), (latest - timedelta(days=7)).isoformat()),
                )
                conn.execute(
                    "INSERT INTO daily_inventory VALUES (?, 'shopify', 'inbound-covered-warning-sku', 'ITB', 40, 50, ?)",
                    (latest.isoformat(), latest.isoformat()),
                )
                conn.commit()
            finally:
                conn.close()

            result = subprocess.run(
                [str(SCRIPTS / "astro-commerce"), "--db", str(db_path), "inventory-alerts", "--output", "json"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["stockout_risk_count"], 1)
        self.assertNotIn("inbound-covered-warning-sku", {row["sku"] for row in data["action_items"]})
        row = data["action_items"][0]
        self.assertEqual(row["sku"], "warning-sku")
        self.assertEqual(row["priority"], "warning")
        self.assertEqual(row["status"], "warning")
        self.assertEqual(row["days_remaining_7d"], 20)
        self.assertGreater(row["days_remaining_30d"], 30)


class SourceScriptTests(unittest.TestCase):
    def test_shopify_sales_extracts_store_date_and_records_payload(self):
        shopify = load_script("shopify-sales")
        orders = [
            {
                "id": 123,
                "created_at": "2026-05-15T01:30:00+00:00",
                "currency": "USD",
                "line_items": [
                    {"sku": "LUNA-USB-C", "quantity": 2, "price": "89.50"},
                    {"sku": "ASTROPAD-STUDIO", "quantity": 1, "price": "99.99"},
                ],
            }
        ]

        rows = shopify.extract_line_items(orders, "luna")
        self.assertEqual(rows, [
            {
                "date": "2026-05-14",
                "sku": "LUNA-USB-C",
                "quantity": 2,
                "amount": 179.0,
                "currency": "USD",
                "source_order_id": "123",
            }
        ])

        payload = json.loads(shopify.format_records_payload(rows, {"store": "example.myshopify.com"}, "2026-05-14", "2026-05-14"))
        self.assertEqual(payload["schema"], "astro.commerce.sales.v1")
        self.assertEqual(payload["source"], "shopify")
        self.assertEqual(payload["summary"]["total_gross_revenue"], 179.0)

    def test_amazon_sales_parses_json_and_tsv_and_filters_aggregate_rows_from_records(self):
        amazon = load_script("amazon-sales")
        report = {
            "salesAndTrafficByDate": [
                {"date": "2026-05-13", "salesByDate": {"unitsOrdered": 4, "orderedProductSales": {"amount": 399.96, "currencyCode": "USD"}}}
            ],
            "salesAndTrafficByAsin": [
                {"sku": "LUNA-HDMI", "salesByAsin": {"unitsOrdered": 2, "orderedProductSales": {"amount": 199.98, "currencyCode": "USD"}}},
                {"sku": "OTHER", "salesByAsin": {"unitsOrdered": 1, "orderedProductSales": {"amount": 1, "currencyCode": "USD"}}},
            ],
        }

        by_day = amazon.parse_report(json.dumps(report), None, "day")
        self.assertEqual(by_day[0]["sku"], "ALL")
        by_sku = amazon.parse_report(json.dumps(report), "luna", "sku")
        self.assertEqual(by_sku, [{"date": "all", "sku": "LUNA-HDMI", "quantity": 2, "amount": 199.98, "currency": "USD"}])

        tsv = "purchase-date\tsku\tquantity-purchased\titem-price\tcurrency\n2026-05-14T12:00:00Z\tLUNA-USB-C\t3\t299.97\tUSD\n"
        self.assertEqual(amazon.parse_report(tsv, "usb", "sku-day")[0]["quantity"], 3)

        payload = json.loads(amazon.format_records_payload([by_day[0], by_sku[0]], {"marketplace_id": "ATVPDKIKX0DER"}, "2026-05-13", "2026-05-13"))
        self.assertEqual(len(payload["records"]), 1)
        self.assertEqual(payload["records"][0]["sku"], "LUNA-HDMI")

    def test_stripe_sales_maps_prices_metadata_descriptions_and_filters_refunds(self):
        stripe = load_script("stripe-sales")
        old_build = stripe.build_price_map
        old_map = dict(stripe._amount_to_sku)
        stripe.build_price_map = lambda cfg: None
        stripe._amount_to_sku = {1200: "workbench-monthly"}
        try:
            charges = [
                {"status": "succeeded", "refunded": False, "created": 1778800000, "amount": 1200, "currency": "usd", "metadata": {}},
                {"status": "succeeded", "refunded": False, "created": 1778800000, "amount": 9900, "currency": "usd", "metadata": {"product": "Workbench Annual"}},
                {"status": "succeeded", "refunded": True, "created": 1778800000, "amount": 1200, "currency": "usd", "metadata": {}},
                {"status": "failed", "created": 1778800000, "amount": 1200, "currency": "usd", "metadata": {}},
            ]
            rows = stripe.extract_line_items({"api_key": "sk_test"}, charges, "workbench")
        finally:
            stripe.build_price_map = old_build
            stripe._amount_to_sku = old_map

        self.assertEqual([r["sku"] for r in rows], ["workbench-monthly", "workbench-yearly"])
        payload = json.loads(stripe.format_records_payload(rows, "stripe", "2026-05-13", "2026-05-14"))
        self.assertEqual(payload["source"], "stripe")
        self.assertEqual(payload["summary"]["total_units"], 2)

    def test_fastspring_sales_maps_exact_partial_and_filtered_products(self):
        fastspring = load_script("fastspring-sales")
        report_rows = [
            {"product_path": "astropad-studio", "transaction_date": "2026-05-13", "income_in_usd": "79.99", "product_units": "1"},
            {"product_path": "/store/astropad-studio-monthly-no-trial", "transaction_date": "2026-05-13", "income_in_usd": "12.99", "product_units": "2"},
            {"product_path": "untracked", "transaction_date": "2026-05-13", "income_in_usd": "999", "product_units": "1"},
        ]

        rows = fastspring.map_to_sales_rows(report_rows, None)
        self.assertEqual([r["sku"] for r in rows], ["fs-studio-yearly", "fs-studio-monthly"])
        filtered = fastspring.map_to_sales_rows(report_rows, "monthly")
        self.assertEqual(len(filtered), 1)

    def test_appstore_sales_parses_gzipped_report_and_converts_known_skus(self):
        appstore = load_script("appstore-sales")
        old_api_request = appstore.api_request
        old_to_usd = appstore.to_usd
        tsv = (
            "Begin Date\tSKU\tUnits\tCustomer Price\tCustomer Currency\n"
            "05/13/2026\tcom.astropad.studio.yearly\t2\t99.99\tUSD\n"
            "05/13/2026\tunknown.product\t1\t999.00\tUSD\n"
        )
        appstore.api_request = lambda cfg, endpoint, params=None: Response(content=gzip.compress(tsv.encode("utf-8")))
        appstore.to_usd = lambda amount, currency: amount
        try:
            rows = appstore.fetch_daily_report({"private_key_path": "unused"}, "2026-05-13", "12345")
        finally:
            appstore.api_request = old_api_request
            appstore.to_usd = old_to_usd

        self.assertEqual(rows, [{"date": "2026-05-13", "sku": "studio-yearly", "quantity": 2, "amount": 199.98, "currency": "USD"}])
        self.assertEqual(appstore.normalize_sku("com.astropad.rockplanner.year"), "rock-planner-yearly")

    def test_appstore_sales_converts_common_storefront_currencies(self):
        appstore = load_script("appstore-sales")
        old_fetch_live_rates = appstore._fetch_live_rates
        old_fx_cache = appstore._fx_cache.copy()
        appstore._fx_cache.clear()
        appstore._fx_cache.update(appstore.FALLBACK_FX_RATES)
        appstore._fetch_live_rates = lambda: None
        try:
            self.assertEqual(appstore.to_usd(5600, "PKR"), 20.16)
            self.assertEqual(appstore.to_usd(54.99, "QAR"), 15.11)
        finally:
            appstore._fetch_live_rates = old_fetch_live_rates
            appstore._fx_cache.clear()
            appstore._fx_cache.update(old_fx_cache)

    def test_inventory_scripts_emit_sync_records(self):
        shopify_inventory = load_script("shopify-inventory")
        amazon_inventory = load_script("amazon-inventory")

        shopify_payload = json.loads(shopify_inventory.format_records_payload([
            {"sku": "LUNA-USB-C", "location": "ITB", "on_hand": 7},
            {"sku": "LUNA-HDMI", "location": "Huboo UK", "on_hand": 3, "inbound": 4},
        ], {"store": "example.myshopify.com"}))
        self.assertEqual(shopify_payload["summary"], {"total_on_hand": 10, "total_inbound": 4})

        amazon_payload = json.loads(amazon_inventory.format_records_payload([
            {"sku": "LUNA-USB-C", "location": "US", "on_hand": 5, "inbound": 9},
        ], {"marketplace_id": "ATVPDKIKX0DER", "seller_id": "seller"}))
        self.assertEqual(amazon_payload["source"], "amazon")
        self.assertEqual(amazon_payload["records"][0]["meta"]["marketplace_id"], "ATVPDKIKX0DER")


class RouterAndCliTests(unittest.TestCase):
    def test_astro_commerce_routes_channel_resource_and_validates_all_channel_output(self):
        cli = load_script("astro-commerce")
        calls = []
        old_run_command = cli.run_command
        old_enabled = cli._enabled_or_default
        cli.run_command = lambda command, args, demo=False: calls.append((command, args, demo)) or 0
        cli._enabled_or_default = lambda candidates: ["shopify", "amazon"]
        try:
            self.assertEqual(cli.main(["shopify", "sales", "--days", "7"]), 0)
            self.assertEqual(calls[-1], ("shopify-sales", ["--days", "7"], False))

            self.assertEqual(cli.main(["--demo", "inventory", "--channel", "all"]), 0)
            self.assertEqual(calls[-2:], [
                ("shopify-inventory", [], True),
                ("amazon-inventory", [], True),
            ])

            self.assertEqual(cli.main(["sales", "--channel", "all", "--output", "json"]), 2)
        finally:
            cli.run_command = old_run_command
            cli._enabled_or_default = old_enabled

    def test_demo_transform_preserves_labels_and_recomputes_json_summary(self):
        cli = load_script("astro-commerce")
        original = json.dumps({
            "records": [
                {"date": "2026-05-13", "sku": "LUNA-USB-C", "quantity": 2, "gross_revenue": 199.98},
                {"date": "2026-05-14", "sku": "LUNA-HDMI", "quantity": 1, "gross_revenue": 99.99},
            ],
            "summary": {"total_units": 3, "total_gross_revenue": 299.97},
        })
        transformed = json.loads(cli.demo_transform_output(original))
        self.assertEqual([r["sku"] for r in transformed["records"]], ["LUNA-USB-C", "LUNA-HDMI"])
        self.assertEqual(transformed["summary"]["total_units"], sum(r["quantity"] for r in transformed["records"]))
        self.assertEqual(transformed["summary"]["total_gross_revenue"], round(sum(r["gross_revenue"] for r in transformed["records"]), 2))

    def test_cli_help_and_command_list_are_available_without_credentials(self):
        help_result = subprocess.run([str(SCRIPTS / "astro-commerce"), "--help"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("astro-commerce", help_result.stdout)

        commands_result = subprocess.run([str(SCRIPTS / "astro-commerce"), "commands"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(commands_result.returncode, 0)
        self.assertIn("astro-commerce shopify sales", commands_result.stdout)

    def test_configure_database_initializer_creates_expected_schema(self):
        cli = load_script("astro-commerce")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "shared" / "commerce.db"
            cli._initialize_database(db_path)

            conn = sqlite3.connect(db_path)
            try:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                sales_cols = [row[1] for row in conn.execute("PRAGMA table_info(daily_sales)").fetchall()]
                inventory_cols = [row[1] for row in conn.execute("PRAGMA table_info(daily_inventory)").fetchall()]
            finally:
                conn.close()

        self.assertTrue({"daily_sales", "daily_inventory", "hidden_skus"}.issubset(tables))
        self.assertIn("product_type", sales_cols)
        self.assertIn("location", inventory_cols)

    def test_configure_json_stdin_saves_and_enables_service(self):
        cli = load_script("astro-commerce")
        old_stdin = sys.stdin
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            db_path = config_dir / "sales.db"
            cli.ASTRO_CONFIG_PATH = config_dir / ".astro-commerce.json"
            sys.stdin = io.StringIO(json.dumps({"config": {"api_key": "sk_test_123"}}))
            try:
                rc = cli.configure([
                    "--services",
                    "stripe",
                    "--config-dir",
                    str(config_dir),
                    "--db",
                    str(db_path),
                    "--json-stdin",
                ])
            finally:
                sys.stdin = old_stdin

            self.assertEqual(rc, 0)
            self.assertEqual(json.loads((config_dir / ".stripe-api.json").read_text())["api_key"], "sk_test_123")
            self.assertEqual(json.loads((config_dir / ".astro-commerce.json").read_text())["enabled_services"], ["stripe"])

    def test_configure_print_form_omits_secret_values(self):
        cli = load_script("astro-commerce")
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            cli.ASTRO_CONFIG_PATH = config_dir / ".astro-commerce.json"
            (config_dir / ".stripe-api.json").write_text(json.dumps({"api_key": "sk_test_secret"}))
            form = cli._configure_form_metadata("stripe", config_dir)

        self.assertTrue(form["configured"])
        self.assertTrue(form["fields"][0]["has_value"])
        self.assertNotIn("sk_test_secret", json.dumps(form))


class SyncAndUtilityScriptTests(unittest.TestCase):
    def test_sync_db_writes_sales_and_inventory_rows(self):
        sync = load_script("sync-sales-db")
        old_run_tool = sync.run_tool
        calls = []

        def fake_run_tool(cmd):
            calls.append(cmd)
            if cmd[0].endswith("-sales"):
                return {
                    "schema": "astro.commerce.sales.v1",
                    "source": "shopify",
                    "records": [
                        {"date": "2026-05-13", "sku": "LUNA-USB-C", "quantity": 2, "gross_revenue": 199.98, "currency": "USD"}
                    ],
                }
            if cmd[0].endswith("-inventory"):
                return {
                    "schema": "astro.commerce.inventory.v1",
                    "source": "amazon",
                    "records": [
                        {"sku": "LUNA-USB-C", "location": "US", "on_hand": 10, "inbound": 5}
                    ],
                }
            raise AssertionError(f"unexpected command: {cmd}")

        sync.run_tool = fake_run_tool
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sales.db"
            conn = sync.init_db(str(db_path))
            try:
                self.assertEqual(sync.sync_sales(conn, ["shopify"], "2026-05-13", "2026-05-13"), {"shopify": 1})
                self.assertEqual(sync.sync_inventory(conn, ["amazon"]), {"amazon": 1})
                sales = conn.execute("SELECT date, channel, sku, units, revenue, product_type FROM daily_sales").fetchall()
                inventory = conn.execute("SELECT channel, sku, location, on_hand, inbound FROM daily_inventory").fetchall()
            finally:
                conn.close()
                sync.run_tool = old_run_tool

        self.assertEqual(sales, [("2026-05-13", "shopify", "LUNA-USB-C", 2, 199.98, "physical")])
        self.assertEqual(inventory, [("amazon", "LUNA-USB-C", "US", 10, 5)])
        self.assertTrue(all(cmd[-1] == "records" for cmd in calls))

    def test_sync_main_returns_failure_when_channel_sync_fails(self):
        sync = load_script("sync-sales-db")
        old_run_tool = sync.run_tool
        old_argv = sys.argv[:]
        sync.run_tool = lambda cmd: None

        with tempfile.TemporaryDirectory() as tmp:
            sys.argv = [
                "sync-sales-db",
                "--db",
                str(Path(tmp) / "sales.db"),
                "--channel",
                "amazon",
                "--yesterday",
                "--skip-inventory",
            ]
            try:
                self.assertEqual(sync.main(), 1)
            finally:
                sync.run_tool = old_run_tool
                sys.argv = old_argv

    def test_sync_ingest_payload_writes_canonical_sales_and_inventory(self):
        sync = load_script("sync-sales-db")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sales.db"
            conn = sync.init_db(str(db_path))
            try:
                self.assertEqual(sync.ingest_payload(conn, {
                    "schema": "astro.commerce.sales.v1",
                    "source": "stripe",
                    "records": [
                        {"date": "2026-05-13", "sku": "studio-yearly", "quantity": 1, "gross_revenue": 99.99, "currency": "USD"}
                    ],
                }), 1)
                self.assertEqual(sync.ingest_payload(conn, {
                    "schema": "astro.commerce.inventory.v1",
                    "source": "shopify",
                    "records": [
                        {"sku": "LUNA-HDMI", "location": "ITB", "on_hand": 3, "inbound": 0}
                    ],
                }, inventory_date="2026-05-14"), 1)
                sales = conn.execute("SELECT channel, sku, units, revenue, product_type FROM daily_sales").fetchall()
                inventory = conn.execute("SELECT date, channel, sku, location, on_hand FROM daily_inventory").fetchall()
            finally:
                conn.close()

        self.assertEqual(sales, [("stripe", "studio-yearly", 1, 99.99, "software")])
        self.assertEqual(inventory, [("2026-05-14", "shopify", "LUNA-HDMI", "ITB", 3)])

    def test_csv_graph_helpers_and_png_generation(self):
        chart = load_script("csv-graph")
        self.assertTrue(chart.looks_like_date(["2026-05-13", "2026-05-14", "2026-05-15", "total"]))
        self.assertTrue(chart.is_numeric(["1", "2.50", "bad"]))
        self.assertEqual(chart.parse_numeric("1,234.50"), 1234.5)

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "sales.csv"
            out_path = Path(tmp) / "sales.png"
            csv_path.write_text("Date,Units,Revenue\n2026-05-13,2,199.98\n2026-05-14,1,99.99\nTOTAL,3,299.97\n")
            result = subprocess.run([str(SCRIPTS / "csv-graph"), "--file", str(csv_path), "-o", str(out_path), "--title", "Sales"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out_path.exists())
            self.assertGreater(out_path.stat().st_size, 0)

    def test_installer_copies_public_cli_to_requested_bin_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([str(SCRIPTS / "astro-commerce-install"), "--bin-dir", tmp, "--copy"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            installed = Path(tmp) / "astro-commerce"

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(installed.exists())
            self.assertTrue(os.access(installed, os.X_OK))


if __name__ == "__main__":
    smoke_flags = ("--live", "--channels", "--timeout")
    if any(arg == flag or arg.startswith(f"{flag}=") for arg in sys.argv[1:] for flag in smoke_flags):
        smoke_script = Path(__file__).with_name("test_astro_commerce_smoke.py")
        os.execv(sys.executable, [sys.executable, str(smoke_script), *sys.argv[1:]])
    unittest.main()
