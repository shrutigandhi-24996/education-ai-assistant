const chatEl = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const statusEl = document.getElementById("status");
const suggestionsEl = document.getElementById("suggestions");
const labelPanel = document.getElementById("query-labels");
const labelStatus = document.getElementById("label-status");
const lbl = {
  email: document.getElementById("lbl-email"),
  processing: document.getElementById("lbl-processing"),
  question: document.getElementById("lbl-question"),
  intent: document.getElementById("lbl-intent"),
  multi: document.getElementById("lbl-multi"),
  institution: document.getElementById("lbl-institution"),
  context: document.getElementById("lbl-context"),
  answer: document.getElementById("lbl-answer"),
  sources: document.getElementById("lbl-sources"),
};
const USER_KEY = "edu_assistant_user_email";
const LEGACY_USER_KEY = "edu_assistant_user_id";
const SESSION_KEY = "edu_assistant_session_id";
const INSIGHT_KEY = "edu_query_insight_state";
const INSIGHT_HISTORY_KEY = "edu_query_insight_history";
const userBadge = document.getElementById("user-badge");
const insightHistoryEl = document.getElementById("insight-history");
const historyCountEl = document.getElementById("history-count");
let currentHistoryId = null;
let activeHistoryId = null;

function isValidEmail(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}

function getUserId() {
  const email = localStorage.getItem(USER_KEY);
  if (email && isValidEmail(email)) return email.trim().toLowerCase();
  return null;
}

function setUserId(email) {
  const normalized = email.trim().toLowerCase();
  try {
    localStorage.setItem(USER_KEY, normalized);
    localStorage.removeItem(LEGACY_USER_KEY);
  } catch (_) {
    throw new Error("Could not save your email. Please allow cookies/storage for this site and try again.");
  }
  updateUserBadge(normalized);
}

function updateUserBadge(email) {
  if (!userBadge) return;
  if (email) {
    userBadge.textContent = email;
    userBadge.classList.remove("hidden");
  } else {
    userBadge.classList.add("hidden");
  }
}

function saveInsightState(state) {
  try {
    sessionStorage.setItem(INSIGHT_KEY, JSON.stringify(state));
  } catch (_) {
    /* ignore */
  }
}

function loadInsightState() {
  try {
    const raw = sessionStorage.getItem(INSIGHT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function applyInsightState(state) {
  if (!state) return;
  if (state.email) setLabel(lbl.email, typeof state.email === "string" && state.email.includes("<") ? state.email : escapeHtml(state.email || ""));
  if (state.processing) setLabel(lbl.processing, state.processing.includes("<") ? state.processing : escapeHtml(state.processing));
  if (state.question) setLabel(lbl.question, escapeHtml(state.question));
  if (state.intent) setLabel(lbl.intent, state.intent);
  if (state.multi) setLabel(lbl.multi, state.multi);
  if (state.institution) setLabel(lbl.institution, escapeHtml(state.institution));
  if (state.context) {
    lbl.context.classList.add("mono");
    setLabel(lbl.context, state.context);
  } else {
    lbl.context.classList.remove("mono");
  }
  if (state.answer) setLabel(lbl.answer, state.answer.includes("<") ? state.answer : escapeHtml(state.answer));
  if (state.sources) setLabel(lbl.sources, state.sources);
  if (state.status) {
    labelStatus.textContent = state.status;
    labelStatus.className = state.statusClass || "label-status done";
  }
}

function historyStorageKey() {
  return `${INSIGHT_HISTORY_KEY}_${sessionId}`;
}

function loadInsightHistory() {
  try {
    const raw = sessionStorage.getItem(historyStorageKey());
    return raw ? JSON.parse(raw) : [];
  } catch (_) {
    return [];
  }
}

function saveInsightHistory(history) {
  try {
    sessionStorage.setItem(historyStorageKey(), JSON.stringify(history));
  } catch (_) {
    /* ignore */
  }
}

function formatHistoryTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch (_) {
    return "";
  }
}

function buildInsightStateFromData(email, question, data, answerPreview) {
  const inst = data.institution || (data.context && data.context.Institution && data.context.Institution[0]) || "—";
  const cleanPreview = stripDuplicateSourceSections(answerPreview);
  return {
    email,
    processing: "✅ Complete — all steps finished",
    question,
    institution: inst,
    intent: data.intent ? `<span class="intent-pill">${escapeHtml(data.intent)}</span>` : "—",
    multi: formatMultiIntent(data.intents, data.is_multi_intent || (data.intents && data.intents.length > 1)),
    context: formatContext(data.context),
    answer: escapeHtml(cleanPreview),
    sources: formatSourcesList(data.sources, data.resources),
    status: "Complete",
    statusClass: "label-status done",
  };
}

function upsertHistoryEntry(entry) {
  const history = loadInsightHistory();
  const idx = history.findIndex((h) => h.id === entry.id);
  if (idx >= 0) {
    history[idx] = { ...history[idx], ...entry };
  } else {
    history.push(entry);
  }
  if (history.length > 40) {
    history.splice(0, history.length - 40);
  }
  saveInsightHistory(history);
  renderSessionHistory(entry.id);
  return entry;
}

function renderSessionHistory(highlightId) {
  if (!insightHistoryEl) return;
  const history = loadInsightHistory();
  if (historyCountEl) {
    historyCountEl.textContent = `${history.length} quer${history.length === 1 ? "y" : "ies"}`;
  }
  if (!history.length) {
    insightHistoryEl.innerHTML = '<p class="insight-history-empty">No queries yet in this session.</p>';
    return;
  }
  insightHistoryEl.innerHTML = "";
  [...history].reverse().forEach((item) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "insight-history-item";
    row.classList.add(item.status || "complete");
    if (item.id === (highlightId || activeHistoryId)) row.classList.add("active");
    row.setAttribute("role", "listitem");
    row.dataset.id = String(item.id);

    const statusLabel = item.status === "running" ? "⏳ Processing" : item.status === "error" ? "❌ Error" : "✅ Done";
    const inst = item.institution && item.institution !== "—" ? item.institution : "";
    const step = item.stepLabel ? `<span class="hist-step">${escapeHtml(item.stepLabel)}</span>` : "";

    row.innerHTML =
      `<span class="hist-top"><span class="hist-time">${formatHistoryTime(item.time)}</span>` +
      `<span class="hist-status">${statusLabel}</span></span>` +
      `<span class="hist-q">${escapeHtml(item.question || "—")}</span>` +
      (inst ? `<span class="hist-inst">🏛️ ${escapeHtml(inst)}</span>` : "") +
      step;

    row.addEventListener("click", () => {
      activeHistoryId = item.id;
      if (item.state) {
        applyInsightState(item.state);
        saveInsightState(item.state);
      }
      renderSessionHistory(item.id);
    });
    insightHistoryEl.appendChild(row);
  });
  if (highlightId) activeHistoryId = highlightId;
}

function updateRunningHistoryStep(stepText) {
  if (!currentHistoryId) return;
  const history = loadInsightHistory();
  const item = history.find((h) => h.id === currentHistoryId);
  if (item && item.status === "running") {
    item.stepLabel = stepText;
    saveInsightHistory(history);
    renderSessionHistory(currentHistoryId);
  }
}

function getSessionId() {
  try {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `sess-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  } catch (_) {
    return `sess-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }
}

let userId = getUserId();
const sessionId = getSessionId();
let sending = false;
let searchStepTimer = null;
let searchStepIndex = 0;

const SEARCH_STEPS = [
  { icon: "🧠", title: "Search mode — Step 1/4", step: "Analyzing your question & detecting intent…", intent: "Detecting intent…", multi: "Analyzing multi-intent…", context: "Building context…", answer: "Preparing search…", sources: "Waiting…" },
  { icon: "🌐", title: "Search mode — Step 2/4", step: "Searching official college / university websites…", intent: "Intent analysis in progress…", multi: "Checking multiple intents…", context: "Mapping institution & topic…", answer: "Querying the web…", sources: "Finding official domains…" },
  { icon: "📄", title: "Search mode — Step 3/4", step: "Reading official PDFs & extracting key details…", intent: "Intent detected (finalizing)…", multi: "Multi-intent resolved…", context: "Collecting page context…", answer: "Reading PDF content…", sources: "Scanning for PDFs & links…" },
  { icon: "🤖", title: "Search mode — Step 4/4", step: "Generating answer with official sources…", intent: "Intent ready…", multi: "Multi-intent ready…", context: "Context assembled…", answer: "Writing grounded answer…", sources: "Attaching official sources…" },
];

const searchBanner = document.getElementById("search-banner");
const searchBannerTitle = document.getElementById("search-banner-title");
const searchBannerStep = document.getElementById("search-banner-step");
const sendBtn = document.getElementById("send-btn");
const composerEl = document.getElementById("form");

function setChatEnabled(enabled) {
  input.disabled = !enabled;
  const sendBtn = document.getElementById("send-btn");
  if (sendBtn) sendBtn.disabled = !enabled;
  suggestionsEl.querySelectorAll("button").forEach((b) => {
    b.disabled = !enabled;
  });
}

function setSending(active) {
  sending = active;
  setChatEnabled(!active);
  if (sendBtn) {
    sendBtn.textContent = active ? "Searching…" : "Send";
    sendBtn.classList.toggle("is-searching", active);
  }
  composerEl.classList.toggle("searching", active);
}

function applySearchStep(index) {
  const s = SEARCH_STEPS[index % SEARCH_STEPS.length];
  if (searchBannerTitle) searchBannerTitle.textContent = `${s.icon} ${s.title}`;
  if (searchBannerStep) searchBannerStep.textContent = s.step;
  if (labelStatus) {
    labelStatus.textContent = "🔍 Search mode";
    labelStatus.className = "label-status running";
  }
  if (statusEl) statusEl.textContent = s.step;
  setLabel(lbl.processing, `${s.icon} ${s.title}<br><span class="step-detail">${escapeHtml(s.step)}</span>`, true);
  setLabel(lbl.intent, s.intent, true);
  setLabel(lbl.multi, s.multi, true);
  setLabel(lbl.context, s.context, true);
  setLabel(lbl.answer, s.answer, true);
  setLabel(lbl.sources, s.sources, true);
  updateRunningHistoryStep(s.step);
  if (!currentHistoryId) return;
  const history = loadInsightHistory();
  const item = history.find((h) => h.id === currentHistoryId);
  if (item && item.status === "running" && item.state) {
    item.state.processing = `${s.icon} ${s.title}<br><span class="step-detail">${escapeHtml(s.step)}</span>`;
    item.state.intent = s.intent;
    item.state.multi = s.multi;
    item.state.context = s.context;
    item.state.answer = s.answer;
    item.state.sources = s.sources;
    saveInsightHistory(history);
  }
}

function startSearchMode(email, question) {
  labelPanel.classList.add("is-running");
  searchBanner.classList.remove("hidden");
  searchStepIndex = 0;
  currentHistoryId = Date.now();
  activeHistoryId = currentHistoryId;
  setLabel(lbl.email, escapeHtml(email));
  setLabel(lbl.question, escapeHtml(question));
  setLabel(lbl.institution, "Detecting…", true);
  lbl.context.classList.add("mono");
  applySearchStep(0);
  upsertHistoryEntry({
    id: currentHistoryId,
    time: new Date().toISOString(),
    status: "running",
    question,
    institution: "—",
    stepLabel: SEARCH_STEPS[0].step,
    state: {
      email,
      processing: `${SEARCH_STEPS[0].icon} ${SEARCH_STEPS[0].title}`,
      question,
      institution: "Detecting…",
      intent: SEARCH_STEPS[0].intent,
      multi: SEARCH_STEPS[0].multi,
      context: SEARCH_STEPS[0].context,
      answer: SEARCH_STEPS[0].answer,
      sources: SEARCH_STEPS[0].sources,
      status: "Search mode",
      statusClass: "label-status running",
    },
  });
  searchStepTimer = setInterval(() => {
    searchStepIndex += 1;
    applySearchStep(searchStepIndex);
  }, 3500);
}

function stopSearchMode() {
  if (searchStepTimer) {
    clearInterval(searchStepTimer);
    searchStepTimer = null;
  }
  searchBanner.classList.add("hidden");
  composerEl.classList.remove("searching");
  if (statusEl && !sending) {
    refreshHealth();
  }
}

function openEmailModal() {
  const modal = document.getElementById("email-modal");
  if (!modal) return;
  modal.classList.remove("hidden");
  hideEmailLoginError();
  const emailInput = document.getElementById("email-input");
  if (emailInput) emailInput.focus();
}

function closeEmailModal() {
  const modal = document.getElementById("email-modal");
  if (modal) modal.classList.add("hidden");
  hideEmailLoginError();
}

function showEmailLoginError(message) {
  const el = document.getElementById("email-login-error");
  if (!el) {
    alert(message);
    return;
  }
  el.textContent = message;
  el.classList.remove("hidden");
}

function hideEmailLoginError() {
  const el = document.getElementById("email-login-error");
  if (el) {
    el.textContent = "";
    el.classList.add("hidden");
  }
}

let pendingEmailResolve = null;

function completeEmailLogin(email) {
  try {
    setUserId(email);
  } catch (err) {
    showEmailLoginError(err.message || "Could not sign in. Please try again.");
    return;
  }
  userId = email.trim().toLowerCase();
  closeEmailModal();
  initInsightPanel();
  setChatEnabled(true);
  updateUserBadge(userId);
  if (pendingEmailResolve) {
    pendingEmailResolve(userId);
    pendingEmailResolve = null;
  }
}

function submitEmailLogin() {
  hideEmailLoginError();
  const inputEl = document.getElementById("email-input");
  if (!inputEl) {
    showEmailLoginError("Email field not found. Please refresh the page.");
    return;
  }
  const email = inputEl.value.trim().toLowerCase();
  if (!email) {
    showEmailLoginError("Please enter your email address.");
    inputEl.focus();
    return;
  }
  if (!isValidEmail(email)) {
    showEmailLoginError("Please enter a valid email address (e.g. you@gmail.com).");
    inputEl.focus();
    return;
  }
  completeEmailLogin(email);
}

function setupEmailLogin() {
  const emailForm = document.getElementById("email-form");
  const continueBtn = document.getElementById("email-continue-btn");
  if (!emailForm) return;

  if (emailForm.dataset.bound !== "1") {
    emailForm.dataset.bound = "1";
    emailForm.addEventListener("submit", (e) => {
      e.preventDefault();
      submitEmailLogin();
    });
  }

  if (continueBtn && continueBtn.dataset.bound !== "1") {
    continueBtn.dataset.bound = "1";
    continueBtn.addEventListener("click", (e) => {
      e.preventDefault();
      submitEmailLogin();
    });
  }
}

function ensureUserEmail() {
  if (userId) {
    return Promise.resolve(userId);
  }
  openEmailModal();
  return new Promise((resolve) => {
    pendingEmailResolve = resolve;
  });
}

const SUGGESTIONS = [
  "SRKI BSc IT sem-1 syllabus",
  "SU Sarvajanik University constituent colleges",
  "VNSGU BCA syllabus sem 1",
  "VNSGU admission 2026 fees and eligibility",
  "GTU BCA syllabus sem 2",
  "SCET Sarvajanik University admission",
];

function setLabel(el, html, pending = false) {
  el.innerHTML = html;
  el.classList.toggle("pending", pending);
}

function formatContext(ctx) {
  if (!ctx || typeof ctx !== "object" || !Object.keys(ctx).length) return "—";
  try {
    return escapeHtml(JSON.stringify(ctx, null, 2));
  } catch {
    return "—";
  }
}

function formatMultiIntent(intents, isMulti) {
  if (!intents || !intents.length) return "—";
  const badge = isMulti
    ? '<span class="multi-yes">Multiple intents detected</span><br>'
    : '<span class="multi-yes" style="background:#f1f5f9;color:#475569">Single intent</span><br>';
  const pills = intents.map((i) => `<span class="intent-pill">${escapeHtml(i)}</span>`).join("");
  return badge + pills;
}

function resourceIcon(type) {
  return ({ pdf: "📄", document: "📁", page: "🌐", image: "🖼️" }[type] || "🔗");
}

function formatResourcesList(resources, sources) {
  const parts = [];
  if (resources && resources.length) {
    const groups = { pdf: [], document: [], page: [], image: [] };
    resources.forEach((r) => {
      const t = r.type || "page";
      (groups[t] || groups.page).push(r);
    });
    if (groups.pdf.length) {
      parts.push("<strong>PDFs:</strong>");
      groups.pdf.slice(0, 5).forEach((r) => {
        parts.push(`<a class="src-link" href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${resourceIcon("pdf")} ${escapeHtml(r.title || "PDF")}</a>`);
      });
    }
    if (groups.document.length) {
      parts.push("<strong>Documents:</strong>");
      groups.document.slice(0, 3).forEach((r) => {
        parts.push(`<a class="src-link" href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${resourceIcon("document")} ${escapeHtml(r.title || "Document")}</a>`);
      });
    }
    if (groups.page.length) {
      parts.push("<strong>Web pages:</strong>");
      groups.page.slice(0, 4).forEach((r) => {
        parts.push(`<a class="src-link" href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${resourceIcon("page")} ${escapeHtml(r.title || hostOf(r.url))}</a>`);
      });
    }
    if (groups.image.length) {
      parts.push("<strong>Images:</strong>");
      groups.image.slice(0, 2).forEach((r) => {
        parts.push(`<a class="src-link" href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${resourceIcon("image")} ${escapeHtml(r.title || "Image")}</a>`);
      });
    }
  }
  if (sources && sources.length) {
    parts.push("<strong>Links:</strong>");
    sources.slice(0, 6).forEach((u) => {
      parts.push(`<a class="src-link" href="${escapeHtml(u)}" target="_blank" rel="noopener">🔗 ${escapeHtml(hostOf(u))}</a>`);
    });
  }
  return parts.length ? parts.join("") : "—";
}

function formatSourcesList(sources, resources) {
  return formatResourcesList(resources, sources);
}

const SOURCE_SECTION_PATTERNS = [
  /\n\n\*\*Official sources[\s\S]*$/i,
  /\n\n\*\*📄 Official PDF[\s\S]*$/i,
  /\n\n\*\*Official PDFs[\s\S]*$/i,
  /\n\n📄 Official PDFs[\s\S]*$/i,
  /\n\n\*\*Official PDFs & documents[\s\S]*$/i,
  /\n\n\*\*🌐 Official web pages[\s\S]*$/i,
  /\n\n\*\*📁 Official documents[\s\S]*$/i,
  /\n\n\*\*🖼️ Informative images[\s\S]*$/i,
  /\n\n\*\*🔗 Additional official links[\s\S]*$/i,
  /\n\n\*\*📄 Syllabus PDF[\s\S]*$/i,
  /\n\n\*\*📄 Official syllabus PDF[\s\S]*$/i,
];

function stripDuplicateSourceSections(text) {
  if (!text) return "";
  let cleaned = text.trim();
  let prev = "";
  while (cleaned !== prev) {
    prev = cleaned;
    for (const re of SOURCE_SECTION_PATTERNS) {
      cleaned = cleaned.replace(re, "");
    }
  }
  return cleaned.trim();
}

function getSortedResources(resources, type) {
  return (resources || [])
    .filter((r) => (r.type || "page") === type)
    .slice()
    .sort((a, b) => (b.score || 0) - (a.score || 0));
}

function initInsightPanel() {
  labelPanel.classList.remove("is-running");
  renderSessionHistory(activeHistoryId);
  const saved = loadInsightState();
  if (saved) {
    applyInsightState(saved);
    return;
  }
  labelStatus.textContent = "Ready";
  labelStatus.className = "label-status idle";
  setLabel(lbl.email, escapeHtml(userId || "—"));
  setLabel(lbl.processing, "Ready — ask a question below");
  setLabel(lbl.question, "—");
  setLabel(lbl.intent, "—");
  setLabel(lbl.multi, "—");
  setLabel(lbl.institution, "—");
  lbl.context.classList.remove("mono");
  setLabel(lbl.context, "—");
  setLabel(lbl.answer, "—");
  setLabel(lbl.sources, "—");
}

function showLabelsIdle() {
  initInsightPanel();
}

function showLabelsLoading(email, question) {
  startSearchMode(email, question);
}

function showLabelsResult(email, question, data) {
  stopSearchMode();
  labelPanel.classList.remove("is-running");
  labelStatus.textContent = "Complete";
  labelStatus.className = "label-status done";
  const answerPreview = stripDuplicateSourceSections((data.reply || "—").replace(/\s+/g, " ").slice(0, 1200));
  const state = buildInsightStateFromData(email, question, data, answerPreview);
  applyInsightState(state);
  saveInsightState(state);
  const inst = data.institution || (data.context && data.context.Institution && data.context.Institution[0]) || "—";
  upsertHistoryEntry({
    id: currentHistoryId || Date.now(),
    time: new Date().toISOString(),
    status: "complete",
    question,
    institution: inst,
    stepLabel: "",
    state,
  });
}

function showLabelsError(email, question, message) {
  stopSearchMode();
  labelPanel.classList.remove("is-running");
  labelStatus.textContent = "Error";
  labelStatus.className = "label-status idle";
  const state = {
    email,
    processing: "Error",
    question,
    institution: "—",
    intent: "—",
    multi: "—",
    context: "—",
    answer: escapeHtml(message),
    sources: "—",
    status: "Error",
    statusClass: "label-status idle",
  };
  applyInsightState(state);
  upsertHistoryEntry({
    id: currentHistoryId || Date.now(),
    time: new Date().toISOString(),
    status: "error",
    question,
    institution: "—",
    stepLabel: message,
    state,
  });
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function formatMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/^### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^## (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^# (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);
  html = html.replace(/\n/g, "<br>");
  return html;
}

function hostOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; }
}

function isOfficial(url) {
  return /(\.edu|\.gov|\.ac\.[a-z]{2,3}|\.edu\.[a-z]{2,3}|\.gov\.[a-z]{2,3}|\.ac\.in|\.edu\.in|\.nic\.in)$/.test(hostOf(url));
}

function pdfProxyUrl(rawUrl) {
  return `/api/pdf/view?url=${encodeURIComponent(rawUrl)}`;
}

function showPdfEmbedFallback(wrap, frame, pdf) {
  frame.classList.add("hidden");
  let fallback = wrap.querySelector(".pdf-fallback");
  if (!fallback) {
    fallback = document.createElement("div");
    fallback.className = "pdf-fallback";
    wrap.insertBefore(fallback, frame.nextSibling);
  }
  fallback.innerHTML = "";
  const msg = document.createElement("p");
  msg.className = "pdf-fallback-msg";
  msg.textContent =
    "This PDF cannot be shown inline here (the site blocks embedding or the file could not be loaded).";
  fallback.appendChild(msg);

  const hint = document.createElement("p");
  hint.className = "pdf-fallback-hint";
  hint.textContent = pdf.has_content
    ? "Your answer above is still based on text read from this official PDF."
    : "Open the official PDF in a new tab to view it.";
  fallback.appendChild(hint);

  const btn = document.createElement("a");
  btn.className = "pdf-open-primary";
  btn.href = pdf.url;
  btn.target = "_blank";
  btn.rel = "noopener";
  btn.textContent = "Open PDF in new tab ↗";
  fallback.appendChild(btn);
}

function attachPdfEmbedGuard(wrap, frame, pdf) {
  let settled = false;
  const fail = () => {
    if (settled) return;
    settled = true;
    showPdfEmbedFallback(wrap, frame, pdf);
  };

  frame.addEventListener("load", () => {
    setTimeout(() => {
      if (settled) return;
      try {
        const href = frame.contentWindow?.location?.href || "";
        if (!href || href === "about:blank" || href.startsWith("about:")) {
          fail();
          return;
        }
        const doc = frame.contentDocument;
        const bodyText = (doc?.body?.innerText || "").trim().toLowerCase();
        if (bodyText.includes("could not load pdf") || bodyText.includes("invalid url")) {
          fail();
        }
      } catch (_) {
        /* Cross-origin embed — cannot inspect; assume it loaded. */
      }
    }, 1200);
  });

  frame.addEventListener("error", fail);
  setTimeout(() => {
    if (settled) return;
    try {
      const href = frame.contentWindow?.location?.href || "";
      if (href === "about:blank") fail();
    } catch (_) {
      /* Loaded cross-origin PDF — keep iframe visible. */
    }
  }, 4500);
}

function createPdfViewer(pdf) {
  const wrap = document.createElement("div");
  wrap.className = "pdf-viewer-wrap";

  const head = document.createElement("div");
  head.className = "pdf-viewer-head";
  const title = document.createElement("span");
  title.className = "pdf-viewer-title";
  title.textContent = `📄 ${pdf.title || "Official PDF"}`;
  head.appendChild(title);

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "pdf-toggle";
  btn.textContent = "Hide PDF";

  const frame = document.createElement("iframe");
  frame.className = "pdf-frame";
  frame.src = pdfProxyUrl(pdf.url);
  frame.title = pdf.title || "Official PDF document";
  frame.loading = "lazy";
  attachPdfEmbedGuard(wrap, frame, pdf);

  btn.addEventListener("click", () => {
    const hidden = frame.classList.toggle("hidden");
    btn.textContent = hidden ? "Open PDF" : "Hide PDF";
    if (!hidden && frame.src === "about:blank") {
      frame.src = pdfProxyUrl(pdf.url);
    }
  });

  head.appendChild(btn);
  wrap.appendChild(head);
  wrap.appendChild(frame);

  const tabLink = document.createElement("a");
  tabLink.className = "pdf-open-tab";
  tabLink.href = pdf.url;
  tabLink.target = "_blank";
  tabLink.rel = "noopener";
  tabLink.textContent = "Open PDF in new tab ↗";
  wrap.appendChild(tabLink);

  if (pdf.has_content) {
    const note = document.createElement("p");
    note.className = "pdf-note";
    note.textContent = "Short answer below is based on text read from this official PDF.";
    wrap.appendChild(note);
  }

  return wrap;
}

function renderClarificationOptions(options, bubble) {
  if (!options || !options.length) return;
  const box = document.createElement("div");
  box.className = "clarify-options";
  const label = document.createElement("span");
  label.className = "clarify-label";
  label.textContent = "Tap to clarify your meaning:";
  box.appendChild(label);
  options.forEach((opt) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip clarify-chip";
    btn.textContent = opt.label || opt.resolution || opt.value;
    btn.addEventListener("click", () => {
      input.value = opt.resolution || opt.value || opt.label;
      form.requestSubmit();
    });
    box.appendChild(btn);
  });
  bubble.appendChild(box);
}

function createDocumentCard(doc) {
  const wrap = document.createElement("div");
  wrap.className = "document-card-wrap";
  const link = document.createElement("a");
  link.className = "document-card";
  link.href = doc.url;
  link.target = "_blank";
  link.rel = "noopener";
  link.innerHTML =
    `<span class="document-card-icon">📁</span>` +
    `<span class="document-card-body">` +
    `<span class="document-card-title">${escapeHtml(doc.title || "Official document")}</span>` +
    `<span class="document-card-action">Open document ↗</span>` +
    `</span>`;
  wrap.appendChild(link);
  return wrap;
}

function createImagePreview(img) {
  const wrap = document.createElement("div");
  wrap.className = "image-preview-wrap";
  const title = document.createElement("div");
  title.className = "image-preview-title";
  title.textContent = `🖼️ ${img.title || "Informative image"}`;
  const link = document.createElement("a");
  link.href = img.url;
  link.target = "_blank";
  link.rel = "noopener";
  link.className = "image-preview-link";
  const imgEl = document.createElement("img");
  imgEl.src = img.url;
  imgEl.alt = img.title || "Informative image from official source";
  imgEl.loading = "lazy";
  imgEl.className = "image-preview-img";
  link.appendChild(imgEl);
  wrap.appendChild(title);
  wrap.appendChild(link);
  return wrap;
}

function createPortalCard(page) {
  const wrap = document.createElement("div");
  wrap.className = "portal-card-wrap";
  const link = document.createElement("a");
  link.className = "portal-card";
  link.href = page.url;
  link.target = "_blank";
  link.rel = "noopener";
  link.innerHTML =
    `<span class="portal-card-icon">🌐</span>` +
    `<span class="portal-card-body">` +
    `<span class="portal-card-title">${escapeHtml(page.title || "Official syllabus portal")}</span>` +
    `<span class="portal-card-action">Open official page to select course &amp; semester ↗</span>` +
    `<span class="portal-card-url">${escapeHtml(hostOf(page.url))}</span>` +
    `</span>`;
  wrap.appendChild(link);
  return wrap;
}

function appendAnswerMedia(bubble, resources) {
  const mediaWrap = document.createElement("div");
  mediaWrap.className = "answer-media-first";

  const portals = (resources || [])
    .filter((r) => r.is_portal || r.source === "curated_portal")
    .slice()
    .sort((a, b) => (b.score || 0) - (a.score || 0));
  portals.slice(0, 2).forEach((p) => mediaWrap.appendChild(createPortalCard(p)));

  const pdfs = getSortedResources(resources, "pdf");
  const primaryPdf = pdfs.find((r) => r.has_content) || pdfs[0];
  if (primaryPdf) {
    mediaWrap.appendChild(createPdfViewer(primaryPdf));
  }

  getSortedResources(resources, "document")
    .slice(0, 2)
    .forEach((doc) => mediaWrap.appendChild(createDocumentCard(doc)));

  getSortedResources(resources, "image")
    .slice(0, 2)
    .forEach((img) => mediaWrap.appendChild(createImagePreview(img)));

  if (mediaWrap.childElementCount) {
    bubble.appendChild(mediaWrap);
    return true;
  }
  return false;
}

function appendSupplementarySources(bubble, sources, resources, primaryPdfUrl, includeAllResources) {
  const shown = new Set((resources || []).map((r) => r.url));
  if (primaryPdfUrl) shown.add(primaryPdfUrl);
  (resources || []).filter((r) => r.is_portal).forEach((r) => shown.add(r.url));

  if (includeAllResources) {
    const box = document.createElement("div");
    box.className = "sources";
    const label = document.createElement("span");
    label.className = "src-label";
    label.textContent = "Official pages & sources:";
    box.appendChild(label);
    (resources || []).slice(0, 8).forEach((r) => {
      const t = r.type || "page";
      const a = document.createElement("a");
      a.className = "src" + (t === "pdf" || t === "document" ? " official" : "");
      a.href = r.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = `${resourceIcon(t)} ${r.title || hostOf(r.url)}`;
      box.appendChild(a);
    });
    (sources || []).slice(0, 6).forEach((url) => {
      if (shown.has(url)) return;
      const a = document.createElement("a");
      a.className = "src" + (isOfficial(url) ? " official" : "");
      a.href = url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = (isOfficial(url) ? "🏛️ " : "🔗 ") + hostOf(url);
      box.appendChild(a);
    });
    if (box.querySelectorAll("a").length) bubble.appendChild(box);
    return;
  }

  const extraPages = getSortedResources(resources, "page").filter((r) => !shown.has(r.url));
  const extraSources = (sources || []).filter((u) => !shown.has(u));
  if (!extraPages.length && !extraSources.length) return;

  const box = document.createElement("div");
  box.className = "sources sources-compact";
  const label = document.createElement("span");
  label.className = "src-label";
  label.textContent = "Related official pages:";
  box.appendChild(label);

  extraPages.slice(0, 4).forEach((r) => {
    const a = document.createElement("a");
    a.className = "src official";
    a.href = r.url;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = `🌐 ${r.title || hostOf(r.url)}`;
    box.appendChild(a);
  });
  extraSources.slice(0, 4).forEach((url) => {
    const a = document.createElement("a");
    a.className = "src" + (isOfficial(url) ? " official" : "");
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = (isOfficial(url) ? "🏛️ " : "🔗 ") + hostOf(url);
    box.appendChild(a);
  });
  bubble.appendChild(box);
}

function addMessage(role, text, sources, resources, clarificationOptions) {
  const row = document.createElement("div");
  row.className = "message";
  const avatar = document.createElement("div");
  avatar.className = `avatar ${role}`;
  avatar.textContent = role === "user" ? "☺" : "🤖";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "bot") {
    bubble.classList.add("bot-reply");

    const hasMedia = appendAnswerMedia(bubble, resources);
    const cleanText = stripDuplicateSourceSections(text);
    const content = document.createElement("div");
    content.className = "answer-text" + (hasMedia ? " answer-text-short" : "");
    content.innerHTML = formatMarkdown(cleanText || text);
    bubble.appendChild(content);

    const pdfs = getSortedResources(resources, "pdf");
    const primaryPdf = pdfs.find((r) => r.has_content) || pdfs[0];
    appendSupplementarySources(bubble, sources, resources, primaryPdf && primaryPdf.url, !hasMedia);

    if (clarificationOptions && clarificationOptions.length) {
      renderClarificationOptions(clarificationOptions, bubble);
    }
  } else {
    bubble.textContent = text;
  }
  row.appendChild(avatar);
  row.appendChild(bubble);
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  return row;
}

function addTyping() {
  const row = document.createElement("div");
  row.className = "message search-active";
  row.innerHTML =
    '<div class="avatar bot">🤖</div><div class="bubble typing typing-box">' +
    '<span class="typing-step">🔍 Search mode active</span>' +
    '<span class="typing-detail">Searching official websites, PDFs &amp; documents<span class="dots"></span></span>' +
    '</div>';
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  return row;
}

function renderSuggestions() {
  SUGGESTIONS.forEach((q) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = q;
    b.addEventListener("click", () => {
      input.value = q;
      form.requestSubmit();
    });
    suggestionsEl.appendChild(b);
  });
}

async function refreshHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.mode === "education") {
      statusEl.textContent = data.llm_brain_ready
        ? "AI brain: ready · Web search: on · Multi-intent: on"
        : "AI brain: NOT configured — add GROQ_API_KEY in .env and restart";
    } else {
      statusEl.textContent = [
        `Mode: SRKI`,
        `RAG: ${data.rag_ready ? "ready" : "off"}`,
        `Web search: ${data.external_search_enabled ? "on" : "off"}`,
      ].join(" · ");
    }
  } catch {
    statusEl.textContent = "API offline — run: python run.py then open http://127.0.0.1:8001";
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (sending) return;
  const text = input.value.trim();
  if (!text) return;
  await ensureUserEmail();
  setSending(true);
  showLabelsLoading(userId, text);
  addMessage("user", text);
  input.value = "";
  const typing = addTyping();
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, user_id: userId, session_id: sessionId }),
    });
    const data = await res.json();
    typing.remove();
    if (!res.ok) {
      const errMsg = data.detail || "Please enter your email to continue.";
      showLabelsError(userId, text, errMsg);
      addMessage("bot", errMsg);
      openEmailModal();
      return;
    }
    showLabelsResult(userId, text, data);
    addMessage("bot", data.reply, data.sources, data.resources, data.clarification_options);
  } catch {
    typing.remove();
    showLabelsError(userId, text, "Could not reach the server.");
    addMessage("bot", "Sorry, I could not reach the server. Please try again in a moment.");
  } finally {
    setSending(false);
    stopSearchMode();
  }
});

function initApp() {
  setupEmailLogin();
  renderSuggestions();
  refreshHealth();
  updateUserBadge(userId);
  initInsightPanel();
  setChatEnabled(!!userId);
  if (!userId) {
    openEmailModal();
  }
}

initApp();
