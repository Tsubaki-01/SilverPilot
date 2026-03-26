/**
 * Silver Pilot — API Connector
 *
 * 将前端的 mock 数据替换为真实的后端 API 调用。
 *
 * 使用方式：在 silver-pilot-demo.html 的 </body> 前添加：
 *   <script src="/static/api-connector.js"></script>
 *
 * 功能：
 *   1. REST: 会话 CRUD、用户画像、健康数据、提醒
 *   2. WebSocket: 实时对话 + Agent 事件流
 *   3. 自动降级: 后端不可用时回退到本地 mock
 */

(function () {
  "use strict";

  const API_BASE = window.location.origin;
  const WS_BASE = API_BASE.replace("http", "ws");
  const USER_ID = "default_user";

  let _ws = null;
  let _wsSessionId = null;
  let _connected = false;
  let _pendingDebug = null; // 累积的 debug 数据

  // ── 检测后端 ──
  async function checkBackend() {
    try {
      const resp = await fetch(`${API_BASE}/api/sessions?user_id=${USER_ID}`, {
        signal: AbortSignal.timeout(3000),
      });
      _connected = resp.ok;
    } catch {
      _connected = false;
    }
    console.log(`[API] Backend ${_connected ? "✓ connected" : "✗ offline (using mock)"}`);
    return _connected;
  }

  // ═══════════════════════════════════════
  //  REST: Sessions
  // ═══════════════════════════════════════

  async function fetchSessions() {
    if (!_connected) return null;
    try { return await (await fetch(`${API_BASE}/api/sessions?user_id=${USER_ID}`)).json(); }
    catch { return null; }
  }

  async function createSession(name) {
    if (!_connected) return null;
    try {
      return await (await fetch(`${API_BASE}/api/sessions`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name || "新对话", user_id: USER_ID }),
      })).json();
    } catch { return null; }
  }

  async function deleteSession(id) {
    if (!_connected) return false;
    try { await fetch(`${API_BASE}/api/sessions/${id}`, { method: "DELETE" }); return true; }
    catch { return false; }
  }

  async function fetchMessages(id) {
    if (!_connected) return null;
    try { return await (await fetch(`${API_BASE}/api/sessions/${id}/messages`)).json(); }
    catch { return null; }
  }

  // ═══════════════════════════════════════
  //  REST: Profile / Health / Reminders
  // ═══════════════════════════════════════

  async function fetchProfile() {
    if (!_connected) return null;
    try { return await (await fetch(`${API_BASE}/api/profile/${USER_ID}`)).json(); }
    catch { return null; }
  }

  async function fetchReminders() {
    if (!_connected) return null;
    try { return await (await fetch(`${API_BASE}/api/reminders/${USER_ID}`)).json(); }
    catch { return null; }
  }

  // ═══════════════════════════════════════
  //  WebSocket: 对话
  // ═══════════════════════════════════════

  function connectChat(sessionId) {
    if (_ws && _ws.readyState === WebSocket.OPEN && _wsSessionId === sessionId) return _ws;
    if (_ws) { _ws.close(); _ws = null; }

    _wsSessionId = sessionId;
    _ws = new WebSocket(`${WS_BASE}/ws/chat/${sessionId}`);
    _ws.onopen = () => console.log(`[WS] Connected: ${sessionId}`);
    _ws.onmessage = (e) => { try { _handleWS(JSON.parse(e.data)); } catch (err) { console.error("[WS] Parse:", err); } };
    _ws.onclose = () => { console.log("[WS] Disconnected"); _ws = null; _wsSessionId = null; };
    _ws.onerror = (e) => console.error("[WS] Error:", e);
    return _ws;
  }

  function sendMessage(content, modality, imagePath, audioPath) {
    if (!_ws || _ws.readyState !== WebSocket.OPEN) return false;
    _ws.send(JSON.stringify({
      type: "message", content, modality: modality || { text: true, audio: false, image: false },
      image_path: imagePath || "", audio_path: audioPath || "",
    }));
    return true;
  }

  function sendHITL(confirmed) {
    if (!_ws || _ws.readyState !== WebSocket.OPEN) return false;
    _ws.send(JSON.stringify({ type: "hitl_response", confirmed }));
    return true;
  }

  // ── WS 事件处理（核心修复）──
  function _handleWS(msg) {
    switch (msg.type) {
      case "node_start":
        // 实时驱动前端 Pipeline 动画：将节点标记为 active
        _onNodeStart(msg.node);
        break;

      case "node_end":
        // 节点完成：标记 done + 写入耗时
        _onNodeEnd(msg.node, msg.data || {}, msg.duration_ms || 0);
        break;

      case "hitl_request":
        _onHITLRequest(msg.data || {});
        break;

      case "response":
        _onFinalResponse(msg.content, msg.debug || {});
        break;

      case "error":
        console.error("[Agent Error]", msg.message);
        if (typeof hTyp === "function") hTyp();
        if (typeof addMsg === "function") addMsg("assistant", `⚠️ ${msg.message}`);
        break;
    }
  }

  // ── Pipeline 动画驱动 ──

  function _onNodeStart(nodeName) {
    if (!_pendingDebug) return;

    // 将该节点标记为 active（前端 rPipe 渲染时会应用动画）
    const existing = _pendingDebug.pipeline.find(n => n.name === nodeName);
    if (!existing) {
      _pendingDebug.pipeline.push({
        name: nodeName, color: _nodeColor(nodeName), time: "...", status: "active",
      });
    } else {
      existing.status = "active";
    }

    // 刷新 drawer
    window.DD = _pendingDebug;
    if (typeof updDr === "function") updDr();
  }

  function _onNodeEnd(nodeName, data, durationMs) {
    if (!_pendingDebug) return;

    const timeStr = durationMs < 1000 ? `${Math.round(durationMs)}ms` : `${(durationMs / 1000).toFixed(1)}s`;

    const existing = _pendingDebug.pipeline.find(n => n.name === nodeName);
    if (existing) {
      existing.status = "done";
      existing.time = timeStr;
    } else {
      _pendingDebug.pipeline.push({
        name: nodeName, color: _nodeColor(nodeName), time: timeStr, status: "done",
      });
    }

    // 合并后端传来的 debug 分片数据
    if (data) {
      // intents
      if (data.pending_intents || data.current_agent) {
        // supervisor 输出
      }
    }

    window.DD = _pendingDebug;
    if (typeof updDr === "function") updDr();
  }

  function _onHITLRequest(data) {
    if (typeof hTyp === "function") hTyp();
    // 构造 HITL 卡片
    if (typeof showHTL === "function") {
      showHTL({
        debug: { tools: [data] },
        response_confirmed: "✅ 操作已执行",
        response_cancelled: "好的，已取消。",
      });
    }
  }

  function _onFinalResponse(content, debug) {
    if (typeof hTyp === "function") hTyp();

    // 合并后端的完整 debug 数据（后端在 response 中发送最终版本）
    if (debug && debug.pipeline) {
      _pendingDebug = debug;
    }

    if (typeof addMsg === "function") {
      const sources = _extractSources(debug);
      addMsg("assistant", content, { sources });
    }

    window.DD = _pendingDebug || debug;
    if (typeof updDr === "function") updDr();
    // 自动打开 drawer 展示过程
    if (window.DD && window.DD.pipeline && window.DD.pipeline.length > 0) {
      document.getElementById("drTog")?.classList.add("has");
    }

    _pendingDebug = null;
  }

  // ═══════════════════════════════════════
  //  Override 前端函数
  // ═══════════════════════════════════════

  async function initWithBackend() {
    const ok = await checkBackend();
    if (!ok) return;

    const sessions = await fetchSessions();
    if (sessions && sessions.length > 0 && typeof window.SS !== "undefined") {
      window.SS = sessions.map(s => ({
        id: s.session_id, nm: s.name, dt: _fmtDate(s.updated_at), ms: [], _backend: true,
      }));
      if (typeof rSess === "function") rSess();
      if (typeof loadS === "function" && window.SS.length > 0) loadS(window.SS[0].id);
    }

    const reminders = await fetchReminders();
    if (reminders) {
      const remEl = document.getElementById("remList");
      if (remEl) {
        remEl.innerHTML = reminders.map((r, i) =>
          `<div class="rem-item" style="animation:msgIn .3s ease ${i * 0.04}s both${r.done ? ";opacity:.55" : ""}">
            <div class="rem-dot" style="background:${r.done ? "var(--text-hint)" : "var(--accent)"}"></div>
            <div style="flex:1;min-width:0">
              <div class="rem-msg"${r.done ? ' style="text-decoration:line-through"' : ""}>${r.message}</div>
              <div class="rem-sub">${r.repeat}${r.done ? " · 已完成" : ""}</div>
            </div>
            <div class="rem-time">${r.time}</div>
          </div>`
        ).join("");
      }
    }
  }

  // Override: loadS
  const _origLoadS = window.loadS;
  window.loadS = async function (id) {
    if (!_connected) { if (_origLoadS) _origLoadS(id); return; }

    const messages = await fetchMessages(id);
    if (messages) {
      const session = (window.SS || []).find(s => s.id === id);
      if (session) {
        session.ms = messages.map(m => ({
          r: m.role === "user" ? "u" : "a", c: m.content,
          t: _fmtTime(m.timestamp), s: m.sources,
        }));
      }
    }
    if (_origLoadS) _origLoadS(id);
    connectChat(id);
  };

  // Override: newSess
  const _origNewSess = window.newSess;
  window.newSess = async function () {
    if (!_connected) { if (_origNewSess) _origNewSess(); return; }
    const result = await createSession("新对话");
    if (result) {
      window.SS = window.SS || [];
      window.SS.unshift({
        id: result.session_id, nm: result.name, dt: "刚刚",
        ms: [{ r: "a", c: "您好！我是小银，有什么可以帮您的吗？", t: _fmtTime(Date.now() / 1000) }],
        _backend: true,
      });
      if (typeof loadS === "function") loadS(result.session_id);
      if (typeof tSess === "function") tSess();
    }
  };

  // Override: handleSend（核心：通过 WS 发送消息 + 驱动 Pipeline 动画）
  const _origHandleSend = window.handleSend;
  window.handleSend = function () {
    const field = document.getElementById("iField");
    const text = field ? field.value.trim() : "";
    if (!text) return;

    if (typeof addMsg === "function") addMsg("user", text);
    if (field) field.value = "";
    if (typeof updBtn === "function") updBtn();

    if (_connected && _ws && _ws.readyState === WebSocket.OPEN) {
      // 初始化 pending debug 数据
      _pendingDebug = {
        pipeline: [], intents: [], entities: [], rag: null, tools: [], perception: null,
      };
      window.DD = _pendingDebug;

      // 打开 drawer 展示实时过程
      if (!window.drOpen && typeof tDr === "function") tDr();
      if (typeof dT === "function") dT("pipe");

      if (typeof sTyp === "function") sTyp();

      sendMessage(text, { text: true, audio: false, image: false });
    } else {
      // WS 不可用，走 mock
      if (_origHandleSend) _origHandleSend.call(window);
    }
  };

  // Override: resHTL
  const _origResHTL = window.resHTL;
  window.resHTL = function (id, ok) {
    if (_origResHTL) _origResHTL(id, ok);
    if (_connected) sendHITL(!!ok);
  };

  // ── Utilities ──

  function _fmtDate(ts) {
    const diff = Date.now() / 1000 - ts;
    if (diff < 3600) return "刚刚";
    if (diff < 86400) return "今天";
    if (diff < 172800) return "昨天";
    return `${Math.floor(diff / 86400)}天前`;
  }

  function _fmtTime(ts) {
    const d = new Date(ts * 1000);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  function _extractSources(debug) {
    if (!debug) return [];
    const s = new Set();
    if (debug.rag) {
      (debug.rag.graph_results || []).forEach(r => s.add(r.source));
      (debug.rag.vector_results || []).forEach(r => s.add(r.source));
    }
    return [...s];
  }

  function _nodeColor(name) {
    return {
      "Perception": "var(--n-per)", "Supervisor": "var(--n-sup)",
      "Medical Agent": "var(--n-med)", "Device Agent": "var(--n-dev)",
      "Chat Agent": "var(--yellow)", "Emergency Agent": "var(--red)",
      "Synthesizer": "var(--accent)", "Output Guard": "var(--n-grd)",
      "Memory Writer": "var(--text-hint)",
    }[name] || "var(--text-sub)";
  }

  // ── Global API ──
  window.SilverPilotAPI = {
    checkBackend, fetchSessions, createSession, deleteSession,
    fetchMessages, fetchProfile, fetchReminders,
    connectChat, sendMessage, sendHITL, isConnected: () => _connected,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => setTimeout(initWithBackend, 500));
  } else {
    setTimeout(initWithBackend, 500);
  }

  console.log("[Silver Pilot API v2] Connector loaded.");
})();
