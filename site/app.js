/* The Black Brief: renders data/latest.json as one scrolling home screen.
   Images load straight from each source (never downloaded or committed). */
(function () {
  "use strict";

  const app = document.getElementById("app");

  // Grounding tips: one a day, in order. Edit freely.
  const TIPS = [
    "Breathe in for 4 counts, hold for 4, out for 6. Do it three times before you scroll.",
    "Name 5 things you can see, 4 you can hear, 3 you can touch. Then read on.",
    "Put both feet flat on the floor. Notice the ground holding you up.",
    "Unclench your jaw and drop your shoulders. Take one slow breath.",
    "You can care about the news and still close the app. Pick one story and let the rest wait.",
    "Drink a glass of water before your first headline.",
    "Look out a window for 30 seconds. Find the farthest thing you can see.",
    "Press your palms together for 5 seconds, then release. Notice the warmth.",
    "Say one thing you're grateful for out loud before you read.",
    "Roll your neck slowly, once each way. News can wait ten seconds.",
    "Hold something with texture, like a mug or a stone. Feel it for three breaths.",
    "Breathe out longer than you breathe in. Your body reads that as safe.",
    "Stretch your arms overhead and reach. Then begin.",
    "Read with a question in mind: what can I actually do with this today?",
  ];

  // Section order on the home screen, with the tone (color wash) each uses.
  const SECTIONS = [
    { key: "listen", tone: "listen", title: "Listen" },
    { key: "black", tone: "black", title: "Black Life" },
    { key: "read", tone: "read", title: "Read" },
    { key: "headlines", tone: "head", title: "Headlines" },
    { key: "quotes", tone: "read", title: "Quotes" },
    { key: "levity", tone: "levity", title: "Levity" },
  ];
  const BASE_HUE = { listen: 265, black: 36, read: 216, head: 352, levity: 148 };
  const QUOTE_TONES = ["read", "head", "black", "listen", "levity"];

  // ---------- helpers ----------
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  function highlight(text, word) {
    const safe = esc(text);
    if (!word) return safe;
    const re = new RegExp("(^|[^\\p{L}\\p{N}])(" + esc(word).replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")(?![\\p{L}\\p{N}])", "iu");
    return safe.replace(re, '$1<span class="hl">$2</span>');
  }

  function ago(iso) {
    if (!iso) return "";
    const ms = Date.now() - new Date(iso).getTime();
    if (!isFinite(ms)) return "";
    const h = Math.floor(ms / 3.6e6);
    if (h < 1) return Math.max(1, Math.floor(ms / 6e4)) + "M AGO";
    if (h < 48) return h + "H AGO";
    return Math.floor(h / 24) + "D AGO";
  }

  function hueFor(name, tone) {
    let n = 0;
    for (const ch of String(name)) n = (n * 31 + ch.charCodeAt(0)) % 997;
    return BASE_HUE[tone] + ((n % 5) - 2) * 9;
  }

  const isVideo = (url) => /youtube\.com|youtu\.be/.test(url || "");

  function host(url) {
    try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; }
  }

  // ---------- data ----------
  async function loadBrief() {
    if (window.__BRIEF__) return window.__BRIEF__;
    for (const path of ["data/latest.json", "../data/latest.json"]) {
      try {
        const r = await fetch(path, { cache: "no-cache" });
        if (r.ok) return await r.json();
      } catch (e) { /* try the next path */ }
    }
    return null;
  }

  function buildModel(b) {
    const ep = (b.episodes || []).map((e) => ({
      kind: "episode", id: e.id, title: e.title, source: e.source, published: e.published,
      image: e.image || null, highlight: e.highlight || null, url: e.url,
      dek: e.takeaway, cards: e.cards || [], quotes: e.quotes || [], takeaway: e.takeaway,
      black: !!e.black_life, pill: isVideo(e.url) ? "Video" : "Podcast",
    }));
    const hl = (b.headlines || []).map((h) => ({
      kind: "headline", id: h.id, title: h.headline, source: h.source, published: h.published,
      image: h.image || null, highlight: h.highlight || null, url: h.url,
      dek: h.summary, summary: h.summary, black: !!h.black_life,
    }));
    const lev = (b.levity || []).map((l) => ({
      kind: "levity", id: l.id, title: l.title, source: l.show || l.source, published: l.published,
      image: l.image || null, url: l.url, platform: l.platform, pill: l.platform,
    }));
    const quotes = ep.flatMap((e) =>
      e.quotes.map((q) => ({ ...q, episode: e }))
    );
    const byNewest = (a, c) => new Date(c.published || 0) - new Date(a.published || 0);
    return {
      listen: ep,
      black: [...hl.filter((h) => h.black), ...ep.filter((e) => e.black).sort(byNewest)],
      read: hl.filter((h) => !h.black && h.summary),
      headlines: hl.filter((h) => !h.black && !h.summary),
      quotes,
      levity: lev,
    };
  }

  const names = (items) => [...new Set(items.map((i) => i.source))];
  function listText(arr) {
    if (arr.length <= 2) return arr.join(" and ");
    return arr.slice(0, 2).join(", ") + " and " + (arr.length - 2) + " more";
  }

  function subtitle(key, items) {
    const n = items.length;
    switch (key) {
      case "listen": return `${n} new ${n === 1 ? "episode" : "episodes"} from ${listText(names(items))}`;
      case "black": return `${n} ${n === 1 ? "story" : "stories"} centered on Black life today`;
      case "read": return `Summaries from ${listText(names(items))}`;
      case "headlines": return `Headline and link from ${listText(names(items))}`;
      case "quotes": return "The lines worth hearing, with timestamps";
      case "levity": return `Something to laugh at from ${listText(names(items))}`;
    }
    return "";
  }

  // ---------- rendering ----------
  function imageTag(src) {
    if (!src) return "";
    return `<img class="card__img" src="${esc(src)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">`;
  }

  function cardHTML(item, tone, opts = {}) {
    const when = item.kind === "levity" ? item.platform : ago(item.published);
    const dek = opts.dek !== false && item.dek ? `<p class="card__dek">${esc(item.dek)}</p>` : "";
    const pill = item.pill
      ? `<span class="card__pill">${item.pill === "Video" || item.pill === "YouTube" ? playIcon() : waveIcon()}${esc(item.pill)}</span>`
      : "";
    const body = `
      <div class="card__tile" style="--h:${hueFor(item.source, tone)}"><span>${esc(item.source)}</span></div>
      ${imageTag(item.image)}
      ${pill}
      <div class="card__body">
        <div class="meta"><span class="meta__src">${esc(item.source)}</span>${when ? `<span class="meta__when">&nbsp;· ${esc(when)}</span>` : ""}</div>
        <h3 class="card__title">${highlight(item.title, item.highlight)}</h3>
        ${dek}
      </div>`;
    if (opts.static) return `<div class="card" data-tone="${tone}">${body}</div>`;
    // Headline-only items have nothing more to show: the card is the link.
    const direct = item.kind === "levity" || (item.kind === "headline" && !item.summary);
    if (direct) {
      return `<a class="card" data-tone="${tone}" href="${esc(item.url)}" target="_blank" rel="noopener">${body}</a>`;
    }
    return `<button class="card" type="button" data-tone="${tone}" data-open="${esc(item.id)}" aria-label="${esc(item.title)}">${body}</button>`;
  }

  function quoteHTML(q, i) {
    const tone = QUOTE_TONES[i % QUOTE_TONES.length];
    const who = q.speaker || q.episode.source;
    return `
      <figure class="quote" data-tone="${tone}" style="margin:0">
        <div class="quote__mark" aria-hidden="true">&ldquo;</div>
        <blockquote class="quote__text" style="margin:0">${esc(q.text)}</blockquote>
        <figcaption class="quote__foot">
          <span class="quote__who">${esc(who)}</span>
          <span class="quote__ctx">${esc(q.speaker ? q.episode.source + " · " : "")}${esc(q.episode.title)}</span>
          <a class="stamp" href="${esc(q.url)}" target="_blank" rel="noopener" aria-label="Play from ${esc(q.timestamp)}">${playIcon()}${esc(q.timestamp)}</a>
        </figcaption>
      </figure>`;
  }

  function playIcon() {
    return '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1.2v7.6L8.6 5z"/></svg>';
  }
  function waveIcon() {
    return '<svg viewBox="0 0 12 10" width="12" height="10" aria-hidden="true" fill="currentColor"><rect x="0" y="3.5" width="1.6" height="3" rx=".8"/><rect x="3.2" y="1.5" width="1.6" height="7" rx=".8"/><rect x="6.4" y="0" width="1.6" height="10" rx=".8"/><rect x="9.6" y="2.5" width="1.6" height="5" rx=".8"/></svg>';
  }

  function greeting(d) {
    const h = d.getHours();
    return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  }

  function tipFor(d) {
    const start = new Date(d.getFullYear(), 0, 0);
    const day = Math.floor((d - start) / 864e5);
    return TIPS[day % TIPS.length];
  }

  function heroHTML(brief, model) {
    const now = new Date();
    const date = brief && brief.date ? new Date(brief.date + "T12:00:00") : now;
    const dateText = date.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
    const nEp = model ? model.listen.length : 0;
    const nStories = model ? model.black.filter((x) => x.kind === "headline").length + model.read.length + model.headlines.length : 0;
    const counts = model ? ` · ${nEp} ${nEp === 1 ? "episode" : "episodes"}, ${nStories} stories` : "";
    const photo = window.BRIEF_HEADER || "header.jpg";
    return `
      <header class="hero">
        <div class="hero__fallback"></div>
        <img class="hero__photo" src="${esc(photo)}" alt="" onerror="this.remove()">
        <div class="hero__top">
          <div class="mark"><div class="mark__logo" aria-hidden="true">BB</div><div class="mark__name">The Black Brief</div></div>
          ${window.__SAMPLE__ ? '<span class="chip">Sample brief</span>' : ""}
        </div>
        <h1 class="hero__greet">${greeting(now)}</h1>
        <p class="hero__sub">${esc(dateText)}${esc(counts)}</p>
        ${window.BRIEF_HEADER_CREDIT ? `<span class="hero__credit">${esc(window.BRIEF_HEADER_CREDIT)}</span>` : ""}
      </header>
      <aside class="tip" aria-label="Grounding tip">
        <div class="tip__icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/></svg>
        </div>
        <div><div class="tip__label">Grounding tip</div><p class="tip__text">${esc(tipFor(now))}</p></div>
      </aside>`;
  }

  function sectionHTML(sec, items) {
    if (!items.length) return "";
    const rail = sec.key === "quotes"
      ? items.map(quoteHTML).join("")
      : items.map((it) => cardHTML(it, sec.tone)).join("");
    return `
      <section class="sec" data-tone="${sec.tone}" aria-labelledby="h-${sec.key}">
        <a class="sec__head" href="#${sec.key}">
          <h2 class="sec__title" id="h-${sec.key}">${esc(sec.title)} <span class="sec__chev" aria-hidden="true">›</span></h2>
          <p class="sec__sub">${esc(subtitle(sec.key, items))}</p>
        </a>
        <div class="rail">${rail}</div>
      </section>`;
  }

  let brief = null;
  let model = null;
  const byId = new Map();

  function renderHome() {
    if (!brief) {
      app.innerHTML = heroHTML(null, null) + `
        <div class="empty"><h2>No brief yet</h2>
        <p>Run <b>/black-brief</b> in Claude Code on your computer. The new brief shows up here once it's pushed.</p></div>`;
      return;
    }
    const failed = (brief.failed_sources || []).length
      ? `<div class="notice">Couldn't reach ${esc(listText(brief.failed_sources))} this morning.</div>` : "";
    const feed = SECTIONS.map((s) => sectionHTML(s, model[s.key])).join("");
    const written = brief.generated_at
      ? new Date(brief.generated_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "";
    app.innerHTML = heroHTML(brief, model) + failed + `<main class="feed">${feed}</main>` +
      `<footer class="foot">Written ${esc(written)}. Summaries and short quotes only; tap through to the original.</footer>`;
    wireImages(app);
  }

  function renderPage(key) {
    const sec = SECTIONS.find((s) => s.key === key);
    closePage();
    if (!sec || !model || !model[key].length) return;
    const items = model[key];
    const body = key === "quotes"
      ? `<div class="list" style="grid-template-columns:1fr">${items.map(quoteHTML).join("")}</div>`
      : `<div class="list">${items.map((it) => cardHTML(it, sec.tone)).join("")}</div>`;
    const page = document.createElement("div");
    page.className = "page";
    page.dataset.tone = sec.tone;
    page.setAttribute("role", "dialog");
    page.setAttribute("aria-label", sec.title);
    page.innerHTML = `
      <div class="page__bar"><button class="back" type="button" data-back>
        <svg width="12" height="20" viewBox="0 0 12 20" aria-hidden="true"><path d="M10 2 2 10l8 8" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>Today</button></div>
      <div class="page__head"><h1 class="page__title">${esc(sec.title)}</h1><p class="page__sub">${esc(subtitle(key, items))}</p></div>
      ${body}`;
    document.body.appendChild(page);
    document.body.style.overflow = "hidden";
    wireImages(page);
    page.querySelector("[data-back]").focus({ preventScroll: true });
  }

  function closePage() {
    document.querySelectorAll(".page").forEach((p) => p.remove());
    if (!document.querySelector(".sheet")) document.body.style.overflow = "";
  }

  // The sheet keeps the color of the card that was tapped.
  function openSheet(id, tone) {
    const item = byId.get(id);
    if (!item) return;
    tone = tone || (item.kind === "episode" ? "listen" : "read");
    let inner = cardHTML(item, tone, { static: true, dek: false });
    if (item.kind === "episode") {
      if (item.takeaway) inner += `<div class="takeaway"><div class="label">Takeaway</div><p>${esc(item.takeaway)}</p></div>`;
      if (item.cards.length) {
        inner += `<div class="sheet__section"><div class="label">What was said</div><ol class="points">${
          item.cards.map((c, i) => `<li><b>${i + 1}</b><span>${esc(c)}</span></li>`).join("")}</ol></div>`;
      }
      if (item.quotes.length) {
        inner += `<div class="sheet__section"><div class="label">Quotes</div><div class="quotes">${
          item.quotes.map((q, i) => quoteHTML({ ...q, episode: item }, i)).join("")}</div></div>`;
      }
    } else if (item.summary) {
      inner += `<p class="summary">${esc(item.summary)}</p>`;
    }
    const verb = item.kind === "episode" ? (isVideo(item.url) ? "Watch on YouTube" : "Listen to the episode") : `Read at ${host(item.url) || item.source}`;
    inner += `<a class="open" href="${esc(item.url)}" target="_blank" rel="noopener">${esc(verb)} <span aria-hidden="true">↗</span></a>`;

    const scrim = document.createElement("div");
    scrim.className = "scrim";
    const sheet = document.createElement("div");
    sheet.className = "sheet";
    sheet.dataset.tone = tone;
    sheet.setAttribute("role", "dialog");
    sheet.setAttribute("aria-modal", "true");
    sheet.setAttribute("aria-label", item.title);
    sheet.innerHTML = `<div class="sheet__grab" aria-hidden="true"></div><button class="sheet__close" type="button" aria-label="Close" data-close>✕</button>${inner}`;
    document.body.append(scrim, sheet);
    document.body.style.overflow = "hidden";
    wireImages(sheet);
    scrim.addEventListener("click", closeSheet);
    sheet.querySelector("[data-close]").focus({ preventScroll: true });
  }

  function closeSheet() {
    document.querySelectorAll(".sheet, .scrim").forEach((n) => n.remove());
    if (!document.querySelector(".page")) document.body.style.overflow = "";
  }

  // Broken or missing images fall back to the colored source tile underneath.
  function wireImages(root) {
    root.querySelectorAll("img.card__img").forEach((img) => {
      img.addEventListener("error", () => {
        if (img.src.includes("/hq720.jpg")) img.src = img.src.replace("/hq720.jpg", "/hqdefault.jpg");
        else img.remove();
      }, { once: false });
    });
  }

  // ---------- events ----------
  document.addEventListener("click", (e) => {
    const open = e.target.closest("[data-open]");
    if (open) { openSheet(open.dataset.open, open.dataset.tone); return; }
    if (e.target.closest("[data-close]")) { closeSheet(); return; }
    if (e.target.closest("[data-back]")) {
      if (history.state && history.state.fromHome) history.back();
      else location.hash = "";
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (document.querySelector(".sheet")) closeSheet();
    else if (document.querySelector(".page")) location.hash = "";
  });
  document.addEventListener("click", (e) => {
    const head = e.target.closest(".sec__head");
    if (!head) return;
    e.preventDefault();
    history.pushState({ fromHome: true }, "", head.getAttribute("href"));
    route();
  });
  window.addEventListener("hashchange", route);
  window.addEventListener("popstate", route);

  function route() {
    const key = location.hash.slice(1);
    if (key) renderPage(key);
    else closePage();
  }

  loadBrief().then((b) => {
    brief = b;
    if (b) {
      model = buildModel(b);
      [...model.listen, ...model.black, ...model.read, ...model.headlines].forEach((i) => byId.set(i.id, i));
    }
    renderHome();
    route();
  });
})();
