/* Migration by Skill: the page frame. Top bar with section links, the ? and Dark/Light buttons, a reading progress
   line, the footer, and lazy drawing (charts draw as they come near the screen). */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el } = MBS.util;

  const LINKS = [
    { href: "#story", label: "Story", id: "story" },
    { href: "#simulator", label: "Simulator", id: "simulator" },
    { href: "#report", label: "Report", id: "report" },
    { href: "#models", label: "Models", id: "models" },
    { href: "brief.html", label: "Brief", ext: true },
    { href: "methods.html", label: "Methods", ext: true }
  ];

  function logo() {
    const ns = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(ns, "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("width", "22"); s.setAttribute("height", "22"); s.setAttribute("aria-hidden", "true");
    s.setAttribute("class", "logo");
    [[3, 14, 4, 7], [10, 8, 4, 13], [17, 3, 4, 18]].forEach(([x, y, w, h], i) => {
      const r = document.createElementNS(ns, "rect");
      r.setAttribute("x", x); r.setAttribute("y", y); r.setAttribute("width", w); r.setAttribute("height", h); r.setAttribute("rx", "1.5");
      r.setAttribute("class", i === 2 ? "logo-hi" : "logo-lo");
      s.appendChild(r);
    });
    return s;
  }

  function header(opts) {
    const page = (opts && opts.page) || "index";
    const local = page === "index";
    const href = l => (l.ext || local ? l.href : `index.html${l.href}`);
    const nav = el("nav", { class: "nav", "aria-label": "Sections" },
      LINKS.map(l => el("a", { href: href(l), "data-sec": l.id || null, class: (page === "methods" && l.label === "Methods") || (page === "brief" && l.label === "Brief") ? "is-current" : null,
        "aria-current": (page === "methods" && l.label === "Methods") || (page === "brief" && l.label === "Brief") ? "page" : null }, l.label)));
    const menu = el("details", { class: "menu" }, el("summary", { "aria-label": "Sections" }, "Menu"),
      el("div", { class: "menu-list" }, LINKS.map(l => el("a", { href: href(l), onclick: () => { menu.open = false; } }, l.label))));
    const bar = el("header", { class: "topbar" },
      el("div", { class: "topbar-in" },
        el("a", { class: "brand", href: local ? "#top" : "index.html" }, logo(), el("span", null, MBS.content.meta.title)),
        nav,
        el("span", { class: "spacer" }),
        el("button", { class: "help-btn", type: "button", id: "help-btn", "aria-label": "How to use this page", title: "How to use this page",
          onclick: () => MBS.guide && MBS.guide.open() }, "?"),
        MBS.ui.themeToggle(),
        menu),
      el("div", { class: "progress-bar", "aria-hidden": "true" }, el("span", { id: "progress-fill" })));
    return bar;
  }

  function footer() {
    const C = MBS.content, d = MBS.data, F = MBS.fmt;
    return el("footer", { class: "site-footer" }, el("div", { class: "wrap-wide footer-in" },
      el("div", null,
        el("p", { class: "footer-brand" }, C.meta.title),
        el("p", null, C.meta.tagline)),
      el("div", null,
        el("p", null, `Version ${d.version}. Data to ${F.yearTo("Year to " + monthShort(d.data_to)).replace("year to ", "")}. Made by ${C.meta.author}.`),
        el("p", null, "Skills, not nationality: this project looks at jobs, skills and places, never at where people come from."),
        el("p", null, el("a", { href: "methods.html", text: "Data and methods" }), " · ", el("a", { href: "brief.html", text: "Two-page brief" }), " · ",
          el("a", { href: "#top", text: "Back to top" })))));
  }
  function monthShort(p) { const [y, m] = p.split("-"); return `${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+m - 1]} ${y}`; }

  // reading progress and the current section in the top bar
  function track() {
    const fill = document.getElementById("progress-fill");
    const onScroll = () => {
      const h = document.documentElement.scrollHeight - window.innerHeight;
      if (fill) fill.style.width = `${h > 0 ? Math.min(100, (100 * window.scrollY) / h) : 0}%`;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    if (typeof window.IntersectionObserver !== "function") return;
    const links = Array.from(document.querySelectorAll(".nav a[data-sec]"));
    const io = new IntersectionObserver(es => {
      es.forEach(e => {
        if (!e.isIntersecting) return;
        const id = e.target.id;
        links.forEach(a => {
          const on = a.getAttribute("data-sec") === id;
          a.classList.toggle("is-current", on);
          if (on) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current");
        });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    ["story", "simulator", "report", "models"].forEach(id => { const n = document.getElementById(id); if (n) io.observe(n); });
  }

  // draw fn() once the element is within `margin` of the screen; headless browsers draw at once
  const pending = [];
  let lazyIO = null;
  function lazy(node, fn, margin) {
    if (typeof window.IntersectionObserver !== "function") { fn(); return; }
    if (!lazyIO) {
      lazyIO = new IntersectionObserver(es => es.forEach(e => {
        if (!e.isIntersecting) return;
        lazyIO.unobserve(e.target);
        const i = pending.findIndex(p => p.node === e.target);
        if (i >= 0) { const p = pending.splice(i, 1)[0]; p.fn(); }
      }), { rootMargin: margin || "300px 0px" });
    }
    pending.push({ node, fn });
    lazyIO.observe(node);
  }
  // draw everything still waiting (used before printing)
  function flushLazy() { while (pending.length) { const p = pending.shift(); if (lazyIO) lazyIO.unobserve(p.node); p.fn(); } }

  MBS.shell = { header, footer, track, lazy, flushLazy, logo };
})();
