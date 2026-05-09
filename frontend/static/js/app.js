// ============================================================
// frontend/static/js/app.js  —  NeuroAgent
// ============================================================

const API = "";

const S = {
  user:           null,
  modelId:        "llama-3.3-70b-versatile",
  models:         [],
  voiceEnabled:   false,
  isThinking:     false,
  recorder:       null,
  audioChunks:    [],
  sidebarOpen:    true,
  selectedModel:  "llama-3.3-70b-versatile",
  // Runtime keys
  geminiKey:      "",
  openaiKey:      "",
  openrouterKey:  "",
  sarvamKey:      "",
  agentMode:      "default",
};

// ── Boot ──────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", async () => {
  await loadModels();
  await restoreSession();
  document.getElementById("username-input")
    .addEventListener("keydown", e => { if (e.key === "Enter") handleLogin(); });
  document.getElementById("user-input")
    .addEventListener("input", function () { autoResize(this); });
});

async function loadModels() {
  try {
    const r = await fetch(`${API}/api/models`);
    const d = await r.json();
    S.models = d.models || [];
  } catch (e) { console.warn("loadModels:", e); }
}

async function restoreSession() {
  try {
    const r = await fetch(`${API}/api/session`, { credentials: "include" });
    if (r.ok) {
      const d = await r.json();
      if (d.status === "ok") {
        S.user         = { user_id: d.user_id, username: d.username };
        S.modelId      = d.model_id || "llama-3.3-70b-versatile";
        S.voiceEnabled = d.voice_enabled;
        S.agentMode    = d.agent_mode || "default";
        showChat();
        renderAgentMode();
        return;
      }
    }
  } catch (e) {}
  showLogin();
}

// ── Login ─────────────────────────────────────────────────────
async function handleLogin() {
  const inp  = document.getElementById("username-input");
  const btn  = document.getElementById("login-btn");
  const err  = document.getElementById("login-err");
  const name = inp.value.trim();
  err.textContent = "";

  if (!name || name.length < 2) { err.textContent = "Username must be at least 2 characters."; return; }

  btn.disabled = true;
  document.getElementById("login-btn-text").textContent = "Connecting…";

  try {
    const r = await fetch(`${API}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username: name }),
    });
    const d = await r.json();

    if (d.status === "ok") {
      S.user    = { user_id: d.user_id, username: d.username };
      S.modelId = d.model_id || "llama-3.3-70b-versatile";
      openModelModal(true);  // Show model selector right after login
    } else {
      err.textContent = d.message || "Login failed.";
    }
  } catch (e) {
    err.textContent = "Cannot connect to server. Is it running?";
  }

  btn.disabled = false;
  document.getElementById("login-btn-text").textContent = "Continue →";
}

async function handleLogout() {
  await fetch(`${API}/api/logout`, { method: "POST", credentials: "include" });
  S.user = null; S.geminiKey = S.openaiKey = S.openrouterKey = S.sarvamKey = "";
  document.getElementById("messages").innerHTML = "";
  showLogin();
  showToast("Logged out.");
}

// ── Screen Transitions ────────────────────────────────────────
function showLogin() {
  document.getElementById("login-screen").classList.add("active");
  document.getElementById("chat-screen").classList.remove("active");
  document.getElementById("model-modal").classList.add("hidden");
}

function showChat() {
  document.getElementById("login-screen").classList.remove("active");
  document.getElementById("chat-screen").classList.add("active");
  document.getElementById("model-modal").classList.add("hidden");
  renderSidebarUser();
  renderActiveModel();
  updateVoiceBtn();
  checkCaps();
  loadHistory();
  setTimeout(() => document.getElementById("user-input")?.focus(), 80);
}

async function loadHistory() {
  try {
    const r = await fetch(`${API}/api/history?limit=50`, { credentials:"include" });
    const d = await r.json();
    if (!r.ok || d.status !== "ok") return;

    const c = document.getElementById("messages");
    c.innerHTML = "";
    for (const m of (d.history || [])) {
      if (m.role === "user") appendMsg("user", m.content || "", S.user?.username || "You");
      else if (m.role === "assistant") appendMsg("assistant", m.content || "", "NeuroAgent", m.model_used || "", 0, "");
    }
    if (!(d.history || []).length) {
      // Restore welcome if no history
      c.innerHTML = `
        <div class="welcome" id="welcome">
          <div class="wg">⟳</div>
          <h2>System Online</h2>
          <p>Ask anything — web search, Gmail, code execution, or deep research.</p>
          <div class="qgrid">
            <button class="qbtn" onclick="quickPrompt('What are the latest AI news today?')">🔍 Latest AI news</button>
            <button class="qbtn" onclick="quickPrompt('Read my 5 most recent emails')">📧 Read emails</button>
            <button class="qbtn" onclick="quickPrompt('Research quantum computing in 2025')">🔬 Deep research</button>
            <button class="qbtn" onclick="quickPrompt('What tools and capabilities do you have?')">💡 Your capabilities</button>
          </div>
        </div>`;
    }
  } catch (e) { /* ignore */ }
}

// ── Model Modal ───────────────────────────────────────────────
function openModelModal(afterLogin = false) {
  S.selectedModel = S.modelId;
  document.getElementById("modal-greet").textContent = afterLogin && S.user
    ? `Welcome, ${S.user.username}! Pick an AI model to get started.`
    : "Select a model. You can switch anytime during the chat.";

  buildModelGrid();
  filterModels("all", document.querySelector(".ftab[data-f='all']"));
  hideKeyPanels();
  document.getElementById("model-modal").classList.remove("hidden");
  document.getElementById("modal-err").textContent = "";
}

function buildModelGrid() {
  const grid = document.getElementById("mgrid");
  grid.innerHTML = "";
  S.models.forEach(m => {
    const card = document.createElement("div");
    card.className = "mc" + (m.id === S.selectedModel ? " sel" : "");
    card.dataset.id       = m.id;
    card.dataset.provider = m.provider;
    const mode = (m.mode || "").toLowerCase() === "reasoning" ? "REASONING" : "FAST";
    card.innerHTML = `
      <div class="mc-top">
        <div class="mc-name">${m.label} <span class="mc-mode ${mode === "REASONING" ? "reason" : "fast"}">${mode}</span></div>
        <span class="mc-prov p-${m.provider}">${provLabel(m.provider)}</span>
      </div>
      <div class="mc-desc">${m.description}</div>
      <div class="mc-foot"><span class="mc-ctx">ctx ${m.context || "—"}</span></div>
      <div class="mc-ck">
        <svg viewBox="0 0 12 12" fill="none" stroke="#030712" stroke-width="2.2" width="10"><path d="M2 6l3 3 5-5"/></svg>
      </div>`;
    card.addEventListener("click", () => {
      document.querySelectorAll(".mc").forEach(c => c.classList.remove("sel"));
      card.classList.add("sel");
      S.selectedModel = m.id;
      showKeyPanel(m.provider);
    });
    grid.appendChild(card);
  });
}

function provLabel(p) {
  return { groq:"Groq", gemini:"Gemini", openai:"OpenAI", openrouter:"OpenRouter" }[p] || p;
}

function filterModels(f, btn) {
  document.querySelectorAll(".ftab").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  document.querySelectorAll(".mc").forEach(c => {
    c.classList.toggle("hidden", f !== "all" && c.dataset.provider !== f);
  });
  // Show key panel if filtering by provider that needs one
  if (["gemini","openai","openrouter"].includes(f)) showKeyPanel(f);
  else {
    const sel = S.models.find(m => m.id === S.selectedModel);
    sel ? showKeyPanel(sel.provider) : hideKeyPanels();
  }
}

function showKeyPanel(provider) {
  hideKeyPanels();
  const panels = { gemini:"kp-gemini", openai:"kp-openai", openrouter:"kp-openrouter" };
  if (panels[provider]) document.getElementById(panels[provider]).classList.remove("hidden");
}

function hideKeyPanels() {
  ["kp-gemini","kp-openai","kp-openrouter"].forEach(id =>
    document.getElementById(id).classList.add("hidden"));
}

async function confirmModel() {
  const modelId = S.selectedModel;
  const model   = S.models.find(m => m.id === modelId);
  const errEl   = document.getElementById("modal-err");
  errEl.textContent = "";

  // Collect keys
  const gKey  = document.getElementById("inp-gemini-key").value.trim();
  const oKey  = document.getElementById("inp-openai-key").value.trim();
  const orKey = document.getElementById("inp-openrouter-key").value.trim();

  // Validate required keys
  if (model?.provider === "gemini"     && !gKey  && !S.geminiKey)    { errEl.textContent = "Gemini API key required.";    return; }
  if (model?.provider === "openai"     && !oKey  && !S.openaiKey)    { errEl.textContent = "OpenAI API key required.";    return; }
  if (model?.provider === "openrouter" && !orKey && !S.openrouterKey){ errEl.textContent = "OpenRouter API key required.";return; }

  if (gKey)  S.geminiKey     = gKey;
  if (oKey)  S.openaiKey     = oKey;
  if (orKey) S.openrouterKey = orKey;

  const btn = document.getElementById("modal-ok");
  btn.disabled = true;
  btn.textContent = "Saving…";

  try {
    const r = await fetch(`${API}/api/model/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        model_id:           modelId,
        gemini_api_key:     S.geminiKey,
        openai_api_key:     S.openaiKey,
        openrouter_api_key: S.openrouterKey,
        sarvam_api_key:     S.sarvamKey,
      }),
    });
    const d = await r.json();
    if (d.status === "ok") {
      S.modelId = modelId;
      showChat();
      showToast(`Model: ${model?.label || modelId}`, "ok");
    } else {
      errEl.textContent = d.message || "Failed to set model.";
    }
  } catch (e) { errEl.textContent = "Connection error."; }

  btn.disabled = false;
  btn.textContent = "Start Chatting →";
}

// ── Sidebar ───────────────────────────────────────────────────
function renderSidebarUser() {
  const n = S.user?.username || "—";
  document.getElementById("sb-av").textContent = n[0].toUpperCase();
  document.getElementById("sb-un").textContent = n;
}

function renderActiveModel() {
  const m = S.models.find(x => x.id === S.modelId);
  if (!m) return;
  document.getElementById("am-n").textContent      = m.label;
  document.getElementById("am-m").textContent      = `${provLabel(m.provider)} · ctx ${m.context || "—"}`;
  document.getElementById("tb-model").textContent  = m.label;
  const badge = document.getElementById("am-badge");
  badge.textContent = provLabel(m.provider).toUpperCase();
  badge.className   = `am-badge p-${m.provider}`;
}

function toggleSidebar() {
  const sb   = document.getElementById("sidebar");
  const tab  = document.getElementById("sb-tab");
  const mob  = window.innerWidth <= 680;
  if (mob) { sb.classList.toggle("mobile-open"); return; }
  S.sidebarOpen = !S.sidebarOpen;
  sb.classList.toggle("collapsed", !S.sidebarOpen);
  tab.classList.toggle("show", !S.sidebarOpen);
}

async function checkCaps() {
  try {
    const r = await fetch(`${API}/api/health`, { credentials:"include" });
    const d = await r.json();
    setCap("cap-memory", d.memory);
    setCap("cap-gmail",  d.gmail);
    setCap("cap-voice",  d.voice);
  } catch {}
}

function setCap(id, on) {
  const el  = document.getElementById(id);
  if (!el) return;
  const dot = el.querySelector(".cap-dot");
  const val = el.querySelector(".cap-v");
  dot.classList.toggle("on", on);
  val.textContent = on ? "ON" : "OFF";
  val.classList.toggle("on", on);
}

// ── Sarvam Panel ──────────────────────────────────────────────
function saveSarvamKey() {
  const k = document.getElementById("sarvam-key-inp").value.trim();
  if (!k) { showToast("Enter a Sarvam API key first.", "err"); return; }
  S.sarvamKey = k;
  // Persist to session
  fetch(`${API}/api/model/select`, {
    method:"POST", headers:{"Content-Type":"application/json"},
    credentials:"include",
    body: JSON.stringify({ model_id: S.modelId, sarvam_api_key: k }),
  });
  setCap("cap-sarvam", true);
  showToast("Sarvam API key saved!", "ok");
}

async function runSarvamTTS() {
  const text    = document.getElementById("sarvam-tts-text").value.trim();
  const lang    = document.getElementById("sarvam-lang").value;
  const speaker = document.getElementById("sarvam-speaker").value;
  const result  = document.getElementById("sarvam-tts-result");

  if (!text) { showToast("Enter text to convert.", "err"); return; }

  const btn = document.getElementById("sarvam-tts-btn");
  btn.disabled = true; btn.textContent = "Generating…";
  result.classList.add("hidden");

  try {
    const r = await fetch(`${API}/api/sarvam/tts`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      credentials:"include",
      body: JSON.stringify({ text, language: lang, speaker, api_key: S.sarvamKey || undefined }),
    });
    const d = await r.json();
    if (d.status === "ok") {
      // Decode base64 WAV and play
      const bytes    = Uint8Array.from(atob(d.audio_base64), c => c.charCodeAt(0));
      const blob     = new Blob([bytes], { type:"audio/wav" });
      const url      = URL.createObjectURL(blob);
      const audio    = new Audio(url);
      audio.play();
      audio.onended  = () => URL.revokeObjectURL(url);

      result.textContent = `✅ Audio generated! Language: ${lang} | Speaker: ${speaker}`;
      result.classList.remove("hidden");
      showToast("Audio playing!", "ok");
    } else {
      result.textContent = `❌ ${d.message}`;
      result.classList.remove("hidden");
    }
  } catch (e) {
    result.textContent = `❌ Error: ${e.message}`;
    result.classList.remove("hidden");
  }

  btn.disabled = false; btn.textContent = "🎵 Generate Audio";
}

async function runSarvamTranslate() {
  const text = document.getElementById("sarvam-tr-text").value.trim();
  const src  = document.getElementById("sarvam-src-lang").value;
  const tgt  = document.getElementById("sarvam-tgt-lang").value;
  const res  = document.getElementById("sarvam-tr-result");

  if (!text) { showToast("Enter text to translate.", "err"); return; }

  const btn = document.getElementById("sarvam-tr-btn");
  btn.disabled = true; btn.textContent = "Translating…";
  res.classList.add("hidden");

  try {
    const r = await fetch(`${API}/api/sarvam/translate`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      credentials:"include",
      body: JSON.stringify({ text, source_language: src, target_language: tgt, api_key: S.sarvamKey || undefined }),
    });
    const d = await r.json();
    if (d.status === "ok") {
      res.textContent = d.translated_text;
      res.classList.remove("hidden");
      showToast("Translated!", "ok");
    } else {
      res.textContent = `❌ ${d.message}`;
      res.classList.remove("hidden");
    }
  } catch (e) {
    res.textContent = `❌ Error: ${e.message}`;
    res.classList.remove("hidden");
  }

  btn.disabled = false; btn.textContent = "🌐 Translate";
}

// ── Chat ──────────────────────────────────────────────────────
function formatTrace(trace) {
  if (!Array.isArray(trace) || !trace.length) return "";
  const parts = [];
  for (const t of trace.slice(0, 8)) {
    if (t?.type === "tool_call") {
      const k = Array.isArray(t.arg_keys) && t.arg_keys.length ? `(${t.arg_keys.join(",")})` : "";
      parts.push(`→ ${t.name || "tool"}${k}`);
    } else if (t?.type === "tool_result") {
      parts.push(`✓ ${t.name || "result"}`);
    }
  }
  return parts.join(" ");
}

async function sendMessage() {
  const inp  = document.getElementById("user-input");
  const text = inp.value.trim();
  if (!text || S.isThinking) return;

  inp.value = ""; autoResize(inp);
  document.getElementById("welcome")?.remove();
  appendMsg("user", text, S.user?.username || "You");
  const thId = appendThinking();
  setStatus("thinking");
  S.isThinking = true;
  document.getElementById("send-btn").disabled = true;

  try {
    const r = await fetch(`${API}/api/chat`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      credentials:"include",
      body: JSON.stringify({ message: text, model_id: S.modelId }),
    });
    const d = await r.json();
    removeEl(thId);
    if (d.status === "ok") {
      appendMsg("assistant", d.reply, "NeuroAgent", d.model, d.steps, formatTrace(d.trace));
      document.getElementById("tb-intent").textContent = (d.intent || "general").toUpperCase();
      if (d.agent_mode) { S.agentMode = d.agent_mode; renderAgentMode(); }
      if (S.voiceEnabled) speakText(d.reply);
    } else {
      appendMsg("assistant", `⚠️ ${d.message}`, "NeuroAgent");
    }
  } catch (e) {
    removeEl(thId);
    appendMsg("assistant", `⚠️ Connection error: ${e.message}`, "NeuroAgent");
  }

  S.isThinking = false;
  document.getElementById("send-btn").disabled = false;
  setStatus("done");
  setTimeout(() => setStatus("idle"), 2800);
}

function quickPrompt(t) {
  document.getElementById("user-input").value = t;
  sendMessage();
}

function handleKey(e) {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 130) + "px";
}

// ── Message Rendering ─────────────────────────────────────────
function appendMsg(role, content, label, model = "", steps = 0, trace = "") {
  const c   = document.getElementById("messages");
  const id  = "m" + Date.now();
  const el  = document.createElement("div");
  el.className = `msg ${role}`;
  el.id = id;

  const time = new Date().toLocaleTimeString([], { hour:"2-digit", minute:"2-digit" });
  const av   = role === "user" ? "👤" : "⬡";

  let meta = `<strong>${label}</strong><span>${time}</span>`;
  if (role === "assistant" && model) {
    const info = S.models.find(m => m.id === model);
    meta += `<span>${info?.label || model}</span>`;
    if (steps > 0) meta += `<span>${steps} step${steps !== 1 ? "s" : ""}</span>`;
  }

  const ttsBtn = role === "assistant"
    ? `<button class="tts-btn" onclick="speakText(this.closest('.msg').querySelector('.msg-content').textContent)">🔊 Play</button>`
    : "";

  const think = role === "assistant" && trace
    ? `<div class="msg-think">${esc(trace)}</div>`
    : "";

  el.innerHTML = `
    <div class="msg-av">${av}</div>
    <div class="msg-body">
      <div class="msg-meta">${meta}</div>
      <div class="msg-content">${esc(content)}</div>
      ${think}
      ${ttsBtn}
    </div>`;
  c.appendChild(el);
  c.scrollTop = c.scrollHeight;
  return id;
}

function appendThinking() {
  const c  = document.getElementById("messages");
  const id = "t" + Date.now();
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.id = id;
  el.innerHTML = `
    <div class="msg-av">⬡</div>
    <div class="msg-body">
      <div class="msg-meta"><strong>NeuroAgent</strong><span>thinking…</span></div>
      <div class="msg-content"><span class="dots"><span></span><span></span><span></span></span></div>
    </div>`;
  c.appendChild(el);
  c.scrollTop = c.scrollHeight;
  return id;
}

function removeEl(id) { document.getElementById(id)?.remove(); }

function esc(t) {
  return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\n/g,"<br/>");
}

function setStatus(s) {
  const led  = document.getElementById("tb-led");
  const st   = document.getElementById("tb-st");
  if (!led || !st) return;
  led.className = `tb-led ${s}`;
  st.textContent = { idle:"Idle", thinking:"Thinking…", done:"Done" }[s] || s;
}

function renderAgentMode() {
  const el = document.getElementById("tb-mode");
  if (!el) return;
  el.textContent = (S.agentMode || "default").toUpperCase();
}

function toggleAgentMenu() {
  const m = document.getElementById("agent-menu");
  if (!m) return;
  m.classList.toggle("hidden");
}

async function setAgentMode(mode) {
  const m = (mode || "default").toLowerCase();
  try {
    const r = await fetch(`${API}/api/agent/mode`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      credentials:"include",
      body: JSON.stringify({ agent_mode: m }),
    });
    const d = await r.json();
    if (d.status === "ok") {
      S.agentMode = d.agent_mode || m;
      renderAgentMode();
      document.getElementById("agent-menu")?.classList.add("hidden");
      showToast(`Agent mode: ${(S.agentMode || "default").toUpperCase()}`, "ok");
    } else {
      showToast(d.message || "Could not set agent mode.", "err");
    }
  } catch (e) {
    showToast("Agent mode error.", "err");
  }
}

async function clearHistory() {
  if (!confirm("Clear all conversation history?")) return;
  await fetch(`${API}/api/history/clear`, { method:"POST", credentials:"include" });
  document.getElementById("messages").innerHTML = `
    <div class="welcome" id="welcome">
      <div class="wg">⬡</div><h2>History Cleared</h2><p>Start a fresh conversation.</p>
    </div>`;
  showToast("History cleared.", "ok");
}

// ── Voice Input ───────────────────────────────────────────────
async function startVoice() {
  if (!navigator.mediaDevices?.getUserMedia) { showToast("Mic not supported.", "err"); return; }
  try {
    const stream   = await navigator.mediaDevices.getUserMedia({ audio: true });
    S.audioChunks  = [];
    S.recorder     = new MediaRecorder(stream);
    S.recorder.ondataavailable = e => S.audioChunks.push(e.data);
    S.recorder.onstop          = processVoice;
    S.recorder.start();
    document.getElementById("voice-btn").classList.add("rec");
    document.getElementById("voverlay").classList.remove("hidden");
  } catch (e) { showToast("Mic access denied.", "err"); }
}

function stopVoice() {
  S.recorder?.stop();
  S.recorder?.stream?.getTracks().forEach(t => t.stop());
  document.getElementById("voice-btn").classList.remove("rec");
  document.getElementById("voverlay").classList.add("hidden");
}

async function processVoice() {
  if (!S.audioChunks.length) return;
  const blob = new Blob(S.audioChunks, { type:"audio/wav" });
  const fd   = new FormData();
  fd.append("audio", blob, "rec.wav");
  showToast("Transcribing…");
  try {
    const r = await fetch(`${API}/api/voice/input`, { method:"POST", credentials:"include", body:fd });
    const d = await r.json();
    if (d.transcription) {
      const inp = document.getElementById("user-input");
      inp.value = d.transcription; autoResize(inp);
      showToast("Transcribed!", "ok");
    } else showToast("Could not transcribe.", "err");
  } catch { showToast("Transcription error.", "err"); }
  S.audioChunks = [];
}

// ── Voice Output ──────────────────────────────────────────────
async function speakText(text) {
  if (!text) return;
  try {
    const r = await fetch(`${API}/api/voice/output`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      credentials:"include", body:JSON.stringify({ text: text.slice(0, 500) }),
    });
    const d = await r.json();
    if (d.audio_base64) {
      const bytes = Uint8Array.from(atob(d.audio_base64), c => c.charCodeAt(0));
      const mime  = d.audio_mime || "audio/mpeg";
      const url   = URL.createObjectURL(new Blob([bytes], { type: mime }));
      const a     = new Audio(url);
      a.play(); a.onended = () => URL.revokeObjectURL(url);
    }
  } catch (e) { console.warn("TTS:", e); }
}

async function toggleVoice() {
  S.voiceEnabled = !S.voiceEnabled;
  await fetch(`${API}/api/voice/toggle`, {
    method:"POST", headers:{"Content-Type":"application/json"},
    credentials:"include", body:JSON.stringify({ enabled: S.voiceEnabled }),
  });
  updateVoiceBtn();
  showToast(S.voiceEnabled ? "Voice output ON" : "Voice output OFF");
}

function updateVoiceBtn() {
  const b = document.getElementById("voice-btn-sb");
  if (b) b.textContent = S.voiceEnabled ? "🔇 Disable Voice" : "🎙 Enable Voice";
}

// ── Toast ─────────────────────────────────────────────────────
let _tt = null;
function showToast(msg, type = "") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className   = `toast show ${type}`;
  clearTimeout(_tt);
  _tt = setTimeout(() => { el.className = "toast"; }, 3000);
}

// ── Misc ──────────────────────────────────────────────────────
document.addEventListener("click", e => {
  if (window.innerWidth > 680) return;
  const sb  = document.getElementById("sidebar");
  const btn = document.querySelector(".tb-menu");
  if (sb?.classList.contains("mobile-open") && !sb.contains(e.target) && !btn?.contains(e.target))
    sb.classList.remove("mobile-open");
});

document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    document.getElementById("sidebar")?.classList.remove("mobile-open");
    const mm = document.getElementById("model-modal");
    if (!mm.classList.contains("hidden") && S.modelId) closeModal();
  }
});

function closeModal() {
  document.getElementById("model-modal").classList.add("hidden");
}
