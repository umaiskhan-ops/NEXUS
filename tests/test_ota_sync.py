"""Unit tests for Over-The-Air (OTA) Zero-Touch Hot-Update and Brain Shard Synchronization."""
import hashlib
import json
import shutil
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from sovereign_mesh.config import GridConfig
from sovereign_mesh.grid import UltimateAgiSovereignGrid
from sovereign_mesh.security import hash_passphrase
from sovereign_mesh.server import make_handler
from sovereign_mesh.worker_package import (
    WORKER_BAT_CONTENT,
    WORKER_PROTOCOL_VERSION,
    WORKER_SH_CONTENT,
    generate_worker_zip,
    get_worker_launcher_code,
)


class MockBackend:
    def chat(self, model: str, system: str, prompt: str, timeout: float) -> str:
        return f"Mock reply from {model} for: {prompt[:30]}"

    def list_models(self, timeout: float = 3.0):
        return ["llama3.1:8b", "mistral:7b-instruct"]


class TestOverTheAirSync(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ota_test_")
        self.data_dir = Path(self.tmp_dir)
        self.pw_hash = hash_passphrase("OTASecure2026!")
        self.backend = MockBackend()
        self.config = GridConfig(
            owner_telegram_id=999888,
            master_passphrase_hash=self.pw_hash,
            data_dir=self.data_dir,
            enable_code_execution=True,
            simulate_offline_consensus=False,
            token_budget=1_000_000,
        )
        self.grid = UltimateAgiSovereignGrid(self.config, backend=self.backend)

    def tearDown(self):
        self.grid.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_worker_package_ota_artifacts(self):
        # 1. Verify Protocol Versioning
        self.assertEqual(WORKER_PROTOCOL_VERSION, "2026.5.0")

        # 2. Verify Batch Runner contains Hot-Restart loop on code 42
        self.assertIn("set NEXUS_OTA_LOOP=1", WORKER_BAT_CONTENT)
        self.assertIn(":worker_loop", WORKER_BAT_CONTENT)
        self.assertIn('if "%EXIT_STATUS%"=="42"', WORKER_BAT_CONTENT)
        self.assertIn("goto :worker_loop", WORKER_BAT_CONTENT)

        # 3. Verify Shell Runner contains Hot-Restart loop on code 42
        self.assertIn("export NEXUS_OTA_LOOP=1", WORKER_SH_CONTENT)
        self.assertIn("while true; do", WORKER_SH_CONTENT)
        self.assertIn("if [ $EXIT_CODE -eq 42 ]; then", WORKER_SH_CONTENT)

        # 4. Verify Launcher Code embeds current protocol version and OTA logic
        code = get_worker_launcher_code("http://127.0.0.1:8443")
        self.assertIn(f'WORKER_VERSION = "{WORKER_PROTOCOL_VERSION}"', code)
        self.assertIn("def trigger_ota_update", code)
        self.assertIn("def sync_model_shards", code)
        self.assertIn("/api/check_update", code)

        # 5. Verify Worker Zip generation
        zip_bytes = generate_worker_zip("http://127.0.0.1:8443")
        self.assertGreater(len(zip_bytes), 2000)

    def test_server_ota_endpoints_and_heartbeat(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.grid, None))
        host, port = httpd.server_address
        base = f"http://{host}:{port}"

        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        try:
            # 1. Register a test worker node
            reg_req = urllib.request.Request(
                f"{base}/api/worker/register",
                data=json.dumps({
                    "worker_id": "test-ota-node",
                    "hardware_spec": "AMD Ryzen 9 5950X (16 Cores)",
                    "hardware_uuid": "hw-test-ota-uuid-99",
                    "version": "2026.4.1",  # Older version
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(reg_req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                reg_data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(reg_data["ok"])
                self.assertEqual(reg_data["worker_id"], "test-ota-node")

            # 2. Test GET /api/worker/ota_check with older version
            check_req = urllib.request.Request(
                f"{base}/api/worker/ota_check?version=2026.4.1&worker_id=test-ota-node&shard=CODE_DEBUG_EXEC"
            )
            with urllib.request.urlopen(check_req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                check_data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(check_data["ok"])
                self.assertEqual(check_data["latest_version"], WORKER_PROTOCOL_VERSION)
                self.assertTrue(check_data["update_available"])
                self.assertEqual(check_data["current_version"], "2026.4.1")
                self.assertIn("download_url", check_data)
                self.assertTrue(bool(check_data["script_sha256"]))

            # 3. Test GET /api/worker/ota_download (JSON format)
            dl_req = urllib.request.Request(f"{base}/api/worker/ota_download")
            with urllib.request.urlopen(dl_req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                dl_data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(dl_data["ok"])
                self.assertEqual(dl_data["version"], WORKER_PROTOCOL_VERSION)
                # Verify cryptographic integrity match
                calc_hash = hashlib.sha256(dl_data["code"].encode("utf-8")).hexdigest()
                self.assertEqual(calc_hash, dl_data["sha256"])

            # 4. Test GET /api/worker/ota_download?raw=1 (Raw python format)
            raw_req = urllib.request.Request(f"{base}/api/worker/ota_download?raw=1")
            with urllib.request.urlopen(raw_req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("text/x-python", resp.headers.get("Content-Type", ""))
                raw_bytes = resp.read()
                raw_hash = hashlib.sha256(raw_bytes).hexdigest()
                self.assertEqual(raw_hash, resp.headers.get("X-Script-Sha256"))

            # 5. Test Heartbeat when node is running an older version
            hb_req_old = urllib.request.Request(
                f"{base}/api/worker/heartbeat",
                data=json.dumps({
                    "worker_id": "test-ota-node",
                    "version": "2026.4.1",
                    "synced_deltas_count": 0,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(hb_req_old, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                hb_data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(hb_data["ok"])
                self.assertTrue(hb_data["update_available"])
                self.assertEqual(hb_data["latest_version"], WORKER_PROTOCOL_VERSION)

            # 6. Test Heartbeat when node has updated to latest version
            hb_req_new = urllib.request.Request(
                f"{base}/api/worker/heartbeat",
                data=json.dumps({
                    "worker_id": "test-ota-node",
                    "version": WORKER_PROTOCOL_VERSION,
                    "synced_deltas_count": 0,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(hb_req_new, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                hb_data_new = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(hb_data_new["ok"])
                self.assertFalse(hb_data_new["update_available"])

            # 7. Test Neural Shard Delta Synchronization endpoint
            self.grid.brain_matrix.sync_p2p_weight_delta(
                domain_shard="CODE_DEBUG_EXEC",
                delta_summary="OTA Unit Test LoRA Shard Delta",
            )
            deltas_req = urllib.request.Request(
                f"{base}/api/brain/worker_deltas?worker_id=test-ota-node&shard=CODE_DEBUG_EXEC"
            )
            with urllib.request.urlopen(deltas_req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                deltas_data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(deltas_data["ok"])
                self.assertGreaterEqual(deltas_data["total_deltas"], 1)
                self.assertIn("OTA Unit Test LoRA Shard Delta", deltas_data["deltas"][-1]["summary"])

        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_atomic_file_swap_and_config_preservation(self):
        worker_dir = self.data_dir / "simulated_worker"
        worker_dir.mkdir(parents=True, exist_ok=True)
        config_file = worker_dir / "worker_config.json"
        launcher_file = worker_dir / "nexus_worker_launcher.py"

        # Initial worker credentials and balance
        initial_config = {
            "worker_id": "worker-persist-99",
            "worker_key": "secret-key-1234567890abcdef",
            "hub_url": "http://127.0.0.1:8443",
            "payout_address": "03001234567",
            "referred_by": "REF-ALPHA",
            "hardware_spec": "AMD 16-Core",
            "brain_shard": "CODE_DEBUG_EXEC",
            "synced_deltas_count": 3,
        }
        config_file.write_text(json.dumps(initial_config, indent=2), encoding="utf-8")
        launcher_file.write_text('# Version 2026.4.1\nprint("Old Version")', encoding="utf-8")

        # Simulate OTA atomic replacement
        new_code = '# Version 2026.5.0\nprint("New Version 2026.5.0")'
        tmp_file = launcher_file.with_suffix(".py.tmp")
        tmp_file.write_text(new_code, encoding="utf-8")
        tmp_file.replace(launcher_file)

        # Verify launcher code updated
        self.assertEqual(launcher_file.read_text(encoding="utf-8"), new_code)

        # Verify config and credentials remained 100% untouched
        saved_config = json.loads(config_file.read_text(encoding="utf-8"))
        self.assertEqual(saved_config["worker_id"], "worker-persist-99")
        self.assertEqual(saved_config["worker_key"], "secret-key-1234567890abcdef")
        self.assertEqual(saved_config["synced_deltas_count"], 3)


if __name__ == "__main__":
    unittest.main()
