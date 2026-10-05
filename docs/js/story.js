/* Migration by Skill: the data story. A bold opening, eight chapters, and the bottom line. In each chapter a chart
   sticks beside (or under) the text and changes as each step of text scrolls past: Scrollama tells us which step
   is in view. Without IntersectionObserver (old browsers, headless tests) every chapter shows its first step. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el, reducedMotion, debounce } = MBS.util;
  const F = MBS.fmt;
  const S = { layers: {}, active: {}, scroller: null };
  MBS.story = S;

  const rich = MBS.rich;
  const val = (v, d) => (typeof v === "function" ? v(d) : v);
  const canAnimate = () => typeof window.IntersectionObserver === "function" && !reducedMotion();

  // the report exhibit that holds the full version of a chart
  function exhibitFor(chart) {
    const ex = MBS.content.exhibits.find(e => e.chart === chart);
    return ex ? ex.id : null;
  }

  // ---------------------------------------------------------------- the opening
  function hero(d) {
    const H = MBS.content.hero;
    const target = Math.round(d.q1.per_day);
    const num = el("span", { class: "hero-num", "data-to": String(target), "aria-hidden": "true" }, canAnimate() ? "0" : H.number(d));
    const dotsHost = el("div", { class: "hero-dots-host" });
    const sec = el("section", { class: "hero", id: "top", "aria-labelledby": "hero-h" },
      el("div", { class: "wrap-wide hero-in" },
        el("div", { class: "hero-text" },
          el("p", { class: "hero-kicker", text: H.kicker }),
          el("h1", { id: "hero-h", class: "hero-h", "aria-label": `${H.number(d)} ${H.line}` }, num, el("span", { class: "hero-line", "aria-hidden": "true", text: H.line })),
          el("p", { class: "hero-q", text: H.question }),
          el("p", { class: "hero-note", text: H.note(d) }),
          el("div", { class: "hero-actions" },
            el("a", { class: "btn btn-hero", href: "#ch1" }, "Start the story", el("span", { "aria-hidden": "true" }, "↓")),
            el("a", { class: "btn btn-ghost", href: "#simulator" }, "Try the simulator"),
            el("a", { class: "btn btn-ghost", href: "#report" }, "Read the report")),
          el("p", { class: "hero-lede", text: H.lede })),
        el("figure", { class: "hero-dots" }, dotsHost, el("figcaption", { text: H.dots }))),
      el("p", { class: "hero-draft" }, el("strong", null, "Draft for review. "), MBS.content.meta.status));
    S.heroDots = () => dots(dotsHost, target);
    S.heroCount = () => countUp(num, target);
    return sec;
  }
  function dots(host, n) {
    const cols = 40, rows = Math.ceil(n / cols), step = 12;
    const svg = d3.select(host).append("svg").attr("viewBox", `0 0 ${cols * step} ${rows * step}`).attr("aria-hidden", "true")
      .attr("preserveAspectRatio", "xMidYMid meet");
    const c = svg.selectAll("circle").data(d3.range(n)).join("circle")
      .attr("cx", i => (i % cols) * step + step / 2).attr("cy", i => Math.floor(i / cols) * step + step / 2).attr("r", 3.6).attr("class", "hdot");
    if (canAnimate()) {
      const rnd = d3.randomLcg(7);
      const delays = d3.range(n).map(() => rnd() * 1600);
      c.attr("opacity", 0).transition().delay(i => 250 + delays[i]).duration(260).attr("opacity", 1);
    }
  }
  function countUp(node, to) {
    if (!canAnimate() || !window.requestAnimationFrame) { node.textContent = F.int(to); return; }
    const t0 = performance.now(), dur = 1800;
    const tick = now => {
      const k = Math.min(1, (now - t0) / dur);
      node.textContent = F.int(Math.round(to * (1 - Math.pow(1 - k, 3))));
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  // ---------------------------------------------------------------- chapter openers
  function opener(ch, d) {
    return el("header", { class: "opener" }, el("div", { class: "wrap-wide opener-in" },
      el("div", { class: "opener-left" },
        el("p", { class: "opener-num", "aria-hidden": "true", text: String(ch.n).padStart(2, "0") }),
        el("p", { class: "opener-kicker", text: `Chapter ${ch.n} · ${ch.kicker}` }),
        el("h2", { class: "opener-title", id: `${ch.id}-h`, tabindex: "-1", text: val(ch.title, d) })),
      el("div", { class: "opener-stat" },
        el("span", { class: "opener-big", text: ch.stat(d) }),
        el("span", { class: "opener-lab", text: ch.statLabel(d) }))));
  }

  // ---------------------------------------------------------------- one chapter: steps + sticky graphic
  function chapter(ch, d) {
    if (ch.claims) return claimsChapter(ch, d);
    const layers = {};
    const stage = el("div", { class: "stage" });
    const firstState = key => { const s = ch.steps.find(z => z.layer === key); return s ? s.state : null; };
    for (const [key, def] of Object.entries(ch.layers)) {
      const host = el("div", { class: "chart-host" });
      const exId = exhibitFor(def.chart);
      const fig = el("figure", { class: "layer", "data-layer": key, id: `${ch.id}-${key}`, "aria-hidden": "true" },
        el("figcaption", { class: "layer-title", text: val(def.title, d) }),
        host,
        el("div", { class: "layer-foot" }, MBS.ui.badges(def.types), MBS.ui.sourceLine(def.sources(d)),
          exId ? el("a", { class: "layer-more", href: `#${exId}` }, "Table and details", el("span", { "aria-hidden": "true" }, " →")) : null));
      const chart = MBS.charts[def.chart](host, d, { scene: firstState(key) || "report", compact: true });
      layers[key] = { key, def, host, fig, chart, rendered: false, width: 0 };
      stage.appendChild(fig);
    }
    S.layers[ch.id] = layers;
    const steps = el("div", { class: "scrolly-steps" },
      ch.steps.map((st, i) => el("div", { class: "step", "data-ch": ch.id, "data-i": String(i) },
        el("div", { class: "step-card" }, el("p", null, rich(st.text(d)))))));
    const sec = el("section", { class: "chapter", id: ch.id, "aria-labelledby": `${ch.id}-h` },
      opener(ch, d),
      el("div", { class: "scrolly wrap-wide" }, steps, el("div", { class: "scrolly-graphic" }, stage)));
    return sec;
  }

  function claimsChapter(ch, d) {
    const host = el("div", { class: "chart-host" });
    const chart = MBS.charts.claims(host, d);
    S.claims = { host, chart };
    return el("section", { class: "chapter chapter-claims", id: ch.id, "aria-labelledby": `${ch.id}-h` },
      opener(ch, d),
      el("div", { class: "wrap-wide claims-wrap" },
        el("p", { class: "claims-intro" }, rich(ch.intro(d))),
        host,
        el("p", { class: "claims-more" }, el("a", { href: "#ex20" }, `See all ${d.q13.total} claims, with filters, in the report`, el("span", { "aria-hidden": "true" }, " →")))));
  }

  // ---------------------------------------------------------------- scrolling: which step is active
  function activate(chId, i) {
    const ch = MBS.content.chapters.find(c => c.id === chId);
    const L = S.layers[chId];
    if (!ch || !L || !ch.steps[i]) return;
    const st = ch.steps[i];
    S.active[chId] = i;
    document.querySelectorAll(`.step[data-ch="${chId}"]`).forEach(n => n.classList.toggle("is-active", +n.getAttribute("data-i") === i));
    for (const lay of Object.values(L)) {
      const on = lay.key === st.layer;
      lay.fig.classList.toggle("is-on", on);
      lay.fig.setAttribute("aria-hidden", String(!on));
    }
    const lay = L[st.layer];
    if (!lay.rendered) {
      lay.rendered = true;
      lay.width = lay.host.clientWidth;
      if (st.state && lay.chart.update) lay.chart.update(st.state);
      lay.chart.render(canAnimate());
      return;
    }
    if (st.state === "sort" && st.layer === "growth") { lay.chart.render(canAnimate()); return; }
    if (st.state && lay.chart.update) lay.chart.update(st.state);
  }
  S.activate = activate;

  function setupScroll() {
    const chs = MBS.content.chapters.filter(c => !c.claims);
    // each chapter shows its first step as it comes near the screen
    chs.forEach(ch => {
      const node = document.getElementById(ch.id);
      if (node) MBS.shell.lazy(node, () => { if (S.active[ch.id] == null) activate(ch.id, 0); }, "400px 0px");
    });
    if (S.claims) MBS.shell.lazy(S.claims.host, () => S.claims.chart.render(false));
    // the opening animates once it is on screen and the welcome guide (if open) is closed
    let heroDone = false;
    const heroGo = () => { if (heroDone || (MBS.guide && MBS.guide.isOpen)) return; heroDone = true; S.heroDots(); S.heroCount(); };
    document.addEventListener("mbs-guide-closed", () => setTimeout(heroGo, 150));
    MBS.shell.lazy(document.getElementById("top"), heroGo, "0px");
    if (typeof window.scrollama !== "function" || typeof window.IntersectionObserver !== "function") return;
    const sc = window.scrollama();
    S.scroller = sc;
    sc.setup({ step: ".story .step", offset: window.innerWidth < 1000 ? 0.86 : 0.62 })
      .onStepEnter(({ element }) => activate(element.getAttribute("data-ch"), +element.getAttribute("data-i")));
  }

  function onResize() {
    for (const L of Object.values(S.layers)) {
      for (const lay of Object.values(L)) {
        if (!lay.rendered) continue;
        const w = lay.host.clientWidth;
        if (Math.abs(w - lay.width) < 8) continue;
        lay.width = w;
        lay.chart.render(false);
        if (lay.chart.lit && lay.chart.update) lay.chart.update(lay.chart.lit);
      }
    }
    if (S.scroller) S.scroller.resize();
  }

  // ---------------------------------------------------------------- the bottom line
  function bottomLine(d) {
    const B = MBS.content.bottomLine;
    return el("section", { class: "bottom-line", id: "bottom-line", "aria-labelledby": "bl-h" },
      el("div", { class: "wrap-wide" },
        el("h2", { id: "bl-h", class: "bl-title", text: B.title }),
        el("div", { class: "bl-grid" }, B.items.map(it => el("div", { class: "bl-card" },
          el("p", { class: "bl-big", text: it.big(d) }), el("p", { class: "bl-text", text: it.text(d) })))),
        el("div", { class: "bl-actions" },
          el("a", { class: "btn btn-primary", href: "#simulator" }, "Try the simulator", el("span", { "aria-hidden": "true" }, "↓")),
          el("a", { class: "btn", href: "#report" }, "Read the full report"),
          el("a", { class: "btn", href: "brief.html" }, "Get the two-page brief"))));
  }

  function build(main) {
    const d = MBS.data;
    const story = el("div", { class: "story", id: "story" });
    story.appendChild(hero(d));
    for (const ch of MBS.content.chapters) story.appendChild(chapter(ch, d));
    story.appendChild(bottomLine(d));
    main.appendChild(story);
    S.setup = setupScroll;
    window.addEventListener("resize", debounce(onResize, 200));
  }
  MBS.buildStory = build;
})();
