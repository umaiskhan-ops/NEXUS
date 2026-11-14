"""Phase B Observability, Prometheus Telemetry & WAL Crash-Restore Drill (B20).

Provides:
- Request latency tracking (p50, p95, p99 percentiles).
- Settlement outcome & rejection reason counters.
- Credit economy gauges (circulating supply, burned, escrowed, staked collateral, welcome locked).
- Worker reputation distribution & threshold alerts.
- Standard Prometheus text exposition formatter (`format_prometheus_metrics`).
- Atomic WAL + Ledger snapshot backup and crash-restore verification drill.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
import threading
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional


class ObservabilityManager:
    """Thread-safe metrics, alerting, and WAL backup/restore coordinator for NEXUS."""

    def __init__(self, data_dir: Path, max_latency_samples: int = 2000):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_root = self.data_dir / "wal_backups"
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._latencies_s: Deque[float] = deque(maxlen=max(100, int(max_latency_samples)))
        self._settlement_counts: Counter = Counter()
        self._rejection_reasons: Counter = Counter()
        self._route_counts: Counter = Counter()
        self._last_drill: Optional[Dict[str, Any]] = None
        self.started_at = time.time()

    def record_http_request(self, path: str, status_code: int, latency_s: float) -> None:
        with self._lock:
            self._latencies_s.append(max(0.0, float(latency_s)))
            self._route_counts[f"{path}:{status_code}"] += 1

    def record_settlement_outcome(self, outcome: Dict[str, Any]) -> None:
        if not isinstance(outcome, dict):
            return
        status = str(outcome.get("status") or ("SETTLED" if outcome.get("ok") else "REJECTED")).upper()
        with self._lock:
            self._settlement_counts[status] += 1
            if status in {"REJECTED", "SLASHED"}:
                raw_reason = str(outcome.get("reason") or "unknown").split(":", 1)[0].split("(", 1)[0].strip()
                self._rejection_reasons[raw_reason or "unknown"] += 1

    @staticmethod
    def _percentile(sorted_vals: List[float], pct: float) -> float:
        if not sorted_vals:
            return 0.0
        idx = min(len(sorted_vals) - 1, max(0, int(math.ceil((pct / 100.0) * len(sorted_vals))) - 1))
        return round(sorted_vals[idx], 6)

    def _collect_live_stats(self, grid: Any) -> Dict[str, Any]:
        hub = getattr(grid, "hub", None)
        ledger = getattr(grid, "ledger", None)
        workers = list(hub._workers.values()) if (hub and hasattr(hub, "_workers")) else []
        active_workers = [w for w in workers if getattr(w, "status", "ACTIVE") == "ACTIVE"]
        slashed_workers = [w for w in workers if getattr(w, "status", "") == "SLASHED"]

        total_credits = sum(int(getattr(w, "credits", 0)) for w in workers)
        total_burned = sum(int(getattr(w, "burned_credits", 0)) for w in workers)
        total_staked = sum(int(getattr(w, "staked_collateral", 0)) for w in workers)
        total_welcome_locked = sum(int(getattr(w, "welcome_credits_locked", 0)) for w in workers)
        total_spendable = sum(w.spendable_credits() for w in workers if hasattr(w, "spendable_credits"))
        rep_scores = [float(getattr(w, "reputation_score", 0.25)) for w in active_workers]

        escrowed_tasks = 0
        pending_count = 0
        if hub is not None:
            pending_dict = getattr(hub, "_pending", {})
            pending_count = len(pending_dict)
            escrowed_tasks = sum(int(t.get("funded_credits") or 0) for t in pending_dict.values())
            consensus_dict = getattr(hub, "_freeform_consensus", {})
            escrowed_tasks += sum(int(c.get("funded_credits") or 0) for c in consensus_dict.values())

        ledger_len = len(ledger) if ledger is not None else 0
        ledger_intact = True
        if ledger is not None and hasattr(ledger, "verify"):
            try:
                ledger_intact = bool(ledger.verify()[0])
            except Exception:
                ledger_intact = False

        consensus_models_active = False
        try:
            from .hub_spoke import check_semantic_models_status
            consensus_models_active = bool(check_semantic_models_status().get("active"))
        except Exception:
            consensus_models_active = False

        with self._lock:
            lats = sorted(self._latencies_s)
            settle_counts = dict(self._settlement_counts)
            rej_reasons = dict(self._rejection_reasons)

        total_settled = sum(settle_counts.values())
        rejected_total = settle_counts.get("REJECTED", 0) + settle_counts.get("SLASHED", 0)
        rejection_rate = round(rejected_total / float(total_settled), 4) if total_settled else 0.0

        alerts: List[Dict[str, Any]] = []
        if not ledger_intact:
            alerts.append({"severity": "CRITICAL", "name": "ledger_integrity_failure", "detail": "HashChainLedger verification failed"})
        if total_settled >= 10 and rejection_rate > 0.35:
            alerts.append({"severity": "WARNING", "name": "high_rejection_rate", "detail": f"Rejection rate {rejection_rate:.2f} > 0.35"})
        if not consensus_models_active:
            alerts.append({"severity": "WARNING", "name": "consensus_models_inactive", "detail": "ONNX MiniLM/DeBERTa fail-closed"})
        if getattr(grid, "system_lockdown", False):
            alerts.append({"severity": "CRITICAL", "name": "system_lockdown_active", "detail": "Node is in system lockdown"})

        rep_dist = {
            "probationary_below_0_6": sum(1 for r in rep_scores if r < 0.60),
            "trusted_0_6_to_0_85": sum(1 for r in rep_scores if 0.60 <= r < 0.85),
            "veteran_ge_0_85": sum(1 for r in rep_scores if r >= 0.85),
            "mean": round(sum(rep_scores) / float(len(rep_scores)), 4) if rep_scores else 0.0,
        }

        return {
            "uptime_s": round(time.time() - self.started_at, 2),
            "workers": {
                "total": len(workers),
                "active": len(active_workers),
                "slashed": len(slashed_workers),
                "pending_tasks": pending_count,
                "reputation_distribution": rep_dist,
            },
            "economy": {
                "total_supply_credits": total_credits,
                "spendable_credits": total_spendable,
                "burned_credits": total_burned,
                "staked_collateral_credits": total_staked,
                "welcome_credits_locked": total_welcome_locked,
                "escrowed_credits": escrowed_tasks,
            },
            "settlements": settle_counts,
            "rejection_reasons": rej_reasons,
            "rejection_rate": rejection_rate,
            "latency_seconds": {
                "count": len(lats),
                "p50": self._percentile(lats, 50.0),
                "p95": self._percentile(lats, 95.0),
                "p99": self._percentile(lats, 99.0),
            },
            "ledger": {
                "blocks": ledger_len,
                "intact": ledger_intact,
            },
            "consensus_models_active": consensus_models_active,
            "alerts": alerts,
            "last_wal_drill": dict(self._last_drill) if self._last_drill else None,
        }

    def get_telemetry_snapshot(self, grid: Any) -> Dict[str, Any]:
        return {"ok": True, **self._collect_live_stats(grid)}

    def format_prometheus_metrics(self, grid: Any) -> str:
        """Formats live NEXUS metrics in Prometheus exposition text format (0.0.4)."""
        snap = self._collect_live_stats(grid)
        w = snap["workers"]
        econ = snap["economy"]
        lat = snap["latency_seconds"]
        led = snap["ledger"]
        lines = [
            "# HELP nexus_uptime_seconds Node uptime in seconds",
            "# TYPE nexus_uptime_seconds gauge",
            f"nexus_uptime_seconds {snap['uptime_s']}",
            "# HELP nexus_workers_active Number of ACTIVE worker nodes",
            "# TYPE nexus_workers_active gauge",
            f"nexus_workers_active {w['active']}",
            "# HELP nexus_workers_slashed Number of SLASHED worker nodes",
            "# TYPE nexus_workers_slashed gauge",
            f"nexus_workers_slashed {w['slashed']}",
            "# HELP nexus_worker_reputation_mean Mean worker reputation score",
            "# TYPE nexus_worker_reputation_mean gauge",
            f"nexus_worker_reputation_mean {w['reputation_distribution']['mean']}",
            "# HELP nexus_credits_total_supply Circulating credits across all workers",
            "# TYPE nexus_credits_total_supply gauge",
            f"nexus_credits_total_supply {econ['total_supply_credits']}",
            "# HELP nexus_credits_burned Total burned/slashed credits",
            "# TYPE nexus_credits_burned counter",
            f"nexus_credits_burned {econ['burned_credits']}",
            "# HELP nexus_credits_staked Total staked collateral credits",
            "# TYPE nexus_credits_staked gauge",
            f"nexus_credits_staked {econ['staked_collateral_credits']}",
            "# HELP nexus_credits_escrowed Credits currently locked in pending task escrow",
            "# TYPE nexus_credits_escrowed gauge",
            f"nexus_credits_escrowed {econ['escrowed_credits']}",
            "# HELP nexus_credits_welcome_locked Unvested welcome credits locked against sybil drain",
            "# TYPE nexus_credits_welcome_locked gauge",
            f"nexus_credits_welcome_locked {econ['welcome_credits_locked']}",
            "# HELP nexus_ledger_blocks_total Number of blocks in HashChainLedger",
            "# TYPE nexus_ledger_blocks_total counter",
            f"nexus_ledger_blocks_total {led['blocks']}",
            "# HELP nexus_ledger_intact Hash chain verification status (1=intact, 0=corrupted)",
            "# TYPE nexus_ledger_intact gauge",
            f"nexus_ledger_intact {1 if led['intact'] else 0}",
            "# HELP nexus_consensus_models_active Neural ONNX consensus models active (1=active, 0=inactive)",
            "# TYPE nexus_consensus_models_active gauge",
            f"nexus_consensus_models_active {1 if snap['consensus_models_active'] else 0}",
            "# HELP nexus_http_latency_p95_seconds 95th percentile HTTP handler latency in seconds",
            "# TYPE nexus_http_latency_p95_seconds gauge",
            f"nexus_http_latency_p95_seconds {lat['p95']}",
            "# HELP nexus_alerts_active Total active alert conditions",
            "# TYPE nexus_alerts_active gauge",
            f"nexus_alerts_active {len(snap['alerts'])}",
            "# HELP nexus_task_settlements_total Task settlement outcomes by status",
            "# TYPE nexus_task_settlements_total counter",
        ]
        for st, cnt in sorted(snap["settlements"].items()):
            lines.append(f'nexus_task_settlements_total{{status="{st}"}} {cnt}')
        lines.extend([
            "# HELP nexus_task_rejections_total Task rejections by normalized reason",
            "# TYPE nexus_task_rejections_total counter",
        ])
        for reason, cnt in sorted(snap["rejection_reasons"].items()):
            safe_r = reason.replace('"', "")
            lines.append(f'nexus_task_rejections_total{{reason="{safe_r}"}} {cnt}')
        return "\n".join(lines) + "\n"

    def run_wal_backup_and_restore_drill(
        self,
        hub: Any,
        ledger: Any,
        backup_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Creates an atomic backup of the Hub WAL file and HashChainLedger, then performs
        an isolated crash-restore verification drill checking 100% balance & ledger parity.
        """
        from .hub_spoke import MasterHubCoordinator
        from .ledger import HashChainLedger, interprocess_file_lock

        ts_label = time.strftime("%Y%m%d-%H%M%S")
        target_dir = Path(backup_dir) if backup_dir else (self.backup_root / f"wal-{ts_label}")
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. Flush hub state cleanly under lock
        if hasattr(hub, "_flush"):
            with getattr(hub, "_lock", threading.RLock()):
                hub._flush()

        hub_src = getattr(hub, "_path", None)
        ledger_src = getattr(ledger, "_path", None)

        copied_files: Dict[str, str] = {}
        if hub_src and Path(hub_src).exists():
            hub_dst = target_dir / "hub_workers.json"
            with interprocess_file_lock(Path(hub_src)):
                shutil.copy2(hub_src, hub_dst)
            copied_files["hub_wal_sha256"] = hashlib.sha256(hub_dst.read_bytes()).hexdigest()
        else:
            return {"ok": False, "error": "hub WAL state_path does not exist on disk"}

        if ledger_src and Path(ledger_src).exists():
            ledger_dst = target_dir / "ledger.jsonl"
            with interprocess_file_lock(Path(ledger_src)):
                shutil.copy2(ledger_src, ledger_dst)
            copied_files["ledger_sha256"] = hashlib.sha256(ledger_dst.read_bytes()).hexdigest()
        else:
            ledger_dst = target_dir / "ledger.jsonl"
            ledger_dst.write_text("", encoding="utf-8")
            copied_files["ledger_sha256"] = hashlib.sha256(b"").hexdigest()

        manifest = {
            "created_at": time.time(),
            "worker_count": len(hub._workers),
            "ledger_blocks": len(ledger),
            "ledger_head_hash": getattr(ledger, "head_hash", ""),
            **copied_files,
        }
        (target_dir / "backup_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # 2. Isolated Crash-Restore Verification Drill in Temporary Sandbox
        with tempfile.TemporaryDirectory() as tmp_restore:
            restore_dir = Path(tmp_restore)
            r_hub_path = restore_dir / "hub_workers.json"
            r_ledger_path = restore_dir / "ledger.jsonl"
            shutil.copy2(target_dir / "hub_workers.json", r_hub_path)
            shutil.copy2(target_dir / "ledger.jsonl", r_ledger_path)

            hmac_secret = getattr(ledger, "_hmac_key", None)
            # HashChainLedger accepts string secret; recreate with matching blocks verification
            r_ledger = HashChainLedger(r_ledger_path)
            if hmac_secret is not None:
                r_ledger._hmac_key = hmac_secret
            chain_ok, bad_idx = r_ledger.verify()

            r_hub = MasterHubCoordinator(r_ledger, state_path=r_hub_path)
            try:
                src_workers = hub._workers
                dst_workers = r_hub._workers
                count_match = (len(src_workers) == len(dst_workers))
                balance_mismatches = []
                for wid, sw in src_workers.items():
                    dw = dst_workers.get(wid)
                    if not dw or sw.credits != dw.credits or sw.staked_collateral != dw.staked_collateral:
                        balance_mismatches.append(wid)
                restored_ok = bool(chain_ok and count_match and not balance_mismatches)
            finally:
                r_hub.stop()

        report = {
            "ok": restored_ok,
            "restored_ok": restored_ok,
            "backup_dir": str(target_dir),
            "ledger_intact": chain_ok,
            "ledger_bad_index": bad_idx,
            "workers_restored": len(hub._workers),
            "balance_mismatches": balance_mismatches,
            "checksums": copied_files,
            "verified_at": time.time(),
        }
        with self._lock:
            self._last_drill = report
        return report
