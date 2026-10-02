"use strict";
const TABS = [
  ["listen", "Listen"], ["read", "Read"], ["headlines", "Headlines"],
  ["blacklife", "Black Life"], ["quotes", "Quotes"], ["levity", "Levity"],
];
// Items with long_read (set per source in config/sources.json) go in Read, not Headlines.

const $ = (id) => document.getElementById(id);
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
const opened = new Set(store.get("opened", []));
let brief = null, tabs = {}, current = location.hash.slice(1) || store.get("tab", "listen");

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat(Infinity)) if (k != null && k !== false) e.append(k);
  return e;
}
const shortSource = (s) => (s || "").replace(/\s*\((?!AAIHS).*?\)/g, "").replace(/ \(AAIHS\)/, "");
function ago(iso) {
  const t = Date.parse(iso); if (!t) return "";
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 60) return Math.max(m, 1) + "m ago";
  if (m < 1440) return Math.round(m / 60) + "h ago";
  const d = Math.round(m / 1440); return d === 1 ? "yesterday" : d + "d ago";
}
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const tag = () => h("span", { class: "bl" }, "Black Life");

function markOpened(id, card) {
  opened.add(id); store.set("opened", [...opened].slice(-500));
  card?.classList.add("seen"); renderTabDots();
}
function go(url, id, card) { markOpened(id, card); window.open(url, "_blank", "noopener"); }

function cardShell(id, url, ...kids) {
  const c = h("article", { class: "item" + (opened.has(id) ? " seen" : ""), tabindex: 0, role: "link" }, kids);
  const open = (e) => { if (!e.target.closest("button, a")) go(url, id, c); };
  c.addEventListener("click", open);
  c.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target === c) go(url, id, c); });
  return c;
}

// Small line above each title: unread dot, source, time, and the Black Life mark.
const eyebrow = (source, when, bl) => h("div", { class: "eyebrow" },
  h("i", { class: "udot", title: "Not opened yet" }), h("span", { class: "src" }, source),
  when ? h("span", { class: "when" }, when) : null, bl && tag());

// First sentence of a point, not fooled by "U.S.", "D.C." or "Rep.".
function firstSentence(t) {
  const re = /[.!?](?=\s+[A-Z“"])/g; let m;
  while ((m = re.exec(t))) {
    const word = t.slice(0, m.index + 1).split(/\s+/).pop();
    if (!/^(?:[A-Za-z]\.){1,}$|^(?:Mr|Mrs|Ms|Dr|Rep|Sen|Gov|Gen|St|Jr|Sr|No|Sept|Oct|Nov|Dec|Jan|Feb|Aug)\.$/.test(word)) return t.slice(0, m.index + 1);
  }
  return t;
}

function episodeCard(ep) {
  const points = ep.cards.map(firstSentence);
  const list = h("ul", { class: "bullets", hidden: true }, points.map((t) => h("li", {}, t)));
  const btn = h("button", { class: "more", "aria-expanded": "false", onclick() {
    const open = list.hidden; list.hidden = !open;
    btn.textContent = open ? "Hide key points" : `${plural(points.length, "key point")} ▾`;
    btn.setAttribute("aria-expanded", open);
  } }, `${plural(points.length, "key point")} ▾`);
  return cardShell(ep.id, ep.url,
    eyebrow(shortSource(ep.source), ago(ep.published), ep.black_life),
    h("h2", { class: "title" }, ep.title),
    ep.takeaway && h("p", { class: "sum" }, ep.takeaway),
    points.length ? [btn, list] : null);
}

function headlineCard(x) {
  return cardShell(x.id, x.url,
    eyebrow(shortSource(x.source), ago(x.published), x.black_life),
    h("h2", { class: "title" }, x.headline),
    x.summary && h("p", { class: "sum" }, x.summary));
}

function levityCard(x) {
  return cardShell(x.id, x.url,
    eyebrow(x.show, [x.platform, ago(x.published)].filter(Boolean).join(" · ")),
    h("h2", { class: "title" }, x.title));
}

function quoteCard(q, item, source) {
  const link = h("a", { class: "ts", href: q.url, target: "_blank", rel: "noopener",
    "aria-label": q.timestamp ? `Open at ${q.timestamp}` : "Open the article", onclick() { markOpened(item.id); } },
    q.timestamp ? "\u25B6\uFE0E " + q.timestamp : "Read");
  return h("article", { class: "quote" },
    h("blockquote", {}, q.text),
    h("div", { class: "qwho" }, q.speaker && h("b", {}, q.speaker), link, item.black_life && tag()),
    h("p", { class: "qctx" }, q.context),
    h("div", { class: "qep" }, `${shortSource(source)} · ${item.title || item.headline}`));
}

const longReads = () => brief.headlines.filter((x) => x.summary && x.long_read);
const quickHeadlines = () => brief.headlines.filter((x) => !(x.summary && x.long_read));
const allQuotes = () => [
  ...brief.episodes.flatMap((ep) => ep.quotes.map((q) => quoteCard(q, ep, ep.source))),
  ...brief.headlines.flatMap((x) => (x.quotes || []).map((q) => quoteCard(q, x, x.source))),
];

function items(tab) {
  const b = brief;
  switch (tab) {
    case "listen": return b.episodes.map(episodeCard);
    case "read": return longReads().map(headlineCard);
    case "headlines": return quickHeadlines().map(headlineCard);
    case "blacklife": {
      const eps = b.episodes.filter((e) => e.black_life), hs = b.headlines.filter((x) => x.black_life);
      return [...eps.map(episodeCard), ...hs.map(headlineCard)];
    }
    case "quotes": return allQuotes();
    case "levity": return b.levity.map(levityCard);
  }
}
const EMPTY = {
  listen: "No new episodes today.", read: "No long reads today.", headlines: "No headlines today.",
  blacklife: "Nothing tagged Black Life today.", quotes: "No quotes today.", levity: "Nothing from Levity this week.",
};
const tabCount = (t) => ({
  listen: brief.episodes.length, read: longReads().length, headlines: quickHeadlines().length,
  blacklife: brief.episodes.filter((e) => e.black_life).length + brief.headlines.filter((x) => x.black_life).length,
  quotes: allQuotes().length, levity: brief.levity.length,
}[t]);
function unreadIn(t) {
  const ids = { listen: brief.episodes, read: longReads(), headlines: quickHeadlines(), levity: brief.levity,
    blacklife: [...brief.episodes, ...brief.headlines].filter((x) => x.black_life), quotes: [] }[t];
  return ids.some((x) => !opened.has(x.id));
}
function renderTabDots() { for (const [id] of TABS) tabs[id]?.querySelector(".udot")?.toggleAttribute("hidden", !unreadIn(id)); }

function show(tab) {
  current = tab; store.set("tab", tab);
  document.body.dataset.tab = tab;
  for (const [id, b] of Object.entries(tabs)) b.setAttribute("aria-selected", id === tab);
  const list = items(tab);
  const main = $("main"); main.replaceChildren(...(list.length ? list : [h("p", { class: "empty" }, EMPTY[tab])]));
  window.scrollTo(0, 0);
}

function render() {
  const d = new Date(brief.date + "T12:00:00");
  $("date").textContent = d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  $("count").textContent = [plural(brief.episodes.length, "episode"), plural(quickHeadlines().length, "headline"),
    plural(longReads().length, "long read")].join(" · ");
  const nav = $("tabs"); nav.replaceChildren(); tabs = {};
  for (const [id, label] of TABS) {
    const n = tabCount(id);
    tabs[id] = h("button", { class: "tab", "data-id": id, role: "tab", onclick: () => show(id) },
      label, n ? h("small", {}, n) : null, h("i", { class: "udot", hidden: true }));
    nav.append(tabs[id]);
  }
  if (!tabs[current]) current = "listen";
  renderTabDots(); show(current);
  const banner = brief.failed_sources.length
    ? h("p", { class: "banner" }, "Couldn't reach: " + brief.failed_sources.join(", ")) : null;
  if (banner) $("main").before(banner);
  $("foot").textContent = "Generated " + new Date(brief.generated_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

async function load() {
  try {
    const r = await fetch("data/latest.json", { cache: "no-cache" });
    if (!r.ok) throw new Error(r.status);
    brief = await r.json();
    render();
  } catch (e) {
    $("main").replaceChildren(h("p", { class: "empty" }, "Couldn't load the brief. Check your connection and reopen the app."));
  }
}
load();
if ("serviceWorker" in navigator) addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));

// ---- Hero: today's park photo and a grounding tip (both independent of the brief) ----
async function loadJSON(url) { try { const r = await fetch(url); return r.ok ? r : null; } catch { return null; } }

async function setupPhoto() {
  const r = await loadJSON("photos/photos.json"); if (!r) return;
  const list = await r.json(); if (!list.length) return;
  const d = new Date(); // one per day, in order, on the phone's own calendar day
  const day = Math.floor(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 864e5);
  const p = list[day % list.length], img = $("heroImg");
  img.onload = () => { img.hidden = false; };
  img.src = "photos/" + p.file;
  $("credit").textContent = p.credit;
  $("credit").title = p.title || "";
}

async function setupTips() {
  const r = await loadJSON("tips.txt"); if (!r) return;
  const tips = (await r.text()).split("\n").map((t) => t.trim()).filter((t) => t && !t.startsWith("#"));
  if (!tips.length) return;
  const deck = tips.map((t) => [Math.random(), t]).sort((a, b) => a[0] - b[0]).map((x) => x[1]); // shuffled
  let i = 0;
  const el = $("tip"); el.hidden = false; el.textContent = deck[0];
  el.addEventListener("click", () => {
    i = (i + 1) % deck.length;
    el.classList.add("swap");
    setTimeout(() => { el.textContent = deck[i]; el.classList.remove("swap"); }, 200);
  });
}
setupPhoto(); setupTips();
