# NEXUS API Route Permissions Matrix (B5 Standard)

| Route Path | HTTP Method | Access Level | Authentication Mechanism | Description / Sensitivity Notes |
|:---|:---:|:---:|:---|:---|
| `/` | GET | Public | None | Web Dashboard UI (nonce-protected CSP) |
| `/chat` | GET | Public | None | Chat UI assistant interface |
| `/healthz` | GET | Public | None | Node health status and version |
| `/api/features` | GET | Public | None | List of registered mesh features |
| `/api/leaderboard` | GET | Public | None | Network worker ranking by verified tasks |
| `/api/p2p/orders` | GET | Public | None | Public marketplace order book |
| `/api/tokensink/stats` | GET | Public | None | Deflationary metrics (burned tokens, lottery pool) |
| `/api/worker/download` | GET | Public | None | Download worker client script (`nexus_worker.py`) |
| `/download/worker` | GET | Public | None | Direct alias for downloading worker client script |
| `/api/worker/ota_check` | GET | Public | Cryptographic HMAC | Worker version check & OTA hash signature |
| `/api/worker/update_check` | GET | Public | Cryptographic HMAC | Alias for `/api/worker/ota_check` |
| `/api/worker/ota_download` | GET | Public | Cryptographic HMAC | Worker code download with pinned signature |
| `/api/worker/latest_script` | GET | Public | Cryptographic HMAC | Alias for `/api/worker/ota_download` |
| `/api/brain/safetensors` | GET | Public | None | Public download of open Safetensors model shard weights |
| `/api/crypto/quantum_spec` | GET | Public | None | Public cryptographic specification (HSQK-4096 params) |
| `/api/machines` | GET | Public (Redacted) | None / Owner for raw | Physical machine status (IP/port targets redacted unless owner) |
| `/api/p2p/leaderboard` | GET | Public | None | Alias for `/api/leaderboard` |
| `/api/tunnel/status` | GET | Public (Redacted) | None / Owner for raw | Cloudflare tunnel status (`github_gist_id` redacted unless owner) |
| `/api/tunnel/bootstrap` | GET | Public (Redacted) | None / Owner for raw | Anchor bootstrap payload (`github_gist_id` redacted unless owner) |
| `/api/learning/status` | GET | Public (Redacted) | None / Owner for raw | Continuous learning state (Host local paths redacted unless owner) |
| `/api/brain/status` | GET | Public | None | Brain Matrix autonomy era status |
| `/api/lottery/status` | GET | Public | None | Current lottery jackpot and tickets count |
| `/api/worker/register` | POST | Public (PoW) | Micro-PoW / IP Guard | Register new edge worker node (Micro-PoW challenge) |
| `/api/auth/session` | POST | Public | Scrypt Password / Lockout | Authenticate session and obtain cookie |
| `/api/worker/pull_task` | GET | Worker / Owner | `X-Worker-Key` or Bearer | Pull pending tasks for registered worker node |
| `/api/worker/heartbeat` | POST | Worker | Worker Key / HMAC Proof | Send periodic heartbeat and claim uptime rewards |
| `/api/worker/settle_task`| POST | Worker | Worker Key / HMAC Proof | Submit signed task results for verification and settlement |
| `/api/p2p/my_trades` | GET | Worker / Owner | `X-Worker-Key` / Cookie | List authenticated worker's active trade orders |
| `/api/staking/status` | GET | Worker / Owner | `X-Worker-Key` / Cookie | View authenticated worker's staking balance & yield |
| `/api/supercomputer/instances` | GET | Worker / Owner | `X-Worker-Key` / Cookie | View instances rented by authenticated worker |
| `/api/brain/worker_deltas` | GET | Worker / Owner | `X-Worker-Key` / Cookie | View shard weight updates for authenticated worker |
| `/api/p2p/buy` | POST | Worker / Owner | Worker Key / Auth Token | Place buy order on P2P market |
| `/api/p2p/sell` | POST | Worker / Owner | Worker Key / Auth Token | Place sell order on P2P market (escrow locked) |
| `/api/p2p/confirm_payment` | POST | Worker / Owner | Worker Key / Auth Token | Confirm payment sent for P2P order |
| `/api/p2p/release` | POST | Worker / Owner | Worker Key / Auth Token | Release escrowed credits to buyer |
| `/api/p2p/cancel` | POST | Worker / Owner | Worker Key / Auth Token | Cancel order and refund escrow (pre-payment only) |
| `/api/p2p/dispute` | POST | Worker / Owner | Worker Key / Auth Token | Raise dispute on pending order (freezes trade escrow) |
| `/api/lottery/buy_ticket` | POST | Worker / Owner | Worker Key / Auth Token | Spend credits to buy lottery tickets |
| `/api/staking/stake` | POST | Worker / Owner | Worker Key / Auth Token | Stake credits in deflationary staking vault |
| `/api/staking/claim` | POST | Worker / Owner | Worker Key / Auth Token | Claim staking yield rewards |
| `/api/supercomputer/rent` | POST | Worker / Owner | Worker Key / Auth Token | Rent compute instances using credits |
| `/api/supercomputer/job` | POST | Worker / Owner | Worker Key / Auth Token | Dispatch compute job to rented instance |
| `/api/supercomputer/terminate` | POST | Worker / Owner | Worker Key / Auth Token | Terminate rented compute instance |
| `/api/worker/enqueue_task` | POST | Hub Owner / Auth | `DASHBOARD_TOKEN` / Cookie | Enqueue commercial compute/LLM task to worker pool |
| `/api/machine/connect` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Connect to CNC/3D-Printer/Robotic machine |
| `/api/machine/command` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Send G-code or machine instruction |
| `/api/brain/sync` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Sync weight matrices across shards |
| `/api/brain/route` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Route model inference prompt |
| `/api/brain/self_play` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Trigger self-play synthetic data generation |
| `/api/brain/fedavg` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Execute Federated Averaging on worker LoRA weights |
| `/api/brain/swarm_infer` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Dispatch parallel inference across shard swarm |
| `/api/ide/execute` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Execute Python in isolated AST sandbox |
| `/api/ide/file/save` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Save project files in IDE workspace |
| `/api/ide/projects/create` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Create project directory |
| `/api/learning/train` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Trigger QLoRA fine-tuning training cycle |
| `/api/learning/verify` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Trigger paired bootstrap evaluation gate |
| `/api/learning/deploy` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Promote candidate LoRA adapter to production |
| `/api/learning/rollback` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Roll back active adapter to baseline |
| `/api/learning/kill_switch` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Engage emergency learning kill switch |
| `/api/p2p/dispute/resolve` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Owner dispute resolution authority |
| `/api/lottery/draw` | POST | Hub Owner | `DASHBOARD_TOKEN` / Cookie | Trigger lottery draw with commit-reveal randomness |
