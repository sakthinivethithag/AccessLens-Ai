"use strict";

/* AccessLens AI - frontend logic. Talks to the Flask REST API with fetch(). */

const MAX_CHARS = 20000;
const DEFAULT_PREFS = { font_size: 18, line_spacing: 1.6, dark_mode: false, high_contrast: false };

const SAMPLE_TEXT = `Pursuant to Section 4 of the Tenancy Agreement, the tenant is required to remit the monthly rent of $1,250 no later than March 5, 2026, and failure to comply with this provision may result in a late penalty of 5% of the outstanding balance, which will be added to the following month's invoice.

Prior to the commencement of the inspection on April 12, 2026, all individuals residing in the premises must utilize the designated parking area; vehicles parked elsewhere will be towed at the owner's expense. Do not block the fire exits under any circumstances, as this is a serious safety risk.

In addition, the landlord will endeavor to facilitate repairs within 14 days of receiving a written request, although it is important to note that emergency repairs are handled immediately. Approximately 30 residents have already submitted their renewal forms, and the deadline for renewal is 06/30/2026.`;

const $ = (id) => document.getElementById(id);
const root = document.documentElement;

let prefs = normalisePrefs(window.INITIAL_PREFS);
let currentResult = null;
let saveTimer = null;
let toastTimer = null;
let lastFocus = null;

/* ---------------------------------------------------------------- helpers */

/** Call the Flask API and return parsed JSON. Throws an Error with a friendly message. */
async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (err) {
    throw new Error("Cannot reach the server. Is app.py still running?");
  }
  let data = {};
  try { data = await response.json(); } catch (err) { /* empty body */ }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

/** Show a short message at the bottom of the screen. */
function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
}

function formatDate(iso) {
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

/* ------------------------------------------------------------ preferences */

/** Convert server values (0/1) into booleans and make sure every field exists. */
function normalisePrefs(p) {
  return {
    font_size: Number(p.font_size) || DEFAULT_PREFS.font_size,
    line_spacing: Number(p.line_spacing) || DEFAULT_PREFS.line_spacing,
    dark_mode: !!p.dark_mode,
    high_contrast: !!p.high_contrast,
  };
}

/** Apply the current preferences to the page and keep the controls in sync. */
function applyPrefs() {
  root.style.setProperty("--reader-size", prefs.font_size + "px");
  root.style.setProperty("--reader-lh", prefs.line_spacing);
  root.dataset.dark = prefs.dark_mode ? "on" : "off";
  root.dataset.contrast = prefs.high_contrast ? "on" : "off";
  $("fontRange").value = prefs.font_size;
  $("fontValue").textContent = prefs.font_size;
  $("spacingRange").value = prefs.line_spacing;
  $("spacingValue").textContent = prefs.line_spacing.toFixed(1);
  $("darkToggle").checked = prefs.dark_mode;
  $("contrastToggle").checked = prefs.high_contrast;
}

/** Save preferences to SQLite shortly after the last change (avoids a request per slider tick). */
function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    try {
      await api("/api/preferences", { method: "PUT", body: JSON.stringify(prefs) });
      toast("Preferences saved");
    } catch (err) {
      toast(err.message, true);
    }
  }, 400);
}

function changePrefs(changes) {
  prefs = { ...prefs, ...changes };
  applyPrefs();
  scheduleSave();
}

function changeFont(delta) {
  changePrefs({ font_size: Math.min(32, Math.max(14, prefs.font_size + delta)) });
}

async function resetPrefs() {
  try {
    clearTimeout(saveTimer);
    prefs = normalisePrefs(await api("/api/preferences/reset", { method: "POST" }));
    applyPrefs();
    toast("Settings reset to defaults");
  } catch (err) {
    toast(err.message, true);
  }
}

/** Tell the user their saved settings were applied automatically on load. */
function showAutoAppliedStatus() {
  const parts = [`${prefs.font_size}px text`, `${prefs.line_spacing.toFixed(1)} line spacing`];
  if (prefs.dark_mode) parts.push("dark mode");
  if (prefs.high_contrast) parts.push("high contrast");
  $("statusMessage").textContent = "Your saved settings were applied automatically: " + parts.join(", ") + ".";
}

/* ------------------------------------------------------------------ stats */

async function loadStats() {
  try {
    const s = await api("/api/stats");
    const has = s.total_texts > 0;
    $("statTotal").textContent = s.total_texts.toLocaleString();
    $("statWords").textContent = s.total_words.toLocaleString();
    $("statSentence").textContent = has ? s.avg_sentence_reduction.toFixed(1) : "\u2014";
    $("statEase").textContent = has ? (s.avg_ease_gain > 0 ? "+" : "") + s.avg_ease_gain.toFixed(1) : "\u2014";
    $("statHighlights").textContent = s.total_highlights.toLocaleString();
  } catch (err) {
    toast(err.message, true);
  }
}

/* ---------------------------------------------------------------- history */

function renderHistory(items) {
  const list = $("historyList");
  list.innerHTML = "";
  $("historyEmpty").hidden = items.length > 0;
  $("clearHistoryBtn").disabled = items.length === 0;
  for (const item of items) {
    const li = document.createElement("li");
    li.className = "history-item";

    const info = document.createElement("div");
    info.className = "history-info";
    const preview = document.createElement("p");
    preview.className = "history-preview";
    preview.textContent = item.preview; // textContent, so stored text can never inject HTML
    const meta = document.createElement("p");
    meta.className = "history-meta";
    meta.textContent = `${formatDate(item.created_at)} \u00b7 ${item.words_before} words \u00b7 ${item.highlight_count} highlights`;
    info.append(preview, meta);

    const actions = document.createElement("div");
    actions.className = "history-actions";
    for (const [action, label, extra] of [["view", "View", ""], ["delete", "Delete", " danger"]]) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn small" + extra;
      btn.dataset.action = action;
      btn.dataset.id = item.id;
      btn.textContent = label;
      btn.setAttribute("aria-label", `${label} saved text from ${formatDate(item.created_at)}`);
      actions.append(btn);
    }
    li.append(info, actions);
    list.append(li);
  }
}

async function loadHistory() {
  try {
    renderHistory(await api("/api/history"));
  } catch (err) {
    toast(err.message, true);
  }
}

async function onHistoryClick(event) {
  const btn = event.target.closest("button[data-action]");
  if (!btn) return;
  const id = btn.dataset.id;
  try {
    if (btn.dataset.action === "view") {
      const record = await api(`/api/history/${id}`);
      $("textInput").value = record.original;
      updateCount();
      showResult(record);
      $("resultTitle").scrollIntoView({ behavior: "smooth" });
      toast("Loaded from history");
    } else {
      await api(`/api/history/${id}`, { method: "DELETE" });
      toast("Deleted");
      await Promise.all([loadHistory(), loadStats()]);
    }
  } catch (err) {
    toast(err.message, true);
    loadHistory();
  }
}

async function clearHistory() {
  if (!confirm("Delete all saved history? This cannot be undone.")) return;
  try {
    const r = await api("/api/history", { method: "DELETE" });
    toast(`Deleted ${r.deleted} item(s)`);
    await Promise.all([loadHistory(), loadStats()]);
  } catch (err) {
    toast(err.message, true);
  }
}

/* ------------------------------------------------------ text processing */

function updateCount() {
  const n = $("textInput").value.length;
  $("charCount").textContent = `${n.toLocaleString()} / ${MAX_CHARS.toLocaleString()} characters`;
}

/** Display a processed record (from /api/process or /api/history/<id>). */
function showResult(record) {
  currentResult = record;
  $("output").innerHTML = record.html; // already HTML-escaped by the server
  $("readingContent").innerHTML = record.html;
  $("readingBtn").disabled = false;
  $("copyBtn").disabled = false;

  const metrics = $("metrics");
  metrics.innerHTML = "";
  const chips = [
    `Words: ${record.before.words} \u2192 ${record.after.words}`,
    `Avg. sentence: ${record.before.avg_sentence} \u2192 ${record.after.avg_sentence} words`,
    `Reading ease: ${record.before.ease} \u2192 ${record.after.ease} (higher = easier)`,
    `Highlights: ${record.highlight_count}`,
  ];
  for (const text of chips) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = text;
    metrics.append(chip);
  }
}

async function simplify() {
  const text = $("textInput").value;
  const errorEl = $("inputError");
  errorEl.textContent = "";
  if (!text.trim()) { errorEl.textContent = "Please enter some text first."; return; }
  if (text.length > MAX_CHARS) { errorEl.textContent = "That text is too long."; return; }

  const btn = $("simplifyBtn");
  btn.disabled = true;
  btn.textContent = "Working...";
  try {
    const record = await api("/api/process", { method: "POST", body: JSON.stringify({ text }) });
    showResult(record);
    await Promise.all([loadHistory(), loadStats()]);
    toast("Text simplified and saved to history");
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Simplify & highlight";
  }
}

async function copyResult() {
  if (!currentResult) return;
  try {
    await navigator.clipboard.writeText(currentResult.simplified);
    toast("Copied to clipboard");
  } catch (err) {
    toast("Copy failed. Select the text and press Ctrl+C instead.", true);
  }
}

/* ----------------------------------------------------------- reading mode */

function openReading() {
  lastFocus = document.activeElement;
  $("readingOverlay").hidden = false;
  document.body.classList.add("no-scroll");
  $("closeReadingBtn").focus();
}

function closeReading() {
  $("readingOverlay").hidden = true;
  document.body.classList.remove("no-scroll");
  if (lastFocus) lastFocus.focus();
}

/** Esc closes reading mode; Tab stays inside it while it is open. */
function onKeydown(event) {
  const overlay = $("readingOverlay");
  if (overlay.hidden) return;
  if (event.key === "Escape") { closeReading(); return; }
  if (event.key === "Tab") {
    const buttons = [...overlay.querySelectorAll("button")];
    const first = buttons[0];
    const last = buttons[buttons.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
}

/* ------------------------------------------------------------------- init */

function init() {
  applyPrefs();
  showAutoAppliedStatus(); // preferences were already applied by the server-rendered page
  updateCount();

  $("fontRange").addEventListener("input", (e) => changePrefs({ font_size: Number(e.target.value) }));
  $("spacingRange").addEventListener("input", (e) => changePrefs({ line_spacing: Math.round(Number(e.target.value) * 10) / 10 }));
  $("darkToggle").addEventListener("change", (e) => changePrefs({ dark_mode: e.target.checked }));
  $("contrastToggle").addEventListener("change", (e) => changePrefs({ high_contrast: e.target.checked }));
  $("fontDown").addEventListener("click", () => changeFont(-2));
  $("fontUp").addEventListener("click", () => changeFont(2));
  $("readingFontDown").addEventListener("click", () => changeFont(-2));
  $("readingFontUp").addEventListener("click", () => changeFont(2));
  $("resetBtn").addEventListener("click", resetPrefs);

  $("textInput").addEventListener("input", updateCount);
  $("simplifyBtn").addEventListener("click", simplify);
  $("sampleBtn").addEventListener("click", () => {
    $("textInput").value = SAMPLE_TEXT;
    $("inputError").textContent = "";
    updateCount();
  });
  $("clearBtn").addEventListener("click", () => {
    $("textInput").value = "";
    $("inputError").textContent = "";
    updateCount();
    $("textInput").focus();
  });

  $("copyBtn").addEventListener("click", copyResult);
  $("readingBtn").addEventListener("click", openReading);
  $("closeReadingBtn").addEventListener("click", closeReading);
  document.addEventListener("keydown", onKeydown);

  $("historyList").addEventListener("click", onHistoryClick);
  $("clearHistoryBtn").addEventListener("click", clearHistory);

  loadStats();
  loadHistory();
}

init();
