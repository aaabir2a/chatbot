// CSS injected into the widget's Shadow DOM. Scoped — cannot leak into or be
// affected by the host page. Theme is driven by CSS custom properties set on
// the shadow host (see core.ts).

export const WIDGET_CSS = `
:host { all: initial; }
*, *::before, *::after { box-sizing: border-box; }

.rc-root {
  --rc-primary: #5b5bf5;
  --rc-on-primary: #ffffff;
  --rc-bg: #ffffff;
  --rc-surface: #f4f5f9;
  --rc-text: #1a1d29;
  --rc-text-2: #6b7280;
  --rc-border: #e6e8ef;
  --rc-z: 2147483000;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: var(--rc-text);
}

/* ── Launcher bubble ── */
.rc-launcher {
  position: fixed; bottom: 22px; z-index: var(--rc-z);
  width: 58px; height: 58px; border-radius: 50%;
  background: var(--rc-primary); color: var(--rc-on-primary);
  border: none; cursor: pointer; font-size: 26px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 24px rgba(0,0,0,0.22);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.rc-launcher:hover { transform: scale(1.06); }
.rc-launcher:active { transform: scale(0.97); }
.rc-pos-right .rc-launcher { right: 22px; }
.rc-pos-left  .rc-launcher { left: 22px; }

/* ── Panel ── */
.rc-panel {
  position: fixed; bottom: 92px; z-index: var(--rc-z);
  width: 380px; max-width: calc(100vw - 32px);
  height: 560px; max-height: calc(100vh - 130px);
  background: var(--rc-bg); border-radius: 16px; overflow: hidden;
  box-shadow: 0 12px 48px rgba(0,0,0,0.24);
  display: flex; flex-direction: column;
  transform-origin: bottom right; animation: rc-pop 0.16s ease;
}
.rc-pos-right .rc-panel { right: 22px; transform-origin: bottom right; }
.rc-pos-left  .rc-panel { left: 22px; transform-origin: bottom left; }
@keyframes rc-pop { from { opacity: 0; transform: translateY(10px) scale(0.97); } }
.rc-hidden { display: none !important; }

/* ── Header ── */
.rc-header {
  background: var(--rc-primary); color: var(--rc-on-primary);
  padding: 16px 18px; display: flex; align-items: center; gap: 12px;
}
.rc-header-text { flex: 1; min-width: 0; }
.rc-title { font-weight: 650; font-size: 15px; }
.rc-subtitle { font-size: 12.5px; opacity: 0.85; }
.rc-head-btn {
  background: rgba(255,255,255,0.18); border: none; color: inherit;
  width: 30px; height: 30px; border-radius: 8px; cursor: pointer; font-size: 16px;
  display: flex; align-items: center; justify-content: center;
}
.rc-head-btn:hover { background: rgba(255,255,255,0.3); }

/* ── Messages ── */
.rc-messages {
  flex: 1; overflow-y: auto; padding: 16px; display: flex;
  flex-direction: column; gap: 10px; background: var(--rc-surface);
}
.rc-row { display: flex; }
.rc-row.user { justify-content: flex-end; }
.rc-bubble {
  max-width: 80%; padding: 10px 13px; border-radius: 14px;
  white-space: pre-wrap; word-wrap: break-word; font-size: 14px;
}
.rc-bubble.bot {
  background: var(--rc-bg); border: 1px solid var(--rc-border);
  border-bottom-left-radius: 4px;
}
.rc-bubble.user {
  background: var(--rc-primary); color: var(--rc-on-primary);
  border-bottom-right-radius: 4px;
}
.rc-bubble.error { background: #fdeded; border: 1px solid #f5c2c2; color: #c0392b; }
.rc-bubble.agent {
  background: #eef2ff; border: 1px solid #d6ddff; color: var(--rc-text);
  border-bottom-left-radius: 4px;
}
.rc-bubble-meta {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.04em;
  font-weight: 700; color: var(--rc-primary); margin-bottom: 3px;
}

/* ── Live-agent banner + system lines ── */
.rc-banner {
  background: #e9f7ed; color: #1e7a34; font-size: 12.5px; font-weight: 600;
  padding: 8px 14px; text-align: center; border-bottom: 1px solid #cdebd6;
}
.rc-sys {
  text-align: center; font-size: 11.5px; color: var(--rc-text-2);
  margin: 2px 0; padding: 2px 8px;
}

/* ── Lead capture form ── */
.rc-lead {
  background: var(--rc-bg); border: 1px solid var(--rc-border);
  border-radius: 12px; padding: 14px; margin: 4px 0;
  box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}
.rc-lead-title { font-weight: 700; font-size: 14px; margin-bottom: 2px; }
.rc-lead-sub { font-size: 12.5px; color: var(--rc-text-2); margin-bottom: 10px; }
.rc-lead-input {
  width: 100%; border: 1px solid var(--rc-border); border-radius: 9px;
  padding: 9px 11px; font-size: 14px; font-family: inherit; margin-bottom: 8px;
  outline: none; color: var(--rc-text); background: var(--rc-bg);
}
.rc-lead-input:focus { border-color: var(--rc-primary); }
.rc-lead-error .rc-lead-input { border-color: #e5484d; }
.rc-lead-actions { display: flex; gap: 8px; justify-content: flex-end; }
.rc-lead-skip {
  background: transparent; border: none; color: var(--rc-text-2);
  font-size: 13px; cursor: pointer; padding: 8px 10px; border-radius: 8px;
}
.rc-lead-skip:hover { background: var(--rc-surface); }
.rc-lead-submit {
  background: var(--rc-primary); color: var(--rc-on-primary); border: none;
  border-radius: 9px; padding: 8px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
}

/* ── Typing indicator ── */
.rc-typing { display: inline-flex; gap: 4px; align-items: center; padding: 2px 0; }
.rc-typing span {
  width: 7px; height: 7px; border-radius: 50%; background: var(--rc-text-2);
  animation: rc-blink 1.2s infinite both;
}
.rc-typing span:nth-child(2) { animation-delay: 0.2s; }
.rc-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes rc-blink { 0%,80%,100% { opacity: 0.25; } 40% { opacity: 1; } }

/* ── Composer ── */
.rc-composer {
  display: flex; gap: 8px; padding: 12px; border-top: 1px solid var(--rc-border);
  background: var(--rc-bg);
}
.rc-input {
  flex: 1; resize: none; border: 1px solid var(--rc-border); border-radius: 10px;
  padding: 10px 12px; font-family: inherit; font-size: 14px; outline: none;
  max-height: 96px; color: var(--rc-text); background: var(--rc-bg);
}
.rc-input:focus { border-color: var(--rc-primary); }
.rc-send {
  background: var(--rc-primary); color: var(--rc-on-primary); border: none;
  border-radius: 10px; width: 42px; cursor: pointer; font-size: 18px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.rc-send:disabled { opacity: 0.5; cursor: not-allowed; }

.rc-footer {
  text-align: center; font-size: 11px; color: var(--rc-text-2);
  padding: 6px; background: var(--rc-bg);
}
.rc-footer a { color: var(--rc-text-2); }
`;
