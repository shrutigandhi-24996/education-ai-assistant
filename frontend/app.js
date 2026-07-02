const chatEl = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const statusEl = document.getElementById("status");
const suggestionsEl = document.getElementById("suggestions");
const labelPanel = document.getElementById("query-labels");
const labelStatus = document.getElementById("label-status");
const lbl = {
  email: document.getElementById("lbl-email"),
  question: document.getElementById("lbl-question"),
  intent: document.getElementById("lbl-intent"),
  multi: document.getElementById("lbl-multi"),
  context: document.getElementById("lbl-context"),
  answer: document.getElementById("lbl-answer"),
  sources: document.getElementById("lbl-sources"),
};
const USER_KEY = "edu_assistant_user_email";
const LEGACY_USER_KEY = "edu_assistant_user_id";
const SESSION_KEY = "edu_assistant_session_id";

function isValidEmail(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}

function getUserId() {
  const email = localStorage.getItem(USER_KEY);
  if (email && isValidEmail(email)) return email.trim().toLowerCase();
  return null;
}

function setUserId(email) {
  localStorage.setItem(USER_KEY, email.trim().toLowerCase());
  localStorage.removeItem(LEGACY_USER_KEY);
}

function getSessionId() {
  let id = sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
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
  setLabel(lbl.intent, s.intent, true);
  setLabel(lbl.multi, s.multi, true);
  setLabel(lbl.context, s.context, true);
  setLabel(lbl.answer, s.answer, true);
  setLabel(lbl.sources, s.sources, true);
}

function startSearchMode(email, question) {
  labelPanel.classList.add("is-running");
  searchBanner.classList.remove("hidden");
  searchStepIndex = 0;
  setLabel(lbl.email, escapeHtml(email));
  setLabel(lbl.question, escapeHtml(question));
  lbl.context.classList.add("mono");
  applySearchStep(0);
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
  modal.classList.remove("hidden");
  const emailInput = document.getElementById("email-input");
  if (emailInput) emailInput.focus();
}

function closeEmailModal() {
  document.getElementById("email-modal").classList.add("hidden");
}

function ensureUserEmail() {
  if (userId) {
    return Promise.resolve(userId);
  }
  openEmailModal();
  return new Promise((resolve) => {
    const emailForm = document.getElementById("email-form");
    const inputEl = document.getElementById("email-input");
    const onSubmit = (e) => {
      e.preventDefault();
      const email = inputEl.value.trim().toLowerCase();
      if (!isValidEmail(email)) {
        alert("Please enter a valid email address (e.g. you@gmail.com).");
        return;
      }
      setUserId(email);
      userId = email;
      closeEmailModal();
      showLabelsIdle();
      emailForm.removeEventListener("submit", onSubmit);
      resolve(email);
    };
    emailForm.addEventListener("submit", onSubmit);
  });
}

const SUGGESTIONS = [
  "Admission process & fees at Stanford University",
  "Scholarships for international students in Canada",
  "What is VNSGU's admission process for 2026?",
  "How do I become a data scientist after BSc IT?",
  "Top universities for an MBA in the UK",
  "MIT computer science department and official website",
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

function showLabelsIdle() {
  labelPanel.classList.remove("is-running");
  labelStatus.textContent = "Waiting for query";
  labelStatus.className = "label-status idle";
  setLabel(lbl.email, userId || "—");
  setLabel(lbl.question, "—");
  setLabel(lbl.intent, "—");
  setLabel(lbl.multi, "—");
  setLabel(lbl.context, "—");
  lbl.context.classList.remove("mono");
  setLabel(lbl.answer, "—");
  setLabel(lbl.sources, "—");
}

function showLabelsLoading(email, question) {
  startSearchMode(email, question);
}

function showLabelsResult(email, question, data) {
  stopSearchMode();
  labelPanel.classList.remove("is-running");
  labelStatus.textContent = "Complete";
  labelStatus.className = "label-status done";
  setLabel(lbl.email, escapeHtml(email));
  setLabel(lbl.question, escapeHtml(question));
  setLabel(lbl.intent, data.intent
    ? `<span class="intent-pill">${escapeHtml(data.intent)}</span>`
    : "—");
  setLabel(
    lbl.multi,
    formatMultiIntent(data.intents, data.is_multi_intent || (data.intents && data.intents.length > 1))
  );
  lbl.context.classList.add("mono");
  setLabel(lbl.context, formatContext(data.context));
  const answerPreview = (data.reply || "—").replace(/\s+/g, " ").slice(0, 1200);
  setLabel(lbl.answer, escapeHtml(answerPreview));
  setLabel(lbl.sources, formatSourcesList(data.sources, data.resources));
}

function showLabelsError(email, question, message) {
  stopSearchMode();
  labelPanel.classList.remove("is-running");
  labelStatus.textContent = "Error";
  labelStatus.className = "label-status idle";
  setLabel(lbl.email, escapeHtml(email));
  setLabel(lbl.question, escapeHtml(question));
  setLabel(lbl.intent, "—");
  setLabel(lbl.multi, "—");
  setLabel(lbl.context, "—");
  setLabel(lbl.answer, escapeHtml(message));
  setLabel(lbl.sources, "—");
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
    note.textContent = "Answer above is based on text read from this official PDF.";
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

    const content = document.createElement("div");
    content.className = "answer-text";
    content.innerHTML = formatMarkdown(text);
    bubble.appendChild(content);

    const pdfs = (resources || []).filter((r) => r.type === "pdf");
    const primaryPdf = pdfs.find((r) => r.has_content) || pdfs[0];
    if (primaryPdf) {
      bubble.appendChild(createPdfViewer(primaryPdf));
    }

    const hasRes = (resources && resources.length) || (sources && sources.length);
    if (hasRes) {
      const box = document.createElement("div");
      box.className = "sources";
      const label = document.createElement("span");
      label.className = "src-label";
      label.textContent = "Official PDFs, pages & sources:";
      box.appendChild(label);

      if (resources && resources.length) {
        resources.slice(0, 10).forEach((r) => {
          const a = document.createElement("a");
          const t = r.type || "page";
          a.className = "src" + (t === "pdf" || t === "document" ? " official" : "");
          a.href = r.url;
          a.target = "_blank";
          a.rel = "noopener";
          const suffix = r.has_content && t === "pdf" ? " · read" : "";
          a.textContent = `${resourceIcon(t)} ${r.title || hostOf(r.url)}${suffix}`;
          if (t === "pdf") {
            a.addEventListener("click", (e) => {
              e.preventDefault();
              const viewer = bubble.querySelector(".pdf-viewer-wrap");
              const iframe = bubble.querySelector(".pdf-frame");
              const toggle = bubble.querySelector(".pdf-toggle");
              const fallback = bubble.querySelector(".pdf-fallback");
              if (fallback) {
                window.open(r.url, "_blank", "noopener");
                return;
              }
              if (viewer && iframe && toggle) {
                iframe.src = pdfProxyUrl(r.url);
                iframe.classList.remove("hidden");
                if (fallback) fallback.remove();
                attachPdfEmbedGuard(viewer, iframe, r);
                toggle.textContent = "Hide PDF";
                viewer.scrollIntoView({ behavior: "smooth", block: "nearest" });
              } else {
                window.open(r.url, "_blank", "noopener");
              }
            });
          }
          box.appendChild(a);
        });
      }
      const resUrls = new Set((resources || []).map((r) => r.url));
      (sources || []).slice(0, 6).forEach((url) => {
        if (resUrls.has(url)) return;
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
  renderSuggestions();
  refreshHealth();
  showLabelsIdle();
  setChatEnabled(true);
  if (!userId) {
    openEmailModal();
  }
}

initApp();
