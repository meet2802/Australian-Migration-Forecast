/* Migration by Skill: start-up. Draw the frame, the story, the simulator and the report, then load the bigger
   explore data (for the report's tools and the Models appendix) in the background. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el } = MBS.util;

  function loadExplore() {
    if (MBS.explore && MBS.explore.models) { ready(); return; }
    const s = document.createElement("script");
    s.src = "data/data-explore.js";
    s.onload = ready;
    s.onerror = () => {
      document.querySelectorAll(".tool-wait").forEach(n => { n.textContent = "This part needs data/data-explore.js, which did not load. Check that the data folder sits next to this page."; });
    };
    document.body.appendChild(s);
  }
  function ready() {
    MBS.exploreReady();
    jumpToHash(true);
  }
  // shared links: #ch3, #ex12, #simulator, or a tool's saved view (#ex17?job=3411)
  function jumpToHash(toolsOnly) {
    const h = (location.hash || "").slice(1);
    if (!h) return;
    const id = h.split("?")[0];
    if (toolsOnly && !/^ex(8|11|17|20)$/.test(id) && !/^exA\d$/.test(id) && id !== "models") return;
    const t = document.getElementById(id);
    if (t && t.scrollIntoView) t.scrollIntoView({ block: "start" });
  }
  function start() {
    MBS.ui.initTheme();
    MBS.ui.ensureDefs();
    const app = document.getElementById("app");
    app.textContent = "";
    document.body.insertBefore(el("a", { class: "skip-link", href: "#report" }, "Skip the story and go to the report"), document.body.firstChild);
    app.appendChild(MBS.shell.header({ page: "index" }));
    const main = el("main", { id: "main" });
    app.appendChild(main);
    MBS.buildStory(main);
    MBS.buildSim(main);
    MBS.buildReport(main);
    app.appendChild(MBS.shell.footer());
    if (MBS.guide) MBS.guide.init();
    MBS.story.setup();
    MBS.shell.track();
    jumpToHash(false);
    setTimeout(loadExplore, 30);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
