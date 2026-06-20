function esc(s) {
  return (s == null ? "" : String(s))
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function shortId(id) {
  if (!id) return "—";
  if (id.includes("@")) return id.length > 28 ? id.slice(0, 26) + "…" : id;
  return id.length > 10 ? id.slice(0, 8) + "…" : id;
}

function ctxText(ctx) {
  if (!ctx || typeof ctx !== "object") return "—";
  try {
    return JSON.stringify(ctx, null, 0).slice(0, 200);
  } catch {
    return "—";
  }
}

function multiIntentHtml(intents) {
  if (!intents || !intents.length) return '<span class="pill no">—</span>';
  if (intents.length === 1) {
    return '<span class="pill no">single</span>';
  }
  return intents
    .map((i) => `<span class="pill yes">${esc(i)}</span>`)
    .join(" ");
}

function scenarioShort(s) {
  if (!s) return "—";
  const map = {
    single_user_single_question_single_intent: "S1",
    single_user_single_question_multiple_intent: "S2",
    single_user_multiple_questions_single_intent: "S3a",
    single_user_multiple_questions_multiple_intent: "S3b",
  };
  return map[s] || s.slice(0, 12);
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
  const intents = Array.isArray(r.multi_intent) ? r.multi_intent : [];
  return `<tr class="${isNew ? "row-new" : ""}">
    <td>${r.id}</td>
    <td>${esc((r.created_at || "").replace("T", " ").replace("+00:00", ""))}</td>
    <td title="${esc(r.user_id)}">${esc(shortId(r.user_id))}</td>
    <td title="${esc(r.session_id)}">${esc(shortId(r.session_id))} <span class="turn">#${r.turn_index || 1}</span></td>
    <td title="${esc(r.scenario || "")}"><span class="pill scenario">${esc(scenarioShort(r.scenario))}</span></td>
    <td class="q">${esc(r.question)}</td>
    <td><span class="pill intent">${esc(r.intent || "—")}</span></td>
    <td class="multi">${multiIntentHtml(intents)}</td>
    <td class="ctx">${esc(ctxText(r.context))}</td>
    <td class="a">${esc(ans)}</td>
    <td>${sourcesHtml(r.sources)}</td>
  </tr>`;
}

const rowsEl = document.getElementById("rows");
const countEl = document.getElementById("count");
const refreshModal = document.getElementById("refresh-modal");
let seenTop = 0;

async function refreshTable() {
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

function downloadExport(fmt) {
  window.location.href = `/api/conversations/export?fmt=${encodeURIComponent(fmt)}`;
}

function showModal() {
  refreshModal.classList.remove("hidden");
}

function hideModal() {
  refreshModal.classList.add("hidden");
}

async function clearDatabase() {
  const res = await fetch("/api/conversations", { method: "DELETE" });
  if (!res.ok) throw new Error("clear failed");
  const data = await res.json();
  alert(`Database refreshed. ${data.removed || 0} record(s) deleted.`);
  seenTop = 0;
  await refreshTable();
}

async function exportThenClear(fmt) {
  downloadExport(fmt);
  await new Promise((r) => setTimeout(r, 800));
  await clearDatabase();
  hideModal();
}

document.getElementById("export-btn").addEventListener("click", () => downloadExport("xlsx"));
document.getElementById("export-pdf-btn").addEventListener("click", () => downloadExport("pdf"));
document.getElementById("refresh-btn").addEventListener("click", showModal);
document.getElementById("modal-cancel").addEventListener("click", hideModal);
document.getElementById("modal-excel").addEventListener("click", () => exportThenClear("xlsx"));
document.getElementById("modal-pdf").addEventListener("click", () => exportThenClear("pdf"));
document.getElementById("modal-refresh-only").addEventListener("click", async () => {
  if (!window.confirm("Are you sure? All conversation data will be permanently deleted.")) return;
  await clearDatabase();
  hideModal();
});

refreshTable();
setInterval(refreshTable, 3000);
