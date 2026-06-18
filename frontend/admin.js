const rowsEl = document.getElementById("rows");
const countEl = document.getElementById("count");
let seenTop = 0;

function esc(s) {
  return (s == null ? "" : String(s))
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function shortUser(id) {
  return id && id.length > 10 ? id.slice(0, 8) + "…" : id || "—";
}

function ctxText(ctx) {
  if (!ctx) return "—";
  const parts = [];
  if (ctx.role) parts.push("role: " + ctx.role);
  if (ctx.intents && ctx.intents.length) parts.push("intents: [" + ctx.intents.join(", ") + "]");
  if (ctx.institution) parts.push("institution: " + ctx.institution);
  if (ctx.answer_source) parts.push("source: " + ctx.answer_source);
  return parts.join("\n") || "—";
}

function sourcesHtml(sources) {
  if (!sources || !sources.length) return "—";
  return sources.slice(0, 3).map((u) => {
    let host = u;
    try { host = new URL(u).hostname.replace(/^www\./, ""); } catch {}
    return `<a class="srclink" href="${esc(u)}" target="_blank" rel="noopener">${esc(host)}</a>`;
  }).join("<br>");
}

function rowHtml(r, isNew) {
  const ans = (r.answer || "").replace(/\s+/g, " ").slice(0, 280);
  const multi = r.multi_intent === "yes"
    ? '<span class="pill yes">yes</span>'
    : '<span class="pill no">no</span>';
  return `<tr class="${isNew ? "row-new" : ""}">
    <td>${r.id}</td>
    <td>${esc((r.created_at || "").replace("T", " ").replace("+00:00", ""))}</td>
    <td title="${esc(r.user_id)}">${esc(shortUser(r.user_id))}</td>
    <td class="q">${esc(r.question)}</td>
    <td><span class="pill intent">${esc(r.intent || "—")}</span></td>
    <td>${multi}</td>
    <td class="ctx">${esc(ctxText(r.context))}</td>
    <td class="a">${esc(ans)}</td>
    <td>${sourcesHtml(r.sources)}</td>
  </tr>`;
}

async function refresh() {
  try {
    const res = await fetch("/api/conversations?limit=200");
    const data = await res.json();
    const rows = data.rows || [];
    const topId = rows.length ? rows[0].id : 0;
    countEl.textContent = `${data.count} rows`;
    rowsEl.innerHTML = rows.map((r) => rowHtml(r, r.id > seenTop && seenTop > 0)).join("");
    seenTop = topId;
  } catch {
    countEl.textContent = "offline — retrying…";
  }
}

refresh();
setInterval(refresh, 3000);
