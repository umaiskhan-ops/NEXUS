"""Embedded Single-Page Web Studio & Cloud IDE for Sovereign Mesh Node.
Zero external dependencies; fully responsive dark-mode UI for Chat, Cloud IDE & Sandbox,
Direct Feature Execution, and Distributed Mesh Monitoring.
"""
from __future__ import annotations

import json


def get_web_ui_html(node_id: str, active_models: list, feature_counts: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NEXUS Sovereign Studio & Cloud IDE</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #e6edf3;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --accent-glow: rgba(88, 166, 255, 0.15);
      --success: #3fb950;
      --warning: #d29922;
      --danger: #f85149;
      --code-bg: #0b0f14;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    header {{
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      padding: 0.75rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 1rem;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .brand-icon {{
      width: 28px;
      height: 28px;
      background: linear-gradient(135deg, #58a6ff, #1f6feb);
      border-radius: 6px;
      display: grid;
      place-items: center;
      color: white;
      font-weight: 800;
      font-size: 0.9rem;
    }}
    .stats-bar {{
      display: flex;
      gap: 1.25rem;
      font-size: 0.82rem;
    }}
    .stat-pill {{
      display: flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.25rem 0.6rem;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border);
      border-radius: 999px;
    }}
    .status-dot {{
      width: 8px;
      height: 8px;
      background: var(--success);
      border-radius: 50%;
      box-shadow: 0 0 6px var(--success);
    }}
    .main-layout {{
      display: grid;
      grid-template-columns: 300px 1fr;
      flex: 1;
      height: calc(100vh - 65px);
      overflow: hidden;
    }}
    @media (max-width: 900px) {{
      .main-layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ display: none; }}
    }}
    .sidebar {{
      background: var(--card-bg);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .sidebar-header {{
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border);
    }}
    .search-input {{
      width: 100%;
      padding: 0.5rem 0.75rem;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      font-size: 0.85rem;
      outline: none;
    }}
    .search-input:focus {{ border-color: var(--accent); }}
    .features-list {{
      flex: 1;
      overflow-y: auto;
      padding: 0.5rem;
    }}
    .block-header {{
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      padding: 0.6rem 0.5rem 0.2rem;
    }}
    .feature-item {{
      padding: 0.45rem 0.6rem;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
      font-size: 0.82rem;
      transition: background 0.15s ease;
    }}
    .feature-item:hover {{
      background: rgba(88, 166, 255, 0.1);
      color: var(--accent);
    }}
    .feature-badge {{
      font-size: 0.68rem;
      padding: 0.15rem 0.35rem;
      border-radius: 4px;
      background: rgba(255, 255, 255, 0.06);
    }}
    .badge-vip {{ background: rgba(210, 153, 34, 0.2); color: var(--warning); }}
    .badge-pro {{ background: rgba(88, 166, 255, 0.2); color: var(--accent); }}
    .badge-free {{ background: rgba(63, 185, 80, 0.2); color: var(--success); }}

    .content-area {{
      display: flex;
      flex-direction: column;
      height: 100%;
      background: var(--bg);
      overflow: hidden;
    }}
    .tabs-nav {{
      display: flex;
      border-bottom: 1px solid var(--border);
      background: var(--card-bg);
      padding: 0 1rem;
      overflow-x: auto;
    }}
    .tab-btn {{
      padding: 0.75rem 1.15rem;
      background: none;
      border: none;
      color: var(--text-muted);
      font-weight: 600;
      font-size: 0.85rem;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.2s ease;
      white-space: nowrap;
    }}
    .tab-btn.active {{
      color: var(--text);
      border-bottom-color: var(--accent);
    }}
    .tab-content {{
      flex: 1;
      display: none;
      flex-direction: column;
      height: calc(100% - 46px);
      overflow: hidden;
    }}
    .tab-content.active {{
      display: flex;
    }}

    /* Chat View */
    .chat-messages {{
      flex: 1;
      overflow-y: auto;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }}
    .msg-card {{
      max-width: 85%;
      padding: 1rem 1.25rem;
      border-radius: 10px;
      line-height: 1.5;
      font-size: 0.92rem;
    }}
    .msg-user {{
      align-self: flex-end;
      background: #1f6feb;
      color: white;
      border-bottom-right-radius: 2px;
    }}
    .msg-assistant {{
      align-self: flex-start;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-bottom-left-radius: 2px;
    }}
    .msg-meta {{
      font-size: 0.72rem;
      color: var(--text-muted);
      margin-top: 0.5rem;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}
    .code-box {{
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.8rem;
      margin: 0.6rem 0;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 0.84rem;
      white-space: pre-wrap;
      overflow-x: auto;
    }}
    .chat-composer {{
      padding: 1rem 1.5rem;
      background: var(--card-bg);
      border-top: 1px solid var(--border);
      display: flex;
      gap: 0.75rem;
    }}
    .chat-input {{
      flex: 1;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      padding: 0.75rem 1rem;
      font-size: 0.92rem;
      outline: none;
      resize: none;
      min-height: 44px;
      max-height: 140px;
    }}
    .chat-input:focus {{ border-color: var(--accent); }}
    .send-btn {{
      background: #238636;
      color: white;
      border: none;
      border-radius: 6px;
      padding: 0.45rem 1rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.85rem;
      transition: background 0.15s ease;
    }}
    .send-btn:hover {{ background: #2ea043; }}
    .send-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}

    /* Runner View */
    .runner-container {{
      padding: 1.5rem;
      overflow-y: auto;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }}
    .form-row {{
      display: grid;
      grid-template-columns: 140px 1fr;
      align-items: center;
      gap: 1rem;
    }}
    .form-label {{ font-size: 0.85rem; font-weight: 600; color: var(--text-muted); }}
    .form-control {{
      width: 100%;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 0.6rem 0.8rem;
      font-size: 0.88rem;
      outline: none;
    }}
    .form-control:focus {{ border-color: var(--accent); }}

    /* Workers View */
    .workers-view {{
      padding: 1.5rem;
      overflow-y: auto;
      flex: 1;
    }}
    .worker-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 1rem;
      font-size: 0.85rem;
    }}
    .worker-table th, .worker-table td {{
      padding: 0.75rem 1rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    .worker-table th {{
      background: var(--card-bg);
      color: var(--text-muted);
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-icon">N</div>
      <span>NEXUS Sovereign Studio & Cloud IDE</span>
    </div>
    <div class="stats-bar">
      <div class="stat-pill"><div class="status-dot"></div> Node: <strong style="margin-left:2px">{node_id[:8]}</strong></div>
      <div class="stat-pill">⚡ Features: <strong>130</strong></div>
      <div class="stat-pill">🤖 Cloud Models: <strong id="model-count">{len(active_models)}</strong></div>
      <div class="stat-pill">🔒 Sandbox: <strong style="color:var(--success)">Active</strong></div>
    </div>
  </header>

  <div class="main-layout">
    <!-- Sidebar: 130 Features Directory -->
    <div class="sidebar">
      <div class="sidebar-header">
        <input type="text" id="feature-search" class="search-input" placeholder="Search 130 capabilities...">
      </div>
      <div class="features-list" id="features-container">
        <!-- populated dynamically -->
      </div>
    </div>

    <!-- Main Workspace -->
    <div class="content-area">
      <nav class="tabs-nav">
        <button class="tab-btn active" onclick="switchTab('ide')">💻 Cloud IDE & Sandbox</button>
        <button class="tab-btn" onclick="switchTab('chat')">💬 AGI Chat Assistant</button>
        <button class="tab-btn" onclick="switchTab('runner')">⚡ Direct Feature Studio</button>
        <button class="tab-btn" onclick="switchTab('workers')">🌐 Workers & Economy</button>
        <button class="tab-btn" onclick="switchTab('status')">📊 Node Telemetry</button>
      </nav>

      <!-- TAB 1: CLOUD IDE & TEST SANDBOX -->
      <div id="tab-ide" class="tab-content active">
        <div style="padding: 0.75rem 1.25rem; border-bottom: 1px solid var(--border); background: var(--card-bg); display: flex; flex-direction: column; gap: 0.5rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
            <div>
              <div style="display: flex; align-items: center; gap: 0.6rem;">
                <h3 style="font-size: 1.05rem; font-weight: 700;">💻 Sovereign Cloud IDE & Execution Sandbox</h3>
                <span style="font-size: 0.7rem; padding: 0.15rem 0.45rem; background: rgba(63, 185, 80, 0.2); color: var(--success); border-radius: 4px; font-weight: 600;">SUBPROCESS ISOLATION READY</span>
              </div>
              <p style="color: var(--text-muted); font-size: 0.8rem; margin-top: 0.2rem;">
                Enter what you want to build. Sovereign Mesh generates the Python code, executes it in a live sandbox, tests it, and auto-fixes bugs!
              </p>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <button class="send-btn" style="background:#238636" onclick="generateIdeCode()">🚀 Generate Code</button>
              <button class="send-btn" style="background:#d29922" onclick="autoDebugFixLoop()">🛠️ Auto-Fix Loop</button>
            </div>
          </div>
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <input type="text" id="ide-prompt" class="search-input" style="flex:1" placeholder="Describe what to build... (e.g. Build an algorithm to find primes up to N and measure execution time, or a REST API)">
          </div>
          <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; font-size: 0.75rem; color: var(--text-muted);">
            <span>Quick Presets:</span>
            <span class="feature-badge badge-pro" style="cursor:pointer" onclick="setIdePreset('primes')">⚡ Prime Sieve Benchmark</span>
            <span class="feature-badge badge-pro" style="cursor:pointer" onclick="setIdePreset('matrix')">📊 Matrix Multiplication</span>
            <span class="feature-badge badge-pro" style="cursor:pointer" onclick="setIdePreset('json_validator')">🛡️ Schema Validator</span>
            <span class="feature-badge badge-pro" style="cursor:pointer" onclick="setIdePreset('crypto')">🔐 Token Generator</span>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 55% 45%; flex: 1; overflow: hidden; height: 100%;">
          <!-- Left: Code Editor -->
          <div style="display: flex; flex-direction: column; border-right: 1px solid var(--border); background: #0b0f14; overflow: hidden;">
            <div style="padding: 0.4rem 1rem; background: var(--card-bg); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
              <span style="font-family: monospace; font-size: 0.82rem; color: var(--accent);">📄 main.py <span style="color:var(--text-muted)">(Python 3.10)</span></span>
              <div style="display: flex; gap: 0.4rem;">
                <button class="send-btn" style="background: #238636; padding: 0.25rem 0.6rem; font-size: 0.78rem;" onclick="runIdeSandbox()">▶️ Run Code</button>
                <button class="send-btn" style="background: #1f6feb; padding: 0.25rem 0.6rem; font-size: 0.78rem;" onclick="testIdeCode()">🧪 Auto-Test</button>
                <button class="send-btn" style="background: #8957e5; padding: 0.25rem 0.6rem; font-size: 0.78rem;" onclick="reviewIdeCode()">🔍 AI Review</button>
                <button class="send-btn" style="background: #30363d; padding: 0.25rem 0.6rem; font-size: 0.78rem;" onclick="copyIdeCode()">📋 Copy</button>
              </div>
            </div>
            <textarea id="ide-editor" style="flex: 1; width: 100%; background: #0b0f14; color: #7ee787; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 0.86rem; line-height: 1.5; padding: 1rem; border: none; outline: none; resize: none; tab-size: 4;" spellcheck="false"># Welcome to Sovereign Cloud IDE & Sandbox
# Click '▶️ Run Code' to execute in the isolated subprocess sandbox
# Or type an instruction in the top prompt bar and click '🚀 Generate Code'

def compute_primes(limit: int):
    sieve = [True] * (limit + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            for j in range(i*i, limit + 1, i):
                sieve[j] = False
    return [i for i, is_prime in enumerate(sieve) if is_prime]

if __name__ == "__main__":
    import time
    t0 = time.perf_counter()
    primes = compute_primes(50000)
    elapsed = time.perf_counter() - t0
    print(f"Found {{len(primes)}} primes up to 50,000 in {{elapsed*1000:.2f}}ms")
    print(f"Top 10 largest: {{primes[-10:]}}")
</textarea>
          </div>

          <!-- Right: Terminal & Results -->
          <div style="display: flex; flex-direction: column; background: #070a0d; overflow: hidden;">
            <div style="padding: 0.4rem 1rem; background: var(--card-bg); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
              <div style="display: flex; gap: 0.5rem; align-items: center;">
                <span style="font-size: 0.82rem; font-weight: 600;">💻 Terminal & Sandbox Output</span>
                <span id="ide-status-badge" style="font-size: 0.7rem; padding: 0.15rem 0.4rem; background: rgba(255,255,255,0.06); border-radius: 4px;">IDLE</span>
              </div>
              <button class="send-btn" style="background: transparent; color: var(--text-muted); border: 1px solid var(--border); padding: 0.2rem 0.5rem; font-size: 0.74rem;" onclick="clearIdeTerminal()">Clear Console</button>
            </div>
            <div id="ide-terminal" style="flex: 1; padding: 1rem; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 0.84rem; line-height: 1.5; color: #e6edf3; overflow-y: auto; white-space: pre-wrap;">
<span style="color: #58a6ff;">[Sovereign Mesh Sandbox Terminal Initialized]</span>
- Python 3.10 Subprocess Sandbox Active
- Ready to compile, execute, test, and auto-debug code.
Type an instruction or click '▶️ Run Code' above.</div>
            <div style="padding: 0.4rem 1rem; background: var(--card-bg); border-top: 1px solid var(--border); font-size: 0.75rem; color: var(--text-muted); display: flex; justify-content: space-between;">
              <span id="ide-exit-code">Exit Code: -</span>
              <span id="ide-exec-time">Execution Time: -</span>
              <span>Isolation: Disposable Subprocess</span>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 2: Chat Assistant -->
      <div id="tab-chat" class="tab-content">
        <div class="chat-messages" id="chat-stream">
          <div class="msg-card msg-assistant">
            <strong>Sovereign Mesh Assistant</strong>
            <p style="margin-top:0.4rem">Assalam-o-Alaikum! Sovereign Mesh AGI online hai. Aap yahan pure natural language me koi bhi task type kar sakte hain (e.g. <em>"Write a Python script for web scraping"</em>, <em>"Audit security vulnerabilities"</em>, ya <em>"Analyze this dataset"</em>).</p>
            <div class="msg-meta">
              <span>Model Mesh: Online</span>
              <span>130 Features Ready</span>
            </div>
          </div>
        </div>

        <div class="chat-composer">
          <textarea id="prompt-input" class="chat-input" rows="1" placeholder="Type your instruction or prompt... (e.g. Write a python scraper, /features, /status_grid)"></textarea>
          <button id="send-btn" class="send-btn" onclick="handleSend()">
            <span>Send</span>
          </button>
        </div>
      </div>

      <!-- TAB 3: Direct Feature Runner -->
      <div id="tab-runner" class="tab-content">
        <div class="runner-container">
          <h3>⚡ Direct Feature Execution Studio</h3>
          <p style="color:var(--text-muted); font-size:0.85rem">Execute any of the 130 modular features directly with granular JSON parameters.</p>

          <div class="form-row">
            <label class="form-label">Select Feature</label>
            <select id="runner-feature-select" class="form-control" onchange="populateFeaturePayload()">
              <!-- populated dynamically -->
            </select>
          </div>

          <div class="form-row" style="align-items:start">
            <label class="form-label" style="padding-top:0.5rem">JSON Payload</label>
            <textarea id="runner-payload" class="form-control" style="font-family:monospace; min-height:160px;">{{}}</textarea>
          </div>

          <div style="display:flex; justify-content:flex-end; gap:0.75rem">
            <button class="send-btn" style="background:#1f6feb" onclick="executeFeatureRunner()">Execute Feature</button>
          </div>

          <div style="margin-top:1rem">
            <h4>Output Result</h4>
            <div id="runner-result" class="code-box">// Result will appear here after execution...</div>
          </div>
        </div>
      </div>

      <!-- TAB 4: Workers & Economy -->
      <div id="tab-workers" class="tab-content">
        <div class="workers-view">
          <h3>🌐 Distributed Mesh Workers & 3 Economic Models</h3>
          <p style="color:var(--text-muted); font-size:0.85rem; margin-bottom:1rem">
            External worker nodes contribute compute and earn barter credits or 70/30 enterprise revenue shares.
          </p>
          <button class="send-btn" style="background:#30363d; padding:0.4rem 0.8rem; font-size:0.8rem; margin-bottom:1rem" onclick="refreshStatus()">Refresh Network</button>
          <table class="worker-table">
            <thead>
              <tr>
                <th>Worker ID</th>
                <th>Status</th>
                <th>Credits</th>
                <th>Tier</th>
                <th>Payout Address</th>
                <th>Jobs Completed</th>
              </tr>
            </thead>
            <tbody id="workers-tbody">
              <tr><td colspan="6" style="text-align:center; color:var(--text-muted)">Loading mesh workers...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- TAB 5: Status / Telemetry -->
      <div id="tab-status" class="tab-content">
        <div class="workers-view">
          <h3>📊 Node Telemetry & Sovereign Ledger</h3>
          <pre id="telemetry-pre" class="code-box" style="min-height:350px">Loading telemetry...</pre>
        </div>
      </div>

    </div>
  </div>

  <script>
    let allFeatures = [];
    let featureMap = {{}};

    function switchTab(name) {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById('tab-' + name).classList.add('active');
      if (name === 'workers' || name === 'status') refreshStatus();
    }}

    /* --- CLOUD IDE FUNCTIONS --- */
    function logToIdeTerminal(text, type='info') {{
      const term = document.getElementById('ide-terminal');
      const time = new Date().toLocaleTimeString();
      let color = '#e6edf3';
      if (type === 'error') color = '#f85149';
      if (type === 'success') color = '#3fb950';
      if (type === 'info') color = '#58a6ff';
      if (type === 'warning') color = '#d29922';

      term.innerHTML += `\\n<span style="color:${{color}}">[${{time}}] ${{escapeHtml(text)}}</span>`;
      term.scrollTop = term.scrollHeight;
    }}

    function clearIdeTerminal() {{
      document.getElementById('ide-terminal').innerHTML = '<span style="color:#58a6ff;">[Console Cleared]</span>';
    }}

    async function runIdeSandbox() {{
      const code = document.getElementById('ide-editor').value;
      const badge = document.getElementById('ide-status-badge');
      badge.textContent = 'RUNNING';
      badge.style.background = 'rgba(210, 153, 34, 0.3)';
      badge.style.color = '#d29922';

      logToIdeTerminal('Compiling bytecode and executing in isolated sandbox...', 'info');
      const t0 = performance.now();

      try {{
        const res = await fetch('/api/ide/execute', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ code: code, timeout: 10.0 }})
        }});
        const data = await res.json();
        const elapsed = ((performance.now() - t0) / 1000).toFixed(3);
        document.getElementById('ide-exec-time').textContent = `Execution Time: ${{elapsed}}s`;
        document.getElementById('ide-exit-code').textContent = `Exit Code: ${{data.returncode !== undefined ? data.returncode : 'ERR'}}`;

        if (data.ok) {{
          badge.textContent = 'PASS (0)';
          badge.style.background = 'rgba(63, 185, 80, 0.3)';
          badge.style.color = '#3fb950';
          logToIdeTerminal(data.stdout || '(Program completed with no stdout output)', 'success');
        }} else {{
          badge.textContent = 'ERROR (' + (data.returncode || 1) + ')';
          badge.style.background = 'rgba(248, 81, 73, 0.3)';
          badge.style.color = '#f85149';
          if (data.stderr) logToIdeTerminal(data.stderr, 'error');
          if (data.compile && !data.compile.ok) logToIdeTerminal('Compiler: ' + data.compile.error, 'error');
        }}
      }} catch (err) {{
        badge.textContent = 'FAIL';
        logToIdeTerminal('Execution failure: ' + err.toString(), 'error');
      }}
    }}

    async function generateIdeCode() {{
      const prompt = document.getElementById('ide-prompt').value.trim();
      if (!prompt) {{
        alert('Please enter a description of what you want to build in the prompt bar.');
        return;
      }}
      logToIdeTerminal(`Dispatching prompt to JIT Compiler model: "${{prompt}}"`, 'info');
      const badge = document.getElementById('ide-status-badge');
      badge.textContent = 'GENERATING';

      try {{
        const res = await fetch('/api/ide/generate', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ prompt: prompt, mode: 'generate' }})
        }});
        const data = await res.json();
        if (data.ok && data.code) {{
          document.getElementById('ide-editor').value = data.code;
          logToIdeTerminal(`Successfully generated Python script via ${{data.model || 'Mesh JIT Compiler'}}! Ready to run.`, 'success');
          badge.textContent = 'CODE READY';
        }} else {{
          logToIdeTerminal('Code generation failed: ' + (data.error || 'Unknown error'), 'error');
        }}
      }} catch(err) {{
        logToIdeTerminal('Error connecting to backend: ' + err.toString(), 'error');
      }}
    }}

    async function autoDebugFixLoop() {{
      const prompt = document.getElementById('ide-prompt').value.trim() || 'Fix and verify the code in editor';
      const code = document.getElementById('ide-editor').value;
      logToIdeTerminal('Launching Recursive Autonomous Debug & Fix Loop (up to 3 iterations)...', 'warning');
      const badge = document.getElementById('ide-status-badge');
      badge.textContent = 'AUTO-FIXING';

      try {{
        const res = await fetch('/api/ide/generate', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ prompt: prompt, code: code, mode: 'debug_fix', max_iterations: 3 }})
        }});
        const data = await res.json();
        if (data.code) {{
          document.getElementById('ide-editor').value = data.code;
        }}
        if (data.history && data.history.length > 0) {{
          data.history.forEach(h => {{
            logToIdeTerminal(`Iteration ${{h.attempt}}: ok=${{h.ok}} ${{h.error ? '| error: ' + h.error : ''}}`, h.ok ? 'success' : 'warning');
          }});
        }}
        badge.textContent = data.status || 'DONE';
        logToIdeTerminal(`Auto-Debug Loop Finished: Status = ${{data.status}}`, data.ok ? 'success' : 'error');
      }} catch(err) {{
        logToIdeTerminal('Auto-debug error: ' + err.toString(), 'error');
      }}
    }}

    async function testIdeCode() {{
      const code = document.getElementById('ide-editor').value;
      logToIdeTerminal('Generating unittests and testing in sandbox...', 'info');
      try {{
        const res = await fetch('/api/ide/test', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ code: code }})
        }});
        const data = await res.json();
        logToIdeTerminal('=== AUTO-GENERATED TEST SUITE EXECUTION ===', 'info');
        if (data.stdout) logToIdeTerminal(data.stdout, 'info');
        if (data.stderr) logToIdeTerminal(data.stderr, data.ok ? 'success' : 'warning');
        logToIdeTerminal(`Test Suite Result: ${{data.ok ? 'ALL TESTS PASSED' : 'TEST FAILURES DETECTED'}}`, data.ok ? 'success' : 'error');
      }} catch(err) {{
        logToIdeTerminal('Test run failure: ' + err.toString(), 'error');
      }}
    }}

    async function reviewIdeCode() {{
      const code = document.getElementById('ide-editor').value;
      logToIdeTerminal('Analyzing AST & generating automated code review...', 'info');
      try {{
        const res = await fetch('/api/ide/review', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ code: code }})
        }});
        const data = await res.json();
        logToIdeTerminal('=== AI CODE REVIEW & SECURITY FINDINGS ===', 'warning');
        logToIdeTerminal(data.review || 'No critical issues detected.', 'info');
      }} catch(err) {{
        logToIdeTerminal('Review failure: ' + err.toString(), 'error');
      }}
    }}

    function copyIdeCode() {{
      const code = document.getElementById('ide-editor').value;
      navigator.clipboard.writeText(code).then(() => {{
        logToIdeTerminal('Code copied to clipboard.', 'info');
      }});
    }}

    function setIdePreset(name) {{
      const presets = {{
        'primes': `# Prime Sieve Benchmark\\ndef compute_primes(limit: int):\\n    sieve = [True] * (limit + 1)\\n    sieve[0] = sieve[1] = False\\n    for i in range(2, int(limit**0.5) + 1):\\n        if sieve[i]:\\n            for j in range(i*i, limit + 1, i):\\n                sieve[j] = False\\n    return [i for i, is_prime in enumerate(sieve) if is_prime]\\n\\nif __name__ == "__main__":\\n    import time\\n    t0 = time.perf_counter()\\n    primes = compute_primes(50000)\\n    elapsed = time.perf_counter() - t0\\n    print(f"Computed {{len(primes)}} primes up to 50,000 in {{elapsed*1000:.2f}}ms")`,
        'matrix': `# 2D Matrix Multiplication\\ndef matrix_multiply(A, B):\\n    rows_A, cols_A = len(A), len(A[0])\\n    rows_B, cols_B = len(B), len(B[0])\\n    assert cols_A == rows_B, "Incompatible dimensions"\\n    C = [[0] * cols_B for _ in range(rows_A)]\\n    for i in range(rows_A):\\n        for j in range(cols_B):\\n            for k in range(cols_A):\\n                C[i][j] += A[i][k] * B[k][j]\\n    return C\\n\\nif __name__ == "__main__":\\n    A = [[1, 2], [3, 4]]\\n    B = [[5, 6], [7, 8]]\\n    print("Matrix A x B =", matrix_multiply(A, B))`,
        'json_validator': `# JSON Structure Validator\\nimport json\\n\\ndef validate_record(rec_str: str) -> bool:\\n    data = json.loads(rec_str)\\n    required = {{"id", "name", "role", "active"}}\\n    return required.issubset(data.keys()) and isinstance(data["active"], bool)\\n\\nif __name__ == "__main__":\\n    sample = '{{\\"id\\": 101, \\"name\\": \\"Ali\\", \\"role\\": \\"Architect\\", \\"active\\": true}}'\\n    print("Validation passed:", validate_record(sample))`,
        'crypto': `# Secure Token Generator\\nimport secrets\\nimport hashlib\\n\\ndef make_secure_credentials():\\n    raw_token = secrets.token_hex(16)\\n    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()\\n    return raw_token, token_hash\\n\\nif __name__ == "__main__":\\n    tok, h = make_secure_credentials()\\n    print(f"Generated Token: {{tok}}")\\n    print(f"SHA-256 Hash:   {{h}}")`
      }};
      if (presets[name]) {{
        document.getElementById('ide-editor').value = presets[name];
        logToIdeTerminal(`Loaded preset: ${{name}}`, 'info');
      }}
    }}

    /* --- GENERAL FEATURES & TABS --- */
    async function loadFeatures() {{
      try {{
        const res = await fetch('/api/features');
        if (!res.ok) return;
        allFeatures = await res.json();
        renderFeatures(allFeatures);
        populateSelect(allFeatures);
      }} catch (err) {{
        console.error('Failed to load features', err);
      }}
    }}

    function renderFeatures(list) {{
      const cont = document.getElementById('features-container');
      cont.innerHTML = '';
      const blocks = {{}};
      list.forEach(f => {{
        if (!blocks[f.block]) blocks[f.block] = [];
        blocks[f.block].push(f);
        featureMap[f.key] = f;
      }});

      for (const [blk, feats] of Object.entries(blocks)) {{
        const bHeader = document.createElement('div');
        bHeader.className = 'block-header';
        bHeader.textContent = blk.replace('_', ' ');
        cont.appendChild(bHeader);

        feats.forEach(f => {{
          const item = document.createElement('div');
          item.className = 'feature-item';
          const tierClass = f.tier === 'SOVEREIGN_VIP' ? 'badge-vip' : (f.tier === 'PRO' ? 'badge-pro' : 'badge-free');
          item.innerHTML = `
            <span style="font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">${{f.name}}</span>
            <span class="feature-badge ${{tierClass}}">${{f.tier}}</span>
          `;
          item.onclick = () => {{
            switchTab('runner');
            document.querySelectorAll('.tab-btn')[2].classList.add('active');
            document.querySelectorAll('.tab-btn')[0].classList.remove('active');
            document.getElementById('runner-feature-select').value = f.key;
            populateFeaturePayload();
          }};
          cont.appendChild(item);
        }});
      }}
    }}

    function populateSelect(list) {{
      const sel = document.getElementById('runner-feature-select');
      sel.innerHTML = '';
      list.forEach(f => {{
        const opt = document.createElement('option');
        opt.value = f.key;
        opt.textContent = `${{f.name}} (${{f.key}}) [${{f.tier}}]`;
        sel.appendChild(opt);
      }});
      populateFeaturePayload();
    }}

    function populateFeaturePayload() {{
      const fkey = document.getElementById('runner-feature-select').value;
      const samples = {{
        "code_generation": {{"prompt": "Write a Python script to download files with progress bar", "language": "python"}},
        "data_analysis": {{"numbers": [12, 45, 67, 89, 23, 56, 78, 90]}},
        "trend_forecasting": {{"values": [10, 15, 20, 25, 30], "horizon": 3}},
        "unit_test_generator": {{"code": "def add(a, b): return a + b"}},
        "ast_static_analyzer": {{"code": "import os\\ndef test(): pass"}},
        "threat_modeling": {{"architecture": "User -> API Gateway -> Auth Service -> PostgreSQL"}},
        "natural_language_understanding": {{"text": "Analyze system performance"}}
      }};
      document.getElementById('runner-payload').value = JSON.stringify(samples[fkey] || {{"input": "sample text"}}, null, 2);
    }}

    async function executeFeatureRunner() {{
      const fkey = document.getElementById('runner-feature-select').value;
      let payload = {{}};
      try {{
        payload = JSON.parse(document.getElementById('runner-payload').value);
      }} catch(e) {{
        alert('Invalid JSON in payload: ' + e.message);
        return;
      }}
      const outBox = document.getElementById('runner-result');
      outBox.textContent = 'Executing on sovereign mesh...';
      try {{
        const res = await fetch('/api/run', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ feature: fkey, payload: payload }})
        }});
        const data = await res.json();
        outBox.textContent = JSON.stringify(data, null, 2);
      }} catch (err) {{
        outBox.textContent = 'Error: ' + err.toString();
      }}
    }}

    async function handleSend() {{
      const inp = document.getElementById('prompt-input');
      const text = inp.value.trim();
      if (!text) return;
      inp.value = '';

      const stream = document.getElementById('chat-stream');
      const userCard = document.createElement('div');
      userCard.className = 'msg-card msg-user';
      userCard.textContent = text;
      stream.appendChild(userCard);

      const botCard = document.createElement('div');
      botCard.className = 'msg-card msg-assistant';
      botCard.innerHTML = '<em>Thinking... (routing through sovereign mesh models)</em>';
      stream.appendChild(botCard);
      stream.scrollTop = stream.scrollHeight;

      try {{
        const res = await fetch('/api/chat', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ prompt: text }})
        }});
        const data = await res.json();
        let replyHtml = '';
        if (data.reply) {{
          replyHtml = `<p style="white-space:pre-wrap">${{escapeHtml(data.reply)}}</p>`;
        }} else if (data.result) {{
          replyHtml = `<p><strong>Executed Feature:</strong> ${{data.feature || 'Feature'}}</p><div class="code-box">${{escapeHtml(JSON.stringify(data.result, null, 2))}}</div>`;
        }} else {{
          replyHtml = `<div class="code-box">${{escapeHtml(JSON.stringify(data, null, 2))}}</div>`;
        }}

        const meta = `
          <div class="msg-meta">
            <span>Model: ${{data.model || 'Mesh Consensus'}}</span>
            ${{data.latency_s ? `<span>Latency: ${{data.latency_s}}s</span>` : ''}}
            <span>Status: ${{data.status || 'OK'}}</span>
          </div>
        `;
        botCard.innerHTML = replyHtml + meta;
      }} catch(err) {{
        botCard.innerHTML = `<span style="color:var(--danger)">Error: ${{escapeHtml(err.toString())}}</span>`;
      }}
      stream.scrollTop = stream.scrollHeight;
    }}

    function escapeHtml(str) {{
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }}

    async function refreshStatus() {{
      try {{
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const s = await res.json();
        document.getElementById('telemetry-pre').textContent = JSON.stringify(s, null, 2);

        const tbody = document.getElementById('workers-tbody');
        tbody.innerHTML = '';
        if (!s.nodes || s.nodes.length === 0) {{
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted)">No active external worker nodes connected.</td></tr>';
        }} else {{
          s.nodes.forEach(n => {{
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td><strong>${{n.name || n.id}}</strong></td>
              <td><span class="status-dot"></span> ${{n.status}}</td>
              <td><strong>${{n.credits || 0}}</strong> cr</td>
              <td>${{n.tier || 'COMMUNITY'}}</td>
              <td style="font-family:monospace">${{n.payout_address || 'None'}}</td>
              <td>${{n.jobs_completed || 0}}</td>
            `;
            tbody.appendChild(tr);
          }});
        }}
      }} catch (e) {{
        console.error('Status fetch failed', e);
      }}
    }}

    document.getElementById('prompt-input').addEventListener('keydown', (e) => {{
      if (e.key === 'Enter' && !e.shiftKey) {{
        e.preventDefault();
        handleSend();
      }}
    }});

    document.getElementById('feature-search').addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase();
      const filtered = allFeatures.filter(f => f.name.toLowerCase().includes(q) || f.key.toLowerCase().includes(q) || f.block.toLowerCase().includes(q));
      renderFeatures(filtered);
    }});

    window.onload = () => {{
      loadFeatures();
    }};
  </script>
</body>
</html>
"""
