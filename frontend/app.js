const chatEl = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const statusEl = document.getElementById("status");
const suggestionsEl = document.getElementById("suggestions");
const sessionId = crypto.randomUUID();

const SUGGESTIONS = [
  "Admission process & fees at Stanford University",
  "Scholarships for international students in Canada",
  "What is VNSGU's admission process for 2026?",
  "How do I become a data scientist after BSc IT?",
  "Top universities for an MBA in the UK",
  "MIT computer science department and official website",
];

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
  return /(\.edu|\.gov|\.ac\.[a-z]{2,3}|\.edu\.[a-z]{2,3}|\.gov\.[a-z]{2,3})$/.test(hostOf(url));
}

function addMessage(role, text, sources) {
  const row = document.createElement("div");
  row.className = "message";
  const avatar = document.createElement("div");
  avatar.className = `avatar ${role}`;
  avatar.textContent = role === "user" ? "☺" : "🤖";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "bot") {
    bubble.innerHTML = formatMarkdown(text);
    if (sources && sources.length) {
      const box = document.createElement("div");
      box.className = "sources";
      const label = document.createElement("span");
      label.className = "src-label";
      label.textContent = "Sources (verify on official sites):";
      box.appendChild(label);
      sources.slice(0, 6).forEach((url) => {
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
  row.className = "message";
  row.innerHTML =
    '<div class="avatar bot">🤖</div><div class="bubble typing">🔎 Searching the web & thinking<span class="dots"></span></div>';
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
  const text = input.value.trim();
  if (!text) return;
  addMessage("user", text);
  input.value = "";
  const typing = addTyping();
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });
    const data = await res.json();
    typing.remove();
    addMessage("bot", data.reply, data.sources);
  } catch {
    typing.remove();
    addMessage("bot", "Sorry, I could not reach the server. Please try again in a moment.");
  }
});

renderSuggestions();
refreshHealth();
