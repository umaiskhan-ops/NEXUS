"""Unit tests for the Distributed Supercomputer & Virtual Server Rental Engine."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sovereign_mesh.config import GridConfig
from sovereign_mesh.grid import UltimateAgiSovereignGrid
from sovereign_mesh.ledger import HashChainLedger
from sovereign_mesh.models import OllamaBackend
from sovereign_mesh.hub_spoke import MasterHubCoordinator
from sovereign_mesh.security import hash_passphrase
from sovereign_mesh.supercomputer import SupercomputerEngine, VirtualServerInstance


class TestSupercomputerEngine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        self.ledger = HashChainLedger(self.data_dir / "ledger.jsonl")
        self.hub = MasterHubCoordinator(self.ledger, state_path=self.data_dir / "hub.json")
        self.storage = self.data_dir / "supercomputers.json"
        self.engine = SupercomputerEngine(self.hub, self.ledger, storage_path=self.storage)

        # Setup user worker with credits
        self.hub.register_worker("worker-alice", url="local", initial_credits=500)
        self.hub.register_worker("worker-node-1", url="http://192.168.1.10:8443", initial_credits=10)
        self.hub.register_worker("worker-node-2", url="http://192.168.1.11:8443", initial_credits=10)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_provision_success_and_credit_deduction(self):
        initial_bal = self.hub.get_balance("worker-alice")["credits"]
        self.assertEqual(initial_bal, 500)

        # Provision 32-core AI Rig (estimated: ~48 cr/hr)
        res = self.engine.provision_server(
            user_account_key="worker-alice",
            tier_name="Pro AI Rig",
            cores=32,
            ram_gb=128,
            duration_hours=1
        )
        self.assertTrue(res["ok"], res.get("error"))
        self.assertIn("instance", res)
        inst = res["instance"]

        self.assertEqual(inst["allocated_cores"], 32)
        self.assertEqual(inst["allocated_ram_gb"], 128)
        self.assertEqual(inst["status"], "ONLINE")
        self.assertGreaterEqual(inst["nodes_count"], 2)

        # Verify credits deducted
        new_bal = self.hub.get_balance("worker-alice")["credits"]
        self.assertEqual(new_bal, 500 - res["credits_spent"])

        # Check ledger record
        self.assertEqual(self.ledger.tail(1)[0]["data"]["task"], "supercomputer_cluster_provisioned")

    def test_insufficient_credits(self):
        self.hub.register_worker("worker-broke", url="local", initial_credits=5)

        # Renting 128 cores costs ~180 credits, user only has 5
        res = self.engine.provision_server(
            user_account_key="worker-broke",
            tier_name="Enterprise HPC",
            cores=128,
            ram_gb=512,
            duration_hours=1
        )
        self.assertFalse(res["ok"])
        self.assertTrue(res["insufficient_credits"])
        self.assertIn("Insufficient credits", res["error"])

    def test_job_dispatch_across_nodes(self):
        prov = self.engine.provision_server(
            user_account_key="worker-alice",
            tier_name="Test Cluster",
            cores=16,
            ram_gb=64,
            duration_hours=2
        )
        iid = prov["instance"]["instance_id"]

        job_res = self.engine.dispatch_job(
            instance_id=iid,
            user_account_key="worker-alice",
            job_name="Parallel Molecular Dynamics",
            payload_code="def run(): pass"
        )
        self.assertTrue(job_res["ok"])
        job = job_res["job"]
        self.assertEqual(job["cores_active"], 16)
        self.assertGreater(job["nodes_utilized"], 0)
        self.assertIn("Successfully distributed", job["summary"])

    def test_terminate_server(self):
        prov = self.engine.provision_server(
            user_account_key="worker-alice",
            tier_name="Short Lived",
            cores=8,
            ram_gb=32,
            duration_hours=1
        )
        iid = prov["instance"]["instance_id"]

        term_res = self.engine.terminate_server(iid, "worker-alice")
        self.assertTrue(term_res["ok"])
        self.assertEqual(term_res["status"], "TERMINATED")

        # Verify status in listing
        instances = self.engine.list_instances("worker-alice")
        self.assertEqual(instances[0]["status"], "TERMINATED")

    def test_aws_style_server_credentials_and_min_threshold_lock(self):
        # 1. Worker with 100 credits (< 250 threshold) cannot rent even a 12-credit server
        self.hub.register_worker("worker-under-threshold", url="local", initial_credits=100)
        locked = self.engine.provision_server(
            user_account_key="worker-under-threshold",
            tier_name="Fast Compute 8 vCPU",
            cores=8,
            ram_gb=32,
            duration_hours=1
        )
        self.assertFalse(locked["ok"])
        self.assertTrue(locked.get("min_threshold_locked"))
        self.assertIn("Minimum 250 credits", locked["error"])

        # 2. Worker with 500 credits (>= 250 threshold) gets AWS-style credentials upon renting
        prov = self.engine.provision_server(
            user_account_key="worker-alice",
            tier_name="AWS Creds Cluster",
            cores=16,
            ram_gb=64,
            duration_hours=2
        )
        self.assertTrue(prov["ok"])
        creds = prov["credentials"]
        self.assertTrue(creds["access_key_id"].startswith("NXIA"))
        self.assertTrue(creds["server_secret_key"].startswith("nxsrv-"))

        # 3. Connect from ANY device using Access Key ID + Server Secret Key (without main Account Key)
        conn = self.engine.connect_server(creds["access_key_id"], creds["server_secret_key"])
        self.assertTrue(conn["ok"])
        self.assertEqual(conn["instance"]["instance_id"], creds["instance_id"])

        # 4. Wrong server password is rejected
        bad_conn = self.engine.connect_server(creds["instance_id"], "nxsrv-wrong-password")
        self.assertFalse(bad_conn["ok"])

        # 5. Dispatch workload from any device using only Instance ID + Server Secret Key
        job_res = self.engine.dispatch_job(
            instance_id=creds["instance_id"],
            user_account_key="",
            job_name="Multi-Device Remote Task",
            payload_code="print('hello from remote device')",
            server_secret_key=creds["server_secret_key"]
        )
        self.assertTrue(job_res["ok"])
        self.assertIn("hello from remote device", job_res["job"]["output"])

    def test_continuous_auto_renew_and_no_72h_cap(self):
        import time
        # Grant Alice plenty of credits to test >72 hours and continuous auto-renewal
        self.hub.grant_credits("worker-alice", 2000, reason="test_grant")
        prov = self.engine.provision_server(
            user_account_key="worker-alice",
            tier_name="168h Continuous Cluster",
            cores=8,
            ram_gb=32,
            duration_hours=168,  # 7 days (>72h cap removed!)
            auto_renew=True,
        )
        self.assertTrue(prov["ok"])
        self.assertEqual(prov["instance"]["duration_hours"], 168)
        iid = prov["instance"]["instance_id"]
        inst_obj = self.engine._find_instance(iid)

        # Simulate current billing cycle expiring while user still has credits -> should auto-renew!
        bal_before = self.hub.get_balance("worker-alice")["credits"]
        inst_obj.expires_at = time.time() - 5.0
        listed = self.engine.list_instances("worker-alice")
        self.assertEqual(listed[0]["status"], "ONLINE")
        self.assertEqual(inst_obj.auto_renewals_count, 1)
        bal_after = self.hub.get_balance("worker-alice")["credits"]
        self.assertEqual(bal_after, bal_before - inst_obj.hourly_rate)

        # Simulate user credits running out when cycle ends -> should auto-pause (PAUSED_LOW_CREDITS) and save state!
        w_alice = self.hub.get_worker("worker-alice")
        w_alice.credits = 0
        inst_obj.expires_at = time.time() - 5.0
        listed2 = self.engine.list_instances("worker-alice")
        self.assertEqual(listed2[0]["status"], "PAUSED_LOW_CREDITS")

    def test_pause_and_resume_preserves_state_and_time(self):
        prov = self.engine.provision_server(
            user_account_key="worker-alice",
            tier_name="Pause Resume Rig",
            cores=16,
            ram_gb=64,
            duration_hours=2,
        )
        self.assertTrue(prov["ok"])
        iid = prov["instance"]["instance_id"]
        orig_secret = prov["credentials"]["server_secret_key"]

        # Run a job so there is job history state
        self.engine.dispatch_job(iid, "worker-alice", "Job Before Pause", "print('step 1')")

        # Pause the server
        pause_res = self.engine.pause_server(iid, "worker-alice")
        self.assertTrue(pause_res["ok"])
        self.assertEqual(pause_res["status"], "PAUSED")
        self.assertGreater(pause_res["paused_remaining_seconds"], 3600)
        # While paused, 0 cores are used by user and all 16 are shared back to the mesh network!
        self.assertEqual(pause_res["instance"]["active_cores_in_use"], 0)
        self.assertEqual(pause_res["instance"]["shared_to_network_cores"], 16)

        # Resume the server later -> resumes from exact same state, 0 extra credits charged since prepaid time remained!
        bal_before_resume = self.hub.get_balance("worker-alice")["credits"]
        resume_res = self.engine.resume_server(iid, "worker-alice")
        self.assertTrue(resume_res["ok"])
        self.assertEqual(resume_res["status"], "ONLINE")
        self.assertEqual(resume_res["credits_charged"], 0)
        self.assertEqual(self.hub.get_balance("worker-alice")["credits"], bal_before_resume)
        self.assertEqual(resume_res["instance"]["server_secret_key"], orig_secret)
        self.assertEqual(len(resume_res["instance"]["jobs_history"]), 1)

    def test_elastic_dynamic_mesh_pooling(self):
        prov = self.engine.provision_server(
            user_account_key="worker-alice",
            tier_name="Elastic 64C Cluster",
            cores=64,
            ram_gb=256,
            duration_hours=1,
        )
        self.assertTrue(prov["ok"])
        inst = prov["instance"]
        iid = inst["instance_id"]

        # 1. When idle right after provisioning: only 2 standby cores used, 62 cores shared with NEXUS network!
        self.assertEqual(inst["allocated_cores"], 64)
        self.assertEqual(inst["active_cores_in_use"], 2)
        self.assertEqual(inst["shared_to_network_cores"], 62)

        # 2. Run a light job (scales partially to 32 cores, 32 still shared with network)
        light_job = self.engine.dispatch_job(iid, "worker-alice", "Light Script", "x = 1 + 1")
        self.assertTrue(light_job["ok"])
        self.assertEqual(light_job["job"]["elastic_cores_burst"], 32)
        self.assertEqual(light_job["job"]["shared_to_network_cores"], 32)

        # 3. Run a heavy parallel matrix workload -> scales up to full 64/64 cores (100% of purchased limit)!
        heavy_job = self.engine.dispatch_job(iid, "worker-alice", "Heavy Matrix", "import numpy; print('matrix parallel')")
        self.assertTrue(heavy_job["ok"])
        self.assertEqual(heavy_job["job"]["elastic_cores_burst"], 64)
        self.assertEqual(heavy_job["job"]["shared_to_network_cores"], 0)


class MockBackend:
    """Mock LLM backend for deterministic testing."""
    def __init__(self):
        self.history = []

    def chat(self, model: str, system: str, prompt: str, timeout: float) -> str:
        self.history.append({"model": model, "system": system, "prompt": prompt})
        if "Return ONLY executable" in system or "code" in prompt.lower():
            return "```python\ndef calculate_throughput(items, duration):\n    return items / duration if duration > 0 else 0.0\nprint('throughput calculated: 42.0')\n```"
        return f"Mock response from {model} for: {prompt[:30]}"

    def list_models(self, timeout: float = 3.0):
        return ["llama3.1:8b", "mistral:7b-instruct", "gpt-oss:20b"]


class TestSupercomputerGridAndTelegram(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        cfg = GridConfig(data_dir=str(self.data_dir), owner_telegram_id=123456789,
                         master_passphrase_hash=hash_passphrase("pass123"))
        self.grid = UltimateAgiSovereignGrid(cfg, backend=MockBackend())
        self.bob = self.grid.hub.register_worker("worker-bob", url="local", initial_credits=300)

    def tearDown(self):
        self.grid.stop()
        self.tmpdir.cleanup()

    def test_telegram_rent_and_list_servers(self):
        # 1. Rent cluster via telegram intent
        rent_req = {
            "worker_id": "worker-bob",
            "cores": 16,
            "ram_gb": 64,
            "duration": 1,
            "tier_name": "Bob-Cluster-16"
        }
        res = self.grid.process_telegram_inbound_signal(123456789, "/rent_server", rent_req)
        self.assertIn("SUPERCOMPUTER CLUSTER PROVISIONED", res["tele_response"])
        inst_id = res["instance"]["instance_id"]

        # 2. Query servers
        list_res = self.grid.process_telegram_inbound_signal(123456789, "/my_servers", {"worker_id": "worker-bob"})
        self.assertIn(inst_id, list_res["tele_response"])

        # 3. Run job
        job_res = self.grid.process_telegram_inbound_signal(123456789, "/run_server_job", {
            "instance_id": inst_id,
            "worker_id": "worker-bob",
            "job_name": "Telegram Matrix Mult"
        })
        self.assertIn("CLUSTER JOB EXECUTED", job_res["tele_response"])

        # 4. Stop server
        stop_res = self.grid.process_telegram_inbound_signal(123456789, "/stop_server", {"instance_id": inst_id})
        self.assertIn("terminated", stop_res["tele_response"])

    def test_supercomputer_http_endpoints(self):
        from http.server import ThreadingHTTPServer
        import threading
        import urllib.request
        from sovereign_mesh.server import make_handler

        handler = make_handler(self.grid, None)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{port}"
        bob_key = self.bob.key

        try:
            # 1. Rent cluster via POST /api/supercomputer/rent
            req = urllib.request.Request(
                f"{base}/api/supercomputer/rent",
                data=json.dumps({
                    "account_key": bob_key,
                    "tier_name": "API Test Cluster",
                    "cores": 32,
                    "ram_gb": 128,
                    "duration_hours": 1
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                iid = data["instance"]["instance_id"]
                self.assertEqual(data["instance"]["allocated_cores"], 32)

            # 2. Query clusters via GET /api/supercomputer/instances
            with urllib.request.urlopen(f"{base}/api/supercomputer/instances?account_key={bob_key}", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertGreaterEqual(len(data["instances"]), 1)
                self.assertEqual(data["instances"][0]["instance_id"], iid)

            # 3. Run job via POST /api/supercomputer/job
            req = urllib.request.Request(
                f"{base}/api/supercomputer/job",
                data=json.dumps({
                    "instance_id": iid,
                    "account_key": bob_key,
                    "job_name": "API Batch Inference",
                    "payload_code": "import numpy; pass"
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertEqual(data["job"]["cores_active"], 32)
                self.assertIn("Successfully distributed", data["job"]["summary"])

            # 4. Terminate via POST /api/supercomputer/terminate
            req = urllib.request.Request(
                f"{base}/api/supercomputer/terminate",
                data=json.dumps({
                    "instance_id": iid,
                    "account_key": bob_key
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertEqual(data["status"], "TERMINATED")

            # 5. Test GET /api/ide/files (isolated inside self.data_dir so repo root stays clean)
            self.grid.active_project = str(self.data_dir)
            with urllib.request.urlopen(f"{base}/api/ide/files", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertIsInstance(data["files"], list)

            # 6. Test POST /api/ide/file/save
            req = urllib.request.Request(
                f"{base}/api/ide/file/save",
                data=json.dumps({
                    "path": "test_saved_file.py",
                    "content": "print('hello from test_saved_file')"
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])

            # 7. Test GET /api/ide/file
            with urllib.request.urlopen(f"{base}/api/ide/file?path=test_saved_file.py", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertIn("hello from test_saved_file", data["content"])

            # 8. Test POST /api/ide/agent_control (Autonomous Agent In Full Control)
            req = urllib.request.Request(
                f"{base}/api/ide/agent_control",
                data=json.dumps({
                    "instruction": "Build an algorithmic throughput calculator",
                    "target_file": "agent_test_algo.py",
                    "account_key": bob_key
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertTrue(data["file_saved"])
                self.assertIn("agent_test_algo.py", data["target_file"])
            # 9. Test GET /api/ide/projects
            with urllib.request.urlopen(f"{base}/api/ide/projects", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertIn("projects", data)

            # 10. Test POST /api/ide/projects/create
            custom_proj_dir = self.data_dir / "custom_test_project"
            req = urllib.request.Request(
                f"{base}/api/ide/projects/create",
                data=json.dumps({
                    "name": "CustomTestApp",
                    "path": str(custom_proj_dir),
                    "template": "python"
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertTrue(custom_proj_dir.exists())
                self.assertTrue((custom_proj_dir / "main.py").exists())
                self.assertTrue((custom_proj_dir / "README.md").exists())

            # 11. Test GET /api/ide/files for custom project
            with urllib.request.urlopen(f"{base}/api/ide/files?project={urllib.parse.quote(str(custom_proj_dir))}", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                file_names = [f["name"] for f in data["files"]]
                self.assertIn("main.py", file_names)
                self.assertIn("README.md", file_names)

            # 12. Test POST /api/ide/projects/open
            req = urllib.request.Request(
                f"{base}/api/ide/projects/open",
                data=json.dumps({"path": str(custom_proj_dir)}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertEqual(Path(data["project"]).resolve(), custom_proj_dir.resolve())
        finally:
            httpd.shutdown()
            httpd.server_close()
            for base_dir in (
                self.data_dir,
                Path.cwd(),
                Path(getattr(self.grid.config, "workspace_dir", "e:/NEXUS")),
            ):
                for tmp_f in ("test_saved_file.py", "agent_test_algo.py"):
                    p = Path(base_dir) / tmp_f
                    if p.exists():
                        try:
                            p.unlink()
                        except Exception:
                            pass


if __name__ == "__main__":
    unittest.main()

