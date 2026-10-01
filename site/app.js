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
      image: isVideo(e.url) ? e.image || null : null, highlight: e.highlight || null, url: e.url,
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
      image: isVideo(l.url) ? l.image || null : null, url: l.url, platform: l.platform, pill: l.platform,
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

  const dayOfYear = (d) => Math.floor((d - new Date(d.getFullYear(), 0, 0)) / 864e5);
  let tipIndex = dayOfYear(new Date()) % TIPS.length;

  // Park photos come only from the owner's NPS set, listed in site/parks/parks.json
  // (run `python fetcher/parks.py` after adding photos). No set → plain green, never a stand-in.
  async function loadParks() {
    if (Array.isArray(window.__PARKS__)) return window.__PARKS__;
    try {
      const r = await fetch("parks/parks.json", { cache: "no-cache" });
      if (r.ok) {
        const list = await r.json();
        return (Array.isArray(list) ? list : []).filter((p) => p && p.file)
          .map((p) => ({ ...p, src: "parks/" + encodeURIComponent(p.file) }));
      }
    } catch (e) { /* no photo set yet */ }
    return [];
  }

  function openingHTML(brief, model, park) {
    const now = new Date();
    const date = brief && brief.date ? new Date(brief.date + "T12:00:00") : now;
    const weekday = date.toLocaleDateString(undefined, { weekday: "long" });
    const day = date.toLocaleDateString(undefined, { month: "long", day: "numeric" });
    let cue = "Scroll for today's news";
    if (model) {
      const nEp = model.listen.length;
      const nStories = model.black.filter((x) => x.kind === "headline").length + model.read.length + model.headlines.length;
      cue = `${nEp} ${nEp === 1 ? "episode" : "episodes"} · ${nStories} ${nStories === 1 ? "story" : "stories"}`;
    }
    const photo = park
      ? `<img class="opening__photo" src="${esc(park.src)}" alt="${esc(park.park || "National park")}" onerror="this.remove()">`
      : "";
    const credit = park
      ? `<span class="opening__credit">${esc(park.park || "")}${park.credit ? " · " + esc(park.credit) : " · NPS"}</span>`
      : "";
    return `
      <header class="opening" id="opening">
        <div class="opening__bg" aria-hidden="${park ? "false" : "true"}">${photo}<div class="opening__shade"></div></div>
        <div class="opening__inner">
          <div class="opening__brand">The Black Brief${window.__SAMPLE__ ? ' <span class="opening__sample">Sample</span>' : ""}</div>
          <p class="opening__greet">${greeting(now)}</p>
          <h1 class="opening__date"><span>${esc(weekday)}</span> ${esc(day)}</h1>
          <button class="opening__tip" type="button" data-tip aria-live="polite">
            <span class="opening__label">Grounding tip</span>
            <span class="opening__tiptext" data-tip-text>${esc(TIPS[tipIndex])}</span>
            <span class="opening__again">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 4v5h-5"/></svg>
              Tap for another
            </span>
          </button>
        </div>
        <div class="opening__foot">
          ${credit}
          <span class="opening__cue">${esc(cue)}
            <svg width="14" height="9" viewBox="0 0 14 9" aria-hidden="true"><path d="M1.5 1.5 7 7l5.5-5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
        </div>
      </header>`;
  }

  function nextTip() {
    const el = document.querySelector("[data-tip-text]");
    if (!el) return;
    tipIndex = (tipIndex + 1) % TIPS.length;
    el.classList.add("is-out");
    setTimeout(() => { el.textContent = TIPS[tipIndex]; el.classList.remove("is-out"); }, 180);
  }

  // As the news slides up, the park photo fades and the words drift away.
  function wireOpening() {
    const op = document.getElementById("opening");
    if (!op) return;
    const bg = op.querySelector(".opening__bg");
    const inner = op.querySelector(".opening__inner");
    const foot = op.querySelector(".opening__foot");
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let queued = false;
    const paint = () => {
      queued = false;
      const p = Math.min(1, Math.max(0, scrollY / (innerHeight * 0.8)));
      bg.style.opacity = String(1 - p);
      if (!still) bg.style.transform = `scale(${1 + p * 0.06})`;
      inner.style.opacity = String(Math.max(0, 1 - p * 1.7));
      if (!still) inner.style.transform = `translateY(${-p * 48}px)`;
      foot.style.opacity = String(Math.max(0, 1 - p * 3));
    };
    addEventListener("scroll", () => { if (!queued) { queued = true; requestAnimationFrame(paint); } }, { passive: true });
    addEventListener("resize", paint);
    paint();
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

  let park = null;

  function renderHome() {
    if (!brief) {
      app.innerHTML = openingHTML(null, null, park) + `<div class="news">
        <div class="empty"><h2>No brief yet</h2>
        <p>Run <b>/black-brief</b> in Claude Code on your computer. The new brief shows up here once it's pushed.</p></div></div>`;
      wireOpening();
      return;
    }
    const failed = (brief.failed_sources || []).length
      ? `<div class="notice">Couldn't reach ${esc(listText(brief.failed_sources))} this morning.</div>` : "";
    const feed = SECTIONS.map((s) => sectionHTML(s, model[s.key])).join("");
    const written = brief.generated_at
      ? new Date(brief.generated_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "";
    app.innerHTML = openingHTML(brief, model, park) + `<div class="news">${failed}<main class="feed">${feed}</main>` +
      `<footer class="foot">Written ${esc(written)}. Summaries and short quotes only; tap through to the original.</footer></div>`;
    wireImages(app);
    wireOpening();
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
    if (e.target.closest("[data-tip]")) { nextTip(); return; }
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

  Promise.all([loadBrief(), loadParks()]).then(([b, parks]) => {
    brief = b;
    park = parks.length ? parks[dayOfYear(new Date()) % parks.length] : null;
    if (b) {
      model = buildModel(b);
      [...model.listen, ...model.black, ...model.read, ...model.headlines].forEach((i) => byId.set(i.id, i));
    }
    renderHome();
    route();
  });
})();
