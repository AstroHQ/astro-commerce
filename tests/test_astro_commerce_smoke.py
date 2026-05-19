import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ALL_CHANNELS = {"shopify", "amazon", "stripe", "fastspring", "appstore"}


def _parse_smoke_args():
    smoke_args = {"live": False, "channels": None, "timeout": None}
    cleaned_argv = [sys.argv[0]]
    it = iter(sys.argv[1:])
    for arg in it:
        if arg == "--live":
            smoke_args["live"] = True
        elif arg == "--channels":
            smoke_args["channels"] = next(it)
        elif arg.startswith("--channels="):
            smoke_args["channels"] = arg.split("=", 1)[1]
        elif arg == "--timeout":
            smoke_args["timeout"] = int(next(it))
        elif arg.startswith("--timeout="):
            smoke_args["timeout"] = int(arg.split("=", 1)[1])
        else:
            cleaned_argv.append(arg)
    sys.argv[:] = cleaned_argv
    return smoke_args


SMOKE_ARGS = _parse_smoke_args()
LIVE_SMOKE_ENABLED = (
    SMOKE_ARGS["live"] or os.environ.get("ASTRO_COMMERCE_LIVE_SMOKE", "").lower() in {"1", "true", "yes"}
)
SMOKE_TIMEOUT = SMOKE_ARGS["timeout"] or int(os.environ.get("ASTRO_COMMERCE_SMOKE_TIMEOUT", "240"))


def _env_enabled_channels() -> set[str]:
    raw = (SMOKE_ARGS["channels"] or os.environ.get("ASTRO_COMMERCE_SMOKE_CHANNELS", "all")).strip().lower()
    if not raw or raw == "all":
        return set(ALL_CHANNELS)
    channels = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = channels - ALL_CHANNELS
    if unknown:
        raise SystemExit(f"Unknown smoke test channel(s): {', '.join(sorted(unknown))}")
    return channels


ENABLED_CHANNELS = _env_enabled_channels()


CONFIG_HINTS = {
    "shopify": {
        "files": [ROOT / ".shopify-api.json", Path.home() / ".shopify-api.json"],
        "env_files": ["SHOPIFY_API_CONFIG"],
        "env_groups": [
            ["SHOPIFY_STORE", "SHOPIFY_ACCESS_TOKEN"],
            ["SHOPIFY_STORE", "SHOPIFY_API_KEY", "SHOPIFY_API_SECRET"],
        ],
    },
    "amazon": {
        "files": [ROOT / ".amazon-sp-api.json", Path.home() / ".amazon-sp-api.json"],
        "env_files": ["AMAZON_SP_API_CONFIG"],
        "env_groups": [["SP_API_REFRESH_TOKEN", "SP_API_LWA_APP_ID", "SP_API_LWA_CLIENT_SECRET"]],
    },
    "stripe": {
        "files": [ROOT / ".stripe-api.json", Path.home() / ".stripe-api.json"],
        "env_files": ["STRIPE_API_CONFIG"],
        "env_groups": [["STRIPE_API_KEY"]],
    },
    "fastspring": {
        "files": [ROOT / ".fastspring-api.json", Path.home() / ".fastspring-api.json"],
        "env_files": ["FASTSPRING_API_CONFIG"],
        "env_groups": [],
    },
    "appstore": {
        "files": [ROOT / ".appstore-api.json", Path.home() / ".appstore-api.json"],
        "env_files": ["ASC_API_CONFIG"],
        "env_groups": [["ASC_ISSUER_ID", "ASC_KEY_ID", "ASC_PRIVATE_KEY_PATH"]],
    },
}


SMOKE_CASES = [
    ("shopify-sales", "shopify", "sales", ["shopify", "sales", "--yesterday", "--output", "records"]),
    ("shopify-inventory", "shopify", "inventory", ["shopify", "inventory", "--output", "records"]),
    ("amazon-sales", "amazon", "sales", ["amazon", "sales", "--yesterday", "--output", "records"]),
    ("amazon-inventory", "amazon", "inventory", ["amazon", "inventory", "--output", "records"]),
    ("stripe-sales", "stripe", "sales", ["stripe", "sales", "--yesterday", "--output", "records"]),
    ("fastspring-sales", "fastspring", "sales", ["fastspring", "sales", "--yesterday", "--output", "records"]),
    ("appstore-sales", "appstore", "sales", ["appstore", "sales", "--yesterday", "--output", "records"]),
]


def _path_from_env(var_name: str) -> Path | None:
    value = os.environ.get(var_name)
    if not value:
        return None
    return Path(os.path.expandvars(os.path.expanduser(value)))


def _has_credentials(channel: str) -> bool:
    hints = CONFIG_HINTS[channel]
    if any(path.exists() for path in hints["files"]):
        return True
    if any((path := _path_from_env(var_name)) and path.exists() for var_name in hints["env_files"]):
        return True
    return any(all(os.environ.get(var_name) for var_name in group) for group in hints["env_groups"])


def _resolve_existing_relative_path(path_value: str, bases: list[Path]) -> str:
    path = Path(os.path.expandvars(os.path.expanduser(path_value)))
    if path.is_absolute():
        return str(path)
    for base in bases:
        candidate = base / path
        if candidate.exists():
            return str(candidate)
    return str(path)


def _command_env(channel: str) -> dict[str, str]:
    env = os.environ.copy()
    if channel != "appstore":
        return env

    config_path = _path_from_env("ASC_API_CONFIG")
    config_bases = [ROOT, ROOT.parent, Path.home()]
    if config_path:
        config_bases.insert(0, config_path.parent)
    elif (ROOT.parent / ".appstore-api.json").exists():
        env["ASC_API_CONFIG"] = str(ROOT.parent / ".appstore-api.json")
        config_bases.insert(0, ROOT.parent)

    if env.get("ASC_PRIVATE_KEY_PATH"):
        env["ASC_PRIVATE_KEY_PATH"] = _resolve_existing_relative_path(env["ASC_PRIVATE_KEY_PATH"], config_bases)

    return env


def _parse_json_stdout(result: subprocess.CompletedProcess) -> dict:
    stdout = result.stdout.strip()
    if not stdout:
        raise AssertionError(f"command produced no stdout; stderr was:\n{result.stderr}")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"stdout was not JSON: {exc}\nstdout:\n{stdout}\nstderr:\n{result.stderr}") from exc
    if not isinstance(payload, dict):
        raise AssertionError(f"expected JSON object, got {type(payload).__name__}: {stdout}")
    return payload


@unittest.skipUnless(
    LIVE_SMOKE_ENABLED,
    "pass --live or set ASTRO_COMMERCE_LIVE_SMOKE=1 to run live vendor API smoke tests",
)
class LiveApiSmokeTests(unittest.TestCase):
    """Opt-in tests that authenticate to real commerce APIs through the public CLI."""

    def test_live_api_commands_return_canonical_records_payloads(self):
        for label, channel, resource, args in SMOKE_CASES:
            with self.subTest(label):
                if channel not in ENABLED_CHANNELS:
                    self.skipTest(f"{channel} smoke tests disabled")
                if not _has_credentials(channel):
                    self.skipTest(f"{channel} credentials not configured")

                result = subprocess.run(
                    [str(SCRIPTS / "astro-commerce"), *args],
                    cwd=ROOT,
                    env=_command_env(channel),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=SMOKE_TIMEOUT,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                payload = _parse_json_stdout(result)
                self.assertEqual(payload.get("schema"), f"astro.commerce.{resource}.v1")
                self.assertEqual(payload.get("source"), channel)
                self.assertIsInstance(payload.get("records"), list)
                self.assertIsInstance(payload.get("summary"), dict)


if __name__ == "__main__":
    unittest.main()
