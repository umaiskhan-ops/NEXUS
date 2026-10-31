"""SUP Agentic Mesh - Next-Generation User-Friendly Web Interface.
Features:
1. Header with Account Key / Worker ID login, Live Credit Balance & 1-Click Worker Download.
2. Option 1: SUP Agentic Mesh Chat (ChatGPT-style with history, new chat, and markdown).
3. Option 2: SUP Agentic Mesh IDE (VS Code-style with file explorer, tabs, terminal & agent copilot).
4. Option 3: Physical Control (Robotic Arm, 3D Printer, CNC, IoT machines & E-Stop).
5. Option 4: BUY / SELL Credits (P2P Marketplace with EasyPaisa, JazzCash & Escrow).
"""
from __future__ import annotations


def get_web_ui_html(node_id: str, active_models: list, feature_counts: dict, csp_nonce: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SUP Agentic Mesh — Enterprise Compute &amp; Autonomous Engineering Cloud</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script nonce="{csp_nonce}" src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs/loader.min.js"></script>
  <style nonce="{csp_nonce}">
    :root {{
      --bg: #090a0f;
      --card-bg: #101218;
      --card-hover: #151821;
      --border: #1e2230;
      --border-subtle: #161924;
      --border-focus: #3b82f6;
      --text: #f1f5f9;
      --text-muted: #8b95a5;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --code-bg: #07080c;
      --sidebar-bg: #0c0e14;
      --vscode-activity: #0c0e14;
      --vscode-side: #101218;
      --vscode-tab: #151821;
      --vscode-tab-active: #090a0f;
      --vscode-editor: #0d0f17;
      --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      -webkit-font-smoothing: antialiased;
      letter-spacing: -0.011em;
    }}
    code, pre, .mono {{
      font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}

    /* Top Institutional Console Header */
    header {{
      background: #0c0e14;
      border-bottom: 1px solid var(--border);
      padding: 0.6rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 1rem;
      z-index: 100;
    }}
    .brand-wrap {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}
    .brand-icon {{
      width: 30px;
      height: 30px;
      background: #131722;
      border: 1px solid #262d40;
      border-radius: 6px;
      display: grid;
      place-items: center;
      color: var(--accent);
      font-weight: 700;
      font-size: 0.85rem;
    }}
    .brand-name {{
      font-size: 0.96rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #f8fafc;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .brand-tag {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.66rem;
      font-weight: 600;
      padding: 0.12rem 0.45rem;
      border-radius: 4px;
      background: rgba(59, 130, 246, 0.1);
      color: #60a5fa;
      border: 1px solid rgba(59, 130, 246, 0.25);
      letter-spacing: 0.03em;
    }}
    .header-actions {{
      display: flex;
      align-items: center;
      gap: 0.65rem;
      flex-wrap: wrap;
    }}

    /* Account Key Bar */
    .account-bar {{
      display: flex;
      align-items: center;
      background: #08090d;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.18rem 0.3rem;
      gap: 0.35rem;
    }}
    .account-input {{
      background: transparent;
      border: none;
      color: var(--text);
      font-size: 0.78rem;
      padding: 0.32rem 0.55rem;
      outline: none;
      width: 215px;
      font-family: 'JetBrains Mono', monospace;
    }}
    .account-input::placeholder {{ color: #525b6d; }}
    .account-btn {{
      background: #161923;
      border: 1px solid #262c3d;
      color: #e2e8f0;
      padding: 0.36rem 0.75rem;
      font-size: 0.78rem;
      font-weight: 500;
      border-radius: 5px;
      cursor: pointer;
      transition: background 0.15s ease, border-color 0.15s ease;
      white-space: nowrap;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
    }}
    .account-btn:hover {{ background: #1e2330; border-color: #3b445e; color: #ffffff; }}
    .account-badge {{
      display: flex;
      align-items: center;
      gap: 0.55rem;
      background: #10131c;
      border: 1px solid var(--border);
      padding: 0.3rem 0.7rem;
      border-radius: 6px;
      font-size: 0.78rem;
      font-weight: 500;
    }}
    .credits-pill {{
      font-family: 'JetBrains Mono', monospace;
      background: rgba(59, 130, 246, 0.1);
      color: #60a5fa;
      border: 1px solid rgba(59, 130, 246, 0.25);
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
      font-size: 0.74rem;
      font-weight: 600;
    }}

    /* Download Worker Button */
    .btn-download {{
      background: #2563eb;
      color: #ffffff;
      text-decoration: none;
      padding: 0.42rem 0.9rem;
      font-size: 0.78rem;
      font-weight: 600;
      border-radius: 5px;
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      border: 1px solid #3b82f6;
      cursor: pointer;
      transition: background 0.15s ease;
      white-space: nowrap;
    }}
    .btn-download:hover {{ background: #1d4ed8; }}

    /* Main Navigation Tabs */
    .nav-tabs-bar {{
      background: #0c0e14;
      border-bottom: 1px solid var(--border);
      display: flex;
      padding: 0 1.5rem;
      gap: 0.25rem;
      overflow-x: auto;
    }}
    .nav-tab-btn {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 0.68rem 1rem;
      font-size: 0.81rem;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      border-bottom: 2px solid transparent;
      transition: color 0.15s ease, border-color 0.15s ease;
      white-space: nowrap;
    }}
    .nav-tab-btn svg {{
      width: 14px;
      height: 14px;
      stroke: currentColor;
      stroke-width: 1.8;
      fill: none;
      opacity: 0.8;
    }}
    .nav-tab-btn:hover {{ color: #e2e8f0; }}
    .nav-tab-btn.active {{
      color: #ffffff;
      font-weight: 600;
      border-bottom-color: var(--accent);
    }}
    .nav-tab-btn.active svg {{
      stroke: var(--accent);
      opacity: 1;
    }}

    /* Workspace Content Areas */
    .workspace-container {{
      flex: 1;
      height: calc(100vh - 110px);
      overflow: hidden;
      display: none;
    }}
    .workspace-container.active {{
      display: flex;
    }}

    /* ========================================================= */
    /* OPTION 1: CHATGPT-STYLE CHAT INTERFACE                    */
    /* ========================================================= */
    .chat-layout {{
      display: grid;
      grid-template-columns: 260px 1fr;
      width: 100%;
      height: 100%;
      overflow: hidden;
    }}
    @media (max-width: 800px) {{
      .chat-layout {{ grid-template-columns: 1fr; }}
      .chat-sidebar {{ display: none; }}
    }}
    .chat-sidebar {{
      background: var(--sidebar-bg);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .new-chat-btn {{
      margin: 0.85rem;
      background: #21262d;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.65rem 1rem;
      border-radius: 8px;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.6rem;
      transition: all 0.2s;
    }}
    .new-chat-btn:hover {{
      background: #30363d;
      border-color: var(--accent);
      color: var(--accent);
    }}
    .chat-history-list {{
      flex: 1;
      overflow-y: auto;
      padding: 0 0.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }}
    .chat-history-item {{
      padding: 0.6rem 0.8rem;
      border-radius: 6px;
      font-size: 0.84rem;
      color: var(--text-muted);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      transition: all 0.15s;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .chat-history-item:hover, .chat-history-item.active {{
      background: rgba(255, 255, 255, 0.05);
      color: var(--text);
    }}
    .chat-history-item .del-btn {{
      opacity: 0;
      color: var(--danger);
      background: transparent;
      border: none;
      cursor: pointer;
      font-size: 0.8rem;
    }}
    .chat-history-item:hover .del-btn {{ opacity: 1; }}

    .chat-main {{
      display: flex;
      flex-direction: column;
      background: var(--bg);
      height: 100%;
      overflow: hidden;
      position: relative;
    }}
    .chat-messages-area {{
      flex: 1;
      overflow-y: auto;
      padding: 2rem 1rem 1rem;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    .chat-messages-inner {{
      width: 100%;
      max-width: 820px;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }}
    .msg-row {{
      display: flex;
      gap: 1rem;
      width: 100%;
    }}
    .msg-avatar {{
      width: 34px;
      height: 34px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      font-weight: 800;
      font-size: 0.85rem;
      flex-shrink: 0;
    }}
    .avatar-user {{
      background: #30363d;
      color: #e6edf3;
    }}
    .avatar-ai {{
      background: linear-gradient(135deg, #1f6feb, #8957e5);
      color: white;
      box-shadow: 0 0 10px rgba(31, 111, 235, 0.4);
    }}
    .msg-body {{
      flex: 1;
      line-height: 1.6;
      font-size: 0.92rem;
      color: var(--text);
    }}
    .msg-body p {{ margin-bottom: 0.6rem; }}
    .msg-body p:last-child {{ margin-bottom: 0; }}
    .code-snippet {{
      background: #0b0f14;
      border: 1px solid var(--border);
      border-radius: 8px;
      margin: 0.75rem 0;
      overflow: hidden;
    }}
    .code-header {{
      background: #161b22;
      border-bottom: 1px solid var(--border);
      padding: 0.4rem 0.8rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.75rem;
      color: var(--text-muted);
      font-family: ui-monospace, monospace;
    }}
    .code-copy-btn {{
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-size: 0.72rem;
      cursor: pointer;
    }}
    .code-copy-btn:hover {{ background: rgba(255,255,255,0.08); }}
    .code-content {{
      padding: 0.85rem;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 0.85rem;
      color: #7ee787;
      line-height: 1.45;
    }}

    .chat-starter-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 0.85rem;
      width: 100%;
      max-width: 820px;
      margin: auto 0;
      padding: 1.5rem 0;
    }}
    .starter-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .starter-card:hover {{
      background: var(--card-hover);
      border-color: var(--accent);
      transform: translateY(-2px);
    }}
    .starter-card h4 {{ font-size: 0.9rem; margin-bottom: 0.3rem; color: var(--text); }}
    .starter-card p {{ font-size: 0.78rem; color: var(--text-muted); line-height: 1.4; }}

    .chat-bottom-bar {{
      padding: 1rem;
      display: flex;
      flex-direction: column;
      align-items: center;
      background: linear-gradient(180deg, transparent, var(--bg) 35%);
    }}
    .chat-input-capsule {{
      width: 100%;
      max-width: 820px;
      background: #161b22;
      border: 1px solid var(--border);
      border-radius: 24px;
      display: flex;
      align-items: center;
      padding: 0.4rem 0.6rem 0.4rem 1.25rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
      transition: border-color 0.2s;
    }}
    .chat-input-capsule:focus-within {{
      border-color: var(--accent);
    }}
    .chat-textarea {{
      flex: 1;
      background: transparent;
      border: none;
      color: var(--text);
      font-size: 0.92rem;
      outline: none;
      resize: none;
      max-height: 140px;
      font-family: inherit;
      line-height: 1.4;
      padding: 0.35rem 0;
    }}
    .chat-send-btn {{
      width: 36px;
      height: 36px;
      background: #238636;
      border: none;
      border-radius: 50%;
      display: grid;
      place-items: center;
      color: white;
      cursor: pointer;
      transition: all 0.2s;
      flex-shrink: 0;
    }}
    .chat-send-btn:hover {{ background: #2ea043; transform: scale(1.05); }}
    .chat-disclaimer {{
      font-size: 0.74rem;
      color: var(--text-muted);
      margin-top: 0.5rem;
    }}

    /* ========================================================= */
    /* OPTION 2: VS CODE-STYLE IDE INTERFACE                     */
    /* ========================================================= */
    .vscode-layout {{
      display: grid;
      grid-template-columns: 48px 230px 1fr 340px;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: var(--vscode-editor);
    }}
    @media (max-width: 1250px) {{
      .vscode-layout {{ grid-template-columns: 48px 220px 1fr; }}
      .agent-side-panel {{ display: none; }}
    }}
    @media (max-width: 850px) {{
      .vscode-layout {{ grid-template-columns: 48px 1fr; }}
      .vscode-explorer {{ display: none; }}
    }}
    .vscode-activity-bar {{
      background: var(--vscode-activity);
      border-right: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 0.5rem 0;
      gap: 0.75rem;
    }}
    .activity-icon {{
      width: 36px;
      height: 36px;
      display: grid;
      place-items: center;
      color: #858585;
      cursor: pointer;
      border-radius: 6px;
      font-size: 1.1rem;
      transition: color 0.15s;
    }}
    .activity-icon:hover, .activity-icon.active {{ color: #ffffff; }}
    .activity-icon.active {{ border-left: 2px solid var(--accent); }}

    .vscode-explorer {{
      background: var(--vscode-side);
      border-right: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .explorer-header {{
      padding: 0.65rem 0.9rem;
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      color: #bbb;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }}
    .file-tree {{
      flex: 1;
      overflow-y: auto;
      padding: 0.4rem 0;
      font-size: 0.82rem;
    }}
    .file-node {{
      padding: 0.35rem 0.9rem;
      color: #cccccc;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      transition: background 0.15s;
      white-space: nowrap;
    }}
    .file-node:hover {{ background: rgba(255, 255, 255, 0.06); }}
    .file-node.active {{
      background: #37373d;
      color: #ffffff;
    }}

    .vscode-editor-panel {{
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      background: var(--vscode-editor);
    }}
    .editor-tabs-bar {{
      background: #181818;
      display: flex;
      align-items: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      overflow-x: auto;
    }}
    .editor-tab {{
      background: var(--vscode-tab);
      padding: 0.5rem 1rem;
      font-size: 0.82rem;
      color: #969696;
      border-right: 1px solid rgba(255, 255, 255, 0.05);
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .editor-tab.active {{
      background: var(--vscode-tab-active);
      color: #ffffff;
      border-top: 1px solid var(--accent);
    }}

    /* Agent Copilot Toolbar in IDE */
    .ide-copilot-toolbar {{
      background: #161b22;
      border-bottom: 1px solid var(--border);
      padding: 0.6rem 1rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}
    .ide-prompt-input {{
      flex: 1;
      min-width: 280px;
      background: #0b0f14;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 0.45rem 0.8rem;
      font-size: 0.85rem;
      outline: none;
    }}
    .ide-prompt-input:focus {{ border-color: var(--accent); }}
    .ide-actions-group {{
      display: flex;
      gap: 0.4rem;
      align-items: center;
    }}
    .ide-btn {{
      padding: 0.4rem 0.8rem;
      font-size: 0.8rem;
      font-weight: 600;
      border-radius: 6px;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.35rem;
      transition: all 0.15s;
    }}
    .ide-btn-run {{ background: #238636; color: white; }}
    .ide-btn-run:hover {{ background: #2ea043; }}
    .ide-btn-build {{ background: #1f6feb; color: white; }}
    .ide-btn-build:hover {{ background: #388bfd; }}
    .ide-btn-fix {{ background: #d29922; color: white; }}
    .ide-btn-fix:hover {{ background: #e3b341; }}
    .ide-btn-test {{ background: #8957e5; color: white; }}

    .editor-split-body {{
      display: grid;
      grid-template-rows: 1fr 200px;
      flex: 1;
      overflow: hidden;
    }}
    .code-editor-wrap {{
      display: flex;
      height: 100%;
      overflow: hidden;
      background: #1e1e1e;
    }}
    .editor-line-numbers {{
      width: 48px;
      padding: 0.75rem 0.5rem;
      text-align: right;
      color: #858585;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 0.85rem;
      line-height: 1.5;
      user-select: none;
      border-right: 1px solid rgba(255, 255, 255, 0.05);
      background: #1e1e1e;
    }}
    .code-textarea {{
      flex: 1;
      background: #1e1e1e;
      border: none;
      outline: none;
      color: #d4d4d4;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 0.86rem;
      line-height: 1.5;
      padding: 0.75rem 1rem;
      resize: none;
      tab-size: 4;
      white-space: pre;
      overflow: auto;
    }}

    /* Bottom Terminal Dock */
    .terminal-dock {{
      background: #181818;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .terminal-nav {{
      background: #1f1f1f;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.25rem 0.8rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }}
    .terminal-tabs {{
      display: flex;
      gap: 1rem;
      font-size: 0.76rem;
      font-weight: 600;
      color: #858585;
    }}
    .terminal-tab-item {{
      cursor: pointer;
      padding: 0.2rem 0;
    }}
    .terminal-tab-item.active {{
      color: #ffffff;
      border-bottom: 1px solid var(--accent);
    }}
    .terminal-screen {{
      flex: 1;
      padding: 0.75rem 1rem;
      font-family: ui-monospace, monospace;
      font-size: 0.82rem;
      line-height: 1.45;
      color: #cccccc;
      overflow-y: auto;
      background: #0f0f0f;
    }}

    /* Agent Side Panel in IDE */
    .agent-side-panel {{
      background: #141820;
      border-left: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      height: 100%;
    }}
    .agent-side-header {{
      padding: 0.75rem 1rem;
      background: #0d1117;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .agent-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      font-size: 0.72rem;
      font-weight: 700;
      background: rgba(63, 185, 80, 0.15);
      color: var(--success);
      border: 1px solid rgba(63, 185, 80, 0.3);
      padding: 0.2rem 0.5rem;
      border-radius: 999px;
    }}
    .agent-timeline {{
      flex: 1;
      overflow-y: auto;
      padding: 0.85rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }}
    .agent-step-card {{
      background: #1c2128;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.75rem;
      font-size: 0.82rem;
    }}
    .btn-launch-vscode {{
      background: #007acc;
      color: white;
      border: 1px solid #0098ff;
      border-radius: 6px;
      padding: 0.35rem 0.75rem;
      font-size: 0.78rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.2s;
    }}
    .btn-launch-vscode:hover {{ background: #0098ff; transform: scale(1.02); }}

    /* ========================================================= */
    /* OPTION 3: PHYSICAL CONTROL DECK                           */
    /* ========================================================= */
    .physical-layout {{
      flex: 1;
      padding: 1.5rem 2rem;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }}
    .e-stop-banner {{
      background: rgba(239, 68, 68, 0.06);
      border: 1px solid rgba(239, 68, 68, 0.35);
      border-radius: 8px;
      padding: 1.15rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }}
    .btn-estop {{
      background: #dc2626;
      color: white;
      border: 1px solid #ef4444;
      padding: 0.6rem 1.35rem;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .btn-estop:hover {{ background: #b91c1c; }}

    .machine-cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
    }}
    .machine-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }}
    .machine-card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .jog-pad {{
      display: grid;
      grid-template-columns: repeat(3, 42px);
      gap: 6px;
      margin: 0.4rem 0;
    }}
    .jog-btn {{
      background: #161922;
      border: 1px solid var(--border);
      color: var(--text);
      height: 36px;
      border-radius: 5px;
      font-size: 0.8rem;
      font-family: var(--font-mono);
      font-weight: 600;
      cursor: pointer;
    }}
    .jog-btn:hover {{ background: #1e2330; border-color: var(--accent); }}

    /* ========================================================= */
    /* OPTION 4: BUY / SELL CREDITS P2P EXCHANGE                 */
    /* ========================================================= */
    .p2p-layout {{
      flex: 1;
      padding: 1.5rem 2rem;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }}
    .p2p-sub-nav {{
      display: flex;
      gap: 0.4rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.6rem;
    }}
    .p2p-tab-btn {{
      background: #13161f;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 0.42rem 0.9rem;
      border-radius: 6px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .p2p-tab-btn:hover {{
      color: var(--text);
      border-color: var(--border-subtle);
    }}
    .p2p-tab-btn.active {{
      background: rgba(59, 130, 246, 0.14);
      color: #60a5fa;
      border-color: rgba(59, 130, 246, 0.4);
    }}
    .p2p-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 0.4rem;
      font-size: 0.82rem;
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }}
    .p2p-table th, .p2p-table td {{
      padding: 0.7rem 1rem;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }}
    .p2p-table th {{
      background: #0d0f14;
      color: var(--text-muted);
      font-weight: 600;
      font-size: 0.74rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}

    .form-box {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.35rem;
      max-width: 650px;
    }}
    .form-group {{
      margin-bottom: 0.9rem;
    }}
    .form-group label {{
      display: block;
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 0.35rem;
    }}
    .form-ctrl {{
      width: 100%;
      background: #090a0f;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 0.55rem 0.75rem;
      font-size: 0.84rem;
      outline: none;
    }}
    .form-ctrl:focus {{ border-color: var(--accent); }}

    /* ========================================================= */
    /* OPTION 5: DISTRIBUTED SUPERCOMPUTER RENTAL               */
    /* ========================================================= */
    .supercomputer-layout {{
      flex: 1;
      padding: 1.5rem 2rem;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }}
    .supercomputer-hero {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.35rem 1.6rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1.25rem;
    }}
    .cluster-tiers-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 1rem;
    }}
    .cluster-tier-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: border-color 0.15s;
      position: relative;
    }}
    .cluster-tier-card:hover {{
      border-color: var(--accent);
    }}
    .cluster-tier-badge {{
      display: inline-block;
      padding: 0.18rem 0.5rem;
      font-size: 0.68rem;
      font-family: var(--font-mono);
      font-weight: 600;
      letter-spacing: 0.04em;
      border-radius: 4px;
      background: rgba(59, 130, 246, 0.1);
      color: #60a5fa;
      border: 1px solid rgba(59, 130, 246, 0.25);
      margin-bottom: 0.5rem;
    }}
    .cluster-spec-row {{
      display: flex;
      justify-content: space-between;
      font-size: 0.8rem;
      padding: 0.32rem 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }}
    .cluster-spec-label {{ color: var(--text-muted); }}
    .cluster-spec-val {{ font-weight: 600; color: var(--text); font-family: var(--font-mono); font-size: 0.78rem; }}
    .btn-cluster-rent {{
      background: #2563eb;
      color: white;
      border: 1px solid #3b82f6;
      border-radius: 6px;
      padding: 0.55rem;
      font-weight: 600;
      font-size: 0.82rem;
      cursor: pointer;
      margin-top: 1rem;
      transition: background 0.15s;
    }}
    .btn-cluster-rent:hover {{ background: #1d4ed8; }}
    .node-pill {{
      display: inline-block;
      padding: 0.15rem 0.45rem;
      font-size: 0.72rem;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border);
      border-radius: 4px;
      margin: 0.15rem;
      font-family: var(--font-mono);
    }}

    /* Common Utility */
    .status-dot {{
      width: 7px;
      height: 7px;
      background: var(--success);
      border-radius: 50%;
      display: inline-block;
    }}
    .tech-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      font-family: var(--font-mono);
      font-size: 0.72rem;
      font-weight: 600;
      padding: 0.2rem 0.55rem;
      border-radius: 4px;
      background: #141720;
      border: 1px solid var(--border);
      color: var(--text-muted);
    }}

    /* Modal Styles */
    .modal-backdrop {{
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(5, 6, 9, 0.8);
      backdrop-filter: blur(3px);
      z-index: 99999;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1rem;
    }}
    .modal-card {{
      background: #101218;
      border: 1px solid var(--border);
      border-radius: 8px;
      width: 100%;
      max-width: 580px;
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.65);
      overflow: hidden;
    }}
    .modal-header {{
      padding: 0.9rem 1.25rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #0c0e14;
    }}
    .modal-close-btn {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 1rem;
      cursor: pointer;
    }}
    .modal-close-btn:hover {{ color: #ffffff; }}
  </style>
</head>
<body>

  <!-- Top Navigation Header -->
  <header>
    <div class="brand-wrap">
      <div class="brand-icon">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
      </div>
      <div>
        <div class="brand-name">SUP AGENTIC MESH</div>
        <div style="font-size:0.68rem; color:var(--text-muted); letter-spacing:0.01em;">NEXUS CORE • Distributed Compute Fabric &amp; Cloud Platform</div>
      </div>
    </div>

    <div class="header-actions">
      <!-- Cloudflare Public HTTPS Tunnel Indicator -->
      <div id="public-tunnel-pill" class="tech-pill" style="cursor:pointer; display:inline-flex; align-items:center; gap:0.4rem; padding:0.4rem 0.75rem;" onclick="showPublicTunnelModal()" title="Worldwide Remote Worker Public HTTPS Gateway">
        <span class="status-dot" id="tunnel-dot" style="background:#8b92a5;"></span>
        <span id="tunnel-label" style="font-size:0.75rem;">Public Mesh: Localhost</span>
      </div>

      <!-- 1-Click Worker Download Button -->
      <a href="/api/worker/download" class="btn-download">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Download Worker Node (.zip)
      </a>

      <!-- Account Key Box -->
      <div id="account-logged-out" class="account-bar">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-left:0.4rem; color:var(--text-muted);"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
        <input type="text" id="top-account-key" class="account-input" placeholder="Enter Secret Account Key...">
        <button class="account-btn" onclick="connectAccountKey()">Authenticate</button>
      </div>

      <div id="account-logged-in" class="account-badge" style="display:none; gap:0.45rem; align-items:center;">
        <span class="status-dot"></span>
        <span id="account-key-label" style="font-family:var(--font-mono); font-weight:600; font-size:0.76rem;">worker-xxxx</span>
        <span id="quantum-addr-pill" style="display:none; font-family:var(--font-mono); font-size:0.68rem; background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.3); padding:0.15rem 0.45rem; border-radius:4px; cursor:pointer;" onclick="copyTopQuantumAddr()" title="4096-Bit Hyper-Sovereign Quantum Address (Click to Copy)">nxq1...</span>
        <span class="credits-pill" title="1 Credit = 1 UMAIS (Native Sovereign Currency)"><span id="account-credits-label">100</span> UMAIS <span style="opacity:0.65; font-size:0.64rem;">(CR)</span></span>
        <button class="account-btn" style="padding:0.2rem 0.5rem; font-size:0.72rem;" onclick="disconnectAccountKey()">Switch</button>
      </div>
    </div>
  </header>

  <!-- 6 Main Navigation Tabs -->
  <nav class="nav-tabs-bar">
    <button class="nav-tab-btn active" onclick="switchMainTab('chat')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      1. SUP Agentic Mesh Chat
    </button>
    <button class="nav-tab-btn" onclick="switchMainTab('ide')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
      2. SUP Agentic Mesh IDE
    </button>
    <button class="nav-tab-btn" onclick="switchMainTab('physical')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>
      3. Physical Control (Machines)
    </button>
    <button class="nav-tab-btn" onclick="switchMainTab('p2p')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
      4. BUY / SELL UMAIS (Credits)
    </button>
    <button class="nav-tab-btn" onclick="switchMainTab('supercomputer')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
      5. Rent Supercomputer / Server
    </button>
    <button class="nav-tab-btn" onclick="switchMainTab('lottery')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      6. Credit Lottery &amp; Staking Sink (UMAIS)
    </button>
  </nav>

  <!-- ========================================================= -->
  <!-- TAB 1: SUP AGENTIC MESH CHAT (INSTITUTIONAL WORKSPACE)    -->
  <!-- ========================================================= -->
  <div id="tab-chat" class="workspace-container active">
    <div class="chat-layout">
      <!-- Chat History Sidebar -->
      <div class="chat-sidebar">
        <button class="new-chat-btn" onclick="startNewChat()">
          <span>+</span> New Session
        </button>
        <div style="padding:0 0.85rem 0.4rem; font-size:0.68rem; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em;">
          Session History
        </div>
        <div class="chat-history-list" id="chat-history-container">
          <!-- Populated from localStorage -->
        </div>
        <div style="padding:0.75rem 0.85rem; border-top:1px solid var(--border); font-size:0.75rem; color:var(--text-muted); display:flex; justify-content:space-between; align-items:center;">
          <span>Storage: Local Indexed</span>
          <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; font-size:0.73rem;" onclick="clearAllChatHistory()">Purge</button>
        </div>
      </div>

      <!-- Main Chat Area -->
      <div class="chat-main">
        <div class="chat-messages-area" id="chat-scroll-area">
          <div class="chat-messages-inner" id="chat-messages-list">
            <!-- Starter prompt cards (hidden once conversation starts) -->
            <div id="chat-starter-view">
              <div style="text-align:center; margin-bottom:2rem;">
                <div class="brand-icon" style="width:40px; height:40px; margin:0 auto 0.85rem;">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
                </div>
                <h2 style="font-size:1.35rem; font-weight:700; letter-spacing:-0.02em; margin-bottom:0.35rem;">SUP Agentic Mesh <span style="font-size:0.88rem; font-weight:500; color:var(--text-muted);">/ NEXUS Inference Grid</span></h2>
                <p style="color:var(--text-muted); font-size:0.85rem;">Distributed multi-agent planning, code synthesis, verification, and autonomous task execution.</p>
              </div>

              <div class="chat-starter-grid">
                <div class="starter-card" onclick="sendQuickPrompt('Build a complete Python FastAPI backend with JWT Authentication and User CRUD')">
                  <h4>API Architecture &amp; Auth</h4>
                  <p>Synthesize a production Python FastAPI service with JWT authentication and CRUD endpoints</p>
                </div>
                <div class="starter-card" onclick="sendQuickPrompt('Perform real-time statistical data analysis and forecasting on a high-throughput time series')">
                  <h4>Quantitative Forecasting</h4>
                  <p>Compute variance, rolling moving averages, and time-series anomaly detection</p>
                </div>
                <div class="starter-card" onclick="sendQuickPrompt('Audit a smart contract or distributed system for security risks, race conditions, and attack vectors')">
                  <h4>Security &amp; Concurrency Audit</h4>
                  <p>Analyze distributed state machines for race conditions, deadlocks, and attack surfaces</p>
                </div>
                <div class="starter-card" onclick="sendQuickPrompt('Design an autonomous self-improving agent pipeline with verification guards')">
                  <h4>Consensus Pipeline Design</h4>
                  <p>Architect a multi-node verification workflow with deterministic validation guards</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Chat Bottom Input Bar -->
        <div class="chat-bottom-bar">
          <div class="chat-input-capsule">
            <textarea id="chat-input-box" class="chat-textarea" rows="1" placeholder="Enter instruction or technical query for SUP Agentic Mesh..."></textarea>
            <button class="chat-send-btn" onclick="submitChatMessage()" title="Dispatch Prompt">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
          <div class="chat-disclaimer">
            NEXUS ROUTER • Currency Parity: <strong>1 Credit = 1 UMAIS</strong> • Standard Inference: <strong>1 UMAIS (1 CR)</strong> • Frontier Tier (Deep Reasoning): <strong>20 UMAIS (20 CR)</strong> (Auto-distilled to local CoT cache; 1 UMAIS on subsequent calls)
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ========================================================= -->
  <!-- TAB 2: SUP AGENTIC MESH IDE (CLOUD WORKBENCH)             -->
  <!-- ========================================================= -->
  <div id="tab-ide" class="workspace-container">
    <div class="vscode-layout">
      <!-- Activity Bar (Far Left) -->
      <div class="vscode-activity-bar">
        <div class="activity-icon active" title="Workspace Explorer">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
        </div>
        <div class="activity-icon" title="Switch Workspace Directory" onclick="openProjectModal()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>
        </div>
        <div class="activity-icon" title="Autonomous Agent Controller" onclick="focusAgentMission()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </div>
        <div class="activity-icon" title="Execute Active Script (F5)" onclick="ideRunCode()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        </div>
        <div class="activity-icon" title="Launch Native Desktop VS Code" onclick="launchDesktopVsCode()" style="margin-top:auto; color:var(--accent);">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        </div>
      </div>

      <!-- File Explorer Sidebar -->
      <div class="vscode-explorer">
        <div class="explorer-header">
          <div style="display:flex; align-items:center; gap:0.4rem; overflow:hidden; text-overflow:ellipsis; cursor:pointer;" onclick="openProjectModal()" title="Switch Workspace">
            <span id="ide-project-badge" style="font-size:0.73rem; font-family:var(--font-mono); font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--accent);">e:/NEXUS</span>
          </div>
          <div style="display:flex; gap:0.35rem; flex-shrink:0;">
            <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; font-size:0.72rem; font-weight:600;" title="Open Folder" onclick="openProjectModal()">DIR</button>
            <button style="background:transparent; border:none; color:var(--success); cursor:pointer; font-size:0.72rem; font-weight:600;" title="New File" onclick="createNewProjectFile()">+NEW</button>
            <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; font-size:0.72rem; font-weight:600;" title="Refresh" onclick="loadProjectFiles()">SYNC</button>
          </div>
        </div>
        <div class="file-tree" id="ide-file-tree">
          <div style="padding:1rem; color:var(--text-muted); font-size:0.78rem;">Indexing workspace files...</div>
        </div>
      </div>

      <!-- Main Monaco Editor & Terminal Panel -->
      <div class="vscode-editor-panel">
        <!-- Editor Tabs Bar -->
        <div class="editor-tabs-bar" id="editor-tabs-bar">
          <div class="editor-tab active" id="tab-pill-active">
            <span id="current-tab-filename" style="font-family:var(--font-mono); font-size:0.78rem;">sovereign_mesh/grid.py</span>
          </div>
          <div style="margin-left:auto; display:flex; align-items:center; gap:0.5rem; padding-right:0.75rem;">
            <button class="btn-launch-vscode" onclick="launchDesktopVsCode()" title="Open in native Desktop VS Code">
              Open Desktop VS Code
            </button>
            <button class="ide-btn" style="background:#161922; border:1px solid var(--border); color:var(--text);" onclick="saveCurrentFile()" title="Write buffer to disk (Ctrl+S)">
              Save Buffer
            </button>
          </div>
        </div>

        <!-- Monaco Editor & Terminal Body -->
        <div class="editor-split-body">
          <div style="position:relative; width:100%; height:100%; background:#0d0f14; overflow:hidden;">
            <div id="monaco-editor-container" style="width:100%; height:100%;"></div>
            <textarea id="ide-fallback-editor" class="code-textarea" style="display:none; width:100%; height:100%; position:absolute; top:0; left:0;" spellcheck="false"></textarea>
          </div>

          <!-- Bottom Terminal Dock -->
          <div class="terminal-dock">
            <div class="terminal-nav">
              <div class="terminal-tabs">
                <span class="terminal-tab-item active" onclick="switchTerminalTab('terminal')">CONSOLE</span>
                <span class="terminal-tab-item" onclick="switchTerminalTab('output')">AGENT TELEMETRY</span>
                <span class="terminal-tab-item" onclick="switchTerminalTab('problems')">DIAGNOSTICS (0)</span>
              </div>
              <div style="display:flex; gap:0.65rem; align-items:center;">
                <span style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted);">Python Runtime • Disk Synced</span>
                <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; font-size:0.72rem;" onclick="clearIdeTerminal()">Clear</button>
              </div>
            </div>
            <div class="terminal-screen" id="ide-terminal-screen">
              <span style="color:var(--accent);">[NEXUS-IDE] Workspace mounted: e:/NEXUS</span><br>
              <span style="color:var(--text-muted);">Ready. Dispatch tasks via the Autonomous Agent Controller on the right panel.</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Panel: Autonomous Agent Command Deck -->
      <div class="agent-side-panel" id="agent-side-panel">
        <div class="agent-side-header">
          <div>
            <div style="font-size:0.82rem; font-weight:700;">Autonomous Agent Controller</div>
            <div style="font-size:0.68rem; color:var(--text-muted);">Read / Write / Verification Authority</div>
          </div>
          <span class="agent-badge">ACTIVE</span>
        </div>

        <div style="padding:0.85rem; border-bottom:1px solid var(--border); background:#0c0e14;">
          <label style="font-size:0.7rem; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em; margin-bottom:0.35rem; display:block;">
            Task Specification
          </label>
          <textarea id="agent-instruction-input" class="form-ctrl" rows="3" placeholder="Specify module to synthesize, refactor, or verify..." style="font-size:0.8rem; resize:vertical; margin-bottom:0.6rem;"></textarea>

          <button class="ide-btn ide-btn-build" style="width:100%; justify-content:center; padding:0.5rem; font-size:0.8rem;" onclick="runAgentAutonomousMission()">
            Execute Autonomous Task
          </button>

          <div style="display:flex; gap:0.35rem; margin-top:0.5rem; flex-wrap:wrap;">
            <button class="ide-btn ide-btn-run" style="flex:1; min-width:75px; justify-content:center; padding:0.32rem; font-size:0.73rem;" onclick="ideRunCode()">
              Run Local
            </button>
            <button class="ide-btn" style="flex:1; min-width:85px; justify-content:center; padding:0.32rem; font-size:0.73rem; background:#1e293b; border:1px solid #334155; color:#93c5fd;" onclick="ideRunOnSupercomputer()" title="Execute across provisioned Supercomputer cluster">
              Run Cluster
            </button>
            <button class="ide-btn ide-btn-test" style="flex:1; min-width:65px; justify-content:center; padding:0.32rem; font-size:0.73rem;" onclick="ideRunAutoTests()">
              Verify
            </button>
            <button class="ide-btn ide-btn-fix" style="flex:1; min-width:65px; justify-content:center; padding:0.32rem; font-size:0.73rem;" onclick="ideAutoFixLoop()">
              Patch
            </button>
          </div>
        </div>

        <!-- Live Agent Execution Pipeline Timeline -->
        <div style="padding:0.4rem 0.85rem; font-size:0.68rem; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; background:#090a0f; border-bottom:1px solid var(--border);">
          Execution Log
        </div>
        <div class="agent-timeline" id="agent-timeline-feed">
          <div class="agent-step-card">
            <div style="display:flex; justify-content:space-between; margin-bottom:0.25rem;">
              <strong style="color:var(--success); font-size:0.76rem;">STANDBY</strong>
              <span style="font-size:0.7rem; font-family:var(--font-mono); color:var(--text-muted);">IDLE</span>
            </div>
            <p style="font-size:0.76rem; color:var(--text-muted);">Agent controller initialized with full read/write/test access on active workspace.</p>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ========================================================= -->
  <!-- TAB 3: PHYSICAL CONTROL DECK (MACHINES & ROBOTICS)        -->
  <!-- ========================================================= -->
  <div id="tab-physical" class="workspace-container">
    <div class="physical-layout">
      <!-- E-Stop Banner -->
      <div class="e-stop-banner">
        <div>
          <h3 style="color:var(--danger); font-size:1rem; font-weight:700; letter-spacing:0.02em;">
            HARDWARE INTERLOCK &amp; EMERGENCY HALT (E-STOP)
          </h3>
          <p style="color:var(--text-muted); font-size:0.82rem; margin-top:0.25rem;">
            Triggers immediate hardware interrupt across all connected ROS 2 manipulators, CNC controllers, and thermal actuators.
          </p>
        </div>
        <button class="btn-estop" onclick="triggerHardwareEStop()">TRIGGER E-STOP</button>
      </div>

      <!-- Connect Machine Form -->
      <div class="form-box" style="max-width:100%;">
        <h4 style="font-size:0.92rem; font-weight:700; margin-bottom:0.75rem;">Register Hardware Endpoint</h4>
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:1rem;">
          <div class="form-group">
            <label>Controller Profile</label>
            <select id="mach-type" class="form-ctrl">
              <option value="robotic_arm">ROS 2 Articulated Manipulator (UR5 / Doosan)</option>
              <option value="3d_printer">Additive Manufacturing Controller (OctoPrint / Klipper)</option>
              <option value="cnc_machine">CNC Motion Controller (GRBL / LinuxCNC)</option>
              <option value="iot_sensor">Modbus / Serial Telemetry &amp; Relay Bus</option>
            </select>
          </div>
          <div class="form-group">
            <label>Endpoint Identifier</label>
            <input type="text" id="mach-name" class="form-ctrl" placeholder="e.g. Bay-1 Manipulator">
          </div>
          <div class="form-group">
            <label>Host URI / Serial Interface</label>
            <input type="text" id="mach-target" class="form-ctrl" placeholder="e.g. COM3 or 192.168.1.150">
          </div>
          <div class="form-group">
            <label>Baudrate / Transport</label>
            <input type="text" id="mach-baud" class="form-ctrl" value="115200">
          </div>
        </div>
        <button class="account-btn" style="background:#2563eb; color:white; border-color:#3b82f6; padding:0.5rem 1.15rem;" onclick="connectPhysicalMachine()">
          Bind Hardware Interface
        </button>
      </div>

      <!-- Connected Machines List -->
      <h4 style="font-size:0.88rem; font-weight:700; text-transform:uppercase; letter-spacing:0.04em; color:var(--text-muted); margin-top:0.25rem;">Registered Telemetry &amp; Motion Endpoints</h4>
      <div class="machine-cards-grid" id="machines-grid">
        <!-- Default Machine 1: Robotic Arm -->
        <div class="machine-card">
          <div class="machine-card-header">
            <strong style="font-size:0.88rem;">ROS 2 Manipulator (UR5e)</strong>
            <span class="status-dot"></span>
          </div>
          <p style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted)">URI: 192.168.1.120:8080 | STATE: ONLINE</p>
          <div style="font-size:0.76rem; font-weight:600; color:var(--text-muted);">Cartesian Jog Vector:</div>
          <div class="jog-pad">
            <button class="jog-btn" onclick="sendJogCommand('mach-arm', 'Y+')">Y+</button>
            <button class="jog-btn" onclick="sendJogCommand('mach-arm', 'Z+')">Z+</button>
            <button class="jog-btn" onclick="sendJogCommand('mach-arm', 'Y-')">Y-</button>
            <button class="jog-btn" onclick="sendJogCommand('mach-arm', 'X-')">X-</button>
            <button class="jog-btn" onclick="sendJogCommand('mach-arm', 'HOME')">G28</button>
            <button class="jog-btn" onclick="sendJogCommand('mach-arm', 'X+')">X+</button>
          </div>
          <div style="display:flex; gap:0.4rem; margin-top:0.3rem;">
            <input type="text" id="cmd-arm" class="form-ctrl" style="font-size:0.76rem; font-family:var(--font-mono); padding:0.35rem 0.6rem;" placeholder="Joint vector / ROS topic...">
            <button class="account-btn" onclick="sendRawMachineCmd('mach-arm', 'cmd-arm')">Dispatch</button>
          </div>
        </div>

        <!-- Default Machine 2: 3D Printer -->
        <div class="machine-card">
          <div class="machine-card-header">
            <strong style="font-size:0.88rem;">CoreXY Additive System (Voron 2.4)</strong>
            <span class="status-dot"></span>
          </div>
          <p style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted)">BUS: OctoPrint REST | STATE: 210°C / 60°C</p>
          <div style="display:flex; gap:0.45rem; font-size:0.76rem; margin:0.4rem 0;">
            <button class="account-btn" onclick="sendMachineCommand('mach-printer', 'G28')">Home Axes</button>
            <button class="account-btn" onclick="sendMachineCommand('mach-printer', 'M104 S210')">Set Extruder</button>
            <button class="account-btn" onclick="sendMachineCommand('mach-printer', 'M140 S60')">Set Bed</button>
          </div>
          <div style="display:flex; gap:0.4rem; margin-top:0.3rem;">
            <input type="text" id="cmd-printer" class="form-ctrl" style="font-size:0.76rem; font-family:var(--font-mono); padding:0.35rem 0.6rem;" placeholder="G-code instruction (G1 X50 Y50 F3000)...">
            <button class="account-btn" onclick="sendRawMachineCmd('mach-printer', 'cmd-printer')">Dispatch</button>
          </div>
        </div>

        <!-- Default Machine 3: CNC Machine -->
        <div class="machine-card">
          <div class="machine-card-header">
            <strong style="font-size:0.88rem;">CNC 3-Axis Mill (GRBL 1.1)</strong>
            <span class="status-dot"></span>
          </div>
          <p style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted)">BUS: COM4 @ 115200 | STATE: STANDBY</p>
          <div style="display:flex; gap:0.45rem; font-size:0.76rem; margin:0.4rem 0;">
            <button class="account-btn" onclick="sendMachineCommand('mach-cnc', '$H')">Homing Cycle</button>
            <button class="account-btn" onclick="sendMachineCommand('mach-cnc', 'G92 X0 Y0 Z0')">Zero WCS</button>
            <button class="account-btn" onclick="sendMachineCommand('mach-cnc', 'M3 S10000')">Spindle Enable</button>
          </div>
          <div style="display:flex; gap:0.4rem; margin-top:0.3rem;">
            <input type="text" id="cmd-cnc" class="form-ctrl" style="font-size:0.76rem; font-family:var(--font-mono); padding:0.35rem 0.6rem;" placeholder="GRBL frame ($$ or G0 X10)...">
            <button class="account-btn" onclick="sendRawMachineCmd('mach-cnc', 'cmd-cnc')">Dispatch</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ========================================================= -->
  <!-- TAB 4: BUY / SELL CREDITS P2P EXCHANGE                    -->
  <!-- ========================================================= -->
  <div id="tab-p2p" class="workspace-container">
    <div class="p2p-layout">
      <!-- Institutional Economics & Halving Telemetry Banner -->
      <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:1.15rem 1.4rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem;">
        <div style="flex:1; min-width:280px;">
          <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.4rem; flex-wrap:wrap;">
            <span class="tech-pill" style="color:var(--success); border-color:rgba(16,185,129,0.3);">NATIVE CURRENCY: UMAIS (1 CREDIT = 1 UMAIS)</span>
            <span class="tech-pill" style="color:#60a5fa; border-color:rgba(59,130,246,0.3);">ESCROW PROTECTED P2P SETTLEMENT</span>
            <span id="p2p-halving-badge" class="tech-pill" style="color:var(--warning); border-color:rgba(245,158,11,0.3);">Halving Era 1 (1.0x) • Uptime: 2–4 UMAIS/hr • Task: +25 UMAIS</span>
          </div>
          <h3 style="font-size:1rem; font-weight:700; color:var(--text); margin-bottom:0.25rem;">
            Peer-to-Peer UMAIS (Compute Credit) Liquidity Exchange
          </h3>
          <p style="font-size:0.8rem; color:var(--text-muted); line-height:1.45; margin:0;">
            Acquire <strong>UMAIS</strong> (<strong>1 Credit = 1 UMAIS</strong>) directly from verified edge node operators via escrow-backed local settlement (EasyPaisa / JazzCash / Raast). Every active compute job dispatches <strong>+25 UMAIS (25 CR)</strong> to participating worker nodes.
          </p>
        </div>
        <div style="display:flex; gap:0.65rem; flex-wrap:wrap;">
          <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.55rem 0.85rem; text-align:center;">
            <div style="font-size:0.66rem; color:var(--text-muted); text-transform:uppercase; font-family:var(--font-mono);">Legacy Cloud Benchmark</div>
            <div style="font-size:0.88rem; font-weight:700; font-family:var(--font-mono); color:var(--text-muted); text-decoration:line-through;">PKR 5,600 – 11,000</div>
          </div>
          <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.3); border-radius:6px; padding:0.55rem 0.9rem; text-align:center;">
            <div style="font-size:0.66rem; color:var(--success); text-transform:uppercase; font-family:var(--font-mono); font-weight:600;">P2P Spot Rate (250 UMAIS)</div>
            <div style="font-size:0.9rem; font-weight:700; font-family:var(--font-mono); color:var(--text);">PKR 100 – 200</div>
          </div>
        </div>
      </div>

      <!-- Protocol Referral Telemetry Bar -->
      <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:0.8rem 1.25rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.85rem;">
        <div>
          <div style="font-size:0.84rem; font-weight:700; color:var(--text);">
            Node Operator Referral Protocol (+5% UMAIS Royalty Minting)
          </div>
          <div style="font-size:0.76rem; color:var(--text-muted); margin-top:0.15rem;">
            Referred worker nodes automatically mint a <strong>+5% UMAIS protocol dividend</strong> to your account key upon verified task or uptime settlement.
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:0.6rem; flex-wrap:wrap;">
          <span style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted);">Nodes: <strong id="ref-count-badge" style="color:var(--text);">0</strong> • Yield: <strong id="ref-bonus-badge" style="color:var(--success);">+0 UMAIS</strong></span>
          <code id="my-referral-code-pill" style="background:#090a0f; border:1px solid var(--border); color:var(--accent); padding:0.3rem 0.65rem; border-radius:4px; font-family:var(--font-mono); font-weight:600; font-size:0.78rem;">REF-CONNECT-KEY</code>
          <button class="account-btn" style="font-size:0.75rem;" onclick="copyMyReferralCode()">Copy Code</button>
        </div>
      </div>

      <!-- P2P Sub-Navigation -->
      <div class="p2p-sub-nav" style="flex-wrap:wrap;">
        <button class="p2p-tab-btn active" id="btn-p2p-buy" onclick="switchP2PSub('buy')">Spot Orderbook</button>
        <button class="p2p-tab-btn" id="btn-p2p-buy-order" onclick="switchP2PSub('buy-order')">Post Bid (Buy)</button>
        <button class="p2p-tab-btn" id="btn-p2p-sell" onclick="switchP2PSub('sell')">Post Ask (Sell)</button>
        <button class="p2p-tab-btn" id="btn-p2p-leaderboard" onclick="switchP2PSub('leaderboard')">Node Rankings &amp; Treasury Floor</button>
        <button class="p2p-tab-btn" id="btn-p2p-brain" onclick="switchP2PSub('brain')">Distributed Neural Shards</button>
        <button class="p2p-tab-btn" id="btn-p2p-orders" onclick="switchP2PSub('orders')">Escrow Settlements</button>
        <button class="p2p-tab-btn" id="btn-p2p-transfer" onclick="switchP2PSub('transfer')">Ledger Transfer</button>
      </div>

      <!-- SUB-TAB 1: 2-WAY P2P ORDERBOOK (SELL OFFERS + BUYER ORDERS) -->
      <div id="p2p-view-buy">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.65rem; flex-wrap:wrap; gap:0.5rem;">
          <h4 style="font-size:0.9rem; font-weight:700;">Active Ask Offers (Escrow-Locked UMAIS Credits Available for Immediate Purchase)</h4>
          <div style="display:flex; gap:0.5rem;">
            <button class="account-btn" style="background:#2563eb; color:white; border-color:#3b82f6;" onclick="switchP2PSub('buy-order')">+ New Bid Order</button>
            <button class="account-btn" onclick="loadP2POffers()">Refresh Book</button>
          </div>
        </div>
        <table class="p2p-table" style="margin-bottom:1.75rem;">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Operator</th>
              <th>Volume (UMAIS / CR)</th>
              <th>Settlement Total</th>
              <th>Unit Price</th>
              <th>Settlement Rail</th>
              <th>Execution</th>
            </tr>
          </thead>
          <tbody id="p2p-offers-tbody">
            <tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:1.75rem;">Querying active ask offers...</td></tr>
          </tbody>
        </table>

        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.65rem;">
          <h4 style="font-size:0.9rem; font-weight:700;">Active Bid Orders (Open UMAIS Liquidity Requests from Buyers)</h4>
        </div>
        <table class="p2p-table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Buyer ID</th>
              <th>Volume Requested (UMAIS)</th>
              <th>Bid Total</th>
              <th>Unit Bid</th>
              <th>Settlement Rail</th>
              <th>Execution (For Node Operators)</th>
            </tr>
          </thead>
          <tbody id="p2p-buy-orders-tbody">
            <tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:1.75rem;">Querying active bid orders...</td></tr>
          </tbody>
        </table>
      </div>

      <!-- SUB-TAB 1B: POST A BUY ORDER (WANT TO BUY CREDITS) -->
      <div id="p2p-view-buy-order" style="display:none;">
        <div class="form-box">
          <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:0.4rem;">Submit Bid Order (Acquire UMAIS Credits)</h4>
          <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom:0.65rem;">
            Publish a bid to the P2P orderbook. When a node operator fills your bid, their UMAIS credits are cryptographically locked in protocol escrow prior to fiat settlement.
          </p>
          <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25); border-radius:6px; padding:0.6rem 0.85rem; font-size:0.76rem; color:var(--success); margin-bottom:1rem; line-height:1.45;">
            <strong>Escrow Verification Guarantee:</strong> Zero prior balance required to post a bid. Fiat transfer is only initiated after counterparty UMAIS credits are locked in escrow.
          </div>
          <div class="form-group">
            <label>Buyer Account Key</label>
            <input type="text" id="buyorder-buyer-id" class="form-ctrl" placeholder="Enter your Account Key or Buyer Identifier...">
          </div>
          <div class="form-group">
            <label>UMAIS Volume Requested (1 Credit = 1 UMAIS • 250 UMAIS recommended for Cluster Provisioning)</label>
            <input type="number" id="buyorder-amount" class="form-ctrl" placeholder="e.g. 250" value="250" min="1">
          </div>
          <div class="form-group">
            <label>Total Bid Price (PKR)</label>
            <input type="number" id="buyorder-price" class="form-ctrl" placeholder="e.g. 150" value="150" min="1">
          </div>
          <div class="form-group">
            <label>Settlement Rail (EasyPaisa / JazzCash / Raast)</label>
            <input type="text" id="buyorder-method" class="form-ctrl" value="EasyPaisa / JazzCash / Raast" placeholder="e.g. EasyPaisa / JazzCash">
          </div>
          <button class="btn-download" style="width:100%; justify-content:center; padding:0.6rem;" onclick="submitP2PBuyOrder()">
            Publish Bid to Orderbook
          </button>
        </div>
      </div>

      <!-- SUB-TAB 2: SELL CREDITS -->
      <div id="p2p-view-sell" style="display:none;">
        <div class="form-box">
          <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:0.4rem;">Submit Ask Offer (Liquidate Earned UMAIS Credits)</h4>
          <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom:0.65rem;">
            Offered UMAIS credits are held in protocol escrow until you confirm receipt of settlement via your designated payment rail.
          </p>
          <div style="background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.25); border-radius:6px; padding:0.65rem 0.85rem; font-size:0.76rem; color:var(--warning); margin-bottom:1rem; line-height:1.5;">
            <strong>Protocol Liquidity Controls:</strong><br>
            • Minimum <strong>150 UMAIS (150 CR)</strong> settled balance required to unlock ask creation.<br>
            • Daily liquidation cap: <strong>20%</strong> of available balance per 24h epoch.<br>
            • Maximum <strong>1 concurrent open ask order</strong> per operator key.
          </div>
          <div class="form-group">
            <label>Operator Account Key</label>
            <input type="text" id="sell-worker-id" class="form-ctrl" placeholder="Enter your Secret Account Key...">
          </div>
          <div class="form-group">
            <label>UMAIS Volume to Lock (Max 20% of balance)</label>
            <input type="number" id="sell-amount" class="form-ctrl" placeholder="e.g. 30" min="1">
          </div>
          <div class="form-group">
            <label>Total Ask Settlement Price (PKR / USD)</label>
            <input type="number" id="sell-price" class="form-ctrl" placeholder="e.g. 150" min="1">
          </div>
          <div class="form-group">
            <label>Beneficiary Settlement Account (EasyPaisa / JazzCash / Raast IBAN)</label>
            <input type="text" id="sell-method" class="form-ctrl" placeholder="e.g. EasyPaisa: 0300-1234567 (Account Title)">
          </div>
          <button class="btn-download" style="width:100%; justify-content:center; padding:0.6rem;" onclick="submitP2PSellOrder()">
            Lock in Escrow &amp; Publish Ask
          </button>
        </div>
      </div>

      <!-- SUB-TAB 5: WEEKLY TOP 3 MINERS BUYBACK LEADERBOARD -->
      <div id="p2p-view-leaderboard" style="display:none;">
        <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:1.15rem 1.35rem; margin-bottom:1.15rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem;">
          <div>
            <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:0.25rem;">Node Performance Telemetry &amp; Treasury Floor Settlement</h4>
            <p style="font-size:0.78rem; color:var(--text-muted); margin:0; max-width:680px; line-height:1.45;">
              Top 3 verified compute operators ranked by completed task proofs (<strong>+25 UMAIS/task</strong>) and continuous uptime epochs qualify for weekly Sovereign Treasury floor settlement (<strong>PKR 500 guaranteed floor</strong>).
            </p>
          </div>
          <div style="display:flex; gap:0.5rem; align-items:center;">
            <button class="account-btn" onclick="loadP2PLeaderboard()">Refresh Telemetry</button>
            <button class="account-btn" style="background:#1e293b; color:#93c5fd; border-color:#334155;" onclick="executeOwnerTop3Buyback()">
              Execute Treasury Settlement
            </button>
          </div>
        </div>

        <table class="p2p-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Node ID</th>
              <th>Hardware Spec &amp; Assigned Shard</th>
              <th>Verified Tasks</th>
              <th>Uptime Hours</th>
              <th>Consensus Score</th>
              <th>UMAIS Balance</th>
              <th>Settlement Status</th>
            </tr>
          </thead>
          <tbody id="p2p-leaderboard-tbody">
            <tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:1.75rem;">Loading operator telemetry...</td></tr>
          </tbody>
        </table>
      </div>

      <!-- SUB-TAB 6: DECENTRALIZED BRAIN MATRIX -->
      <div id="p2p-view-brain" style="display:none;">
        <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:1.25rem 1.4rem; margin-bottom:1.25rem;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:1rem;">
            <div style="flex:1; min-width:280px;">
              <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.4rem; flex-wrap:wrap;">
                <span id="bm-era-badge" class="tech-pill" style="color:#93c5fd;">Era 1 (1–50 Nodes) • Seed Topology</span>
                <span id="bm-survivability-badge" class="tech-pill" style="color:var(--success);">100% P2P Shard Redundancy</span>
              </div>
              <h4 style="font-size:1rem; font-weight:700; margin-bottom:0.25rem;">Distributed Neural Shards, LoRA Backpropagation &amp; Binary <code>.safetensors</code> FedAvg</h4>
              <p style="font-size:0.78rem; color:var(--text-muted); margin:0; line-height:1.45;">
                Operates a <strong>Two-Tier Memory Architecture</strong>: <strong>Layer 1 (Episodic RAG JSON)</strong> for verified Chain-of-Thought retrieval + <strong>Layer 2 (Parametric Weight Fusion)</strong> computing IEEE-754 <code>float32</code> Low-Rank Adapter gradients (<code>&Delta;W = B&middot;A</code>) merged via <strong>Federated Averaging (FedAvg)</strong> into spec-compliant HuggingFace <code>.safetensors</code> binary checkpoints.
              </p>
            </div>
            <div style="display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center;">
              <button class="account-btn" style="background:#2563eb; color:white; border-color:#3b82f6;" onclick="triggerBrainSelfPlay()">
                Run Self-Play Distillation
              </button>
              <button class="account-btn" onclick="triggerBrainP2PSync()">
                Sync Weight Deltas
              </button>
              <button class="account-btn" onclick="loadBrainMatrixStatus()">Refresh</button>
            </div>
          </div>

          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(175px, 1fr)); gap:0.85rem; margin-top:1rem;">
            <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.75rem 1rem;">
              <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase; font-family:var(--font-mono);">Local Mesh Autonomy</div>
              <div id="bm-autonomy-val" style="font-size:1.25rem; font-weight:700; font-family:var(--font-mono); color:var(--success); margin-top:0.2rem;">20%</div>
            </div>
            <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.75rem 1rem;">
              <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase; font-family:var(--font-mono);">External Upstream Reliance</div>
              <div id="bm-api-dep-val" style="font-size:1.25rem; font-weight:700; font-family:var(--font-mono); color:var(--warning); margin-top:0.2rem;">80%</div>
            </div>
            <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.75rem 1rem;">
              <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase; font-family:var(--font-mono);">Distilled CoT Corpus</div>
              <div id="bm-samples-val" style="font-size:1.25rem; font-weight:700; font-family:var(--font-mono); color:var(--accent); margin-top:0.2rem;">0 Samples</div>
            </div>
            <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.75rem 1rem;">
              <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase; font-family:var(--font-mono);">Replicated Weight Deltas</div>
              <div id="bm-deltas-val" style="font-size:1.25rem; font-weight:700; font-family:var(--font-mono); color:var(--text); margin-top:0.2rem;">0 Packets</div>
            </div>
          </div>
        </div>

        <h4 style="font-size:0.88rem; font-weight:700; margin-bottom:0.5rem;">Domain Specialization Shards &amp; Peer Replica Topology</h4>
        <table class="p2p-table" style="margin-bottom:1.5rem;">
          <thead>
            <tr>
              <th>Shard ID</th>
              <th>Domain &amp; Base Architecture</th>
              <th>Hardware Target</th>
              <th>Primary Holders</th>
              <th>Replica Nodes</th>
              <th>Availability</th>
            </tr>
          </thead>
          <tbody id="bm-shards-tbody">
            <tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:1.5rem;">Loading shard topology...</td></tr>
          </tbody>
        </table>

        <h4 style="font-size:0.88rem; font-weight:700; margin-bottom:0.5rem;">Autonomy Transition Phases</h4>
        <table class="p2p-table">
          <thead>
            <tr>
              <th>Phase</th>
              <th>Upstream Reliance</th>
              <th>Mesh Topology State</th>
              <th>Distillation Mechanism</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="bm-eras-tbody">
            <tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:1.5rem;">Loading autonomy phases...</td></tr>
          </tbody>
        </table>
      </div>

      <!-- SUB-TAB 3: MY ORDERS & RELEASES -->
      <div id="p2p-view-orders" style="display:none;">
        <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:0.9rem 1rem; margin-bottom:1.25rem; display:flex; gap:0.65rem; align-items:center;">
          <input type="text" id="p2p-check-id" class="form-ctrl" style="max-width:320px;" placeholder="Enter Account Key to query escrow ledger...">
          <button class="account-btn" onclick="loadMyTrades()">Query Escrow</button>
        </div>

        <h4 style="font-size:0.88rem; font-weight:700; margin-bottom:0.45rem;">Outbound Ask Contracts (Selling)</h4>
        <table class="p2p-table" style="margin-bottom:1.75rem;">
          <thead>
            <tr>
              <th>Contract ID</th>
              <th>Volume</th>
              <th>Settlement</th>
              <th>Escrow State</th>
              <th>Counterparty</th>
              <th>Settlement Reference (TID)</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="my-sales-tbody">
            <tr><td colspan="7" style="text-align:center; color:var(--text-muted)">Authenticate account key to view outbound contracts.</td></tr>
          </tbody>
        </table>

        <h4 style="font-size:0.88rem; font-weight:700; margin-bottom:0.45rem;">Inbound Bid Contracts (Buying)</h4>
        <table class="p2p-table">
          <thead>
            <tr>
              <th>Contract ID</th>
              <th>Counterparty</th>
              <th>Volume</th>
              <th>Amount Due</th>
              <th>Escrow State</th>
              <th>Beneficiary Rail</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="my-buys-tbody">
            <tr><td colspan="7" style="text-align:center; color:var(--text-muted)">Authenticate account key to view inbound contracts.</td></tr>
          </tbody>
        </table>
      </div>

      <!-- SUB-TAB 4: DIRECT TRANSFER -->
      <div id="p2p-view-transfer" style="display:none;">
        <div class="form-box">
          <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:0.4rem;">Direct Ledger Transfer</h4>
          <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom:1.1rem;">Execute atomic credit transfers between operator keys with zero protocol fee.</p>
          <div class="form-group">
            <label>Source Account Key</label>
            <input type="text" id="tr-from" class="form-ctrl" placeholder="Sender ID">
          </div>
          <div class="form-group">
            <label>Destination Account Key</label>
            <input type="text" id="tr-to" class="form-ctrl" placeholder="Recipient ID">
          </div>
          <div class="form-group">
            <label>Transfer Volume (UMAIS / CR)</label>
            <input type="number" id="tr-amount" class="form-ctrl" placeholder="e.g. 25" min="1">
          </div>
          <button class="btn-download" style="width:100%; justify-content:center; padding:0.6rem;" onclick="submitDirectTransfer()">
            Execute Ledger Transfer
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- ========================================================= -->
  <!-- TAB 5: DISTRIBUTED SUPERCOMPUTER & VIRTUAL SERVER RENTAL   -->
  <!-- ========================================================= -->
  <div id="tab-supercomputer" class="workspace-container">
    <div class="supercomputer-layout">
      <!-- Hero Banner -->
      <div class="supercomputer-hero">
        <div>
          <h2 style="font-size:1.2rem; font-weight:700; letter-spacing:-0.01em; margin-bottom:0.35rem; color:var(--text);">
            Elastic Distributed Supercomputer &amp; Virtual Cluster Provisioning
          </h2>
          <p style="font-size:0.82rem; color:var(--text-muted); max-width:720px; line-height:1.45;">
            Provision multi-node compute clusters backed by <strong>IAM-Style Access Credentials</strong> (Instance ID, Access Key ID &amp; Secret Key) for remote execution via REST API, Python SDK, or Cloud Workbench. Metered in <strong>UMAIS (1 Credit = 1 UMAIS)</strong>.
          </p>
          <div style="margin-top:0.6rem; display:flex; gap:0.5rem; flex-wrap:wrap;">
            <span class="tech-pill" style="color:var(--warning); border-color:rgba(245,158,11,0.3);">
              MIN BALANCE GATE: 250+ UMAIS (250 CR)
            </span>
            <span class="tech-pill" style="color:var(--success); border-color:rgba(16,185,129,0.3);">
              CONTINUOUS RUNTIME: NO 72H CAP (PAUSE / RESUME ANYTIME)
            </span>
            <span class="tech-pill" style="color:#60a5fa; border-color:rgba(59,130,246,0.3);">
              ELASTIC SHARED MESH: IDLE CORES SERVE NETWORK • BURSTS TO 100% CEILING ON LOAD
            </span>
          </div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:0.68rem; font-family:var(--font-mono); color:var(--text-muted); text-transform:uppercase;">Scheduler State</div>
          <div style="font-size:0.95rem; font-family:var(--font-mono); font-weight:700; color:var(--success); margin-top:0.15rem;">● ELASTIC POOL READY</div>
        </div>
      </div>

      <!-- Presets Section -->
      <div>
        <h3 style="font-size:0.9rem; font-weight:700; text-transform:uppercase; letter-spacing:0.04em; color:var(--text-muted); margin-bottom:0.75rem;">
          Standard Compute Instance Tiers (Metered in UMAIS)
        </h3>
        <div class="cluster-tiers-grid">
          <!-- Tier 1 -->
          <div class="cluster-tier-card">
            <div>
              <span class="cluster-tier-badge">TIER-1 / STANDARD</span>
              <h4 style="font-size:1.02rem; font-weight:700; margin-bottom:0.4rem;">8 vCPU Compute Node</h4>
              <p style="font-size:0.76rem; color:var(--text-muted); margin-bottom:0.85rem;">Parallel build pipelines, lightweight microservices, and API backends.</p>
              <div class="cluster-spec-row"><span class="cluster-spec-label">vCPU Ceiling</span><span class="cluster-spec-val">8 Cores (~2.2 TFLOPS)</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Memory Pool</span><span class="cluster-spec-val">32 GB Distributed</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Mesh Topology</span><span class="cluster-spec-val">2 Worker Nodes</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Metered Rate</span><span class="cluster-spec-val" style="color:var(--accent);">12 UMAIS / hr</span></div>
            </div>
            <button class="btn-cluster-rent" onclick="rentSupercomputerPreset('Fast Compute 8 vCPU', 8, 32, 1)">Provision Instance (12 UMAIS/hr)</button>
          </div>

          <!-- Tier 2 -->
          <div class="cluster-tier-card">
            <div>
              <span class="cluster-tier-badge" style="color:var(--success); border-color:rgba(16,185,129,0.3); background:rgba(16,185,129,0.08);">TIER-2 / AI WORKLOAD</span>
              <h4 style="font-size:1.02rem; font-weight:700; margin-bottom:0.4rem;">32 vCPU AI Cluster</h4>
              <p style="font-size:0.76rem; color:var(--text-muted); margin-bottom:0.85rem;">LoRA fine-tuning, batch inference, and multi-agent verification loops.</p>
              <div class="cluster-spec-row"><span class="cluster-spec-label">vCPU Ceiling</span><span class="cluster-spec-val">32 Cores (~9.0 TFLOPS)</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Memory Pool</span><span class="cluster-spec-val">128 GB Distributed</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Mesh Topology</span><span class="cluster-spec-val">8 Worker Nodes</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Metered Rate</span><span class="cluster-spec-val" style="color:var(--accent);">48 UMAIS / hr</span></div>
            </div>
            <button class="btn-cluster-rent" onclick="rentSupercomputerPreset('Pro AI Rig 32 vCPU', 32, 128, 1)">Provision Instance (48 UMAIS/hr)</button>
          </div>

          <!-- Tier 3 -->
          <div class="cluster-tier-card">
            <div>
              <span class="cluster-tier-badge" style="color:var(--warning); border-color:rgba(245,158,11,0.3); background:rgba(245,158,11,0.08);">TIER-3 / HPC GRID</span>
              <h4 style="font-size:1.02rem; font-weight:700; margin-bottom:0.4rem;">128 vCPU HPC Array</h4>
              <p style="font-size:0.76rem; color:var(--text-muted); margin-bottom:0.85rem;">Monte Carlo simulations, quantitative modeling, and high-throughput ETL.</p>
              <div class="cluster-spec-row"><span class="cluster-spec-label">vCPU Ceiling</span><span class="cluster-spec-val">128 Cores (~35.8 TFLOPS)</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Memory Pool</span><span class="cluster-spec-val">512 GB Distributed</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Mesh Topology</span><span class="cluster-spec-val">32 Worker Nodes</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Metered Rate</span><span class="cluster-spec-val" style="color:var(--accent);">180 UMAIS / hr</span></div>
            </div>
            <button class="btn-cluster-rent" onclick="rentSupercomputerPreset('Enterprise HPC 128 vCPU', 128, 512, 1)">Provision Instance (180 UMAIS/hr)</button>
          </div>

          <!-- Tier 4 -->
          <div class="cluster-tier-card">
            <div>
              <span class="cluster-tier-badge" style="color:#c084fc; border-color:rgba(192,132,252,0.3); background:rgba(192,132,252,0.08);">TIER-4 / HYPERSCALE</span>
              <h4 style="font-size:1.02rem; font-weight:700; margin-bottom:0.4rem;">512 vCPU Matrix</h4>
              <p style="font-size:0.76rem; color:var(--text-muted); margin-bottom:0.85rem;">Distributed neural training and large-scale parallel MapReduce execution.</p>
              <div class="cluster-spec-row"><span class="cluster-spec-label">vCPU Ceiling</span><span class="cluster-spec-val">512 Cores (~143.4 TFLOPS)</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Memory Pool</span><span class="cluster-spec-val">2048 GB (2 TB)</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Mesh Topology</span><span class="cluster-spec-val">128+ Worker Nodes</span></div>
              <div class="cluster-spec-row"><span class="cluster-spec-label">Metered Rate</span><span class="cluster-spec-val" style="color:var(--accent);">600 UMAIS / hr</span></div>
            </div>
            <button class="btn-cluster-rent" onclick="rentSupercomputerPreset('Sovereign Supercomputer Matrix 512 Core', 512, 2048, 1)">Provision Matrix (600 UMAIS/hr)</button>
          </div>
        </div>
      </div>

      <!-- Custom Spec Configurator -->
      <div class="form-box" style="max-width:100%;">
        <h3 style="font-size:0.95rem; font-weight:700; margin-bottom:0.3rem;">Custom Elastic Cluster Specification</h3>
        <p style="font-size:0.78rem; color:var(--text-muted); margin-bottom:1.15rem;">
          Define your peak compute ceiling. Instances operate on <strong>continuous auto-renewal</strong> until explicitly paused or UMAIS balance depletes. Under light load, idle cores remain available to the NEXUS mesh and scale instantaneously up to your provisioned ceiling upon job dispatch.
        </p>

        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:1.25rem; margin-bottom:1.15rem;">
          <div>
            <label style="font-size:0.78rem; font-weight:600; color:var(--text-muted); display:flex; justify-content:space-between; margin-bottom:0.35rem;">
              <span>Peak vCPU Ceiling</span>
              <span id="cust-cores-val" style="color:var(--accent); font-family:var(--font-mono); font-weight:700;">64 Cores</span>
            </label>
            <input type="range" id="cust-cores-slider" min="4" max="512" step="4" value="64" style="width:100%;" oninput="updateSupercomputerCostEstimate()">
          </div>

          <div>
            <label style="font-size:0.78rem; font-weight:600; color:var(--text-muted); display:flex; justify-content:space-between; margin-bottom:0.35rem;">
              <span>Peak Memory Ceiling</span>
              <span id="cust-ram-val" style="color:var(--accent); font-family:var(--font-mono); font-weight:700;">256 GB</span>
            </label>
            <input type="range" id="cust-ram-slider" min="16" max="2048" step="16" value="256" style="width:100%;" oninput="updateSupercomputerCostEstimate()">
          </div>

          <div>
            <label style="font-size:0.78rem; font-weight:600; color:var(--text-muted); display:flex; justify-content:space-between; margin-bottom:0.35rem;">
              <span>Billing &amp; Lifecycle Policy</span>
              <span id="cust-duration-val" style="color:var(--success); font-family:var(--font-mono); font-weight:600;">Continuous (Auto-Renew)</span>
            </label>
            <select id="cust-duration-slider" class="form-ctrl" style="width:100%; padding:0.4rem;" onchange="updateSupercomputerCostEstimate()">
              <option value="1" selected>Hourly Metered Auto-Renew (1h Epoch • Runs Until Paused or 0 UMAIS)</option>
              <option value="6">6-Hour Initial Commitment + Continuous Auto-Renew</option>
              <option value="24">24-Hour (1 Day) Initial Commitment + Continuous Auto-Renew</option>
              <option value="168">168-Hour (7 Days) Initial Commitment + Continuous Auto-Renew</option>
              <option value="720">720-Hour (30 Days) Initial Commitment + Continuous Auto-Renew</option>
            </select>
          </div>
        </div>

        <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.9rem 1.15rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem;">
          <div style="display:flex; gap:1.75rem; flex-wrap:wrap;">
            <div>
              <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase; font-family:var(--font-mono);">Elastic Node Pool</div>
              <div id="est-nodes-val" style="font-size:0.92rem; font-family:var(--font-mono); font-weight:700;">Up to 16 Nodes</div>
            </div>
            <div>
              <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase; font-family:var(--font-mono);">Peak Throughput</div>
              <div id="est-tflops-val" style="font-size:0.92rem; font-family:var(--font-mono); font-weight:700;">~17.9 TFLOPS</div>
            </div>
            <div>
              <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase; font-family:var(--font-mono);">Burn Rate</div>
              <div id="est-rate-val" style="font-size:0.92rem; font-family:var(--font-mono); font-weight:700; color:var(--accent);">96 UMAIS/hr</div>
            </div>
            <div>
              <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase; font-family:var(--font-mono);">Initial Epoch Settlement</div>
              <div id="est-total-val" style="font-size:1rem; font-family:var(--font-mono); font-weight:700; color:var(--success);">96 UMAIS (Credits)</div>
            </div>
          </div>
          <button class="btn-download" style="padding:0.55rem 1.25rem; font-size:0.84rem;" onclick="rentCustomSupercomputer()">
            Provision Elastic Cluster
          </button>
        </div>
      </div>

      <!-- Connect to Existing Rented Server from Any Device (AWS-Style Access) -->
      <div class="form-box" style="max-width:100%;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem; margin-bottom:0.75rem;">
          <div>
            <h3 style="font-size:0.95rem; font-weight:700; margin-bottom:0.2rem;">Remote Instance Authentication (IAM Credentials)</h3>
            <p style="font-size:0.78rem; color:var(--text-muted); margin:0;">
              Authenticate using your Instance ID (or Access Key ID <code>NXIA...</code>) and Secret Key (<code>nxsrv-...</code>) to attach to a running or paused cluster from any workstation.
            </p>
          </div>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr auto; gap:0.75rem; align-items:center;">
          <input type="text" id="remote-server-id" class="form-ctrl" placeholder="Instance ID (vsup-xxxx) or Access Key (NXIA...)" style="font-family:var(--font-mono);">
          <input type="password" id="remote-server-secret" class="form-ctrl" placeholder="Server Secret Key (nxsrv-...)" style="font-family:var(--font-mono);">
          <button class="btn-download" style="padding:0.55rem 1.15rem; white-space:nowrap;" onclick="connectRemoteServerByCredentials()">
            Attach Console
          </button>
        </div>
      </div>

      <!-- Active Clusters List -->
      <div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.65rem;">
          <h3 style="font-size:0.92rem; font-weight:700;">Provisioned Compute Instances</h3>
          <button class="account-btn" onclick="loadMyClusters()">Refresh Instances</button>
        </div>
        <table class="p2p-table">
          <thead>
            <tr>
              <th>Instance ID</th>
              <th>Tier Profile</th>
              <th>Elastic Allocation</th>
              <th>IAM Access Credentials</th>
              <th>RPC Endpoint</th>
              <th>Lifecycle State</th>
              <th>Billing Cycle</th>
              <th>Operations</th>
            </tr>
          </thead>
          <tbody id="my-clusters-tbody">
            <tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:1.75rem;">Authenticate your Account Key or attach via IAM Instance Credentials to manage provisioned clusters.</td></tr>
          </tbody>
        </table>
      </div>

      <!-- Distributed Job Execution Output -->
      <div id="cluster-job-output-card" style="display:none; background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:1.15rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.65rem;">
          <h4 style="font-size:0.88rem; font-weight:700;" id="cluster-job-title">Distributed Execution Telemetry</h4>
          <span class="credits-pill" id="cluster-job-time">0 ms</span>
        </div>
        <div id="cluster-job-summary" style="font-size:0.8rem; font-family:var(--font-mono); color:var(--accent); margin-bottom:0.65rem;"></div>
        <div id="cluster-job-slices" style="display:flex; flex-wrap:wrap; gap:0.45rem; font-family:var(--font-mono); font-size:0.75rem;"></div>
      </div>
    </div>
  </div>

  <!-- Modal: Public Cloud HTTPS Gateway (Cloudflare Tunnel) -->
  <div id="modal-public-tunnel" class="modal-backdrop" style="display:none;" onclick="if(event.target===this)closePublicTunnelModal()">
    <div class="modal-card">
      <div class="modal-header">
        <div>
          <h3 style="margin:0; font-size:0.95rem; font-weight:700;">Worldwide Remote Worker Public Gateway</h3>
          <div style="font-size:0.72rem; color:var(--text-muted);">Zero-configuration Cloudflare Tunnel (HTTPS/WSS) for distributed edge nodes</div>
        </div>
        <button class="modal-close-btn" onclick="closePublicTunnelModal()">✕</button>
      </div>
      <div style="padding:1.25rem;">
        <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:1rem; margin-bottom:1rem;">
          <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase; font-family:var(--font-mono); margin-bottom:0.25rem;">Active Public Endpoint</div>
          <div id="modal-tunnel-url-display" style="font-size:1.05rem; font-family:var(--font-mono); font-weight:700; color:var(--success); word-break:break-all;">
            Localhost Only (127.0.0.1:8443)
          </div>
        </div>
        <p style="font-size:0.78rem; color:var(--text-muted); line-height:1.45; margin-bottom:1rem;">
          Remote workers anywhere in the world (on mobile data, home Wi-Fi behind NAT, or cloud GPUs) can pull signed tasks and mine UMAIS directly through this public HTTPS gateway without opening any router ports.
        </p>
        <div style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-bottom:0.75rem;">
          <button class="account-btn" style="background:#2563eb; color:white; border-color:#3b82f6;" onclick="copyPublicTunnelUrl()">Copy Public Endpoint</button>
          <button class="account-btn" style="background:#10b981; color:#000; border-color:#10b981; font-weight:600;" onclick="startCloudflareTunnelFromUi()">Start Cloudflare Tunnel</button>
          <button class="account-btn" onclick="checkPublicTunnelStatus()">Refresh Status</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal: Open / Switch / Create Project -->
  <div id="modal-project-picker" class="modal-backdrop" style="display:none;" onclick="if(event.target===this)closeProjectModal()">
    <div class="modal-card">
      <div class="modal-header">
        <div>
          <h3 style="margin:0; font-size:0.95rem; font-weight:700;">Mount Workspace Directory</h3>
          <div style="font-size:0.72rem; color:var(--text-muted);">Bind local directory path or initialize a new project scaffold</div>
        </div>
        <button class="modal-close-btn" onclick="closeProjectModal()">✕</button>
      </div>
      <div style="padding:1.25rem;">
        <label style="font-size:0.72rem; font-weight:600; color:var(--text-muted); text-transform:uppercase; margin-bottom:0.4rem; display:block;">
          Local Filesystem Path
        </label>
        <div style="display:flex; gap:0.5rem; margin-bottom:1.1rem;">
          <input type="text" id="project-path-input" class="form-ctrl" placeholder="e.g. C:/Projects/Service or e:/NEXUS" style="font-family:var(--font-mono); font-size:0.8rem;">
          <button class="account-btn" style="background:#2563eb; border-color:#3b82f6; color:white; padding:0.45rem 1rem; white-space:nowrap;" onclick="submitOpenProject()">Mount Path</button>
        </div>

        <div style="margin-bottom:1.2rem;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
            <label style="font-size:0.72rem; font-weight:600; color:var(--text-muted); text-transform:uppercase;">
              Recent Workspaces
            </label>
            <span style="font-size:0.7rem; color:var(--text-muted);">Click to mount</span>
          </div>
          <div id="recent-projects-list" style="display:flex; flex-direction:column; gap:0.35rem; max-height:140px; overflow-y:auto;">
            <!-- Populated dynamically -->
          </div>
        </div>

        <div style="border-top:1px solid var(--border); padding-top:1rem;">
          <label style="font-size:0.72rem; font-weight:600; color:var(--text-muted); text-transform:uppercase; margin-bottom:0.4rem; display:block;">
            Initialize New Project Scaffold
          </label>
          <div style="display:grid; grid-template-columns:1fr 130px auto; gap:0.5rem;">
            <input type="text" id="new-project-name" class="form-ctrl" placeholder="Repository name" style="font-size:0.8rem;">
            <select id="new-project-template" class="form-ctrl" style="font-size:0.78rem;">
              <option value="python">Python Package</option>
              <option value="fastapi">FastAPI Service</option>
              <option value="empty">Empty Directory</option>
            </select>
            <button class="account-btn" style="background:#161922; border-color:var(--border); color:var(--text); padding:0.45rem 0.85rem;" onclick="submitCreateProject()">Initialize</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal: Use Rented Supercomputer / Virtual Server Console -->
  <div id="modal-server-console" class="modal-backdrop" style="display:none;" onclick="if(event.target===this)closeServerConsole()">
    <div class="modal-card" style="max-width:780px;">
      <div class="modal-header">
        <div>
          <h3 style="margin:0; font-size:0.98rem; font-weight:700; font-family:var(--font-mono);" id="m-server-title">Instance Console: vsup-xxxx</h3>
          <div style="font-size:0.73rem; font-family:var(--font-mono); color:var(--text-muted); margin-top:0.15rem;" id="m-server-specs">64 Cores • 256GB RAM • ONLINE</div>
        </div>
        <button class="modal-close-btn" onclick="closeServerConsole()">✕</button>
      </div>

      <!-- IAM Server Credentials Banner inside Console -->
      <div style="background:#090a0f; border-bottom:1px solid var(--border); padding:0.65rem 1.25rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.75rem; font-size:0.75rem;">
        <div style="display:flex; gap:1.1rem; flex-wrap:wrap; font-family:var(--font-mono);">
          <span><strong style="color:var(--text-muted);">INSTANCE:</strong> <span id="m-cred-iid" style="color:var(--accent);">vsup-xxxx</span></span>
          <span><strong style="color:var(--text-muted);">ACCESS KEY:</strong> <span id="m-cred-akid" style="color:var(--success);">NXIA...</span></span>
          <span><strong style="color:var(--text-muted);">SECRET:</strong> <span id="m-cred-secret" style="color:var(--warning);">nxsrv-...</span></span>
        </div>
        <button class="account-btn" style="font-size:0.72rem; padding:0.22rem 0.6rem;" onclick="copyActiveServerCredentials()">Copy IAM Keys</button>
      </div>

      <!-- Server Navigation Tabs -->
      <div style="display:flex; border-bottom:1px solid var(--border); background:#0c0e14; padding:0 1rem; gap:0.4rem;">
        <button class="account-btn" id="stab-btn-code" style="background:#161922; border-radius:6px 6px 0 0; border-bottom:none; font-size:0.76rem;" onclick="switchServerModalTab('code')">1. Interactive Workload Dispatch</button>
        <button class="account-btn" id="stab-btn-api" style="background:transparent; border-radius:6px 6px 0 0; border:none; font-size:0.76rem;" onclick="switchServerModalTab('api')">2. HTTP REST / cURL</button>
        <button class="account-btn" id="stab-btn-sdk" style="background:transparent; border-radius:6px 6px 0 0; border:none; font-size:0.76rem;" onclick="switchServerModalTab('sdk')">3. Python Client SDK</button>
      </div>

      <div style="padding:1.25rem;">
        <!-- Tab 1: Run Code & Tasks -->
        <div id="modal-server-tab-code">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.45rem;">
            <label style="font-size:0.72rem; font-weight:600; color:var(--text-muted); text-transform:uppercase;">
              Workload Template
            </label>
            <select id="server-code-template" class="form-ctrl" style="width:280px; padding:0.25rem 0.5rem; font-size:0.75rem;" onchange="applyServerCodeTemplate(this.value)">
              <option value="matrix">1. Parallel Matrix Factorization</option>
              <option value="batch">2. High-Throughput Stream Processing</option>
              <option value="simulation">3. Distributed Monte Carlo Kernel</option>
              <option value="custom">4. Custom Python Workload</option>
            </select>
          </div>

          <textarea id="server-code-input" class="form-ctrl" rows="7" style="font-family:var(--font-mono); font-size:0.78rem; margin-bottom:0.75rem;" spellcheck="false"></textarea>

          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
            <div style="font-size:0.73rem; color:var(--text-muted);">
              Elastic scheduler automatically scales active cores up to instance ceiling during execution.
            </div>
            <button class="account-btn" style="background:#2563eb; border-color:#3b82f6; color:white; padding:0.45rem 1.15rem; font-weight:600;" onclick="submitServerCodeRun()">
              Dispatch Workload
            </button>
          </div>

          <!-- Live Output Dock inside Modal -->
          <div id="server-run-output-area" style="display:none; background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.85rem; max-height:160px; overflow-y:auto; font-family:var(--font-mono); font-size:0.75rem;">
            <div style="color:var(--accent); font-weight:600; margin-bottom:0.25rem;" id="server-run-status-line">Execution Status:</div>
            <pre id="server-run-stdout" style="color:var(--text); margin:0; white-space:pre-wrap;"></pre>
            <div id="server-run-slices" style="display:flex; flex-wrap:wrap; gap:0.4rem; margin-top:0.5rem;"></div>
          </div>
        </div>

        <!-- Tab 2: REST API & Curl -->
        <div id="modal-server-tab-api" style="display:none;">
          <p style="font-size:0.78rem; color:var(--text-muted); margin-bottom:0.75rem;">
            Dispatch compute payloads from external infrastructure via standard HTTP POST using your instance <code>server_secret_key</code>:
          </p>
          <pre id="server-curl-snippet" style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.85rem; font-family:var(--font-mono); font-size:0.75rem; color:#93c5fd; overflow-x:auto; user-select:all;"></pre>
          <button class="account-btn" style="margin-top:0.5rem;" onclick="navigator.clipboard.writeText(document.getElementById('server-curl-snippet').textContent); alert('Copied cURL snippet to clipboard.');">Copy cURL Command</button>
        </div>

        <!-- Tab 3: Python SDK Client -->
        <div id="modal-server-tab-sdk" style="display:none;">
          <p style="font-size:0.78rem; color:var(--text-muted); margin-bottom:0.75rem;">
            Embed this zero-dependency Python client in external services to execute remote workloads on your cluster:
          </p>
          <pre id="server-python-snippet" style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.85rem; font-family:var(--font-mono); font-size:0.75rem; color:var(--success); overflow-x:auto; user-select:all;"></pre>
          <button class="account-btn" style="margin-top:0.5rem;" onclick="navigator.clipboard.writeText(document.getElementById('server-python-snippet').textContent); alert('Copied Python SDK client to clipboard.');">Copy Python SDK Snippet</button>
        </div>
      </div>
    </div>
  </div>

  <!-- ========================================================= -->
  <!-- TAB 6: THE TOKEN SINK (LOTTERY & STAKING VAULT)           -->
  <!-- ========================================================= -->
  <div id="tab-lottery" class="workspace-container">
    <div style="flex:1; padding:1.5rem 2rem; overflow-y:auto; display:flex; flex-direction:column; gap:1.25rem;">
      
      <!-- Utility Sink Banner -->
      <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:1.15rem 1.4rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem;">
        <div style="flex:2; min-width:300px;">
          <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.35rem; flex-wrap:wrap;">
            <span class="tech-pill" style="color:var(--success); border-color:rgba(16,185,129,0.3);">
              INTERNAL UMAIS (CREDIT) UTILITY &amp; DEFLATIONARY SINK
            </span>
            <span class="tech-pill" style="color:#60a5fa; border-color:rgba(59,130,246,0.3);">
              1 CREDIT = 1 UMAIS • ZERO FIAT SUBSCRIPTION
            </span>
          </div>
          <h2 style="font-size:1.05rem; font-weight:700; margin-bottom:0.25rem;">
            Developer Compute Utility &amp; UMAIS Protocol Treasury Sink
          </h2>
          <p style="font-size:0.8rem; color:var(--text-muted); line-height:1.45; margin:0;">
            Redeem mined <strong>UMAIS</strong> (<strong>1 Credit = 1 UMAIS</strong>) directly for 24/7 frontier AI inference and autonomous IDE execution, or commit UMAIS to the cryptographic consensus pool and staking vault to reduce circulating supply.
          </p>
        </div>
        <div style="display:flex; gap:0.6rem; flex-wrap:wrap;">
          <button class="account-btn" style="background:#2563eb; border-color:#3b82f6; color:white; padding:0.5rem 1rem; font-size:0.8rem;" onclick="switchMainTab('chat')">
            Launch Inference Chat
          </button>
          <button class="account-btn" style="padding:0.5rem 1rem; font-size:0.8rem;" onclick="switchMainTab('ide')">
            Launch Cloud IDE
          </button>
        </div>
      </div>

      <!-- Main Grid: Lottery + Staking -->
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(360px, 1fr)); gap:1.25rem;">
        
        <!-- CARD 1: CONSENSUS LOTTERY & BURN POOL -->
        <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:1.35rem; display:flex; flex-direction:column; gap:1rem;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
            <div>
              <span style="font-size:0.68rem; font-family:var(--font-mono); font-weight:600; color:var(--warning); text-transform:uppercase; letter-spacing:0.05em;">
                VERIFIABLE RANDOM CONSENSUS POOL
              </span>
              <h3 style="font-size:1.05rem; font-weight:700; margin-top:0.15rem;">UMAIS Credit Lottery &amp; Deflationary Burn</h3>
            </div>
            <span id="lottery-round-badge" class="tech-pill" style="color:var(--warning); border-color:rgba(245,158,11,0.3);">
              Round #1 Active
            </span>
          </div>

          <!-- Pool Meter -->
          <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:1rem; text-align:center;">
            <div style="font-size:0.7rem; font-family:var(--font-mono); color:var(--text-muted); text-transform:uppercase;">ACTIVE POOL LIQUIDITY (1 CREDIT = 1 UMAIS)</div>
            <div style="font-size:1.85rem; font-family:var(--font-mono); font-weight:700; color:var(--text); margin:0.25rem 0;" id="lottery-current-pot">
              0 UMAIS (Credits)
            </div>
            <div style="display:flex; justify-content:center; gap:1.25rem; font-size:0.76rem; font-family:var(--font-mono); color:var(--text-muted); margin-top:0.3rem;">
              <span>Winner Allocation: <strong style="color:var(--success);" id="lottery-win-payout">45 UMAIS (90%)</strong></span>
              <span>Protocol Burn: <strong style="color:var(--danger);" id="lottery-burn-payout">5 UMAIS (10%)</strong></span>
            </div>
          </div>

          <!-- Ticket Buy Controls -->
          <div style="background:#0c0e14; border:1px solid var(--border); border-radius:6px; padding:0.9rem; display:flex; flex-direction:column; gap:0.65rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.78rem; font-family:var(--font-mono);">
              <span>Unit Entry: <strong style="color:var(--accent);">5 UMAIS (5 CR)</strong></span>
              <span id="lottery-tickets-needed" style="color:var(--text-muted);">10 entries required for auto-settlement</span>
            </div>
            <div style="display:flex; gap:0.5rem; align-items:center;">
              <select id="lottery-ticket-qty" class="form-ctrl" style="max-width:165px; padding:0.45rem; font-family:var(--font-mono); font-size:0.78rem;">
                <option value="1">1 Entry (5 UMAIS)</option>
                <option value="2">2 Entries (10 UMAIS)</option>
                <option value="3">3 Entries (15 UMAIS)</option>
                <option value="5">5 Entries (25 UMAIS)</option>
                <option value="10">10 Entries (50 UMAIS)</option>
              </select>
              <button class="account-btn" style="flex:1; background:#2563eb; border-color:#3b82f6; color:#fff; font-weight:600; font-size:0.82rem; padding:0.48rem;" onclick="buyLotteryTicketsNow()">
                Commit Pool Entries
              </button>
            </div>
            <button class="account-btn" style="background:#161922; border:1px solid var(--border); color:var(--text-muted); font-size:0.76rem;" onclick="drawLotteryNow()">
              Execute Consensus Draw (SHA-256 Beacon)
            </button>
          </div>

          <!-- Deflationary Telemetry -->
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.75rem; font-size:0.78rem;">
            <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.65rem 0.85rem;">
              <div style="color:var(--text-muted); font-size:0.68rem; font-family:var(--font-mono); text-transform:uppercase;">CUMULATIVE SUPPLY BURNED</div>
              <div style="font-size:1.05rem; font-family:var(--font-mono); font-weight:700; color:var(--danger); margin-top:0.2rem;" id="lottery-total-burned">0 UMAIS</div>
            </div>
            <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.65rem 0.85rem;">
              <div style="color:var(--text-muted); font-size:0.68rem; font-family:var(--font-mono); text-transform:uppercase;">CUMULATIVE POOL PAYOUTS</div>
              <div style="font-size:1.05rem; font-family:var(--font-mono); font-weight:700; color:var(--success); margin-top:0.2rem;" id="lottery-total-awarded">0 UMAIS</div>
            </div>
          </div>

          <!-- Recent Winners List -->
          <div>
            <div style="font-size:0.72rem; font-weight:600; color:var(--text-muted); margin-bottom:0.4rem; text-transform:uppercase; letter-spacing:0.04em;">Settled Consensus Rounds</div>
            <div id="lottery-recent-winners" style="font-size:0.78rem; font-family:var(--font-mono); display:flex; flex-direction:column; gap:0.35rem; max-height:130px; overflow-y:auto;">
              <div style="color:var(--text-muted);">No settled rounds recorded. Commit entries to initialize Round #1.</div>
            </div>
          </div>
        </div>

        <!-- CARD 2: THE STAKING VAULT (YIELD & LUCK MULTIPLIER) -->
        <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:1.35rem; display:flex; flex-direction:column; gap:1rem;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
            <div>
              <span style="font-size:0.68rem; font-family:var(--font-mono); font-weight:600; color:var(--accent); text-transform:uppercase; letter-spacing:0.05em;">
                PROTOCOL COLLATERAL &amp; YIELD MULTIPLIER
              </span>
              <h3 style="font-size:1.05rem; font-weight:700; margin-top:0.15rem;">UMAIS Staking Vault</h3>
            </div>
            <span id="my-staking-badge" class="tech-pill" style="color:#60a5fa; border-color:rgba(59,130,246,0.3);">
              Tier: NONE
            </span>
          </div>

          <!-- Staking Info & Tiers -->
          <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:1rem;">
            <div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:0.6rem;">
              <span style="color:var(--text-muted);">Operator Staked Balance:</span>
              <strong style="color:var(--accent); font-family:var(--font-mono); font-size:0.9rem;" id="my-staked-credits">0 UMAIS (Credits)</strong>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:0.65rem;">
              <span style="color:var(--text-muted);">Total Network TVL:</span>
              <strong style="color:var(--text); font-family:var(--font-mono); font-size:0.9rem;" id="vault-total-staked">0 UMAIS (Credits)</strong>
            </div>
            <div style="border-top:1px solid var(--border); padding-top:0.6rem; font-size:0.75rem; display:flex; flex-direction:column; gap:0.35rem; color:var(--text-muted);">
              <div><strong style="color:var(--text); font-family:var(--font-mono);">[TIER-1 BRONZE • 20+ UMAIS]</strong> +5% Compute Task Dividend Yield</div>
              <div><strong style="color:var(--text); font-family:var(--font-mono);">[TIER-2 SILVER • 50+ UMAIS]</strong> +10% Yield + Priority Scheduler Queue</div>
              <div><strong style="color:var(--text); font-family:var(--font-mono);">[TIER-3 GOLD • 150+ UMAIS]</strong> +20% Yield + 2.0x Consensus Pool Weight</div>
            </div>
          </div>

          <!-- Stake / Unstake Controls -->
          <div style="background:#0c0e14; border:1px solid var(--border); border-radius:6px; padding:0.9rem; display:flex; flex-direction:column; gap:0.65rem;">
            <label style="font-size:0.76rem; font-weight:600; color:var(--text-muted);">Modify Vault Collateral (1 Credit = 1 UMAIS):</label>
            <div style="display:flex; gap:0.5rem;">
              <input type="number" id="staking-input-amount" class="form-ctrl" placeholder="Volume (UMAIS / CR)" min="1" style="font-family:var(--font-mono);">
              <button class="account-btn" style="background:#2563eb; border-color:#3b82f6; color:white; font-weight:600; min-width:105px;" onclick="stakeCreditsNow()">
                Lock Stake
              </button>
              <button class="account-btn" style="background:#161922; border:1px solid var(--border); color:var(--text); min-width:105px;" onclick="unstakeCreditsNow()">
                Withdraw
              </button>
            </div>
            <p style="font-size:0.73rem; color:var(--text-muted); margin-top:0.15rem;">
              Staked UMAIS collateral remains under your cryptographic key custody and can be withdrawn to your liquid balance without lockup penalties.
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
  <script nonce="{csp_nonce}">
    let activeAccountKey = '';
    let activeRemoteServerSecret = '';
    let currentChatSessionId = localStorage.getItem('sup_chat_session_id') || 'default';
    let chatSessions = (() => {{
      try {{
        const parsed = JSON.parse(localStorage.getItem('sup_chat_sessions') || '{{}}');
        return (parsed && typeof parsed === 'object') ? parsed : {{}};
      }} catch (e) {{
        return {{}};
      }}
    }})();

    /* --- INITIALIZATION --- */
    window.onload = () => {{
      // Auto-detect account key from URL if passed from worker launcher, store in HttpOnly cookie, then scrub URL bar (N6 / H11 / R1)
      const params = new URLSearchParams(window.location.search);
      const urlKey = params.get('account_key');
      const urlToken = params.get('token');
      if (urlKey) {{
        activeAccountKey = urlKey;
        fetch('/api/auth/session', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ account_key: urlKey, token: urlToken || '' }})
        }}).catch(() => {{}});
      }} else if (urlToken) {{
        fetch('/api/auth/session', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ token: urlToken }})
        }}).catch(() => {{}});
      }}
      if ((urlKey || urlToken) && window.history && window.history.replaceState) {{
        window.history.replaceState({{}}, document.title, window.location.pathname + window.location.hash);
      }}

      verifyAndDisplayAccount(activeAccountKey);
      renderChatHistory();
      loadActiveChat();
      initMonaco();
      const urlTab = params.get('tab') || window.location.hash.replace('#tab-', '').replace('#', '');
      if (urlTab && ['chat', 'ide', 'physical', 'p2p', 'supercomputer', 'lottery'].includes(urlTab)) {{
        switchMainTab(urlTab);
      }}
      checkPublicTunnelStatus();
    }};

    /* --- CLOUDFLARE PUBLIC HTTPS TUNNEL HELPER --- */
    let activePublicTunnelUrl = '';
    async function checkPublicTunnelStatus() {{
      try {{
        const res = await fetch('/api/tunnel/status');
        const data = await res.json();
        const dot = document.getElementById('tunnel-dot');
        const label = document.getElementById('tunnel-label');
        const modalUrl = document.getElementById('modal-tunnel-url-display');
        if (data.ok && data.public_hub_url) {{
          activePublicTunnelUrl = data.public_hub_url;
          if (dot) dot.style.background = '#10b981';
          if (label) label.textContent = '🌐 Cloudflare HTTPS Active';
          if (modalUrl) modalUrl.textContent = activePublicTunnelUrl;
        }} else {{
          if (dot) dot.style.background = '#8b92a5';
          if (label) label.textContent = 'Public Mesh: Localhost';
          if (modalUrl) modalUrl.textContent = 'Localhost Only (127.0.0.1:8443)';
        }}
      }} catch(err) {{
        console.error('Error checking tunnel status', err);
      }}
    }}

    function showPublicTunnelModal() {{
      const m = document.getElementById('modal-public-tunnel');
      if (m) m.style.display = 'flex';
      checkPublicTunnelStatus();
    }}

    function closePublicTunnelModal() {{
      const m = document.getElementById('modal-public-tunnel');
      if (m) m.style.display = 'none';
    }}

    function copyPublicTunnelUrl() {{
      const target = activePublicTunnelUrl || window.location.origin;
      navigator.clipboard.writeText(target);
      alert('Public Hub Endpoint copied to clipboard:\\n' + target);
    }}

    async function startCloudflareTunnelFromUi() {{
      try {{
        const res = await fetch('/api/tunnel/start', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }} }});
        const data = await res.json();
        if (data.ok && data.public_hub_url) {{
          activePublicTunnelUrl = data.public_hub_url;
          alert('Cloudflare Public Tunnel Online!\\n\\nPublic URL: ' + data.public_hub_url);
          checkPublicTunnelStatus();
        }} else {{
          alert('Notice: ' + (data.error || data.status || 'Could not start tunnel automatically. Ensure cloudflared is installed or set PUBLIC_HUB_URL.'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    /* --- ACCOUNT KEY LOGIN / CONNECT --- */
    async function connectAccountKey() {{
      const key = document.getElementById('top-account-key').value.trim();
      if (!key) return alert('Please enter your Secret Account Key');
      await verifyAndDisplayAccount(key);
    }}

    async function verifyAndDisplayAccount(key) {{
      try {{
        const reqHeaders = key ? {{ 'X-Account-Key': key }} : {{}};
        const res = await fetch('/api/account/status', {{ headers: reqHeaders }});
        const data = await res.json();
        if (data.ok) {{
          activeAccountKey = data.account_key || key;
          if (key) {{
            fetch('/api/auth/session', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ account_key: activeAccountKey }})
            }}).catch(() => {{}});
          }}
          document.getElementById('account-logged-out').style.display = 'none';
          document.getElementById('account-logged-in').style.display = 'flex';
          document.getElementById('account-key-label').textContent = data.worker_id + (data.dispute_frozen ? ' (FROZEN)' : '');
          document.getElementById('account-credits-label').textContent = data.credits;

          if (document.getElementById('quantum-addr-pill') && data.quantum_address) {{
            document.getElementById('quantum-addr-pill').style.display = 'inline-block';
            document.getElementById('quantum-addr-pill').textContent = data.quantum_address.slice(0, 10) + '...' + data.quantum_address.slice(-6);
            document.getElementById('quantum-addr-pill').setAttribute('data-full-addr', data.quantum_address);
          }}

          if (document.getElementById('my-referral-code-pill')) {{
            document.getElementById('my-referral-code-pill').textContent = data.referral_code || ('REF-' + String(data.worker_id).toUpperCase());
          }}
          if (document.getElementById('ref-count-badge')) {{
            document.getElementById('ref-count-badge').textContent = data.referrals_count || 0;
          }}
          if (document.getElementById('ref-bonus-badge')) {{
            document.getElementById('ref-bonus-badge').textContent = '+' + (data.referral_bonus_credits || 0) + ' UMAIS';
          }}

          // Prefill in forms with secret account key (backend resolves to public worker_id in orderbooks)
          if (document.getElementById('sell-worker-id')) document.getElementById('sell-worker-id').value = activeAccountKey;
          if (document.getElementById('tr-from')) document.getElementById('tr-from').value = activeAccountKey;
          if (document.getElementById('p2p-check-id')) document.getElementById('p2p-check-id').value = activeAccountKey;
        }} else if (key) {{
          alert('Could not verify key: ' + (data.error || 'Unknown'));
        }}
      }} catch(err) {{
        console.error('Account verification error', err);
      }}
    }}

    function copyTopQuantumAddr() {{
      const el = document.getElementById('quantum-addr-pill');
      const addr = el ? el.getAttribute('data-full-addr') : '';
      if (addr) {{
        navigator.clipboard.writeText(addr);
        alert('4096-Bit Hybrid Quantum Vault Address copied:\\n' + addr);
      }}
    }}

    function copyMyReferralCode() {{
      const el = document.getElementById('my-referral-code-pill');
      const code = el ? el.textContent.trim() : '';
      if (!code || code === 'REF-CONNECT-KEY') {{
        return alert('Connect your Secret Account Key in the top bar first to get your personal Referral Code!');
      }}
      navigator.clipboard.writeText(code);
      alert('Referral Code copied: ' + code + '\\nShare it with friends to earn +5% extra bonus credits on all their tasks & uptime!');
    }}

    function disconnectAccountKey() {{
      activeAccountKey = '';
      document.getElementById('account-logged-in').style.display = 'none';
      document.getElementById('account-logged-out').style.display = 'flex';
      document.getElementById('top-account-key').value = '';
    }}

    /* --- MAIN TABS NAVIGATION --- */
    function switchMainTab(tabId) {{
      document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.workspace-container').forEach(c => c.classList.remove('active'));
      const activeBtn = (typeof event !== 'undefined' && event && event.currentTarget && event.currentTarget.classList && event.currentTarget.classList.contains('nav-tab-btn'))
        ? event.currentTarget
        : document.querySelector(`.nav-tab-btn[onclick*="'${{tabId}}'"]`);
      if (activeBtn) activeBtn.classList.add('active');
      const targetContainer = document.getElementById('tab-' + tabId);
      if (targetContainer) targetContainer.classList.add('active');

      if (tabId === 'ide') {{
        if (monacoEditorInstance) setTimeout(() => monacoEditorInstance.layout(), 100);
        loadProjectFiles();
      }}
      if (tabId === 'p2p') loadP2POffers();
      if (tabId === 'supercomputer') loadMyClusters();
      if (tabId === 'lottery') loadLotteryAndStaking();
    }}

    /* ========================================================= */
    /* CHATGPT-STYLE CHAT FUNCTIONS                              */
    /* ========================================================= */
    function renderChatHistory() {{
      const cont = document.getElementById('chat-history-container');
      cont.innerHTML = '';
      const sessionIds = Object.keys(chatSessions);
      if (sessionIds.length === 0) {{
        chatSessions['default'] = {{ title: 'New Session', messages: [] }};
      }}
      Object.keys(chatSessions).reverse().forEach(sid => {{
        const s = chatSessions[sid];
        const item = document.createElement('div');
        item.className = 'chat-history-item' + (sid === currentChatSessionId ? ' active' : '');
        item.innerHTML = `
          <span style="overflow:hidden; text-overflow:ellipsis;">${{escapeHtml(s.title || 'Session')}}</span>
          <button class="del-btn" onclick="event.stopPropagation(); deleteChatSession('${{sid}}')">✕</button>
        `;
        item.onclick = () => selectChatSession(sid);
        cont.appendChild(item);
      }});
    }}

    function startNewChat() {{
      const newId = 'chat_' + Date.now();
      chatSessions[newId] = {{ title: 'New Session', messages: [] }};
      currentChatSessionId = newId;
      localStorage.setItem('sup_chat_session_id', newId);
      saveChatSessions();
      renderChatHistory();
      loadActiveChat();
    }}

    function selectChatSession(sid) {{
      currentChatSessionId = sid;
      localStorage.setItem('sup_chat_session_id', sid);
      renderChatHistory();
      loadActiveChat();
    }}

    function deleteChatSession(sid) {{
      delete chatSessions[sid];
      if (currentChatSessionId === sid) {{
        currentChatSessionId = Object.keys(chatSessions)[0] || 'default';
        if (!chatSessions[currentChatSessionId]) chatSessions[currentChatSessionId] = {{ title: 'New Session', messages: [] }};
      }}
      saveChatSessions();
      renderChatHistory();
      loadActiveChat();
    }}

    function clearAllChatHistory() {{
      if (!confirm('Purge all local session history?')) return;
      chatSessions = {{ default: {{ title: 'New Session', messages: [] }} }};
      currentChatSessionId = 'default';
      saveChatSessions();
      renderChatHistory();
      loadActiveChat();
    }}

    function saveChatSessions() {{
      localStorage.setItem('sup_chat_sessions', JSON.stringify(chatSessions));
    }}

    function loadActiveChat() {{
      const s = chatSessions[currentChatSessionId] || {{ messages: [] }};
      const list = document.getElementById('chat-messages-list');
      const starter = document.getElementById('chat-starter-view');

      if (!s.messages || s.messages.length === 0) {{
        if (starter) starter.style.display = 'block';
        // Remove existing message rows
        const rows = list.querySelectorAll('.msg-row');
        rows.forEach(r => r.remove());
        return;
      }}

      if (starter) starter.style.display = 'none';
      const rows = list.querySelectorAll('.msg-row');
      rows.forEach(r => r.remove());

      s.messages.forEach(m => {{
        appendMessageToDom(m.role, m.content, m.meta);
      }});
      scrollChatToBottom();
    }}

    function appendMessageToDom(role, content, meta) {{
      const starter = document.getElementById('chat-starter-view');
      if (starter) starter.style.display = 'none';

      const list = document.getElementById('chat-messages-list');
      const row = document.createElement('div');
      row.className = 'msg-row';

      const avatar = document.createElement('div');
      avatar.className = 'msg-avatar ' + (role === 'user' ? 'avatar-user' : 'avatar-ai');
      avatar.textContent = (role === 'user' ? 'OP' : 'NX');

      const body = document.createElement('div');
      body.className = 'msg-body';
      body.innerHTML = formatMarkdown(content);

      if (meta) {{
        body.innerHTML += `<div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted); margin-top:0.45rem;">${{meta}}</div>`;
      }}

      row.appendChild(avatar);
      row.appendChild(body);
      list.appendChild(row);
      scrollChatToBottom();
    }}

    async function submitChatMessage() {{
      const inp = document.getElementById('chat-input-box');
      const text = inp.value.trim();
      if (!text) return;
      inp.value = '';

      if (!chatSessions[currentChatSessionId]) {{
        chatSessions[currentChatSessionId] = {{ title: text.slice(0, 30), messages: [] }};
      }}
      if (chatSessions[currentChatSessionId].messages.length === 0) {{
        chatSessions[currentChatSessionId].title = text.slice(0, 30);
        renderChatHistory();
      }}

      chatSessions[currentChatSessionId].messages.push({{ role: 'user', content: text }});
      appendMessageToDom('user', text);
      saveChatSessions();

      // Placeholder thinking message
      const list = document.getElementById('chat-messages-list');
      const thinkRow = document.createElement('div');
      thinkRow.className = 'msg-row';
      thinkRow.id = 'think-row';
      thinkRow.innerHTML = `
        <div class="msg-avatar avatar-ai">NX</div>
        <div class="msg-body" style="color:var(--text-muted); font-family:var(--font-mono); font-size:0.8rem;">Dispatching query across SUP Agentic Mesh...</div>
      `;
      list.appendChild(thinkRow);
      scrollChatToBottom();

      try {{
        const res = await fetch('/api/chat', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ prompt: text, account_key: activeAccountKey }})
        }});
        const data = await res.json();
        const tr = document.getElementById('think-row');
        if (tr) tr.remove();

        if (data.insufficient_credits) {{
          appendMessageToDom('assistant', `**Insufficient UMAIS Balance**: ${{data.error}}\\n\\nNavigate to Tab 4 (**BUY / SELL UMAIS**) to acquire UMAIS via P2P Escrow, or run a Worker Node to mint UMAIS.`);
          return;
        }}
        if (data.ok === false && data.error) {{
          appendMessageToDom('assistant', `**System Notice**: ${{data.error}}`);
          return;
        }}

        let reply = data.reply || (data.result ? JSON.stringify(data.result, null, 2) : 'Task completed.');
        let meta = `ENGINE: ${{data.model || 'SUP Agentic Mesh'}} • STATE: ${{data.status || 'VERIFIED'}}`;
        if (data.attention_route && data.attention_route.primary_shard) {{
          meta += ` • SHARD: ${{data.attention_route.primary_shard}} (${{data.attention_route.base_model}})`;
        }}
        if (data.cost_credits !== undefined) {{
          meta += ` • COST: ${{data.cost_credits}} UMAIS`;
        }}
        if (data.distilled_from_cache || (data.distillation && data.distillation.distilled_from_cache)) {{
          meta += ` • CACHE: Local Distilled CoT (0 Upstream Cost)`;
        }} else if (data.self_play_freedom_loop && data.self_play_freedom_loop.ok) {{
          meta += ` • DISTILLATION: +${{data.self_play_freedom_loop.synthetic_variations_generated}} Synthetic Samples + P2P Delta Replicated`;
        }} else if (data.cot_reasoning) {{
          meta += ` • CACHE: CoT Indexed Locally (1 UMAIS on repeat)`;
        }}
        if (data.credits_info) {{
          meta += ` • BALANCE: ${{data.credits_info.remaining_credits}} UMAIS`;
          document.getElementById('account-credits-label').textContent = data.credits_info.remaining_credits;
        }}

        chatSessions[currentChatSessionId].messages.push({{ role: 'assistant', content: reply, meta: meta }});
        appendMessageToDom('assistant', reply, meta);
        saveChatSessions();
      }} catch(err) {{
        const tr = document.getElementById('think-row');
        if (tr) tr.remove();
        appendMessageToDom('assistant', 'Error executing request: ' + err.toString());
      }}
    }}

    function sendQuickPrompt(promptText) {{
      document.getElementById('chat-input-box').value = promptText;
      submitChatMessage();
    }}

    function scrollChatToBottom() {{
      const el = document.getElementById('chat-scroll-area');
      if (el) el.scrollTop = el.scrollHeight;
    }}

    const _chatInputBox = document.getElementById('chat-input-box');
    if (_chatInputBox) {{
      _chatInputBox.addEventListener('keydown', (e) => {{
        if (e.key === 'Enter' && !e.shiftKey) {{
          e.preventDefault();
          submitChatMessage();
        }}
      }});
    }}

    function formatMarkdown(text) {{
      if (!text) return '';
      // Escape HTML
      let s = escapeHtml(text);
      // Code blocks ```lang ... ```
      s = s.replace(/```([a-zA-Z0-9_-]*)\\n([\\s\\S]*?)```/g, (m, lang, code) => {{
        return `<div class="code-snippet">
          <div class="code-header">
            <span>${{lang || 'code'}}</span>
            <button class="code-copy-btn" onclick="copySnippet(this)">Copy</button>
          </div>
          <pre class="code-content">${{code}}</pre>
        </div>`;
      }});
      // Bold
      s = s.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
      // Inline code
      s = s.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.06); padding:0.15rem 0.35rem; border-radius:4px; font-family:var(--font-mono); font-size:0.8rem;">$1</code>');
      return s.replace(/\\n/g, '<br>');
    }}

    function copySnippet(btn) {{
      const code = btn.closest('.code-snippet').querySelector('.code-content').textContent;
      navigator.clipboard.writeText(code);
      btn.textContent = 'Copied';
      setTimeout(() => btn.textContent = 'Copy', 2000);
    }}

    function escapeHtml(str) {{
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }}

    /* ========================================================= */
    /* REAL VS CODE & MONACO ENGINE + CUSTOM PROJECT MANAGEMENT  */
    /* ========================================================= */
    let monacoEditorInstance = null;
    let currentProjectRoot = 'e:/NEXUS';
    let currentOpenFile = 'sovereign_mesh/grid.py';
    let cachedFilesList = [];
    let recentProjectsList = ['e:/NEXUS'];

    async function openProjectModal() {{
      const m = document.getElementById('modal-project-picker');
      if (m) m.style.display = 'flex';
      const inp = document.getElementById('project-path-input');
      if (inp) inp.value = currentProjectRoot;
      await loadRecentProjects();
    }}

    function closeProjectModal() {{
      const m = document.getElementById('modal-project-picker');
      if (m) m.style.display = 'none';
    }}

    async function loadRecentProjects() {{
      const listDiv = document.getElementById('recent-projects-list');
      if (!listDiv) return;
      try {{
        const res = await fetch('/api/ide/projects');
        const data = await res.json();
        if (data.ok && data.projects) {{
          recentProjectsList = data.projects;
          listDiv.innerHTML = data.projects.map(p => `
            <div style="display:flex; justify-content:space-between; align-items:center; background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.4rem 0.65rem; cursor:pointer;" onclick="selectRecentProject('${{escapeHtml(String(p).replace(/\\\\/g, '/'))}}')">
              <span style="font-family:var(--font-mono); font-size:0.78rem; color:${{p === currentProjectRoot ? 'var(--accent)' : 'var(--text)'}};">
                ${{p === currentProjectRoot ? '● [MOUNTED] ' : ''}}${{escapeHtml(p)}}
              </span>
              <button class="account-btn" style="padding:0.2rem 0.5rem; font-size:0.7rem;">Mount</button>
            </div>
          `).join('');
        }}
      }} catch(err) {{
        console.error('Error fetching recent projects', err);
      }}
    }}

    async function selectRecentProject(path) {{
      closeProjectModal();
      await switchProject(path);
    }}

    async function submitOpenProject() {{
      const inp = document.getElementById('project-path-input');
      const targetPath = (inp ? inp.value.trim() : '');
      if (!targetPath) return alert('Please specify a directory path.');

      try {{
        const res = await fetch('/api/ide/projects/open', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ path: targetPath }})
        }});
        const data = await res.json();
        if (data.ok) {{
          closeProjectModal();
          await switchProject(data.project);
        }} else {{
          alert('Could not mount directory: ' + (data.error || 'Failed'));
        }}
      }} catch(err) {{
        alert('Request failed: ' + err.toString());
      }}
    }}

    async function submitCreateProject() {{
      const nameInp = document.getElementById('new-project-name');
      const tmplSel = document.getElementById('new-project-template');
      const name = (nameInp ? nameInp.value.trim() : '');
      const tmpl = (tmplSel ? tmplSel.value : 'python');
      if (!name) return alert('Please enter a repository name.');

      try {{
        const res = await fetch('/api/ide/projects/create', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ name: name, template: tmpl }})
        }});
        const data = await res.json();
        if (data.ok) {{
          closeProjectModal();
          alert(`Workspace '${{name}}' initialized at: ${{data.project}}`);
          if (nameInp) nameInp.value = '';
          await switchProject(data.project);
        }} else {{
          alert('Could not initialize project: ' + (data.error || 'Failed'));
        }}
      }} catch(err) {{
        alert('Request failed: ' + err.toString());
      }}
    }}

    async function switchProject(newPath) {{
      currentProjectRoot = newPath;
      const badge = document.getElementById('ide-project-badge');
      if (badge) {{
        badge.textContent = currentProjectRoot;
        badge.title = currentProjectRoot;
      }}
      logToIdeTerminal(`Workspace mounted: ${{currentProjectRoot}}`, '#3b82f6');
      await loadProjectFiles(currentProjectRoot);
    }}

    function initMonaco() {{
      const container = document.getElementById('monaco-editor-container');
      const fallback = document.getElementById('ide-fallback-editor');
      if (typeof require !== 'undefined') {{
        require.config({{ paths: {{ 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' }} }});
        require(['vs/editor/editor.main'], function() {{
          monacoEditorInstance = monaco.editor.create(container, {{
            value: '# Loading workspace file from ' + currentProjectRoot + '...',
            language: 'python',
            theme: 'vs-dark',
            automaticLayout: true,
            fontSize: 13,
            lineHeight: 20,
            minimap: {{ enabled: true }},
            scrollBeyondLastLine: false,
            wordWrap: 'on'
          }});

          monacoEditorInstance.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, function() {{
            saveCurrentFile();
          }});

          loadRealFile(currentOpenFile);
        }});
      }} else {{
        if (fallback) fallback.style.display = 'block';
        loadRealFile(currentOpenFile);
      }}
      loadProjectFiles();
    }}

    function getEditorCode() {{
      if (monacoEditorInstance) return monacoEditorInstance.getValue();
      const fb = document.getElementById('ide-fallback-editor');
      return fb ? fb.value : '';
    }}

    function setEditorCode(code, lang = 'python') {{
      if (monacoEditorInstance) {{
        monacoEditorInstance.setValue(code);
        const model = monacoEditorInstance.getModel();
        if (model && window.monaco && monaco.languages) {{
          monaco.editor.setModelLanguage(model, lang);
        }}
      }}
      const fb = document.getElementById('ide-fallback-editor');
      if (fb) fb.value = code;
    }}

    async function loadProjectFiles(projectPath) {{
      if (projectPath) currentProjectRoot = projectPath;
      const tree = document.getElementById('ide-file-tree');
      if (!tree) return;
      tree.innerHTML = `<div style="padding:0.75rem; color:var(--text-muted); font-size:0.76rem;">Indexing ${{currentProjectRoot}}...</div>`;

      try {{
        const res = await fetch('/api/ide/files?project=' + encodeURIComponent(currentProjectRoot));
        const data = await res.json();
        if (!data.ok || !data.files) {{
          tree.innerHTML = '<div style="padding:0.75rem; color:var(--danger); font-size:0.76rem;">Failed to index directory</div>';
          return;
        }}
        cachedFilesList = data.files;
        if (data.root) {{
          currentProjectRoot = data.root;
          const badge = document.getElementById('ide-project-badge');
          if (badge) {{ badge.textContent = currentProjectRoot; badge.title = currentProjectRoot; }}
        }}

        if (data.files.length === 0) {{
          tree.innerHTML = '<div style="padding:1rem; color:var(--text-muted); font-size:0.78rem; text-align:center;">Empty directory.<br><button class="account-btn" style="margin-top:0.5rem;" onclick="createNewProjectFile()">+ New File</button></div>';
          return;
        }}

        tree.innerHTML = data.files.map(f => {{
          if (f.is_dir) {{
            return `<div style="padding:0.25rem 0.6rem; font-weight:600; font-family:var(--font-mono); color:var(--text-muted); font-size:0.74rem;">/${{f.path}}</div>`;
          }}
          const tag = f.ext === 'py' ? 'PY' : (f.ext === 'json' ? 'JSN' : (f.ext === 'md' ? 'MD' : 'FILE'));
          const isActive = (f.path === currentOpenFile);
          return `
            <div class="file-node ${{isActive ? 'active' : ''}}" onclick="switchIdeFile('${{f.path}}')">
              <span style="font-family:var(--font-mono); font-size:0.65rem; color:var(--text-muted); min-width:26px;">[${{tag}}]</span>
              <span style="overflow:hidden; text-overflow:ellipsis; font-family:var(--font-mono); font-size:0.75rem;" title="${{f.path}}">${{f.path}}</span>
            </div>
          `;
        }}).join('');

        const fileExists = data.files.some(f => !f.is_dir && f.path === currentOpenFile);
        if (!fileExists) {{
          const firstFile = data.files.find(f => !f.is_dir);
          if (firstFile) switchIdeFile(firstFile.path);
        }}
      }} catch(err) {{
        tree.innerHTML = `<div style="padding:0.75rem; color:var(--danger); font-size:0.76rem;">Error: ${{err.toString()}}</div>`;
      }}
    }}

    async function switchIdeFile(relPath) {{
      currentOpenFile = relPath;
      document.getElementById('current-tab-filename').textContent = relPath;
      document.querySelectorAll('.file-node').forEach(el => {{
        el.classList.toggle('active', el.textContent.includes(relPath));
      }});
      await loadRealFile(relPath);
    }}

    async function loadRealFile(relPath) {{
      try {{
        const res = await fetch('/api/ide/file?path=' + encodeURIComponent(relPath) + '&project=' + encodeURIComponent(currentProjectRoot));
        const data = await res.json();
        if (data.ok) {{
          let lang = 'plaintext';
          if (relPath.endsWith('.py')) lang = 'python';
          else if (relPath.endsWith('.json')) lang = 'json';
          else if (relPath.endsWith('.html')) lang = 'html';
          else if (relPath.endsWith('.js')) lang = 'javascript';
          else if (relPath.endsWith('.md')) lang = 'markdown';
          setEditorCode(data.content, lang);
          logToIdeTerminal(`Loaded buffer: ${{relPath}} (${{data.content.length}} bytes)`, '#60a5fa');
        }} else {{
          logToIdeTerminal(`Read error on ${{relPath}}: ${{data.error}}`, '#ef4444');
        }}
      }} catch(err) {{
        logToIdeTerminal(`Read exception: ${{err.toString()}}`, '#ef4444');
      }}
    }}

    async function saveCurrentFile() {{
      const code = getEditorCode();
      logToIdeTerminal(`Flushing buffer '${{currentOpenFile}}' to disk...`, '#60a5fa');

      try {{
        const res = await fetch('/api/ide/file/save', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ path: currentOpenFile, content: code, project: currentProjectRoot }})
        }});
        const data = await res.json();
        if (data.ok) {{
          logToIdeTerminal(`[OK] Saved '${{currentOpenFile}}' (${{code.length}} bytes)`, '#10b981');
        }} else {{
          logToIdeTerminal(`[ERR] Save failed: ${{data.error}}`, '#ef4444');
        }}
      }} catch(err) {{
        logToIdeTerminal(`Save error: ${{err.toString()}}`, '#ef4444');
      }}
    }}

    async function launchDesktopVsCode() {{
      logToIdeTerminal(`Spawning native Visual Studio Code process for ${{currentProjectRoot}}...`, '#60a5fa');
      try {{
        const res = await fetch('/api/ide/launch_vscode', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ project: currentProjectRoot }})
        }});
        const data = await res.json();
        if (data.ok) {{
          logToIdeTerminal(`[OK] Native VS Code launched for ${{data.project}}.`, '#10b981');
          alert(`Visual Studio Code Desktop launched with workspace: ${{data.project}}`);
        }} else {{
          logToIdeTerminal(`[ERR] VS Code launch failed: ${{data.error}}`, '#ef4444');
        }}
      }} catch(err) {{
        logToIdeTerminal(`Launch exception: ${{err.toString()}}`, '#ef4444');
      }}
    }}

    async function createNewProjectFile() {{
      const fname = prompt(`Enter relative file path in ${{currentProjectRoot}} (e.g. app.py or tests/test_core.py):`);
      if (!fname) return;
      currentOpenFile = fname;
      setEditorCode(`# Module: ${{fname}}\\n\\n`, 'python');
      document.getElementById('current-tab-filename').textContent = fname;
      await saveCurrentFile();
      await loadProjectFiles(currentProjectRoot);
    }}

    function focusAgentMission() {{
      document.getElementById('agent-instruction-input').focus();
    }}

    async function runAgentAutonomousMission() {{
      const inp = document.getElementById('agent-instruction-input');
      const instruction = inp.value.trim();
      if (!instruction) return alert('Please specify a task instruction for the Agent Controller.');

      const feed = document.getElementById('agent-timeline-feed');
      const timeStr = new Date().toLocaleTimeString();

      const startCard = document.createElement('div');
      startCard.className = 'agent-step-card';
      startCard.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom:0.25rem;">
          <strong style="color:var(--accent); font-size:0.75rem;">DISPATCHED</strong>
          <span style="font-size:0.7rem; font-family:var(--font-mono); color:var(--text-muted);">${{timeStr}}</span>
        </div>
        <p style="font-size:0.78rem; color:var(--text);">${{escapeHtml(instruction)}}</p>
        <div style="font-size:0.7rem; font-family:var(--font-mono); color:var(--text-muted); margin-top:0.35rem;">
          ROOT: <code>${{currentProjectRoot}}</code> | TARGET: <code>${{currentOpenFile}}</code>
        </div>
      `;
      feed.prepend(startCard);

      logToIdeTerminal(`[AGENT] Executing task in '${{currentProjectRoot}}': "${{instruction}}"`, '#93c5fd');

      try {{
        const res = await fetch('/api/ide/agent_control', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            instruction: instruction,
            target_file: currentOpenFile,
            project: currentProjectRoot,
            account_key: activeAccountKey
          }})
        }});
        const data = await res.json();

        if (data.insufficient_credits) {{
          logToIdeTerminal(`[ERR] ${{data.error}}`, '#ef4444');
          return alert(data.error);
        }}

        if (data.ok) {{
          if (data.file_saved && data.code) {{
            setEditorCode(data.code, 'python');
          }}

          const resCard = document.createElement('div');
          resCard.className = 'agent-step-card';
          resCard.innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom:0.25rem;">
              <strong style="color:var(--success); font-size:0.75rem;">VERIFIED &amp; COMMITTED</strong>
              <span class="credits-pill" style="font-size:0.68rem;">${{data.elapsed_ms}}ms</span>
            </div>
            <p style="font-size:0.76rem; color:var(--text-muted);">${{escapeHtml(data.plan_note)}}</p>
            <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text); margin:0.35rem 0;">
              FILE: <strong>${{data.target_file}}</strong>
            </div>
            ${{data.test_output ? `<pre style="background:#090a0f; border:1px solid var(--border); padding:0.4rem; border-radius:4px; font-family:var(--font-mono); font-size:0.7rem; color:var(--text-muted); max-height:80px; overflow-y:auto;">${{escapeHtml(data.test_output)}}</pre>` : ''}}
            <div style="font-size:0.66rem; font-family:var(--font-mono); color:var(--text-muted); margin-top:0.3rem;">
              BLOCK: <code>${{data.ledger_block}}</code>
            </div>
          `;
          feed.prepend(resCard);

          logToIdeTerminal(`[OK] Task completed in ${{data.elapsed_ms}}ms. Block: ${{data.ledger_block}}`, '#10b981');
          if (data.test_output) logToIdeTerminal(`Verification: ${{data.test_output}}`, '#60a5fa');
          loadProjectFiles(currentProjectRoot);
        }} else {{
          logToIdeTerminal(`[ERR] Task failed: ${{data.error || 'Unknown error'}}`, '#ef4444');
        }}
      }} catch(err) {{
        logToIdeTerminal(`Agent execution exception: ${{err.toString()}}`, '#ef4444');
      }}
    }}

    async function ideRunCode() {{
      const code = getEditorCode();
      logToIdeTerminal(`Executing '${{currentOpenFile}}' in ${{currentProjectRoot}}...`, '#60a5fa');

      try {{
        const res = await fetch('/api/ide/execute', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ code: code, project: currentProjectRoot, account_key: activeAccountKey }})
        }});
        const data = await res.json();
        if (data.insufficient_credits) return logToIdeTerminal(`[ERR] ${{data.error}}`, '#ef4444');
        if (data.ok) {{
          logToIdeTerminal(data.stdout || '(Process exited with code 0)', '#10b981');
        }} else {{
          logToIdeTerminal(data.stderr || 'Process failed', '#ef4444');
        }}
      }} catch(err) {{
        logToIdeTerminal('Execution error: ' + err.toString(), '#ef4444');
      }}
    }}

    async function ideRunAutoTests() {{
      const code = getEditorCode();
      logToIdeTerminal('Synthesizing unit tests and running verification suite...', '#93c5fd');

      try {{
        const res = await fetch('/api/ide/test', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ code: code, project: currentProjectRoot, account_key: activeAccountKey }})
        }});
        const data = await res.json();
        if (data.ok) {{
          logToIdeTerminal('[PASS] Verification Suite:\\n' + (data.stdout || 'OK'), '#10b981');
        }} else {{
          logToIdeTerminal('[FAIL] Diagnostics:\\n' + (data.stderr || data.stdout), '#ef4444');
        }}
      }} catch(err) {{
        logToIdeTerminal('Verification error: ' + err.toString(), '#ef4444');
      }}
    }}

    async function ideAutoFixLoop() {{
      const code = getEditorCode();
      logToIdeTerminal('Initiating automated static analysis and patch synthesis...', '#f59e0b');

      try {{
        const res = await fetch('/api/ide/generate', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ prompt: 'Fix errors and ensure robust execution', code: code, mode: 'debug_fix', account_key: activeAccountKey }})
        }});
        const data = await res.json();
        if (data.code) {{
          setEditorCode(data.code, 'python');
          logToIdeTerminal(`[OK] Patch applied (${{data.status}})`, '#10b981');
        }}
      }} catch(err) {{
        logToIdeTerminal('Patch error: ' + err.toString(), '#ef4444');
      }}
    }}

    function logToIdeTerminal(text, color='#d1d5db') {{
      const scr = document.getElementById('ide-terminal-screen');
      if (!scr) return;
      const time = new Date().toLocaleTimeString();
      scr.innerHTML += `\\n<span style="color:${{color}}">[${{time}}] ${{escapeHtml(text)}}</span>`;
      scr.scrollTop = scr.scrollHeight;
    }}

    function clearIdeTerminal() {{
      const scr = document.getElementById('ide-terminal-screen');
      if (scr) scr.innerHTML = '<span style="color:var(--text-muted);">[Console Buffer Cleared]</span>';
    }}

    function switchTerminalTab(tab) {{
      document.querySelectorAll('.terminal-tab-item').forEach(t => t.classList.remove('active'));
      if (typeof event !== 'undefined' && event && event.target) {{
        event.target.classList.add('active');
      }}
    }}

    /* ========================================================= */
    /* PHYSICAL CONTROL FUNCTIONS                                */
    /* ========================================================= */
    async function triggerHardwareEStop() {{
      if (!confirm('CONFIRM HARDWARE INTERLOCK: Immediately halt all connected motion & thermal endpoints?')) return;
      try {{
        const res = await fetch('/api/machine/command', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ machine_id: 'all', command: 'E-STOP' }})
        }});
        alert('EMERGENCY STOP ENGAGED. All hardware interfaces halted.');
      }} catch(err) {{
        alert('E-Stop interrupt transmitted.');
      }}
    }}

    async function connectPhysicalMachine() {{
      const type = document.getElementById('mach-type').value;
      const name = document.getElementById('mach-name').value.trim() || 'Hardware Endpoint';
      const target = document.getElementById('mach-target').value.trim() || 'COM3';
      const baud = document.getElementById('mach-baud').value.trim() || '115200';

      try {{
        const res = await fetch('/api/machine/connect', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ type: type, name: name, target: target, baud: baud }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`Hardware endpoint '${{name}}' bound to mesh telemetry bus.`);
          document.getElementById('mach-name').value = '';
        }}
      }} catch(err) {{
        alert('Interface binding error: ' + err.toString());
      }}
    }}

    async function sendMachineCommand(machineId, cmd) {{
      try {{
        const res = await fetch('/api/machine/command', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ machine_id: machineId, command: cmd }})
        }});
        const data = await res.json();
        alert(`Frame '${{cmd}}' dispatched. Bus response: ${{data.status || 'ACK'}}`);
      }} catch(err) {{
        alert('Bus error: ' + err.toString());
      }}
    }}

    function sendJogCommand(machId, axis) {{
      sendMachineCommand(machId, 'JOG ' + axis);
    }}

    function sendRawMachineCmd(machId, inputId) {{
      const val = document.getElementById(inputId).value.trim();
      if (!val) return;
      sendMachineCommand(machId, val);
      document.getElementById(inputId).value = '';
    }}

    /* ========================================================= */
    /* P2P CREDITS MARKET FUNCTIONS                              */
    /* ========================================================= */
    function switchP2PSub(sub) {{
      document.querySelectorAll('.p2p-tab-btn').forEach(b => b.classList.remove('active'));
      const btn = document.getElementById('btn-p2p-' + sub);
      if (btn) btn.classList.add('active');

      document.getElementById('p2p-view-buy').style.display = (sub === 'buy') ? 'block' : 'none';
      const boView = document.getElementById('p2p-view-buy-order');
      if (boView) boView.style.display = (sub === 'buy-order') ? 'block' : 'none';
      document.getElementById('p2p-view-sell').style.display = (sub === 'sell') ? 'block' : 'none';
      const lbView = document.getElementById('p2p-view-leaderboard');
      if (lbView) lbView.style.display = (sub === 'leaderboard') ? 'block' : 'none';
      const bmView = document.getElementById('p2p-view-brain');
      if (bmView) bmView.style.display = (sub === 'brain') ? 'block' : 'none';
      document.getElementById('p2p-view-orders').style.display = (sub === 'orders') ? 'block' : 'none';
      document.getElementById('p2p-view-transfer').style.display = (sub === 'transfer') ? 'block' : 'none';

      if (sub === 'buy') loadP2POffers();
      if (sub === 'leaderboard') loadP2PLeaderboard();
      if (sub === 'brain') loadBrainMatrixStatus();
      if (sub === 'orders') loadMyTrades();
    }}

    function updateHalvingBadge(lbData) {{
      if (!lbData || !lbData.halving) return;
      const h = lbData.halving;
      const badge = document.getElementById('p2p-halving-badge');
      if (badge) {{
        badge.textContent = `${{h.era}} (${{h.active_workers}} Nodes) • Uptime: ${{h.idle_credits_per_hour_standard}}–${{h.idle_credits_per_hour_high_core}} UMAIS/hr • Task: +${{h.active_task_reward_credits}} UMAIS`;
      }}
    }}

    async function loadP2PLeaderboard() {{
      try {{
        const res = await fetch('/api/p2p/leaderboard?limit=10');
        const data = await res.json();
        updateHalvingBadge(data);
        const tbody = document.getElementById('p2p-leaderboard-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        const list = data.leaderboard || [];
        if (list.length === 0) {{
          tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:1.75rem;">No active edge worker nodes registered in current epoch.</td></tr>';
          return;
        }}
        list.forEach(m => {{
          const tr = document.createElement('tr');
          const rankLabel = `#${{m.rank}}`;
          const hwSpec = m.hardware_spec || `${{m.cores || 4}}-Core Node`;
          const brainShard = m.brain_shard || 'CODE_DEBUG_EXEC';
          const flexText = `Rank #${{m.rank}} on SUP Agentic Mesh (${{hwSpec}} • Shard: ${{brainShard}}) — ${{m.uptime_hours}}h uptime, ${{m.tasks_verified}} verified tasks, ${{m.credits}} UMAIS`;
          const eligBadge = m.eligible_for_sunday_buyback
            ? `<span class="tech-pill" style="color:var(--success); border-color:rgba(16,185,129,0.35);">QUALIFIED (PKR 500 FLOOR)</span>`
            : `<span style="color:var(--text-muted); font-size:0.74rem; font-family:var(--font-mono);">ACTIVE</span>`;
          tr.innerHTML = `
            <td style="font-family:var(--font-mono); font-weight:700;">${{rankLabel}}</td>
            <td><code style="font-family:var(--font-mono);">${{escapeHtml(m.worker_id)}}</code></td>
            <td>
              <div style="display:flex; flex-direction:column; gap:0.2rem;">
                <span style="font-size:0.76rem; font-weight:600; color:var(--text);">${{escapeHtml(hwSpec)}}</span>
                <span style="font-size:0.7rem; font-family:var(--font-mono); color:var(--accent);">SHARD: ${{escapeHtml(brainShard)}}</span>
              </div>
            </td>
            <td style="font-family:var(--font-mono);"><strong>${{m.tasks_verified}}</strong></td>
            <td style="font-family:var(--font-mono);">${{m.uptime_hours}}h (${{m.uptime_minutes_verified}}m)</td>
            <td style="font-family:var(--font-mono);"><strong style="color:var(--accent);">${{m.competition_score}}</strong></td>
            <td style="font-family:var(--font-mono);"><strong style="color:var(--success);">${{m.credits}} UMAIS</strong></td>
            <td>
              <div style="display:flex; gap:0.4rem; align-items:center; flex-wrap:wrap;">
                ${{eligBadge}}
                <button class="account-btn" style="font-size:0.7rem; padding:0.2rem 0.5rem;" onclick="flexMinerRig('${{escapeHtml(flexText)}}')">Copy Proof</button>
              </div>
            </td>
          `;
          tbody.appendChild(tr);
        }});
      }} catch(err) {{
        console.error('Error loading leaderboard', err);
      }}
    }}

    async function loadBrainMatrixStatus() {{
      try {{
        const res = await fetch('/api/brain/status');
        const data = await res.json();
        if (!data || !data.ok) return;

        const eraBadge = document.getElementById('bm-era-badge');
        if (eraBadge) eraBadge.textContent = `${{data.era}} • ${{data.state_of_brain}}`;

        const surv = data.survivability || {{}};
        const survBadge = document.getElementById('bm-survivability-badge');
        if (survBadge) {{
          survBadge.textContent = `${{surv.survivability_pct !== undefined ? surv.survivability_pct : 100}}% P2P Shard Redundancy`;
        }}

        const autEl = document.getElementById('bm-autonomy-val');
        if (autEl) autEl.textContent = `${{data.local_brain_autonomy_pct || 20}}%`;
        const depEl = document.getElementById('bm-api-dep-val');
        if (depEl) depEl.textContent = `${{data.api_dependency_pct !== undefined ? data.api_dependency_pct : 80}}%`;
        const smpEl = document.getElementById('bm-samples-val');
        if (smpEl) smpEl.textContent = `${{data.total_knowledge_samples || 0}} (${{data.synthetic_samples_generated || 0}} Synth)`;
        const delEl = document.getElementById('bm-deltas-val');
        if (delEl) delEl.textContent = `${{data.p2p_weight_deltas_synced || 0}} Packets • ${{data.fedavg_merges_completed || 0}} FedAvg`;

        const stCheckpoints = {{}};
        (data.safetensors_checkpoints || []).forEach(c => {{
          if (c && c.shard) stCheckpoints[c.shard] = c;
        }});

        const shardsTbody = document.getElementById('bm-shards-tbody');
        if (shardsTbody) {{
          const shardsMap = surv.shards || {{}};
          const shardKeys = Object.keys(shardsMap);
          if (shardKeys.length === 0) {{
            shardsTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:1rem;">No neural shards initialized.</td></tr>';
          }} else {{
            shardsTbody.innerHTML = shardKeys.map(sid => {{
              const s = shardsMap[sid];
              const pHolders = (s.primary_holders || []).join(', ') || 'Auto-Routing';
              const rHolders = (s.replica_holders || []).join(', ') || 'sovereign-hub-vault';
              const st = stCheckpoints[sid] || {{}};
              const stHash = st.sha256 ? st.sha256.slice(0, 12) + '...' : 'INIT';
              const stFile = st.file || `${{sid}}_lora_adapter.safetensors`;
              return `
                <tr>
                  <td>
                    <code style="color:var(--accent); font-family:var(--font-mono); font-weight:600;">${{escapeHtml(sid)}}</code>
                    <div style="font-size:0.68rem; font-family:var(--font-mono); color:var(--success); margin-top:2px;">
                      <a href="/api/brain/safetensors?shard=${{encodeURIComponent(sid)}}&raw=1" style="color:var(--success); text-decoration:none;" title="Download binary HuggingFace .safetensors checkpoint">⬇ ${{escapeHtml(stFile)}} (${{stHash}})</a>
                    </div>
                  </td>
                  <td>
                    <div><strong>${{escapeHtml(s.title || sid)}}</strong></div>
                    <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted);">Base: ${{escapeHtml(s.base_model || '')}} • F32 LoRA [8x32]</div>
                  </td>
                  <td style="font-size:0.76rem; color:var(--text-muted);">${{escapeHtml(s.target_hardware || '')}}</td>
                  <td><span class="credits-pill" style="font-size:0.72rem;">${{escapeHtml(pHolders)}}</span></td>
                  <td style="font-size:0.74rem; font-family:var(--font-mono); color:var(--text-muted);">${{escapeHtml(rHolders)}}</td>
                  <td><span class="tech-pill" style="color:var(--success); border-color:rgba(16,185,129,0.35);">${{escapeHtml(s.status || 'REDUNDANT')}} (${{s.total_copies || 1}}x)</span></td>
                </tr>
              `;
            }}).join('');
          }}
        }}

        const erasTbody = document.getElementById('bm-eras-tbody');
        if (erasTbody) {{
          const timeline = data.era_timeline || [];
          erasTbody.innerHTML = timeline.map(e => {{
            const isCurr = (data.era && data.era.startsWith(e.era.split(' ')[0] + ' ' + e.era.split(' ')[1]));
            const statusPill = isCurr
              ? `<span class="tech-pill" style="color:var(--accent); border-color:rgba(59,130,246,0.45);">● ACTIVE PHASE</span>`
              : `<span style="color:var(--text-muted); font-size:0.74rem; font-family:var(--font-mono);">SCHEDULED</span>`;
            return `
              <tr style="${{isCurr ? 'background:rgba(59,130,246,0.05);' : ''}}">
                <td><strong>${{escapeHtml(e.era)}}</strong></td>
                <td style="font-family:var(--font-mono);"><strong style="color:var(--warning);">${{escapeHtml(e.api_dependency)}}</strong></td>
                <td><strong style="color:var(--text);">${{escapeHtml(e.state)}}</strong></td>
                <td style="font-size:0.78rem; color:var(--text-muted);">${{escapeHtml(e.mechanism)}}</td>
                <td>${{statusPill}}</td>
              </tr>
            `;
          }}).join('');
        }}
      }} catch(err) {{
        console.error('Error loading Brain Matrix status', err);
      }}
    }}

    async function triggerBrainSelfPlay() {{
      const topic = prompt(
        'Run Self-Play & Contradiction-Forcing Distillation\\n\\nSpecify technical domain to synthesize verified training trajectories and replicate weight deltas:',
        'Distributed Byzantine Consensus & Zero-API Neural Routing'
      );
      if (!topic) return;
      try {{
        const res = await fetch('/api/brain/self_play', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ topic: topic, num_variations: 4 }})
        }});
        const data = await res.json();
        if (data.ok) {{
          const pkt = data.weight_delta_packet || {{}};
          alert(
            `Self-Play & LoRA Backprop Distillation Completed\\n\\n` +
            `• Target Shard: ${{data.domain_shard}}\\n` +
            `• Trajectories Distilled: +${{data.synthetic_variations_generated}}\\n` +
            `• LoRA MSE Loss: ${{pkt.initial_loss}} → ${{pkt.final_loss}} (Grad L2: ${{pkt.gradient_l2_norm}})\\n` +
            `• Binary Checkpoint: ${{pkt.safetensors_file}} (${{(pkt.safetensors_sha256 || '').slice(0, 14)}}...)\\n` +
            `• Replica Nodes: ${{(pkt.holder_worker_ids || []).join(', ')}}`
          );
          loadBrainMatrixStatus();
        }} else {{
          alert('Distillation error: ' + (data.error || 'Failed'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function triggerBrainP2PSync() {{
      const shard = prompt(
        'Synchronize P2P Weight Delta Ledger & FedAvg .safetensors\\n\\nSpecify target shard (MATH_PROOF_LOGIC, CODE_DEBUG_EXEC, SECURITY_AUDIT_REDTEAM, or DATA_MEMORY_SYNTHESIS):',
        'CODE_DEBUG_EXEC'
      );
      if (!shard) return;
      try {{
        const res = await fetch('/api/brain/sync', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ domain_shard: shard.trim().toUpperCase(), synthetic_samples_added: 4 }})
        }});
        const data = await res.json();
        if (data.ok) {{
          const pkt = data.delta_packet || {{}};
          const surv = data.survivability || {{}};
          alert(
            `P2P Weight Delta & FedAvg .safetensors Merged\\n\\n` +
            `• Packet ID: ${{pkt.delta_id}} (${{pkt.domain_shard}})\\n` +
            `• Binary File: ${{pkt.safetensors_file}} (SHA-256: ${{(pkt.safetensors_sha256 || pkt.sha256_anchor || '').slice(0, 16)}}...)\\n` +
            `• Backprop Loss: ${{pkt.initial_loss}} → ${{pkt.final_loss}} (Grad L2: ${{pkt.gradient_l2_norm}})\\n` +
            `• Replica Holders: ${{(pkt.holder_worker_ids || []).join(', ') }}\\n` +
            `• Shard Redundancy: ${{surv.survivability_pct || 100}}%`
          );
          loadBrainMatrixStatus();
        }} else {{
          alert('Sync error: ' + (data.error || 'Failed'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    function flexMinerRig(shareText) {{
      navigator.clipboard.writeText(shareText);
      alert('Node telemetry proof copied to clipboard:\\n\\n' + shareText);
    }}

    async function executeOwnerTop3Buyback() {{
      const acc = activeAccountKey || prompt('Enter Treasury Authority Account Key (owner-master):', '');
      if (!acc) return;
      if (!confirm('Execute Weekly Top 3 Node Operators Treasury Floor Settlement (PKR 500 each)?')) return;
      try {{
        const res = await fetch('/api/p2p/buyback', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ account_key: acc, reward_pkr_each: 500, credits_bought_each: 100 }})
        }});
        const data = await res.json();
        if (data.ok) {{
          const summary = (data.winners || []).map(w => `#${{w.rank}} ${{w.worker_id}}: PKR ${{w.reward_pkr}} (${{w.credits_bought_back}} CR settled)`).join('\\n');
          alert(`Treasury Floor Settlement Executed\\nTotal Disbursed: PKR ${{data.total_pkr_paid}}\\n\\nSettled Operators:\\n${{summary}}`);
          loadP2PLeaderboard();
        }} else {{
          alert('Settlement rejected: ' + (data.error || 'Unauthorized'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function loadP2POffers() {{
      try {{
        const res = await fetch('/api/p2p/orders?status=OPEN');
        const data = await res.json();
        if (data.leaderboard_data) updateHalvingBadge(data.leaderboard_data);

        // 1. Render Sell Offers (Sellers offering credits)
        const tbody = document.getElementById('p2p-offers-tbody');
        tbody.innerHTML = '';
        const sellOrders = data.sell_orders || (data.orders || []).filter(o => (o.order_type || 'SELL') === 'SELL');

        if (sellOrders.length === 0) {{
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:1.5rem;">No open ask offers on the orderbook. Select "Post Bid (Buy)" to publish a liquidity request or "Post Ask (Sell)" to list UMAIS credits.</td></tr>';
        }} else {{
          sellOrders.forEach(o => {{
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td><code style="font-family:var(--font-mono);">${{escapeHtml(o.order_id)}}</code></td>
              <td><strong style="font-family:var(--font-mono);">${{escapeHtml(o.seller_id)}}</strong></td>
              <td style="font-family:var(--font-mono);"><strong style="color:var(--success);">${{o.amount_credits}} UMAIS</strong></td>
              <td style="font-family:var(--font-mono);"><strong>${{escapeHtml(o.currency)}} ${{o.price_fiat}}</strong></td>
              <td style="color:var(--text-muted); font-family:var(--font-mono);">${{escapeHtml(o.currency)}} ${{o.price_per_credit}}/UMAIS</td>
              <td><span class="credits-pill" style="font-size:0.72rem;">${{escapeHtml(o.payment_method)}}</span></td>
              <td>
                <button class="account-btn" style="background:#2563eb; color:white; border-color:#3b82f6;"
                  onclick="buyP2POffer('${{escapeHtml(o.order_id)}}', ${{o.price_fiat}}, '${{escapeHtml(o.currency)}}', '${{escapeHtml(o.payment_method)}}', ${{o.amount_credits}})">
                  Execute Buy
                </button>
              </td>
            `;
            tbody.appendChild(tr);
          }});
        }}

        // 2. Render Buy Orders (Buyers looking for credits)
        const buyTbody = document.getElementById('p2p-buy-orders-tbody');
        if (buyTbody) {{
          buyTbody.innerHTML = '';
          const buyOrders = data.buy_orders || (data.orders || []).filter(o => o.order_type === 'BUY');
          if (buyOrders.length === 0) {{
            buyTbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:1.5rem;">No open bid orders. Click "+ New Bid Order" above to publish a bid.</td></tr>';
          }} else {{
            buyOrders.forEach(o => {{
              const tr = document.createElement('tr');
              tr.innerHTML = `
                <td><code style="font-family:var(--font-mono);">${{escapeHtml(o.order_id)}}</code></td>
                <td><strong style="font-family:var(--font-mono);">${{escapeHtml(o.buyer_id)}}</strong></td>
                <td style="font-family:var(--font-mono);"><strong style="color:var(--accent);">${{o.amount_credits}} UMAIS</strong></td>
                <td style="font-family:var(--font-mono);"><strong style="color:var(--success);">${{escapeHtml(o.currency)}} ${{o.price_fiat}}</strong></td>
                <td style="color:var(--text-muted); font-family:var(--font-mono);">${{escapeHtml(o.currency)}} ${{o.price_per_credit}}/UMAIS</td>
                <td><span class="credits-pill" style="font-size:0.72rem;">${{escapeHtml(o.payment_method)}}</span></td>
                <td>
                  <button class="account-btn"
                    onclick="sellToBuyerOrder('${{escapeHtml(o.order_id)}}', ${{o.price_fiat}}, '${{escapeHtml(o.currency)}}', ${{o.amount_credits}}, '${{escapeHtml(o.buyer_id)}}')">
                    Fill Bid (Lock Escrow)
                  </button>
                </td>
              `;
              buyTbody.appendChild(tr);
            }});
          }}
        }}
      }} catch(err) {{
        console.error('Error loading P2P offers', err);
      }}
    }}

    async function submitP2PBuyOrder() {{
      const bid = document.getElementById('buyorder-buyer-id').value.trim() || activeAccountKey;
      const amt = parseInt(document.getElementById('buyorder-amount').value || '0');
      const price = parseFloat(document.getElementById('buyorder-price').value || '0');
      const method = document.getElementById('buyorder-method').value.trim() || 'EasyPaisa / JazzCash';

      if (!bid || amt <= 0 || price <= 0) {{
        return alert('Please provide Buyer Account Key, Credit Volume (> 0), and Bid Price (> 0).');
      }}

      try {{
        const res = await fetch('/api/p2p/buy_order', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ buyer_id: bid, amount: amt, price: price, currency: 'PKR', payment_method: method }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`Bid Order Published\\nContract ID: ${{data.order_id}}\\nVolume: ${{amt}} CR @ PKR ${{price}}\\n\\nNode operators can now fill your bid by locking credits in protocol escrow.`);
          switchP2PSub('buy');
        }} else {{
          alert('Order rejected: ' + (data.error || 'Failed to publish bid'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function sellToBuyerOrder(orderId, price, currency, credits, buyerId) {{
      const sellerId = prompt(`Filling Bid (${{credits}} CR for ${{currency}} ${{price}}) from '${{buyerId}}'.\\n\\nEnter your Operator Account Key:`, activeAccountKey || '');
      if (!sellerId) return;
      const paymentDetails = prompt(`Enter beneficiary settlement account (EasyPaisa / JazzCash / Raast) for '${{buyerId}}' (${{currency}} ${{price}}):`, 'EasyPaisa: 0300-1234567');
      if (!paymentDetails) return;

      try {{
        const res = await fetch('/api/p2p/accept_buy_order', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ order_id: orderId, seller_id: sellerId, payment_method: paymentDetails }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`Escrow Locked (${{credits}} CR)\\n\\nCounterparty '${{buyerId}}' has been notified to settle ${{currency}} ${{price}} via ${{paymentDetails}}.\\nUpon TID verification, release escrow under "Escrow Settlements".`);
          if (activeAccountKey) verifyAndDisplayAccount(activeAccountKey);
          document.getElementById('p2p-check-id').value = sellerId;
          switchP2PSub('orders');
        }} else {{
          alert('Failed to fill bid: ' + (data.error || 'Rejected'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function submitPaymentForBuyOrder(orderId, buyerId, price, currency, sellerPaymentMethod) {{
      const tid = prompt(
        `Counterparty credits are locked in Escrow for Contract ${{orderId}}.\\n\\n` +
        `Remit ${{currency}} ${{price}} to beneficiary account:\\n` +
        `${{sellerPaymentMethod}}\\n\\n` +
        `Enter Settlement Reference / Transaction ID (TID):`
      );
      if (!tid) return;
      try {{
        const res = await fetch('/api/p2p/pay', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ order_id: orderId, buyer_id: buyerId, payment_reference: tid }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`Settlement Reference Recorded (TID: ${{tid}}).\\nAwaiting counterparty verification and escrow release.`);
          loadMyTrades();
        }} else {{
          alert('Failed to record settlement reference: ' + (data.error || 'Rejected'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function submitP2PSellOrder() {{
      const wid = document.getElementById('sell-worker-id').value.trim() || activeAccountKey;
      const amt = parseInt(document.getElementById('sell-amount').value || '0');
      const price = parseFloat(document.getElementById('sell-price').value || '0');
      const method = document.getElementById('sell-method').value.trim();

      if (!wid || amt <= 0 || price <= 0 || !method) {{
        return alert('Please complete all fields (Operator Key, Credit Volume > 0, Ask Price > 0, and Beneficiary Account).');
      }}

      try {{
        const res = await fetch('/api/p2p/sell', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ worker_id: wid, amount: amt, price: price, currency: 'PKR', payment_method: method }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`Ask Offer Published & Escrow Locked\\nContract ID: ${{data.order_id}}\\nVolume: ${{amt}} CR held in protocol escrow.`);
          document.getElementById('sell-amount').value = '';
          document.getElementById('sell-price').value = '';
          switchP2PSub('buy');
        }} else {{
          alert('Offer rejected: ' + (data.error || 'Failed'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function buyP2POffer(orderId, price, currency, method, credits) {{
      const buyerId = prompt(`Acquiring ${{credits}} CR for ${{currency}} ${{price}}.\\n\\nEnter your Buyer Account Key:`, activeAccountKey || 'buyer-node');
      if (!buyerId) return;

      try {{
        const res = await fetch('/api/p2p/buy', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ order_id: orderId, buyer_id: buyerId }})
        }});
        const data = await res.json();
        if (!data.ok) return alert('Error: ' + (data.error || 'Failed'));

        const tid = prompt(
          `Contract Reserved in Protocol Escrow\\n\\n` +
          `Remit ${{currency}} ${{price}} to beneficiary account:\\n` +
          `${{method}}\\n\\n` +
          `Enter Settlement Reference / Transaction ID (TID):`
        );

        if (tid) {{
          const payRes = await fetch('/api/p2p/pay', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ order_id: orderId, buyer_id: buyerId, payment_reference: tid }})
          }});
          alert(`Settlement Reference Recorded (TID: ${{tid}}).\\nCounterparty will verify and release escrowed credits.`);
          switchP2PSub('orders');
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function loadMyTrades() {{
      const wid = document.getElementById('p2p-check-id').value.trim() || activeAccountKey;
      if (!wid) return alert('Please enter your Account Key.');

      try {{
        const res = await fetch('/api/p2p/my_trades?worker_id=' + encodeURIComponent(wid));
        const data = await res.json();
        const trades = data.trades || {{ selling: [], buying: [] }};

        // Render Sales
        const salesT = document.getElementById('my-sales-tbody');
        salesT.innerHTML = '';
        if (!trades.selling || trades.selling.length === 0) {{
          salesT.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted)">No outbound ask contracts found.</td></tr>';
        }} else {{
          trades.selling.forEach(o => {{
            const tr = document.createElement('tr');
            let action = '';
            if (o.status === 'PAYMENT_SUBMITTED' || o.status === 'IN_ESCROW') {{
              action = `<div style="display:flex; gap:0.35rem; flex-wrap:wrap;">` +
                `<button class="account-btn" style="background:#10b981; color:#000; border-color:#10b981; font-weight:600;" onclick="releaseEscrow('${{o.order_id}}', '${{wid}}')">Release Escrow</button>` +
                `<button class="account-btn" style="color:var(--danger); border-color:rgba(239,68,68,0.4);" onclick="raiseDisputePrompt('${{o.order_id}}', '${{wid}}')">Flag Dispute</button>` +
                `</div>`;
            }} else if (o.status === 'DISPUTED') {{
              action = `<span style="color:var(--danger); font-family:var(--font-mono); font-weight:600; font-size:0.74rem;">DISPUTED (ARBITRATION LOCK)</span>`;
            }} else if (o.status === 'OPEN') {{
              action = `<button class="account-btn" style="color:var(--danger);" onclick="cancelP2POrder('${{o.order_id}}', '${{wid}}')">Cancel Ask</button>`;
            }} else {{
              action = `<span style="font-family:var(--font-mono); font-size:0.75rem;">${{escapeHtml(o.status)}}</span>`;
            }}
            tr.innerHTML = `
              <td><code style="font-family:var(--font-mono);">${{escapeHtml(o.order_id)}}</code></td>
              <td style="font-family:var(--font-mono);"><strong>${{o.amount_credits}} CR</strong></td>
              <td style="font-family:var(--font-mono);">${{escapeHtml(o.currency)}} ${{o.price_fiat}}</td>
              <td style="font-family:var(--font-mono); font-size:0.76rem;">${{escapeHtml(o.status)}}</td>
              <td style="font-family:var(--font-mono);">${{escapeHtml(o.buyer_id || 'UNFILLED')}}</td>
              <td style="font-family:var(--font-mono);"><strong>${{escapeHtml(o.payment_reference || 'PENDING')}}</strong></td>
              <td>${{action}}</td>
            `;
            salesT.appendChild(tr);
          }});
        }}

        // Render Buys
        const buysT = document.getElementById('my-buys-tbody');
        buysT.innerHTML = '';
        if (!trades.buying || trades.buying.length === 0) {{
          buysT.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted)">No inbound bid contracts found.</td></tr>';
        }} else {{
          trades.buying.forEach(o => {{
            const tr = document.createElement('tr');
            let buyAction = '';
            if (o.status === 'COMPLETED') {{
              buyAction = '<span style="color:var(--success); font-family:var(--font-mono); font-size:0.75rem;">SETTLED</span>';
            }} else if (o.status === 'OPEN') {{
              buyAction = `<button class="account-btn" style="color:var(--danger);" onclick="cancelP2POrder('${{o.order_id}}', '${{wid}}')">Cancel Bid</button>`;
            }} else if (o.status === 'IN_ESCROW') {{
              buyAction = `<div style="display:flex; gap:0.35rem; flex-wrap:wrap;">` +
                `<button class="account-btn" style="background:#2563eb; color:white; border-color:#3b82f6;" onclick="submitPaymentForBuyOrder('${{escapeHtml(o.order_id)}}', '${{escapeHtml(wid)}}', ${{o.price_fiat}}, '${{escapeHtml(o.currency)}}', '${{escapeHtml(o.payment_method)}}')">Submit TID</button>` +
                `<button class="account-btn" style="color:var(--danger); border-color:rgba(239,68,68,0.4);" onclick="raiseDisputePrompt('${{o.order_id}}', '${{wid}}')">Flag Dispute</button>` +
                `</div>`;
            }} else if (o.status === 'PAYMENT_SUBMITTED') {{
              buyAction = `<div style="display:flex; gap:0.35rem; align-items:center; flex-wrap:wrap;">` +
                `<span style="font-size:0.73rem; font-family:var(--font-mono); color:var(--text-muted);">AWAITING RELEASE (TID: ${{escapeHtml(o.payment_reference || 'SENT')}})</span>` +
                `<button class="account-btn" style="color:var(--danger); border-color:rgba(239,68,68,0.4); font-size:0.72rem;" onclick="raiseDisputePrompt('${{o.order_id}}', '${{wid}}')">Flag Dispute</button>` +
                `</div>`;
            }} else if (o.status === 'DISPUTED') {{
              buyAction = `<span style="color:var(--danger); font-family:var(--font-mono); font-weight:600; font-size:0.74rem;">DISPUTED (ARBITRATION LOCK)</span>`;
            }} else {{
              buyAction = `<span style="font-family:var(--font-mono); font-size:0.75rem;">${{escapeHtml(o.status)}}</span>`;
            }}
            tr.innerHTML = `
              <td><code style="font-family:var(--font-mono);">${{escapeHtml(o.order_id)}}</code></td>
              <td style="font-family:var(--font-mono);"><strong>${{escapeHtml(o.seller_id || 'AWAITING FILL')}}</strong></td>
              <td style="font-family:var(--font-mono);"><strong>${{o.amount_credits}} CR</strong></td>
              <td style="font-family:var(--font-mono);">${{escapeHtml(o.currency)}} ${{o.price_fiat}}</td>
              <td style="font-family:var(--font-mono); font-size:0.76rem;">${{escapeHtml(o.status)}}</td>
              <td style="font-size:0.78rem;">${{escapeHtml(o.payment_method)}}</td>
              <td>${{buyAction}}</td>
            `;
            buysT.appendChild(tr);
          }});
        }}
      }} catch(err) {{
        console.error('Error loading trades', err);
      }}
    }}

    async function raiseDisputePrompt(orderId, callerId) {{
      const reason = prompt(
        `INITIATE ESCROW ARBITRATION FOR CONTRACT ${{orderId}}\\n\\n` +
        `Places an immediate cryptographic freeze on both counterparty keys and escalates the contract + TID reference to the Constitutional Guardian for settlement verification.\\n\\n` +
        `Provide arbitration statement & payment reference:`
      );
      if (!reason) return;
      try {{
        const res = await fetch('/api/p2p/dispute', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ order_id: orderId, caller_id: callerId, reason: reason }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(
            `ESCROW ARBITRATION INITIATED\\n\\n` +
            `• Contract: ${{orderId}} (State: DISPUTED)\\n` +
            `• Frozen Counterparties: ${{(data.frozen_accounts || []).join(', ')}}\\n` +
            `• Guardian Dispatch: TRANSMITTED`
          );
          loadMyTrades();
          if (activeAccountKey) verifyAndDisplayAccount(activeAccountKey);
        }} else {{
          alert('Arbitration request rejected: ' + (data.error || 'Failed'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function releaseEscrow(orderId, sellerId) {{
      if (!confirm(`Confirm receipt of fiat settlement for contract ${{orderId}} and release escrowed credits to buyer?`)) return;
      try {{
        const res = await fetch('/api/p2p/release', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ order_id: orderId, seller_id: sellerId }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`Escrow released to ${{data.buyer_id}}. Contract settled.`);
          loadMyTrades();
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function cancelP2POrder(orderId, sellerId) {{
      if (!confirm(`Cancel contract ${{orderId}} and return escrowed credits to liquid balance?`)) return;
      try {{
        const res = await fetch('/api/p2p/cancel', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ order_id: orderId, seller_id: sellerId }})
        }});
        alert(`Contract cancelled and escrowed balance restored.`);
        loadMyTrades();
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function submitDirectTransfer() {{
      const fromW = document.getElementById('tr-from').value.trim() || activeAccountKey;
      const toW = document.getElementById('tr-to').value.trim();
      const amt = parseInt(document.getElementById('tr-amount').value || '0');

      if (!fromW || !toW || amt <= 0) return alert('Please specify source key, destination key, and credit volume.');

      try {{
        const res = await fetch('/api/p2p/transfer', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ from_worker: fromW, to_worker: toW, amount: amt }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`Ledger transfer complete: ${{amt}} CR transferred from ${{fromW}} to ${{toW}}.`);
          document.getElementById('tr-amount').value = '';
          if (activeAccountKey) verifyAndDisplayAccount(activeAccountKey);
        }} else {{
          alert('Transfer rejected: ' + (data.error || 'Failed'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    /* ========================================================= */
    /* OPTION 5: DISTRIBUTED SUPERCOMPUTER JAVASCRIPT            */
    /* ========================================================= */
    function updateSupercomputerCostEstimate() {{
      const cores = parseInt(document.getElementById('cust-cores-slider').value);
      const ram = parseInt(document.getElementById('cust-ram-slider').value);
      const dur = parseInt(document.getElementById('cust-duration-slider').value) || 1;

      document.getElementById('cust-cores-val').textContent = cores + ' Cores';
      document.getElementById('cust-ram-val').textContent = ram + ' GB';
      document.getElementById('cust-duration-val').textContent = dur === 1
        ? 'Continuous (Auto-Renew)'
        : `${{dur}}h Commitment + Auto-Renew`;

      const nodes = Math.max(2, Math.floor(cores / 4));
      const tflops = ((cores * 2.8) / 10.0).toFixed(1);
      const hourlyRate = Math.max(5, Math.floor((cores / 8.0) * 8 + (ram / 32.0) * 4));
      const total = hourlyRate * dur;

      document.getElementById('est-nodes-val').textContent = 'Up to ' + nodes + ' Nodes';
      document.getElementById('est-tflops-val').textContent = '~' + tflops + ' TFLOPS';
      document.getElementById('est-rate-val').textContent = hourlyRate + ' UMAIS/hr';
      document.getElementById('est-total-val').textContent = total + ' UMAIS (Credits)';
    }}

    async function rentSupercomputerPreset(tierName, cores, ramGb, durationHours) {{
      if (!activeAccountKey) {{
        return alert('Please authenticate your Secret Account Key in the top bar first.');
      }}
      if (!confirm(
        `Provision ${{tierName}} (Ceiling: ${{cores}} vCPUs, ${{ramGb}} GB RAM)?\\n` +
        `• Lifecycle: Continuous Auto-Renew (Runs until Paused or 0 CR)\\n` +
        `• Elastic Pool: Unused cores remain in the NEXUS Mesh pool and burst up to ${{cores}} vCPUs on workload demand.`
      )) return;

      try {{
        const res = await fetch('/api/supercomputer/rent', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            account_key: activeAccountKey,
            tier_name: tierName,
            cores: cores,
            ram_gb: ramGb,
            duration_hours: durationHours,
            auto_renew: true
          }})
        }});
        const data = await res.json();
        if (data.ok && data.instance) {{
          const s = data.instance;
          alert(
            `ELASTIC CLUSTER INSTANCE PROVISIONED\\n\\n` +
            `• Instance ID: ${{s.instance_id}}\\n` +
            `• Access Key ID: ${{s.access_key_id}}\\n` +
            `• Secret Key: ${{s.server_secret_key}}\\n` +
            `• RPC Endpoint: ${{s.endpoint}}\\n` +
            `• Billing Policy: Continuous Auto-Renew (${{s.hourly_rate || data.hourly_rate}} CR/hr)\\n` +
            `• Elastic Allocation: Idle cores shared with mesh; bursts to ${{s.allocated_cores}} vCPUs on load.\\n\\n` +
            `Initial Epoch Debited: ${{data.credits_spent}} CR (Remaining Balance: ${{data.remaining_credits}} CR)`
          );
          if (activeAccountKey) verifyAndDisplayAccount(activeAccountKey);
          loadMyClusters();
          openServerConsole(s.instance_id, s.tier_name, s.allocated_cores, s.allocated_ram_gb, s.endpoint, s.access_key_id || '', s.server_secret_key || '');
        }} else {{
          alert('Provisioning Rejected:\\n' + (data.error || 'Unknown error'));
        }}
      }} catch(err) {{
        alert('Request failed: ' + err.toString());
      }}
    }}

    async function rentCustomSupercomputer() {{
      const cores = parseInt(document.getElementById('cust-cores-slider').value);
      const ram = parseInt(document.getElementById('cust-ram-slider').value);
      const dur = parseInt(document.getElementById('cust-duration-slider').value) || 1;
      const tierName = `Custom Elastic Grid (${{cores}}C / ${{ram}}GB)`;
      await rentSupercomputerPreset(tierName, cores, ram, dur);
    }}

    async function connectRemoteServerByCredentials() {{
      const iid = document.getElementById('remote-server-id').value.trim();
      const secret = document.getElementById('remote-server-secret').value.trim();
      if (!iid || !secret) {{
        return alert('Please provide both Instance ID (or Access Key ID) and Server Secret Key.');
      }}
      try {{
        const res = await fetch('/api/supercomputer/connect', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            instance_id: iid,
            server_secret_key: secret
          }})
        }});
        const data = await res.json();
        if (data.ok && data.instance) {{
          const s = data.instance;
          activeRemoteServerSecret = secret;
          openServerConsole(s.instance_id, s.tier_name, s.allocated_cores, s.allocated_ram_gb, s.endpoint, s.access_key_id || '', s.server_secret_key || secret);
          loadMyClusters(secret);
        }} else {{
          alert('Authentication Failed: ' + (data.error || 'Invalid Instance ID or Secret Key'));
        }}
      }} catch(err) {{
        alert('Connection error: ' + err.toString());
      }}
    }}

    async function loadMyClusters(overrideKey) {{
      const tbody = document.getElementById('my-clusters-tbody');
      if (!tbody) return;
      const queryKey = overrideKey || activeAccountKey || activeRemoteServerSecret || '';
      if (!queryKey) {{
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:1.75rem;">Authenticate your Account Key or attach via IAM Instance Credentials to manage provisioned clusters.</td></tr>';
        return;
      }}
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:1rem;">Querying provisioned instances...</td></tr>';

      try {{
        const res = await fetch('/api/supercomputer/instances', {{ headers: {{ 'X-Account-Key': queryKey }} }});
        const data = await res.json();
        if (!data.ok || !data.instances || data.instances.length === 0) {{
          tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:1.75rem;">No active or paused instances found for this key.</td></tr>';
          return;
        }}

        tbody.innerHTML = data.instances.map(s => {{
          const isOnline = (s.status === 'ONLINE');
          const isPaused = (s.status === 'PAUSED' || s.status === 'PAUSED_LOW_CREDITS');
          const remMins = Math.floor((s.remaining_seconds || 0) / 60);
          const akid = s.access_key_id || 'NXIA-DEFAULT';
          const skey = s.server_secret_key || '';
          const activeCores = (s.active_cores_in_use !== undefined) ? s.active_cores_in_use : 2;
          const sharedCores = (s.shared_to_network_cores !== undefined) ? s.shared_to_network_cores : Math.max(0, s.allocated_cores - activeCores);
          const hRate = s.hourly_rate || Math.max(5, Math.floor((s.allocated_cores / 8.0) * 8 + (s.allocated_ram_gb / 32.0) * 4));

          let statusColor = 'var(--danger)';
          let statusLabel = s.status;
          if (isOnline) {{
            statusColor = 'var(--success)';
            statusLabel = 'ONLINE (AUTO-RENEW)';
          }} else if (isPaused) {{
            statusColor = 'var(--warning)';
            statusLabel = (s.status === 'PAUSED_LOW_CREDITS') ? 'PAUSED (0 CR)' : 'PAUSED (SAVED)';
          }}

          const elasticInfo = isPaused
            ? `<div style="font-size:0.7rem; font-family:var(--font-mono); color:var(--warning); margin-top:3px;">ACTIVE: 0C • MESH SHARED: ${{s.allocated_cores}}C</div>`
            : `<div style="font-size:0.7rem; font-family:var(--font-mono); color:var(--accent); margin-top:3px;">ACTIVE: <strong>${{activeCores}}/${{s.allocated_cores}}C</strong> • MESH SHARED: <strong>${{sharedCores}}C</strong></div>`;

          return `
            <tr>
              <td><span style="font-family:var(--font-mono); font-weight:600; color:var(--accent);">${{escapeHtml(s.instance_id)}}</span></td>
              <td><strong>${{escapeHtml(s.tier_name)}}</strong></td>
              <td>
                <div style="font-size:0.78rem;">Ceiling: <strong style="font-family:var(--font-mono);">${{s.allocated_cores}} vCPU / ${{s.allocated_ram_gb}} GB</strong></div>
                ${{elasticInfo}}
              </td>
              <td>
                <div style="font-family:var(--font-mono); font-size:0.72rem; line-height:1.4;">
                  <div><span style="color:var(--text-muted);">ID:</span> <span style="color:var(--success);">${{escapeHtml(akid)}}</span></div>
                  <div><span style="color:var(--text-muted);">KEY:</span> <span style="color:var(--warning);">${{escapeHtml(skey)}}</span></div>
                </div>
              </td>
              <td><span style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-muted);">${{escapeHtml(s.endpoint)}}</span></td>
              <td style="font-family:var(--font-mono); font-size:0.74rem;"><span class="status-dot" style="background:${{statusColor}}"></span> ${{escapeHtml(statusLabel)}}</td>
              <td>
                <div style="font-weight:700; font-family:var(--font-mono); color:var(--text);">${{hRate}} UMAIS/hr</div>
                <div style="font-size:0.7rem; font-family:var(--font-mono); color:var(--text-muted);">${{isPaused ? `FROZEN: ${{remMins}}m` : `EPOCH: ${{remMins}}m`}}</div>
              </td>
              <td>
                <div style="display:flex; gap:4px; flex-wrap:wrap;">
                  ${{isOnline ? `
                    <button class="account-btn" style="background:#2563eb; border-color:#3b82f6; color:white;" onclick="openServerConsole('${{escapeHtml(s.instance_id)}}', '${{escapeHtml(s.tier_name)}}', ${{s.allocated_cores}}, ${{s.allocated_ram_gb}}, '${{escapeHtml(s.endpoint)}}', '${{escapeHtml(akid)}}', '${{escapeHtml(skey)}}')">Console</button>
                    <button class="account-btn" style="color:var(--warning); border-color:rgba(245,158,11,0.35);" onclick="pauseCluster('${{escapeHtml(s.instance_id)}}', '${{escapeHtml(skey)}}')">Pause</button>
                    <button class="account-btn" style="color:var(--danger); border-color:rgba(239,68,68,0.35);" onclick="terminateCluster('${{escapeHtml(s.instance_id)}}', '${{escapeHtml(skey)}}')">Terminate</button>
                  ` : isPaused ? `
                    <button class="account-btn" style="background:#10b981; border-color:#10b981; color:#000; font-weight:600;" onclick="resumeCluster('${{escapeHtml(s.instance_id)}}', '${{escapeHtml(skey)}}')">Resume</button>
                    <button class="account-btn" onclick="openServerConsole('${{escapeHtml(s.instance_id)}}', '${{escapeHtml(s.tier_name)}}', ${{s.allocated_cores}}, ${{s.allocated_ram_gb}}, '${{escapeHtml(s.endpoint)}}', '${{escapeHtml(akid)}}', '${{escapeHtml(skey)}}')">Console</button>
                    <button class="account-btn" style="color:var(--danger); border-color:rgba(239,68,68,0.35);" onclick="terminateCluster('${{escapeHtml(s.instance_id)}}', '${{escapeHtml(skey)}}')">Terminate</button>
                  ` : `<span style="color:var(--text-muted); font-size:0.74rem; font-family:var(--font-mono);">TERMINATED</span>`}}
                </div>
              </td>
            </tr>
          `;
        }}).join('');
      }} catch(err) {{
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--danger); padding:1rem;">Error loading instances: ${{err.toString()}}</td></tr>`;
      }}
    }}

    let currentConsoleInstanceId = '';
    let currentConsoleAccessKeyId = '';
    let currentConsoleServerSecretKey = '';
    const SERVER_TEMPLATES = {{
      matrix: `import numpy as np\\nimport time\\n\\nprint("[CLUSTER] Distributing matrix factorization across pooled vCPUs...")\\nt0 = time.time()\\nA = np.random.rand(1500, 1500)\\nB = np.random.rand(1500, 1500)\\nC = np.dot(A, B)\\nelapsed = round(time.time() - t0, 3)\\nprint(f"[OK] Matrix Multiplication [1500x1500] completed in {{elapsed}}s.")\\nprint(f"Trace: {{np.trace(C):.2f}} | Elements processed: {{A.size:,}}")`,
      batch: `import time\\nimport math\\n\\ndef process_shard(shard_id, items):\\n    return sum(math.sqrt(x * 42.0) for x in items)\\n\\nprint("[CLUSTER] Executing parallel stream aggregation across worker shards...")\\ntotal_records = 500_000\\nchunk = total_records // 16\\nres = [process_shard(i, range(chunk)) for i in range(16)]\\nprint(f"[OK] Completed 500,000 records across 16 shards.")\\nprint(f"Checksum: {{sum(res):,.2f}}")`,
      simulation: `import random\\nimport time\\n\\nprint("[CLUSTER] Running Distributed Monte Carlo Kernel...")\\ntotal_samples = 1_000_000\\ninside = sum(1 for _ in range(total_samples) if (random.random()**2 + random.random()**2) <= 1.0)\\npi_est = 4.0 * inside / total_samples\\nprint(f"[OK] Simulation completed ({{total_samples:,}} samples).")\\nprint(f"Estimated Pi: {{pi_est:.5f}} (Delta: {{abs(pi_est - 3.141592):.5f}})")`,
      custom: `# Custom Python workload for distributed cluster execution\\nimport sys\\nprint("[CLUSTER] Connected to Virtual Supercomputer Instance")\\nprint(f"Runtime: {{sys.version}}")\\n`
    }};

    function openServerConsole(instanceId, tierName, cores, ramGb, endpoint, accessKeyId, serverSecretKey) {{
      currentConsoleInstanceId = instanceId;
      currentConsoleAccessKeyId = accessKeyId || 'NXIA-SERVER';
      currentConsoleServerSecretKey = serverSecretKey || activeRemoteServerSecret || '';
      const m = document.getElementById('modal-server-console');
      if (m) m.style.display = 'flex';

      document.getElementById('m-server-title').textContent = `Instance Console: ${{instanceId}} (${{tierName}})`;
      document.getElementById('m-server-specs').textContent = `${{cores}} vCPU Ceiling • ${{ramGb}} GB RAM • Endpoint: ${{endpoint}}`;
      if (document.getElementById('m-cred-iid')) document.getElementById('m-cred-iid').textContent = instanceId;
      if (document.getElementById('m-cred-akid')) document.getElementById('m-cred-akid').textContent = currentConsoleAccessKeyId;
      if (document.getElementById('m-cred-secret')) document.getElementById('m-cred-secret').textContent = currentConsoleServerSecretKey || '(Authenticated via Account Key)';

      applyServerCodeTemplate('matrix');

      const host = window.location.host || '127.0.0.1:8443';
      const scheme = window.location.protocol || 'http:';
      const authField = currentConsoleServerSecretKey
        ? `"server_secret_key": "${{currentConsoleServerSecretKey}}"`
        : `"account_key": "${{activeAccountKey}}"`;
      document.getElementById('server-curl-snippet').textContent = `curl -X POST "${{scheme}}//${{host}}/api/supercomputer/job" \\\\
  -H "Content-Type: application/json" \\\\
  -d '{{\\n    "instance_id": "${{instanceId}}",\\n    ${{authField}},\\n    "job_name": "Remote Workload",\\n    "payload_code": "import numpy as np; print(\\\\\\"Cluster output:\\\\\\", np.random.rand(3,3))"\\n  }}'`;

      document.getElementById('server-python-snippet').textContent = `import urllib.request, json\\n\\npayload = {{\\n    "instance_id": "${{instanceId}}",\\n    ${{authField}},\\n    "job_name": "Cluster Batch Compute",\\n    "payload_code": open("my_script.py").read()  # or inline Python code\\n}}\\n\\nreq = urllib.request.Request(\\n    "${{scheme}}//${{host}}/api/supercomputer/job",\\n    data=json.dumps(payload).encode("utf-8"),\\n    headers={{"Content-Type": "application/json"}}\\n)\\n\\nwith urllib.request.urlopen(req) as resp:\\n    result = json.loads(resp.read().decode("utf-8"))\\n    print("Cluster Execution Result:", result)`;

      switchServerModalTab('code');
    }}

    function copyActiveServerCredentials() {{
      const txt = `Instance ID: ${{currentConsoleInstanceId}}\\nAccess Key ID: ${{currentConsoleAccessKeyId}}\\nServer Secret Key: ${{currentConsoleServerSecretKey}}`;
      navigator.clipboard.writeText(txt);
      alert('IAM Instance Credentials copied to clipboard.');
    }}

    function closeServerConsole() {{
      const m = document.getElementById('modal-server-console');
      if (m) m.style.display = 'none';
    }}

    function switchServerModalTab(tab) {{
      document.getElementById('modal-server-tab-code').style.display = (tab === 'code' ? 'block' : 'none');
      document.getElementById('modal-server-tab-api').style.display = (tab === 'api' ? 'block' : 'none');
      document.getElementById('modal-server-tab-sdk').style.display = (tab === 'sdk' ? 'block' : 'none');

      document.getElementById('stab-btn-code').style.background = (tab === 'code' ? '#161922' : 'transparent');
      document.getElementById('stab-btn-api').style.background = (tab === 'api' ? '#161922' : 'transparent');
      document.getElementById('stab-btn-sdk').style.background = (tab === 'sdk' ? '#161922' : 'transparent');
    }}

    function applyServerCodeTemplate(tmplKey) {{
      const ta = document.getElementById('server-code-input');
      if (ta && SERVER_TEMPLATES[tmplKey]) {{
        ta.value = SERVER_TEMPLATES[tmplKey];
      }}
    }}

    async function submitServerCodeRun() {{
      const code = document.getElementById('server-code-input').value;
      if (!code.trim()) return alert('Please provide Python workload code.');

      const outArea = document.getElementById('server-run-output-area');
      const stLine = document.getElementById('server-run-status-line');
      const stdPre = document.getElementById('server-run-stdout');
      const slicesDiv = document.getElementById('server-run-slices');

      outArea.style.display = 'block';
      stLine.textContent = `Dispatching workload across pooled worker nodes in ${{currentConsoleInstanceId}}...`;
      stdPre.textContent = 'Running...';
      slicesDiv.innerHTML = '';

      try {{
        const res = await fetch('/api/supercomputer/job', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            instance_id: currentConsoleInstanceId,
            account_key: activeAccountKey,
            server_secret_key: currentConsoleServerSecretKey,
            job_name: 'Console Workload',
            payload_code: code
          }})
        }});
        const data = await res.json();
        if (data.ok && data.job) {{
          const j = data.job;
          const burstCores = j.elastic_cores_burst || j.cores_active;
          const sharedMesh = j.shared_to_network_cores !== undefined ? j.shared_to_network_cores : 0;
          stLine.innerHTML = `<span style="color:var(--success);">[OK] Completed in ${{j.elapsed_ms}}ms across ${{j.nodes_utilized}} nodes (Active Burst: ${{burstCores}}/${{j.cores_active}} vCPUs • Mesh Shared: ${{sharedMesh}} vCPUs)</span>`;
          stdPre.textContent = j.output || '(Process exited with code 0)';
          slicesDiv.innerHTML = (j.node_results || []).map(nr => `
            <div style="background:#101218; border:1px solid var(--border); border-radius:4px; padding:0.22rem 0.5rem; font-size:0.7rem;">
              <span style="color:var(--success);">●</span> <strong>${{escapeHtml(nr.node_id)}}</strong> [#${{nr.slice_index}}]: ${{nr.tflops_utilized}} TF | ${{nr.memory_slice_mb}} MB
            </div>
          `).join('');
          loadMyClusters();
        }} else {{
          stLine.textContent = '[ERR] Execution Failed:';
          stdPre.textContent = data.error || 'Failed to dispatch workload';
        }}
      }} catch(err) {{
        stLine.textContent = '[ERR] Transport Exception:';
        stdPre.textContent = err.toString();
      }}
    }}

    async function ideRunOnSupercomputer() {{
      const queryKey = activeAccountKey || activeRemoteServerSecret || '';
      if (!queryKey) {{
        alert('Please authenticate your Account Key or attach to an instance in Tab 5 first.');
        return;
      }}
      logToIdeTerminal('Querying provisioned Supercomputer instances...', '#60a5fa');
      try {{
        const res = await fetch('/api/supercomputer/instances', {{ headers: {{ 'X-Account-Key': queryKey }} }});
        const data = await res.json();
        const activeInst = (data.instances || []).find(i => i.status === 'ONLINE' || i.status === 'PAUSED' || i.status === 'PAUSED_LOW_CREDITS');
        if (!activeInst) {{
          logToIdeTerminal('No provisioned cluster found. Navigate to Tab 5 to provision an instance.', '#f59e0b');
          if (confirm('No provisioned cluster found for your key.\\nOpen Tab 5 (Rent Supercomputer / Server) to provision an instance?')) {{
            switchMainTab('supercomputer');
          }}
          return;
        }}

        const code = getEditorCode();
        logToIdeTerminal(`Dispatching '${{currentOpenFile}}' to ${{activeInst.tier_name}} (${{activeInst.instance_id}} — Ceiling: ${{activeInst.allocated_cores}} vCPUs)...`, '#93c5fd');

        const jobRes = await fetch('/api/supercomputer/job', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            instance_id: activeInst.instance_id,
            account_key: activeAccountKey,
            server_secret_key: activeInst.server_secret_key || '',
            job_name: `IDE Run: ${{currentOpenFile}}`,
            payload_code: code
          }})
        }});
        const jobData = await jobRes.json();
        if (jobData.ok && jobData.job) {{
          const j = jobData.job;
          logToIdeTerminal(`[OK] Cluster Execution Completed in ${{j.elapsed_ms}}ms across ${{j.nodes_utilized}} nodes (${{j.cores_active}} vCPUs).`, '#10b981');
          if (j.output) {{
            logToIdeTerminal(`Output:\\n${{j.output}}`, '#60a5fa');
          }} else {{
            logToIdeTerminal(j.summary, '#60a5fa');
          }}
        }} else {{
          logToIdeTerminal(`[ERR] Cluster execution failed: ${{jobData.error || 'Failed'}}`, '#ef4444');
        }}
      }} catch (err) {{
        logToIdeTerminal(`Cluster communication error: ${{err.toString()}}`, '#ef4444');
      }}
    }}

    async function pauseCluster(instanceId, serverSecretKey) {{
      if (!confirm(`Pause instance ${{instanceId}}?\\n• Metered billing halts immediately and remaining epoch time is frozen.\\n• All vCPUs are returned to the shared NEXUS mesh while paused.\\n• Click Resume anytime to restore your exact instance state.`)) return;
      try {{
        const res = await fetch('/api/supercomputer/pause', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            instance_id: instanceId,
            account_key: activeAccountKey,
            server_secret_key: serverSecretKey || currentConsoleServerSecretKey || ''
          }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(data.message || `Instance ${{instanceId}} paused. State and remaining epoch frozen.`);
          loadMyClusters();
        }} else {{
          alert('Failed to pause instance: ' + (data.error || 'Unknown'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function resumeCluster(instanceId, serverSecretKey) {{
      try {{
        const res = await fetch('/api/supercomputer/resume', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            instance_id: instanceId,
            account_key: activeAccountKey,
            server_secret_key: serverSecretKey || currentConsoleServerSecretKey || ''
          }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(data.message || `Instance ${{instanceId}} resumed from saved state.`);
          if (activeAccountKey) verifyAndDisplayAccount(activeAccountKey);
          loadMyClusters();
        }} else {{
          alert('Failed to resume instance: ' + (data.error || 'Unknown'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    async function terminateCluster(instanceId, serverSecretKey) {{
      if (!confirm(`Permanently terminate instance ${{instanceId}}?\\n(Note: Use 'Pause' instead if you wish to freeze billing and resume later.)`)) return;
      try {{
        const res = await fetch('/api/supercomputer/terminate', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            instance_id: instanceId,
            account_key: activeAccountKey,
            server_secret_key: serverSecretKey || currentConsoleServerSecretKey || ''
          }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`Instance ${{instanceId}} terminated.`);
          loadMyClusters();
        }} else {{
          alert('Failed to terminate: ' + (data.error || 'Unknown'));
        }}
      }} catch(err) {{
        alert('Error: ' + err.toString());
      }}
    }}

    /* ========================================================= */
    /* TAB 6: THE TOKEN SINK (LOTTERY & STAKING VAULT)           */
    /* ========================================================= */
    async function loadLotteryAndStaking() {{
      try {{
        const lotRes = await fetch('/api/lottery/status');
        const lotData = await lotRes.json();
        if (lotData && lotData.ok) {{
          const roundBadge = document.getElementById('lottery-round-badge');
          if (roundBadge) {{
            roundBadge.textContent = `Round #${{lotData.current_round}} (${{lotData.tickets_sold_in_round || 0}}/${{lotData.target_pool_tickets || 10}} Entries)`;
          }}
          const potEl = document.getElementById('lottery-current-pot');
          if (potEl) potEl.textContent = `${{lotData.current_pool_credits || 0}} UMAIS (Credits)`;

          const winEl = document.getElementById('lottery-win-payout');
          if (winEl) winEl.textContent = `${{lotData.estimated_jackpot_payout || 45}} UMAIS (90%)`;

          const burnEl = document.getElementById('lottery-burn-payout');
          if (burnEl) burnEl.textContent = `${{lotData.estimated_burn_payout || 5}} UMAIS (10%)`;

          const needEl = document.getElementById('lottery-tickets-needed');
          if (needEl) {{
            needEl.textContent = `${{lotData.tickets_needed_for_draw || 0}} entries remaining for auto-settlement`;
          }}

          const burnTotEl = document.getElementById('lottery-total-burned');
          if (burnTotEl) burnTotEl.textContent = `${{lotData.total_deflationary_burned_credits || 0}} UMAIS`;

          const awdTotEl = document.getElementById('lottery-total-awarded');
          if (awdTotEl) awdTotEl.textContent = `${{lotData.total_jackpot_credits_awarded || 0}} UMAIS`;

          const winnersCont = document.getElementById('lottery-recent-winners');
          if (winnersCont) {{
            if (lotData.recent_winners && lotData.recent_winners.length > 0) {{
              winnersCont.innerHTML = lotData.recent_winners.slice().reverse().map(w => `
                <div style="background:#090a0f; border:1px solid var(--border); border-radius:6px; padding:0.45rem 0.65rem; display:flex; justify-content:space-between; align-items:center;">
                  <div>
                    <span style="font-weight:700; color:var(--warning);">ROUND #${{w.round_number}}</span>
                    <span style="color:var(--text-muted); margin-left:0.4rem;">RECIPIENT: <code style="color:var(--accent);">${{escapeHtml(w.winner_worker_id)}}</code></span>
                  </div>
                  <div style="font-weight:700; color:var(--success);">+${{w.jackpot_credits}} UMAIS <span style="font-size:0.7rem; color:var(--danger);">(-${{w.burned_credits}} BURNED)</span></div>
                </div>
              `).join('');
            }} else {{
              winnersCont.innerHTML = `<div style="color:var(--text-muted);">No settled rounds recorded. Commit entries to initialize Round #1.</div>`;
            }}
          }}
        }}

        const queryAcc = activeAccountKey || '';
        const stakeHeaders = queryAcc ? {{ 'X-Account-Key': queryAcc }} : {{}};
        const stakeRes = await fetch('/api/staking/status', {{ headers: stakeHeaders }});
        const stakeData = await stakeRes.json();
        if (stakeData && stakeData.ok) {{
          const myStk = document.getElementById('my-staked-credits');
          if (myStk) myStk.textContent = `${{stakeData.user_staked || 0}} UMAIS (Credits)`;

          const totStk = document.getElementById('vault-total-staked');
          if (totStk) totStk.textContent = `${{stakeData.total_staked_in_vault || 0}} UMAIS (Credits)`;

          const badge = document.getElementById('my-staking-badge');
          if (badge) {{
            const tier = stakeData.user_tier || 'NONE';
            badge.textContent = `Tier: ${{tier}}`;
            if (tier === 'GOLD') {{
              badge.style.background = 'rgba(245,158,11,0.12)';
              badge.style.color = '#fbbf24';
              badge.style.borderColor = 'rgba(245,158,11,0.4)';
            }} else if (tier === 'SILVER') {{
              badge.style.background = 'rgba(148,163,184,0.15)';
              badge.style.color = '#e2e8f0';
              badge.style.borderColor = 'rgba(148,163,184,0.4)';
            }} else if (tier === 'BRONZE') {{
              badge.style.background = 'rgba(59,130,246,0.12)';
              badge.style.color = '#93c5fd';
              badge.style.borderColor = 'rgba(59,130,246,0.35)';
            }} else {{
              badge.style.background = '#141720';
              badge.style.color = 'var(--text-muted)';
              badge.style.borderColor = 'var(--border)';
            }}
          }}
        }}
      }} catch (err) {{
        console.error('Failed to load lottery/staking info:', err);
      }}
    }}

    async function buyLotteryTicketsNow() {{
      const accKey = activeAccountKey || prompt('Enter your Secret Account Key or Operator ID to commit pool entries:');
      if (!accKey) return;
      const qty = parseInt(document.getElementById('lottery-ticket-qty').value, 10) || 1;
      try {{
        const res = await fetch('/api/lottery/buy_ticket', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ account_key: accKey, count: qty }})
        }});
        const data = await res.json();
        if (data.ok) {{
          if (data.auto_drawn && data.draw_result) {{
            const dr = data.draw_result;
            alert(`CONSENSUS ROUND #${{dr.round_number}} SETTLED\\nRecipient: ${{dr.winner_worker_id}}\\nPool Payout: +${{dr.jackpot_credits}} CR\\nProtocol Burn: -${{dr.burned_credits}} CR`);
          }} else {{
            alert(`Committed ${{qty}} pool entry(s) (${{data.cost_credits}} CR).\\nActive Pool: ${{data.current_pool_credits}} CR (${{data.tickets_needed_for_draw}} entries remaining for auto-settlement).`);
          }}
          verifyAndDisplayAccount(accKey);
          loadLotteryAndStaking();
        }} else {{
          alert('Entry commitment rejected: ' + (data.error || 'Unknown error'));
        }}
      }} catch (err) {{
        alert('Error committing entries: ' + err.toString());
      }}
    }}

    async function drawLotteryNow() {{
      if (!confirm('Execute deterministic SHA-256 Consensus Beacon draw on active pool entries?')) return;
      try {{
        const res = await fetch('/api/lottery/draw', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ force: true }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`CONSENSUS DRAW EXECUTED\\nRound #${{data.round_number}}\\nRecipient: ${{data.winner_worker_id}}\\nPayout: +${{data.jackpot_credits}} CR (90%)\\nProtocol Burn: -${{data.burned_credits}} CR (10%)\\nBeacon Digest: ${{data.beacon_hash ? data.beacon_hash.substring(0, 16) : 'VERIFIED'}}...`);
          if (activeAccountKey) verifyAndDisplayAccount(activeAccountKey);
          loadLotteryAndStaking();
        }} else {{
          alert('Draw rejected: ' + (data.error || 'Pool has no active entries'));
        }}
      }} catch (err) {{
        alert('Error executing draw: ' + err.toString());
      }}
    }}

    async function stakeCreditsNow() {{
      const accKey = activeAccountKey || prompt('Enter your Secret Account Key to lock vault stake:');
      if (!accKey) return;
      const amt = parseInt(document.getElementById('staking-input-amount').value, 10);
      if (!amt || amt <= 0) {{
        alert('Please enter a valid credit volume (minimum 1 CR).');
        return;
      }}
      try {{
        const res = await fetch('/api/staking/stake', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ account_key: accKey, amount: amt }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`Locked ${{amt}} CR in Staking Vault.\\nActive Tier: ${{data.tier}}\\nProtocol Benefits: ${{data.perks}}`);
          document.getElementById('staking-input-amount').value = '';
          verifyAndDisplayAccount(accKey);
          loadLotteryAndStaking();
        }} else {{
          alert('Staking rejected: ' + (data.error || 'Unknown error'));
        }}
      }} catch (err) {{
        alert('Error locking stake: ' + err.toString());
      }}
    }}

    async function unstakeCreditsNow() {{
      const accKey = activeAccountKey || prompt('Enter your Secret Account Key to withdraw staked collateral:');
      if (!accKey) return;
      const amt = parseInt(document.getElementById('staking-input-amount').value, 10);
      if (!amt || amt <= 0) {{
        alert('Please enter a valid withdrawal volume.');
        return;
      }}
      try {{
        const res = await fetch('/api/staking/unstake', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ account_key: accKey, amount: amt }})
        }});
        const data = await res.json();
        if (data.ok) {{
          alert(`Withdrew ${{amt}} CR from Staking Vault.\\nLiquid Balance: ${{data.active_credits}} CR.`);
          document.getElementById('staking-input-amount').value = '';
          verifyAndDisplayAccount(accKey);
          loadLotteryAndStaking();
        }} else {{
          alert('Withdrawal rejected: ' + (data.error || 'Unknown error'));
        }}
      }} catch (err) {{
        alert('Error withdrawing stake: ' + err.toString());
      }}
    }}
  </script>
</body>
</html>
"""
