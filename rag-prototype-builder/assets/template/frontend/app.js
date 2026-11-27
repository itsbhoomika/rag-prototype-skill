// Frontend: renders only what the API returns. All document text goes in via
// textContent (never innerHTML), so markup or injection strings in documents show as plain text.

const $ = (id) => document.getElementById(id);

function el(tag, opts = {}, ...children) {
  const node = document.createElement(tag);
  if (opts.className) node.className = opts.className;
  if (opts.text !== undefined) node.textContent = opts.text;
  for (const child of children) node.append(child);
  return node;
}

async function api(path, body) {
  const res = await fetch(path, body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : undefined);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? `${res.status}: ${JSON.stringify(data.detail)}` : `HTTP ${res.status}`);
  return data;
}

function where(p) {
  return p.source + (p.page ? ` p.${p.page}` : "") + (p.section ? ` › ${p.section}` : "");
}

function render(r) {
  const out = $("result");
  out.replaceChildren();
  const card = el("div", { className: "card" });

  if (r.abstained) {
    card.append(el("div", { className: "banner warn", text: `I don't know based on the documents you can access. Reason: ${r.reason}` }));
  } else {
    card.append(el("div", { className: "answer", text: r.answer }));
    card.append(el("p", { className: "muted", text: "Sources: " + r.citations.map((c) => `[${c.label}] ${where(c)}`).join(", ") }));
  }
  for (const w of r.warnings) card.append(el("p", { className: "muted", text: `warning: ${w}` }));

  const cited = new Set(r.citations.map((c) => c.label));
  card.append(el("h3", { text: `Retrieved passages (${r.retrieved.length})` }));
  for (const p of r.retrieved) {
    const summary = el("summary", { text: `[${p.label}] ${where(p)}` });
    if (cited.has(p.label)) summary.append(el("span", { className: "tag", text: "cited" }));
    card.append(el("details", {}, summary,
      el("pre", { text: p.text }),
      el("div", { className: "muted", text: `score ${p.score} · bm25 ${p.bm25} · similarity ${p.vector_sim}` })));
  }
  card.append(el("p", { className: "muted", text: `${r.llm} · ${r.embedder} · ${JSON.stringify(r.timings)}` }));
  out.append(card);
}

async function init() {
  try {
    const [health, users] = await Promise.all([api("/api/health"), api("/api/users")]);
    $("status").textContent = `Model: ${health.llm} · Embeddings: ${health.embedder} · Indexed chunks: ${health.index_chunks}`;
    $("stub").hidden = !health.llm_is_test_stub;
    if (!health.index_chunks) $("status").textContent += " · Run ingest first.";
    for (const u of users) $("user").append(el("option", { text: `${u.id} (${u.role})` }));
    [...$("user").options].forEach((o, i) => (o.value = users[i].id));
  } catch (e) {
    $("status").replaceChildren(el("span", { className: "banner error", text: `Backend not reachable: ${e.message}` }));
  }
}

$("ask").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("go").disabled = true;
  $("result").replaceChildren(el("p", { className: "muted", text: "Searching and answering…" }));
  try {
    render(await api("/api/ask", { user_id: $("user").value, question: $("question").value }));
  } catch (e) {
    // Show the real error. Never substitute a placeholder answer.
    $("result").replaceChildren(el("div", { className: "banner error", text: `Request failed: ${e.message}` }));
  } finally {
    $("go").disabled = false;
  }
});

init();
