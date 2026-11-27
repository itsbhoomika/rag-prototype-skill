// Reader UI. Renders only what the API returns. All document text goes in via textContent
// (never innerHTML), so markup or injection strings in documents show as plain text.
//
// Left pane: the question, what was searched, the answer with [P#] markers, notices.
// Right pane: the sources, rebuilt from the retrieved chunks in document order, with the cited
// passage highlighted. On a phone the right pane becomes a bottom sheet.

const $ = (id) => document.getElementById(id);
const phone = matchMedia("(max-width: 860px)");
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
let current = null;        // last /api/ask response
let shownSource = null;    // source file open in the reader
let lastTrigger = null;    // element to return focus to when the sheet closes
let busy = false;

function el(tag, opts = {}, ...children) {
  const node = document.createElement(tag);
  if (opts.className) node.className = opts.className;
  if (opts.text !== undefined) node.textContent = opts.text;
  for (const [k, v] of Object.entries(opts.attrs || {})) node.setAttribute(k, v);
  for (const child of children) if (child !== null && child !== undefined && child !== false) node.append(child);
  return node;
}

async function api(path, body) {
  const res = await fetch(path, body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : undefined);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : data.detail ? JSON.stringify(data.detail) : "";
    const err = new Error(detail || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

// ---------------------------------------------------------------- wording helpers
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
function names(list) {
  if (list.length <= 1) return list.join("");
  return `${list.slice(0, -1).join(", ")} and ${list[list.length - 1]}`;
}
const num = (label) => label.replace(/^P/, "");
const base = (source) => source.split("/").pop();
const isRecords = (p) => (p.section || "").startsWith("Records from ");
const sectionName = (p) => (!p.section || isRecords(p) ? "" : p.section.split(" > ").slice(1).join(", ") || p.section);
const where = (p) => base(p.source) + (p.page ? `, page ${p.page}` : "") + (sectionName(p) ? `, ${sectionName(p)}` : "");

function body(p) {
  // Chunks start with their heading path (search context); the heading is shown separately.
  const lines = p.text.split("\n");
  return p.section && lines[0].trim() === p.section ? lines.slice(1).join("\n").trim() : p.text;
}

function withoutOverlap(prev, text) {
  // Consecutive chunks repeat up to ~150 characters (CHUNK_OVERLAP). Don't show that twice.
  for (let k = Math.min(200, text.length, prev.length); k >= 20; k--) {
    if (prev.endsWith(text.slice(0, k))) return text.slice(k).trimStart();
  }
  return text;
}

function accessLine(r) {
  if (!r.searched_folders.length) return `${r.user_id} can't search any folders, so nothing was searched.`;
  const folders = r.searched_folders.length === 1 ? "the folder" : "the folders";
  let line = `Searched ${names(r.searched_folders)}, ${folders} ${r.user_id} can see.`;
  if (r.unsearched_folders.length) {
    line += ` ${cap(names(r.unsearched_folders))} ${r.unsearched_folders.length === 1 ? "isn't" : "aren't"} searched.`;
  }
  return line;
}

function timing(t) {
  const parts = [];
  if (t.retrieve_ms !== undefined) parts.push(`searched in ${Math.round(t.retrieve_ms)} ms`);
  if (t.generate_ms !== undefined) {
    parts.push(t.generate_ms < 1000 ? `answered in ${Math.round(t.generate_ms)} ms` : `answered in ${(t.generate_ms / 1000).toFixed(1)} s`);
  }
  return parts.join(", ");
}

function setStatus(state, text) {
  $("status").dataset.state = state;
  $("status").textContent = text;
}

// ---------------------------------------------------------------- left pane
function showLeft(...nodes) {
  $("left").removeAttribute("aria-busy");
  $("left").replaceChildren(...nodes.filter(Boolean));  // optional parts arrive as null
  $("left").scrollTop = 0;
}

function renderWelcome() {
  showLeft(el("div", { className: "empty" },
    el("h2", { text: "Ask about the documents" }),
    el("p", { text: "Answers come only from the folders the selected person can search, and every claim links to the passage it came from." }),
    el("ol", {},
      el("li", { text: "Pick who you're asking as, at the top right." }),
      el("li", { text: "Type a question below and press Enter." }),
      el("li", { text: "Click a number in the answer to see its passage highlighted in the source." }))));
}

function renderLoading(question) {
  $("left").setAttribute("aria-busy", "true");
  $("left").replaceChildren(
    el("h2", { className: "q", text: question }),
    el("p", { className: "access", text: "Searching the folders this person can see…" }),
    el("div", { className: "skel", attrs: { style: "width:94%" } }),
    el("div", { className: "skel", attrs: { style: "width:86%" } }),
    el("div", { className: "skel", attrs: { style: "width:58%" } }));
  renderReaderMessage("Finding sources", "The passages used in the answer will open here.");
}

function facts(r) {
  const items = [el("li", { text: plural(r.citations.length, "passage cited", "passages cited") })];
  items.push(r.numbers_checked
    ? el("li", { text: `${r.numbers_checked === 1 ? "1 number" : `${r.numbers_checked} numbers`}, each found in a cited passage` })
    : el("li", { className: "neutral", text: "No numbers to check" }));
  return el("ul", { className: "facts", attrs: { "aria-label": "Checks on this answer" } }, ...items);
}

function answerText(r) {
  // Split on [P#]. Each run of text before a marker becomes a segment that the marker underlines.
  const p = el("p", { className: "answer" });
  let seg = el("span", { className: "seg" });
  let closed = false;
  p.append(seg);
  for (const part of r.answer.split(/(\[P\d+\])/)) {
    const m = part.match(/^\[(P\d+)\]$/);
    if (m) {
      const label = m[1];
      const passage = r.citations.find((c) => c.label === label);
      seg.dataset.for = `${seg.dataset.for || ""} ${label}`.trim();
      // Keep the marker on the same line as the word before it.
      const tail = seg.lastChild && seg.lastChild.nodeType === 3 ? seg.lastChild : null;
      const word = tail && tail.textContent.match(/(\S+)\s*$/);
      let holder = p;
      if (word) {
        tail.textContent = tail.textContent.slice(0, word.index);
        const glued = el("span", { className: "seg", text: word[1], attrs: { "data-for": seg.dataset.for } });
        holder = el("span", { className: "nowrap" }, glued);
        p.append(holder);
      }
      const b = el("button", { className: "cite", text: num(label), attrs: {
        type: "button", "data-label": label, "aria-pressed": "false",
        "aria-label": `Source ${num(label)}${passage ? `: ${where(passage)}` : ""}` } });
      b.addEventListener("click", () => openPassage(label, { focus: true, trigger: b }));
      holder.append(b);
      closed = true;
    } else if (part) {
      if (closed) { seg = el("span", { className: "seg" }); p.append(seg); closed = false; }
      seg.append(document.createTextNode(part));
    }
  }
  return p;
}

function guardCard(r) {
  const flagged = r.ignored_instructions;
  if (!flagged.length) return null;
  const title = flagged.length === 1
    ? "One retrieved passage contained instructions and was treated as plain text."
    : `${flagged.length} retrieved passages contained instructions and were treated as plain text.`;
  const card = el("div", { className: "card guard", attrs: { role: "note" } },
    el("h3", {}, el("span", { className: "shield", attrs: { "aria-hidden": "true" } }), el("span", { text: title })));
  for (const f of flagged) {
    card.append(el("p", {}, document.createTextNode(`${f.source} says `), el("q", { text: f.quote }),
      document.createTextNode(f.cited ? " The answer cites this passage, so check it before relying on the answer."
                                       : " The answer doesn't use it.")));
  }
  const actions = el("div", { className: "actions" });
  for (const f of flagged) {
    const b = el("button", { text: flagged.length === 1 ? "Show the passage" : `Show ${f.label}`, attrs: { type: "button" } });
    b.addEventListener("click", () => openPassage(f.label, { focus: true, trigger: b }));
    actions.append(b);
  }
  card.append(actions);
  return card;
}

function matchKind(p) {
  if (p.bm25 !== null && p.vector_sim !== null) return "keyword and meaning match";
  return p.vector_sim !== null ? "meaning match" : "keyword match";
}

function alsoSearched(r) {
  const cited = new Set(r.citations.map((c) => c.label));
  const rest = r.retrieved.filter((p) => !cited.has(p.label));
  if (!rest.length) return null;
  const list = el("ol", {}, ...rest.map((p) => {
    const b = el("button", { text: where(p), attrs: { type: "button" } });
    b.addEventListener("click", () => openPassage(p.label, { focus: true, trigger: b }));
    return el("li", {}, el("b", { text: num(p.label) }), b, el("span", { text: matchKind(p) }));
  }));
  return el("details", { className: "also" }, el("summary", { text: `Also searched, not used (${rest.length})` }), list);
}

function metaRow(r, withCopy) {
  const row = el("div", { className: "meta" },
    el("span", { text: `${r.llm}${r.llm_is_test_stub ? " (test stand-in)" : ""}` }), el("span", { text: timing(r.timings) }));
  if (withCopy) {
    const copy = el("button", { className: "link", text: "Copy answer", attrs: { type: "button" } });
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(r.answer.replace(/\s*\[P\d+\]/g, "")); copy.textContent = "Copied"; }
      catch { copy.textContent = "Couldn't copy: select the text instead"; }
      setTimeout(() => (copy.textContent = "Copy answer"), 1800);
    });
    row.append(copy);
  }
  return row;
}

function sourcesButton(r) {
  if (!r.retrieved.length) return null;
  const b = el("button", { className: "sources-btn", text: `View sources (${r.retrieved.length})`, attrs: { type: "button" } });
  b.addEventListener("click", () => { openSheet(b); focusReader(); });
  return b;
}

function renderAnswer(r) {
  showLeft(
    el("h2", { className: "q", text: r.question }),
    el("p", { className: "access", text: accessLine(r) }),
    facts(r),
    answerText(r),
    ...r.warnings.map((w) => el("p", { className: "meta", text: `Note: ${w}` })),
    guardCard(r),
    sourcesButton(r),
    alsoSearched(r),
    metaRow(r, true));
}

function renderNoAnswer(r) {
  const hint = r.unsearched_folders.length
    ? `Try different words. If the answer lives in ${names(r.unsearched_folders)}, ask as someone who can search ${r.unsearched_folders.length === 1 ? "it" : "them"}.`
    : "Try different words, or check that the documents cover this.";
  showLeft(
    el("h2", { className: "q", text: r.question }),
    el("p", { className: "access", text: accessLine(r) }),
    el("div", { className: "card none" },
      el("h3", { text: "No answer in the documents this person can search" }),
      el("p", { className: "why", text: `Reason: ${r.reason}` }),
      el("p", { text: `${hint} Nothing was guessed.` })),
    guardCard(r),
    sourcesButton(r),
    alsoSearched(r),
    metaRow(r, false));
}

function renderError(e, question) {
  const hint = e.status === 403 ? "This person isn't in data/users.json on the server. Pick someone else, or add them there."
    : e.status === 503 ? "There's no search index yet. Run python -m backend.cli ingest, then ask again."
    : e.status === 502 ? "The model or embedding provider failed. Check .env, then run python -m backend.cli doctor."
    : e.status === 422 ? "The question was empty or longer than 2,000 characters."
    : "Check that the server is running, then ask again.";
  showLeft(
    el("h2", { className: "q", text: question }),
    el("div", { className: "card fail", attrs: { role: "alert" } },
      el("h3", { text: "This question couldn't be answered" }),
      el("p", { text: e.message }),
      el("p", { className: "why", text: hint })));
  renderReaderMessage("No sources to show", "The request failed, so there is no answer to check against.");
}

// ---------------------------------------------------------------- reader (right pane)
function groups(r) {
  // One tab per source file: files with cited passages first (in citation order), then by rank.
  const order = [...r.citations.map((c) => c.source), ...r.retrieved.map((p) => p.source)];
  const files = [...new Set(order)];
  return files.map((source) => ({
    source,
    cited: r.citations.filter((c) => c.source === source).length,
    chunks: r.retrieved.filter((p) => p.source === source)
      .sort((a, b) => (a.page || 0) - (b.page || 0) || a.doc_id.localeCompare(b.doc_id) || a.position - b.position),
  }));
}

function renderReaderMessage(title, text) {
  shownSource = null;
  $("reader-body").replaceChildren(el("div", { className: "r-empty" },
    el("span", { className: "mark", attrs: { "aria-hidden": "true" } }), el("h2", { text: title }), el("p", { text: text })));
}

function renderReader(r, source) {
  const all = groups(r);
  if (!all.length) {
    renderReaderMessage("Nothing to show", `None of the folders ${r.user_id} can search had a passage that matched.`);
    return;
  }
  const g = all.find((x) => x.source === source) || all[0];
  shownSource = g.source;
  const cited = new Map(r.citations.map((c) => [c.label, c]));
  const flagged = new Map(r.ignored_instructions.map((f) => [f.label, f]));
  const title = isRecords(g.chunks[0]) ? base(g.source) : (g.chunks[0].section || "").split(" > ")[0] || base(g.source);

  const tabs = el("div", { className: "tabs", attrs: { role: "tablist", "aria-label": "Source files" } }, ...all.map((x) => {
    const t = el("button", { className: "tab", attrs: { type: "button", role: "tab", "aria-selected": String(x.source === g.source) } },
      el("span", { text: base(x.source) }), x.cited ? el("small", { text: `${x.cited} cited` }) : null);
    t.addEventListener("click", () => renderReader(current, x.source));
    return t;
  }));
  const head = el("div", { className: "rh" },
    el("div", { className: "file", text: `${g.source}, rebuilt from the parts that were retrieved` }),
    el("h2", { text: title }), tabs);

  const rail = el("div", { className: "rail", attrs: { "aria-hidden": "true" } });
  const doc = el("div", { className: "doc" });
  let prev = null;
  let prevPage = null;
  for (const p of g.chunks) {
    if (p.page && p.page !== prevPage) { doc.append(el("p", { className: "page", text: `Page ${p.page}` })); prevPage = p.page; }
    const missing = prev && prev.doc_id === p.doc_id ? p.position - prev.position - 1 : (!prev || prev.doc_id !== p.doc_id ? p.position : 0);
    if (missing > 0) {
      doc.append(el("div", { className: "gapline", text: `${plural(missing, "part", "parts")} not retrieved` }));
      rail.append(el("i", { className: "gap" }));
    }
    let text = body(p);
    if (prev && prev.doc_id === p.doc_id && p.position === prev.position + 1) text = withoutOverlap(body(prev), text);
    const isCited = cited.has(p.label);
    const flag = flagged.get(p.label);
    const chunk = el("section", { className: `chunk${isCited ? " cited" : ""}${flag ? " flagged" : ""}`,
      attrs: { id: `chunk-${p.label}`, tabindex: "-1", "aria-label": `Passage ${num(p.label)}${isCited ? ", cited in the answer" : ""}` } });
    const tags = el("div", { className: "tags" },
      isCited ? el("span", { className: "ctag" }, el("b", { text: num(p.label) }), el("span", { text: "Cited in the answer" })) : null,
      flag ? el("span", { className: "ctag red", text: "Contains instructions, treated as plain text" }) : null);
    if (tags.childElementCount) chunk.append(tags);
    const heading = sectionName(p) || (isRecords(p) ? "" : p.section);
    if (heading) chunk.append(el("h3", { text: heading }));
    const paras = text.split(/\n\s*\n/).filter((t) => t.trim());
    chunk.append(el("div", { className: "text" }, ...paras.map((t) => el("p", {}, isCited ? el("span", { text: t }) : document.createTextNode(t)))));
    doc.append(chunk);
    rail.append(el("i", { className: isCited ? "cited" : "", attrs: { style: `height:${Math.max(10, Math.min(90, Math.round(text.length / 6)))}px` } }));
    prev = p;
  }
  const note = r.abstained ? el("p", { className: "page", text: "Nothing was cited. These are the passages that were searched." }) : null;
  const scroller = el("div", { className: "rbody" }, rail, el("div", {}, note, doc));
  $("reader-body").replaceChildren(head, scroller);
}

function focusReader() {
  const first = $("reader-body").querySelector(".chunk.cited, .chunk");
  if (first) first.focus({ preventScroll: false });
}

function openPassage(label, { focus = false, trigger = null } = {}) {
  if (!current) return;
  const p = current.retrieved.find((x) => x.label === label);
  if (!p) return;
  if (shownSource !== p.source) renderReader(current, p.source);

  document.querySelectorAll(".cite").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.label === label)));
  document.querySelectorAll(".seg").forEach((s) => s.classList.toggle("on", (s.dataset.for || "").split(" ").includes(label)));
  document.querySelectorAll(".chunk.active").forEach((c) => c.classList.remove("active"));

  const chunk = document.getElementById(`chunk-${label}`);
  if (!chunk) return;
  chunk.classList.add("active");
  if (phone.matches && focus) openSheet(trigger);
  chunk.scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "center" });
  if (focus) {
    chunk.focus({ preventScroll: true });
    if (!reduceMotion.matches) { chunk.classList.remove("flash"); void chunk.offsetWidth; chunk.classList.add("flash"); }
  }
}

// ---------------------------------------------------------------- phone bottom sheet
function openSheet(trigger) {
  if (!phone.matches) return;
  lastTrigger = trigger || document.activeElement;
  $("reader").classList.add("open");
  $("reader").setAttribute("role", "dialog");
  $("reader").setAttribute("aria-modal", "true");
  $("scrim").hidden = false;
}

function closeSheet() {
  if (!$("reader").classList.contains("open")) return;
  $("reader").classList.remove("open");
  $("reader").removeAttribute("role");
  $("reader").removeAttribute("aria-modal");
  $("scrim").hidden = true;
  if (lastTrigger && document.contains(lastTrigger)) lastTrigger.focus();
}

$("close-sheet").addEventListener("click", closeSheet);
$("scrim").addEventListener("click", closeSheet);
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") closeSheet(); });
phone.addEventListener("change", () => { if (!phone.matches) closeSheet(); });

// ---------------------------------------------------------------- asking
async function ask() {
  const question = $("question").value.trim();
  if (!question || busy) { $("question").focus(); return; }
  busy = true;
  $("go").disabled = true;
  $("go").textContent = "Asking…";
  closeSheet();
  renderLoading(question);
  try {
    const r = await api("/api/ask", { user_id: $("user").value, question });
    current = r;
    if (r.abstained) renderNoAnswer(r); else renderAnswer(r);
    renderReader(r, r.citations[0]?.source);
    if (r.citations.length) openPassage(r.citations[0].label);  // show the first source, without moving focus
    $("question").value = "";
    grow();
  } catch (e) {
    current = null;
    renderError(e, question);
  } finally {
    busy = false;
    $("go").disabled = false;
    $("go").textContent = "Ask";
  }
}

function grow() {
  const t = $("question");
  t.style.height = "auto";
  t.style.height = `${t.scrollHeight}px`;
}

$("ask").addEventListener("submit", (ev) => { ev.preventDefault(); ask(); });
$("question").addEventListener("input", grow);
$("question").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); ask(); }
});

async function init() {
  renderWelcome();
  renderReaderMessage("Sources open here", "When an answer cites a passage, its document opens here with that passage highlighted.");
  try {
    const [health, users] = await Promise.all([api("/api/health"), api("/api/users")]);
    $("test-mode").hidden = !health.llm_is_test_stub;
    if (health.index_chunks) {
      setStatus("ready", `${health.index_chunks} passages indexed`);
    } else {
      setStatus("empty", "Nothing indexed");
      $("down").hidden = false;
      $("down").replaceChildren(el("strong", { text: "Nothing to search yet. " }),
        document.createTextNode("Run python -m backend.cli ingest on the server, then reload this page."));
    }
    $("user").replaceChildren(...users.map((u) => el("option", { text: u.role ? `${u.id}, ${u.role}` : u.id, attrs: { value: u.id } })));
    if (!users.length) setStatus("empty", "No people in data/users.json");
    $("question").focus();
  } catch (e) {
    setStatus("down", "Server not reachable");
    $("down").hidden = false;
    $("down").replaceChildren(el("strong", { text: "Can't reach the server. " }),
      document.createTextNode(`Start it with uvicorn backend.api:app, then reload. (${e.message})`));
    $("go").disabled = true;
  }
}

init();
