"""Unit tests for NEXUS Native Zero-Setup Process Sandbox Engine.
Verifies directory jailing, safe feature whitelisting, payload injection protection,
host CPU throttling, and zero-host-access isolation without Docker.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from sovereign_mesh.worker_package import (
    NativeSandboxEngine,
    SandboxSecurityViolation,
    generate_worker_zip,
    get_worker_launcher_code,
)


class TestNativeProcessSandbox(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="nexus_sb_test_")).resolve()
        self.sandbox = NativeSandboxEngine(self.test_dir)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_sandbox_initialization(self):
        """Sandbox initializes correctly and creates workspace directory."""
        self.assertTrue(self.sandbox.workspace_dir.exists())
        self.assertEqual(self.sandbox.workspace_dir, self.test_dir / "sandbox_workspace")
        self.assertIn(self.sandbox.throttling_mode, ["BELOW_NORMAL (Host UI Protected)", "NICE+10 (Host UI Protected)", "DEFAULT"])

    def test_02_path_validation_and_jailing(self):
        """Ensures filesystem access is strictly jailed to the base directory and workspace."""
        # Safe internal file path
        safe_path = self.sandbox.validate_path("sandbox_workspace/results.json")
        self.assertTrue(str(safe_path).startswith(str(self.test_dir)))

        # Subdirectory path
        safe_sub = self.sandbox.validate_path("brain_shards/model.safetensors")
        self.assertTrue(str(safe_sub).startswith(str(self.test_dir)))

        # Traversal attempts MUST be blocked with SandboxSecurityViolation
        with self.assertRaises(SandboxSecurityViolation):
            self.sandbox.validate_path("../../../windows/system32/cmd.exe")

        with self.assertRaises(SandboxSecurityViolation):
            self.sandbox.validate_path("../../etc/shadow")

        with self.assertRaises(SandboxSecurityViolation):
            self.sandbox.validate_path("C:\\Users\\Administrator\\Desktop")

    def test_03_feature_whitelist_and_injection_blocking(self):
        """Verifies feature names are strictly validated against malicious command injection."""
        # Built-in valid algorithmic features
        self.assertTrue(self.sandbox.is_safe_feature("data_analysis"))
        self.assertTrue(self.sandbox.is_safe_feature("trend_forecasting"))
        self.assertTrue(self.sandbox.is_safe_feature("brain_inference"))
        self.assertTrue(self.sandbox.is_safe_feature("lora_backprop_train"))
        self.assertTrue(self.sandbox.is_safe_feature("neural_shard_compute"))

        # Valid custom identifier
        self.assertTrue(self.sandbox.is_safe_feature("custom_model_shard_42"))

        # Malicious command injections MUST be rejected
        self.assertFalse(self.sandbox.is_safe_feature("calc.exe"))
        self.assertFalse(self.sandbox.is_safe_feature("rm -rf /"))
        self.assertFalse(self.sandbox.is_safe_feature("data_analysis ; whoami"))
        self.assertFalse(self.sandbox.is_safe_feature("brain_inference | nc -l 4444"))
        self.assertFalse(self.sandbox.is_safe_feature(""))
        self.assertFalse(self.sandbox.is_safe_feature("a" * 100))  # too long

    def test_04_dangerous_token_payload_inspection(self):
        """Detects and flags payloads attempting remote code execution or shell injections."""
        # Safe numerical compute payload
        safe_payload = {"data": [10.5, 20.3, 30.1], "algorithm": "standard_deviation"}
        self.assertFalse(self.sandbox.has_dangerous_tokens(safe_payload))

        # Safe text prompt for neural shard
        safe_prompt = {"prompt": "Write a clean binary search algorithm in python."}
        self.assertFalse(self.sandbox.has_dangerous_tokens(safe_prompt))

        # Dangerous payloads
        self.assertTrue(self.sandbox.has_dangerous_tokens({"cmd": "rmdir /s /q C:\\"}))
        self.assertTrue(self.sandbox.has_dangerous_tokens({"exec": "powershell -enc ..."}))
        self.assertTrue(self.sandbox.has_dangerous_tokens({"exploit": "eval(compile(...))"}))
        self.assertTrue(self.sandbox.has_dangerous_tokens({"path": "../../../etc/passwd"}))
        self.assertTrue(self.sandbox.has_dangerous_tokens(["safe", "ok", "__import__('os').system('ls')"]))

    def test_05_sensitive_environment_scrubbing(self):
        """Verifies host API keys and tokens are excluded from sandboxed environment view."""
        os.environ["NEXUS_TEST_SECRET_KEY"] = "super-secret-12345"
        os.environ["NEXUS_TEST_PUBLIC_VAR"] = "public_model_info"
        try:
            scrubbed = self.sandbox.scrub_sensitive_env()
            self.assertNotIn("NEXUS_TEST_SECRET_KEY", scrubbed)
            self.assertIn("NEXUS_TEST_PUBLIC_VAR", scrubbed)
        finally:
            os.environ.pop("NEXUS_TEST_SECRET_KEY", None)
            os.environ.pop("NEXUS_TEST_PUBLIC_VAR", None)

    def test_06_worker_zip_contains_native_sandbox_protection(self):
        """Ensures generated 1-click worker zip bundles sandbox code and documentation."""
        zip_bytes = generate_worker_zip("http://localhost:8443")
        self.assertGreater(len(zip_bytes), 1000)

        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        names = zf.namelist()
        self.assertIn("nexus_worker_launcher.py", names)
        self.assertIn("start_worker.bat", names)
        self.assertIn("README.txt", names)

        # Inspect launcher code inside zip
        launcher_src = zf.read("nexus_worker_launcher.py").decode("utf-8")
        self.assertIn("NativeSandboxEngine", launcher_src)
        self.assertIn("SandboxSecurityViolation", launcher_src)
        self.assertIn("sandbox_workspace", launcher_src)
        self.assertIn("apply_host_ui_throttling", launcher_src)
        self.assertIn("BELOW_NORMAL", launcher_src)

        # Inspect README documentation
        readme_src = zf.read("README.txt").decode("utf-8")
        self.assertIn("SECURITY & ZERO-SETUP NATIVE SANDBOX", readme_src)
        self.assertIn("Zero Host Access", readme_src)

        # Inspect BAT script
        bat_src = zf.read("start_worker.bat").decode("utf-8")
        self.assertIn("Native Zero-Setup Sandbox & Host Shield", bat_src)


if __name__ == "__main__":
    unittest.main()
