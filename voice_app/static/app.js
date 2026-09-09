import { RetellWebClient } from "https://esm.sh/retell-client-js-sdk";

const client = new RetellWebClient();
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const els = {
  path: document.getElementById("pptxPath"),
  loadBtn: document.getElementById("loadBtn"),
  sampleBtn: document.getElementById("sampleBtn"),
  reindexQaBtn: document.getElementById("reindexQaBtn"),
  startBtn: document.getElementById("startBtn"),
  stopBtn: document.getElementById("stopBtn"),
  endShowBtn: document.getElementById("endShowBtn"),
  directorNextBtn: document.getElementById("directorNextBtn"),
  localNextBtn: document.getElementById("localNextBtn"),
  presenterView: document.getElementById("presenterView"),
  startVoice: document.getElementById("startVoice"),
  callState: document.getElementById("callState"),
  deckMeta: document.getElementById("deckMeta"),
  slideList: document.getElementById("slideList"),
  transcript: document.getElementById("transcript"),
  toolLog: document.getElementById("toolLog"),
  liveStatus: document.getElementById("liveStatus"),
  configHint: document.getElementById("configHint"),
  retellFields: document.getElementById("retellFields"),
  bridgeFields: document.getElementById("bridgeFields"),
  avatarStage: document.getElementById("avatarStage"),
  avatarState: document.getElementById("avatarState"),
  agentAvatar: document.getElementById("agentAvatar"),
  agentDialogue: document.getElementById("agentDialogue"),
  userDialogue: document.getElementById("userDialogue"),
  viewToggle: document.getElementById("viewToggle"),
  presenterModeBtn: document.getElementById("presenterModeBtn"),
  arrangeBtn: document.getElementById("arrangeBtn"),
  presenterSurface: document.getElementById("presenterSurface"),
  maintenanceShell: document.getElementById("maintenanceShell"),
};

let loaded = false;
let inCall = false;
let currentCallId = null;
let slidePauseMs = 800;
let processingResetTimer = null;

function setCallState(text, className) {
  els.callState.textContent = text;
  els.callState.className = `call-pill ${className || ""}`.trim();
}

function setAvatarSpeaking(speaking) {
  const isSpeaking = Boolean(speaking);
  if (processingResetTimer) {
    clearTimeout(processingResetTimer);
    processingResetTimer = null;
  }
  if (isSpeaking && !prefersReducedMotion.matches) {
    const playback = els.agentAvatar.play();
    if (playback) {
      playback.catch((error) => console.warn("Avatar video could not play:", error));
    }
  } else {
    els.agentAvatar.pause();
    const rewind = () => {
      try {
        els.agentAvatar.currentTime = 0;
      } catch (error) {
        console.warn("Avatar video could not rewind:", error);
      }
    };
    if (els.agentAvatar.readyState >= HTMLMediaElement.HAVE_METADATA) {
      rewind();
    } else {
      els.agentAvatar.addEventListener("loadedmetadata", rewind, { once: true });
    }
  }
  els.avatarStage.dataset.speaking = String(isSpeaking);
  els.avatarStage.dataset.processing = "false";
  els.avatarStage.setAttribute("aria-busy", "false");
  els.avatarStage.setAttribute(
    "aria-label",
    isSpeaking ? "Aira is speaking" : "Aira is standing by",
  );
  els.avatarState.lastChild.textContent = isSpeaking ? " Speaking" : " Standing by";
}

function setAvatarListening() {
  setAvatarSpeaking(false);
  els.avatarStage.setAttribute("aria-label", "Aira is listening");
  els.avatarState.lastChild.textContent = " Listening";
}

function setAvatarProcessing() {
  setAvatarSpeaking(false);
  els.avatarStage.dataset.processing = "true";
  els.avatarStage.setAttribute("aria-busy", "true");
  els.avatarStage.setAttribute("aria-label", "Aira is preparing the next slide");
  els.avatarState.lastChild.textContent = " Preparing next slide…";
  processingResetTimer = setTimeout(() => {
    processingResetTimer = null;
    if (inCall && els.avatarStage.dataset.speaking !== "true") {
      setAvatarListening();
      setCallState("Listening", "live");
    }
  }, Math.max(3000, slidePauseMs * 4));
}

function setViewMode(view, updateUrl = true) {
  const mode = view === "maintenance" ? "maintenance" : "presenter";
  document.body.dataset.view = mode;
  els.presenterSurface.setAttribute("aria-hidden", String(mode !== "presenter"));
  els.maintenanceShell.setAttribute("aria-hidden", String(mode !== "maintenance"));
  const openingMaintenance = mode === "presenter";
  els.viewToggle.setAttribute(
    "aria-label",
    openingMaintenance ? "Open maintenance console" : "Return to presenter",
  );
  els.viewToggle.title = openingMaintenance
    ? "Maintenance console (Ctrl+Shift+M)"
    : "Return to presenter (Ctrl+Shift+M)";
  if (updateUrl) {
    const url = new URL(window.location.href);
    if (mode === "maintenance") {
      url.searchParams.set("view", "maintenance");
    } else {
      url.searchParams.delete("view");
    }
    window.history.replaceState({}, "", url);
  }
}

function renderDialogue(turns) {
  let latestAgent = "";
  let latestUser = "";
  for (const turn of turns || []) {
    const content = String(turn?.content || "").trim();
    if (!content) continue;
    if (turn.role === "agent") {
      latestAgent = content;
    } else if (turn.role === "user") {
      latestUser = content;
    }
  }
  els.agentDialogue.textContent = latestAgent || "Ready when you are.";
  els.userDialogue.textContent = latestUser || "—";
}

function appendLog(node, role, text) {
  const p = document.createElement("p");
  p.className = role;
  p.textContent = text;
  node.appendChild(p);
  node.scrollTop = node.scrollHeight;
}

async function api(path, options) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.error || response.statusText);
  }
  return data;
}

function renderSlides(slides, current) {
  els.slideList.innerHTML = "";
  for (const slide of slides || []) {
    const li = document.createElement("li");
    if (slide.index === current) li.classList.add("active");
    const index = document.createElement("span");
    index.className = "idx";
    index.textContent = String(slide.index ?? "");
    const title = document.createElement("span");
    title.textContent = slide.title || "(untitled)";
    li.append(index, title);
    els.slideList.appendChild(li);
  }
}

function renderStatus(status) {
  if (!status) {
    els.liveStatus.textContent = "";
    return;
  }
  const notes = (status.notes || "").trim();
  els.liveStatus.textContent = status.running
    ? `Slide ${status.slide}/${status.slide_count} · ${status.title || "(untitled)"} · ${status.state}${notes ? `\nNotes: ${notes}` : ""}`
    : `Deck loaded · ${status.slide_count} slides · slideshow not running`;
}

function renderDeck(snapshot) {
  loaded = Boolean(snapshot.loaded || snapshot.path);
  const name = snapshot.name || "Deck";
  const count = snapshot.status?.slide_count || snapshot.slides?.length || 0;
  els.deckMeta.textContent = loaded ? `${name} · ${count} slides` : "No file loaded.";
  renderSlides(snapshot.slides, snapshot.status?.slide);
  renderStatus(snapshot.status);
  els.startBtn.disabled = !loaded || inCall;
  els.endShowBtn.disabled = !loaded;
  els.directorNextBtn.disabled = !loaded;
  els.localNextBtn.disabled = !loaded;
  els.reindexQaBtn.disabled = !loaded;
}

function renderConfig(cfg) {
  const configuredPause = Number(cfg.slide_pause_ms);
  if (Number.isFinite(configuredPause) && configuredPause >= 0) {
    slidePauseMs = configuredPause;
  }
  const tunnelLabel = cfg.director_public_url
    ? `${cfg.director_tunnel_live ? "Live" : "Starting / unverified"}${cfg.director_auto_tunnel ? " · automatic" : ""} · ${cfg.director_public_url}`
    : "No public URL. Enable DIRECTOR_AUTO_TUNNEL or set DIRECTOR_PUBLIC_URL.";
  const qa = cfg.qa || {};
  const qaLabel = qa.state === "ready"
    ? `${qa.mode === "azure_rag" ? "Azure RAG" : "Safe abstention only"} · ${qa.records || 0} records · ${qa.backend || "local"}`
    : qa.state === "indexing"
      ? "Indexing deck and knowledge…"
      : qa.error
        ? `Index error · ${qa.error}`
        : "Not indexed — load a deck";
  const bridgeRows = [
    ["Python director ingress", tunnelLabel],
    ["Webhook auth", cfg.director_webhook_auth_configured ? "Bearer token configured" : "Not configured"],
    ["Retell functions", cfg.retell_director_sync_ok === true ? "URLs and auth synced" : (cfg.retell_director_sync_error || "Sync pending")],
    ["deliver-next", cfg.director_deliver_next_url || "Available after the public URL starts"],
    ["handle-question", cfg.director_handle_question_url || "Available after the public URL starts"],
    ["Q&A knowledge", qaLabel],
    ["Talk script", `${cfg.script_beats_total || 0} beats · ${cfg.script_source || "not loaded"}`],
    ["Pause between slides", `${cfg.slide_pause_ms ?? 800} ms  (set SLIDE_PAUSE_MS in .env)`],
  ];
  els.bridgeFields.innerHTML = bridgeRows
    .map(([key, value]) => `<dt>${key}</dt><dd>${value}</dd>`)
    .join("");
  const mcpMatch = cfg.mcp_url_match
    ? "Matches this PC (fallback only)"
    : cfg.retell_mcp_url
      ? `Retell still has ${cfg.retell_mcp_url}`
      : "Not used by the scripted Python director";
  const rows = [
    ["Agent", cfg.agent_configured ? `${cfg.agent_name || ""} ${cfg.agent_id}`.trim() : "Optional for slide-bridge smoke test. Needed for voice."],
    ["Fallback MCP", cfg.mcp_url || "No public URL yet."],
    ["MCP in Retell", mcpMatch],
    ["end_call tool", cfg.has_end_call ? "ON — delete it in Retell → Functions." : "Off"],
  ];
  els.retellFields.innerHTML = rows
    .map(([key, value]) => `<dt>${key}</dt><dd>${value}</dd>`)
    .join("");
  if (qa.state === "indexing") {
    els.configHint.textContent = "Q&A is indexing the loaded deck and knowledge sources.";
  } else if (qa.state === "error") {
    els.configHint.textContent = `Q&A index error: ${qa.error}. Only safe abstention remains available.`;
  } else if (!cfg.sample_deck_path) {
    els.configHint.textContent = "Sample deck missing. Run: python -m voice_app.sample_pack";
  } else if (cfg.agent_configured) {
    els.configHint.textContent = "Load a deck, then press Start. Allow the microphone when the browser asks.";
  } else {
    els.configHint.textContent = "You can load the sample and test the Python director without Retell keys. Voice Start needs .env RETELL_* values.";
  }
  window.__sampleDeckPath = cfg.sample_deck_path || "";
}

async function loadDeck() {
  const path = els.path.value.trim();
  if (!path) {
    els.deckMeta.textContent = "Enter a full .pptx path first.";
    return;
  }
  els.loadBtn.disabled = true;
  try {
    const snapshot = await api("/api/session/load", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
    renderDeck(snapshot);
    if (snapshot.qa_index?.state === "indexing") {
      els.configHint.textContent = "Deck loaded. Q&A is indexing in the background.";
    }
  } catch (error) {
    els.deckMeta.textContent = error.message;
  } finally {
    els.loadBtn.disabled = false;
  }
}

async function startCall() {
  els.startBtn.disabled = true;
  setAvatarSpeaking(false);
  setCallState("Connecting…");
  try {
    const created = await api("/api/session/start-call", {
      method: "POST",
      body: JSON.stringify({
        presenter_view: els.presenterView.checked,
        voice: els.startVoice.checked,
      }),
    });
    renderStatus(created.status);
    currentCallId = created.call_id || null;
    if (currentCallId) {
      appendLog(els.transcript, "tool", `Call ${currentCallId}`);
    }
    if (created.director?.ok) {
      appendLog(els.toolLog, "tool", "Python director session reset");
    }
    if (created.access_token) {
      await client.startCall({ accessToken: created.access_token });
      setViewMode("presenter");
    } else {
      inCall = false;
      els.startBtn.disabled = !loaded;
      els.stopBtn.disabled = true;
      setCallState("Slideshow only");
      appendLog(els.transcript, "tool", "Slideshow started without Retell. Trigger the Python director to advance.");
      setViewMode("presenter");
    }
  } catch (error) {
    setCallState("Idle");
    els.configHint.textContent = error.message;
    els.startBtn.disabled = !loaded;
  }
}

function stopCall() {
  setAvatarSpeaking(false);
  try {
    client.stopCall();
  } catch (error) {
    console.error(error);
  }
}

async function endShow() {
  try {
    const snapshot = await api("/api/session/end-show", { method: "POST" });
    renderStatus(snapshot.status);
  } catch (error) {
    els.configHint.textContent = error.message;
  }
}

client.on("call_started", () => {
  inCall = true;
  setAvatarListening();
  setViewMode("presenter");
  els.stopBtn.disabled = false;
  els.startBtn.disabled = true;
  setCallState("Live", "live");
});

client.on("call_ready", () => {
  setAvatarListening();
  setCallState("Agent ready", "live");
});
let speechIdleTimer = null;

function reportSpeech(speaking) {
  if (speaking) {
    if (speechIdleTimer) {
      clearTimeout(speechIdleTimer);
      speechIdleTimer = null;
    }
    api("/api/session/speech", { method: "POST", body: JSON.stringify({ speaking: true }) }).catch(() => {});
    return;
  }
  if (speechIdleTimer) clearTimeout(speechIdleTimer);
  speechIdleTimer = setTimeout(() => {
    speechIdleTimer = null;
    api("/api/session/speech", { method: "POST", body: JSON.stringify({ speaking: false }) })
      .then(() => appendLog(els.toolLog, "tool", "Agent stopped talking"))
      .catch(() => {});
  }, slidePauseMs);
}

client.on("agent_start_talking", () => {
  setAvatarSpeaking(true);
  setCallState("Agent speaking", "talking");
  reportSpeech(true);
});
client.on("agent_stop_talking", () => {
  if (inCall) {
    setAvatarProcessing();
    setCallState("Preparing next slide…", "processing");
  } else {
    setAvatarSpeaking(false);
  }
  reportSpeech(false);
});

client.on("update", (update) => {
  const parts = update?.transcript || [];
  renderDialogue(parts);
  els.transcript.innerHTML = "";
  for (const turn of parts) {
    appendLog(els.transcript, turn.role === "agent" ? "agent" : "user", `${turn.role}: ${turn.content}`);
  }
});

client.on("call_ended", () => {
  inCall = false;
  setAvatarSpeaking(false);
  els.stopBtn.disabled = true;
  els.startBtn.disabled = !loaded;
  setCallState("Idle");
  if (speechIdleTimer) {
    clearTimeout(speechIdleTimer);
    speechIdleTimer = null;
  }
  api("/api/session/speech", { method: "POST", body: JSON.stringify({ speaking: false }) }).catch(() => {});
  if (currentCallId) {
    const id = currentCallId;
    setTimeout(() => loadCallDebug(id), 2500);
  }
});

client.on("error", (error) => {
  setAvatarSpeaking(false);
  els.configHint.textContent = String(error);
  stopCall();
});

els.loadBtn.addEventListener("click", loadDeck);
els.sampleBtn.addEventListener("click", async () => {
  let sample = window.__sampleDeckPath;
  if (!sample) {
    try {
      const latest = await api("/api/config");
      renderConfig(latest);
      sample = latest.sample_deck_path || "";
    } catch (error) {
      els.deckMeta.textContent = `Could not refresh sample configuration: ${error.message}`;
      return;
    }
  }
  if (!sample) {
    els.deckMeta.textContent = "Sample deck missing. Run python -m voice_app.sample_pack";
    return;
  }
  els.path.value = sample;
  localStorage.setItem("pptxPath", sample);
  await loadDeck();
});
els.startBtn.addEventListener("click", startCall);
els.stopBtn.addEventListener("click", stopCall);
els.endShowBtn.addEventListener("click", endShow);
els.viewToggle.addEventListener("click", () => {
  setViewMode(document.body.dataset.view === "maintenance" ? "presenter" : "maintenance");
});
els.presenterModeBtn.addEventListener("click", () => setViewMode("presenter"));
els.arrangeBtn.addEventListener("click", async () => {
  els.arrangeBtn.disabled = true;
  try {
    const result = await api("/api/layout/arrange", { method: "POST" });
    els.configHint.textContent = result.ok
      ? "PowerPoint and AIRA were arranged on the primary monitor."
      : `Layout could not be fully applied: ${result.error || "window not found"}`;
  } catch (error) {
    els.configHint.textContent = `Layout failed: ${error.message}`;
  } finally {
    els.arrangeBtn.disabled = false;
  }
});
document.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "m") {
    event.preventDefault();
    setViewMode(document.body.dataset.view === "maintenance" ? "presenter" : "maintenance");
  }
});
els.reindexQaBtn.addEventListener("click", async () => {
  els.reindexQaBtn.disabled = true;
  try {
    const result = await api("/api/qa/reindex", { method: "POST" });
    els.configHint.textContent = result.started
      ? "Q&A reindex started. Safe abstention remains available while indexing."
      : "Q&A indexing is already running.";
  } catch (error) {
    els.configHint.textContent = `Q&A reindex failed: ${error.message}`;
  } finally {
    setTimeout(() => {
      els.reindexQaBtn.disabled = !loaded;
    }, 1200);
  }
});
els.directorNextBtn.addEventListener("click", async () => {
  els.directorNextBtn.disabled = true;
  appendLog(els.toolLog, "tool", "Calling Python director deliver-next…");
  try {
    const result = await api("/api/debug/director-deliver-next", {
      method: "POST",
      body: JSON.stringify({ dry: false }),
    });
    const summary = JSON.stringify(result).slice(0, 400);
    if (result.ok) {
      appendLog(els.toolLog, "tool", `Director: ${summary}`);
      if (result.hint) els.configHint.textContent = result.hint;
      if (result.slide) {
        renderStatus({
          running: true,
          slide: result.slide,
          slide_count: result.beats_total || "",
          title: "",
          state: result.mode === "qa" ? "qa" : (result.auto_continue ? "auto-continue" : ""),
          notes: result.spoken_text || "",
        });
      }
    } else {
      appendLog(
        els.toolLog,
        "tool",
        `Director failed: ${result.error || result.status || ""} ${summary}`,
      );
      els.configHint.textContent = result.hint || result.error || "The Python director could not advance.";
    }
  } catch (error) {
    appendLog(els.toolLog, "tool", `Director: ${error.message}`);
    els.configHint.textContent = error.message;
  } finally {
    els.directorNextBtn.disabled = !loaded;
  }
});
els.localNextBtn.addEventListener("click", async () => {
  els.localNextBtn.disabled = true;
  appendLog(els.toolLog, "tool", "Local COM next…");
  try {
    const result = await api("/api/session/run", {
      method: "POST",
      body: JSON.stringify({ action: "next" }),
    });
    appendLog(els.toolLog, "tool", result.message || JSON.stringify(result).slice(0, 300));
    if (result.status) renderStatus(result.status);
    els.configHint.textContent = result.ok
      ? "PowerPoint COM works on this PC."
      : (result.error || "Local next failed.");
  } catch (error) {
    appendLog(els.toolLog, "tool", `local: ${error.message}`);
    els.configHint.textContent = `Local COM failed: ${error.message}`;
  } finally {
    els.localNextBtn.disabled = !loaded;
  }
});
els.path.addEventListener("keydown", (event) => {
  if (event.key === "Enter") loadDeck();
});

const events = new EventSource("/api/events");
events.onmessage = (message) => {
  const event = JSON.parse(message.data);
  if (event.type === "tool") {
    const slide = event.result?.status?.slide;
    appendLog(
      els.toolLog,
      "tool",
      `${event.name}${event.args?.slide_number ? ` → ${event.args.slide_number}` : ""}${slide ? `  (now ${slide})` : ""}`,
    );
    if (event.result?.status) renderStatus(event.result.status);
  }
  if (event.type === "mcp") {
    appendLog(els.toolLog, "tool", `MCP ${event.method || ""}`);
  }
  if (event.type === "deck_loaded") renderDeck(event);
};

async function loadCallDebug(callId) {
  try {
    const dbg = await api(`/api/debug/call?call_id=${encodeURIComponent(callId)}`);
    const tools = (dbg.tool_invocations || [])
      .filter((item) => item.role === "tool_call_invocation")
      .map((item) => item.name)
      .join(", ");
    appendLog(
      els.transcript,
      "tool",
      `Ended: ${dbg.disconnection_reason || "unknown"} · tools: ${tools || "none"}`,
    );
    if (dbg.hint) els.configHint.textContent = dbg.hint;
  } catch (error) {
    appendLog(els.transcript, "tool", `Call debug: ${error.message}`);
  }
}

const saved = localStorage.getItem("pptxPath");
if (saved) els.path.value = saved;
els.path.addEventListener("change", () => localStorage.setItem("pptxPath", els.path.value));
setViewMode(
  new URLSearchParams(window.location.search).get("view") === "maintenance"
    ? "maintenance"
    : "presenter",
  false,
);
setAvatarSpeaking(false);

const cfg = await api("/api/config");
renderConfig(cfg);
for (const delay of [2500, 6000]) {
  setTimeout(async () => {
    try {
      renderConfig(await api("/api/config"));
    } catch (error) {
      console.warn(error);
    }
  }, delay);
}
setInterval(async () => {
  if (!loaded) return;
  try {
    renderConfig(await api("/api/config"));
  } catch (error) {
    console.warn(error);
  }
}, 5000);
try {
  renderDeck(await api("/api/session"));
} catch (error) {
  console.warn(error);
}
