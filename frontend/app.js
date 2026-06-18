const chatEl = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const statusEl = document.getElementById("status");
const sessionId = crypto.randomUUID();

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

function addMessage(role, text) {
  const row = document.createElement("div");
  row.className = "message";
  const avatar = document.createElement("div");
  avatar.className = `avatar ${role}`;
  avatar.textContent = role === "user" ? "☺" : "🤖";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "bot") {
    bubble.innerHTML = formatMarkdown(text);
  } else {
    bubble.textContent = text;
  }
  row.appendChild(avatar);
  row.appendChild(bubble);
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
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
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });
    const data = await res.json();
    addMessage("bot", data.reply);
  } catch {
    addMessage("bot", "Sorry, I could not reach the server. Start the API with: python run.py");
  }
});

refreshHealth();
