/* Migration by Skill: the welcome guide. Opens with the page, explains how to read it, and comes back with the
   ? button. Keyboard friendly: focus moves into the guide, Tab stays inside it, Escape or "Start exploring" closes it
   and focus returns to where it was. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el } = MBS.util;
  const KEY = "mbs-guide-hidden";
  let modal = null, lastFocus = null;

  function build() {
    const T = MBS.content.types, G = MBS.content.guide;
    const types = el("span", { class: "guide-types" },
      Object.keys(T).map(k => el("span", { class: "badge" }, MBS.ui.typeSwatch(k), T[k].label)));
    const keep = el("input", { type: "checkbox", id: "guide-keep" });
    const card = el("div", { class: "modal-card", role: "document" },
      el("p", { class: "modal-kicker", text: MBS.content.meta.tagline }),
      el("h2", { id: "guide-title", tabindex: "-1", text: `Welcome to ${MBS.content.meta.title}` }),
      el("p", { class: "modal-lede", text: G.lede }),
      el("ul", { class: "modal-list" }, G.items.map(([lead, rest, withTypes]) =>
        el("li", null, el("strong", { text: lead }), " ", MBS.rich(rest), withTypes ? [" ", types] : null))),
      el("label", { class: "guide-keep", for: "guide-keep" }, keep, "Don't show this when I open the page"),
      el("button", { class: "modal-close-btn", type: "button", id: "guide-close", onclick: close }, "Start exploring"));
    modal = el("div", { class: "modal-backdrop", id: "welcome-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "guide-title", hidden: true }, card);
    modal.addEventListener("click", e => { if (e.target === modal) close(); });
    modal.addEventListener("keydown", trap);
    keep.checked = MBS.ui.store(KEY) === "1";
    keep.addEventListener("change", () => MBS.ui.store(KEY, keep.checked ? "1" : "0"));
    document.body.appendChild(modal);
  }
  function focusables() {
    return Array.from(modal.querySelectorAll("a[href], button, input, [tabindex]:not([tabindex='-1'])")).filter(n => !n.disabled);
  }
  function trap(e) {
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key !== "Tab") return;
    const f = focusables();
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  function open() {
    if (!modal) build();
    lastFocus = document.activeElement;
    modal.hidden = false;
    document.documentElement.classList.add("modal-open");
    // focus the title (not the button at the bottom) so a small screen opens the guide at its top
    const title = document.getElementById("guide-title");
    const card = modal.querySelector(".modal-card");
    if (card) card.scrollTop = 0;
    setTimeout(() => { try { (title || modal).focus({ preventScroll: true }); } catch (e) { /* headless */ } }, 0);
  }
  function close() {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.documentElement.classList.remove("modal-open");
    const back = lastFocus && document.body.contains(lastFocus) ? lastFocus : document.getElementById("help-btn");
    try { if (back && back.focus) back.focus({ preventScroll: true }); } catch (e) { /* headless */ }
    try { document.dispatchEvent(new Event("mbs-guide-closed")); } catch (e) { /* very old browsers */ }
  }
  // opens with the page, unless the reader asked not to see it again or arrived on a shared link deeper in the page
  function init() {
    build();
    const h = location.hash || "";
    const deep = h.length > 1 && !/^#(top|story)$/.test(h);
    if (!deep && MBS.ui.store(KEY) !== "1") open();
  }
  MBS.guide = { init, open, close, get isOpen() { return !!modal && !modal.hidden; } };
})();
