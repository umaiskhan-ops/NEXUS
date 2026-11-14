# NEXUS Sovereign Mesh — Operations & Telemetry Runbook

## 1. Observability & Prometheus Scraping

### Endpoints
- **Telemetry JSON**: `GET /api/metrics` (requires Hub Owner `Authorization: Bearer <DASHBOARD_TOKEN>` or valid session cookie).
- **Prometheus Exposition**: `GET /api/metrics?format=prometheus` or `Accept: text/plain` (same Owner auth required, `Content-Type: text/plain; version=0.0.4; charset=utf-8`).

### Key Metrics Exposed
| Metric Name | Type | Description |
|---|---|---|
| `nexus_http_requests_total` | Counter | Total HTTP requests recorded by the API server |
| `nexus_http_latency_ms_p50` | Gauge | 50th percentile HTTP response latency (ms) |
| `nexus_http_latency_ms_p95` | Gauge | 95th percentile HTTP response latency (ms) |
| `nexus_http_latency_ms_p99` | Gauge | 99th percentile HTTP response latency (ms) |
| `nexus_workers_total` | Gauge | Registered worker count in Hub registry |
| `nexus_workers_active` | Gauge | Currently active online workers |
| `nexus_tasks_settled_total` | Counter | Successfully settled tasks (`SETTLED`) |
| `nexus_tasks_rejected_total` | Counter | Rejected submissions (`REJECTED`, `REJECTED_INELIGIBLE`) |
| `nexus_slashes_total` | Counter | Cryptographically attributable slash events |
| `nexus_credits_total_supply` | Gauge | Aggregate worker credit supply |
| `nexus_credits_spendable_supply` | Gauge | Aggregate spendable (vested) worker credits |
| `nexus_credits_staked_total` | Gauge | Aggregate worker collateral staked |
| `nexus_consensus_models_active` | Gauge | `1` when ONNX MiniLM & DeBERTa models are active, `0` otherwise |
| `nexus_ledger_valid` | Gauge | `1` when HMAC + hash chain integrity passes, `0` on mismatch |

---

## 2. Alert Response Procedures

| Alert Key | Trigger Condition | Severity | Operator Action |
|---|---|---|---|
| `high_rejection_rate` | Rejected/slashed settlements exceed threshold (`> 25%` with `>= 4` outcomes) | Warning | Inspect `rejection_reasons` in `GET /api/metrics`; check `hub.get_telemetry_snapshot` / ledger slashes for Sybil attack or malformed client payloads. |
| `ledger_integrity_failure` | `ledger_valid == 0` (`HashChainLedger.verify()` returns False) | Critical | Engage lockdown/freeze immediately, halt payouts, compare active WAL & ledger against last verified backup snapshot, run forensic diff on failing sequence index. |
| `consensus_models_inactive` | `consensus_models_active == 0` | Critical | Free-form semantic consensus fails closed (`free_form_consensus_unavailable_models_inactive`). Run `python scripts/download_models.py` and verify attested SHA-256 checksums before restart. |
| `system_lockdown_active` | `grid.system_lockdown == True` | Critical | Review intrusion counter and recent Owner audit trail before clearing lockdown. |

---

## 3. WAL Backup & Crash-Restore Drill

Run automated backup & isolated restore verification at any time via Owner-authenticated API:

```http
POST /api/hub/wal_drill
Authorization: Bearer <DASHBOARD_TOKEN>
```

The drill (`ObservabilityManager.run_wal_backup_and_restore_drill`):
1. Flushes in-memory Hub WAL state (`hub._flush_wal()`).
2. Copies `hub_wal.json` (plus SHA-256 digest verification) and hash-chain ledger JSONL into a timestamped backup directory under `data/backups/`.
3. Restores both WAL and hash-chain ledger into an isolated scratch sandbox preserving the HMAC secret key.
4. Verifies restored worker count, pending task count, total credits match live Hub state exactly, and `restored_ledger.verify()` succeeds (`(True, None)`).

Recommended schedule: execute `POST /api/hub/wal_drill` before major upgrades and via daily scheduled automation.

---

## 4. DGM Self-Improvement & Kill-Switch Safeguards

1. **Immutable Evaluation Gate**: `DGMSelfImprovementLoop.verify_evaluator_immutability()` hashes the bytecode/source digest of `AdapterBenchmarkSuite.evaluate_paired_pass_at_1` and the objective verifier at initialization and before every evolution cycle (`POST /api/learning/dgm_cycle`). Any runtime monkey-patching or tampering raises `PermissionError("IMMUTABLE_EVALUATOR_TAMPER_DETECTED")`.
2. **Paired Bootstrap Promotion Gate**: Candidate scaffold proposals are promoted into `data/scaffold_archive.json` only if `evaluate_paired_pass_at_1` shows paired gain `>= min_improvement_margin` with statistical gate approval.
3. **Emergency Kill Switch**: If unexpected behavior occurs in any autonomous learning or evolution loop, engage the Owner kill switch immediately (`POST /api/learning/kill_switch`) and inspect `data/scaffold_archive.json`.
