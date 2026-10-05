# Migration by Skill: dashboard (version 1, draft)

Not how many. Which skills, where, and why.

One page in three parts, plus a brief and a methods page:

1. **The story**: a bold opening and eight short chapters. In each chapter a chart sticks beside the text (on a phone,
   above it) and changes as each step of text scrolls past.
2. **Your turn: the simulator** ("size vs mix", method A, agreed 5 October 2026). Pick a size for net overseas
   migration and a skilled share, and see how many skilled workers reach jobs on the shortage list with today's mix of
   skilled visas or a skills-first mix. Our illustration, labelled as such.
3. **The report**: an executive summary (key numbers and findings), numbered exhibits with takeaway titles, a table,
   an About panel and a CSV for each, four interactive exhibits (build your own plan, your state, find your job, all
   claims), Appendix A (models: the visas and shortages regression, the sensitivity tests, the browser model's live
   self-check, the pipeline) and Appendix B (data and methods).

`brief.html` is a two-page A4 briefing that prints or saves to PDF. `methods.html` is the Data and methods page.

Every number comes from the tables in `../analysis` and `../tidy`, built by the Python scripts in `../analysis`.

## Open it

Double-click `index.html`. No server, no internet and no build step needed.

## Update the data

From the Migration folder run `python3 analysis/run_all.py`. The last step, `analysis/export_web_data.py`, rewrites
`data/data.js`, `data/data-explore.js`, `data/data-methods.js` and the CSV copies in `downloads/`.

## Test it

The headless test must pass 100% before any release.

```
cd dashboard/tests
npm install        # once: installs jsdom
node run_tests.js
```

It checks every chapter, step and chart scene of the story; the simulator's arithmetic against the agreed method and
the ABS tables; every exhibit's title, chart, table, About panel, source and CSV; the four tools; the Models appendix
(including the live self-check); the brief and the methods page; that the numbers match the pipeline's tables; that
the plan model reproduces the pipeline; that every in-page link has a target; and that no em dash appears anywhere.

## What is where

```
index.html, brief.html, methods.html   the three pages
content/content.js     every word: chapters and steps, exhibit titles, findings, the (i) panels, the guide
data/                  written by analysis/export_web_data.py (do not edit by hand)
js/core.js             formatting, badges, (i) panels, tables, tooltip, keyboard reading, theme
js/charts.js           the story charts, with scenes the story can switch between
js/charts-report.js    report and Models charts
js/model.js            the scenario model (same arithmetic as analysis/build_scenario_model.py)
js/shell.js            top bar, footer, reading progress, lazy drawing
js/story.js            the opening, the chapters and the scrolling
js/sim.js              the simulator
js/explore.js          the report's four tools and their small charts
js/report.js           the report: summary, exhibits, appendices
js/brief.js            the two-page brief
js/methods.js          the Data and methods page
js/guide.js            the welcome guide
css/style.css          colours, type, layout, light and dark mode, print
vendor/                D3 7.9.0 and Scrollama 3.2.0 (with licences)
downloads/             copies of the tables behind the charts
figures.csv            every chart: draft, approved or locked
tests/                 headless tests
```

## Publish on GitHub Pages

Put this folder in a repository (as the root or as `/docs`) and turn on Pages for that branch and folder.
`tests/node_modules` does not need to be uploaded.

## Rules the dashboard keeps

Skills, not nationality. Headlines are punchy but say exactly what the data says, and every party is described the
same way. Every chart is labelled with the kind of numbers it shows (official data, forecast or plan, our estimate, our
illustration) and has a table version. Colours: grey for context, blue for the focus, orange for a comparison point,
viridis for continuous values, one blue ramp for claim verdicts; no red or green.
