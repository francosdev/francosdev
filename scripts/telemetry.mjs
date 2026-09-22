#!/usr/bin/env node
/**
 * TELEMETRY — renders a HUD-style SVG with live GitHub stats and a dot-matrix contribution map.
 * Runs every night in GitHub Actions (.github/workflows/nightly.yml).
 *
 *   node scripts/telemetry.mjs [--out dist/telemetry.svg] [--user francosdev] [--sample]
 *
 * Needs GITHUB_TOKEN (the default Actions token is enough: it only reads public data).
 * Zero dependencies. Text is drawn from glyph outlines stored in glyphs.json, so the panel
 * renders identically everywhere (GitHub serves README images under a strict CSP that blocks web fonts).
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const arg = (name, def) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
};
const SAMPLE = args.includes("--sample");
const OUT = arg("out", "dist/telemetry.svg");
const USER = arg("user", process.env.GH_USER || "francosdev");
const TOKEN = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
const G = JSON.parse(fs.readFileSync(path.join(here, "glyphs.json"), "utf8")).fonts;

// palette — keep in sync with scripts/art/build.py
const INK = "#08080A", PANEL = "#0C0C0F", EDGE = "#24242A", BONE = "#E8E4DC";
const GREY = "#8C8C95", DIM = "#55555E", RED = "#F0412A", CYAN = "#6FE3E8";

// ------------------------------------------------------------------ data
const QUERY = `query($login: String!) {
  user(login: $login) {
    login name createdAt
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        name stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel weekday } }
      }
    }
  }
}`;

async function fetchUser(login) {
  if (!TOKEN) throw new Error("GITHUB_TOKEN is not set (use --sample for a local preview)");
  const res = await fetch("https://api.github.com/graphql", {
    method: "POST",
    headers: { Authorization: `bearer ${TOKEN}`, "Content-Type": "application/json", "User-Agent": `${login}-telemetry` },
    body: JSON.stringify({ query: QUERY, variables: { login } }),
  });
  if (!res.ok) throw new Error(`GitHub API ${res.status}: ${await res.text()}`);
  const json = await res.json();
  if (json.errors) throw new Error(JSON.stringify(json.errors));
  return json.data.user;
}

const DAYS_EN = ["SUNDAYS", "MONDAYS", "TUESDAYS", "WEDNESDAYS", "THURSDAYS", "FRIDAYS", "SATURDAYS"];
const DAYS_JP = ["日", "月", "火", "水", "木", "金", "土"];
const LEVEL = { NONE: 0, FIRST_QUARTILE: 1, SECOND_QUARTILE: 2, THIRD_QUARTILE: 3, FOURTH_QUARTILE: 4 };

export function summarize(u) {
  const repos = u.repositories.nodes;
  const cal = u.contributionsCollection.contributionCalendar;
  const weeks = cal.weeks.map((w) => w.contributionDays.map((d) => ({ ...d, level: LEVEL[d.contributionLevel] ?? (d.contributionCount ? 2 : 0) })));
  const days = weeks.flat().sort((a, b) => a.date.localeCompare(b.date));

  let longest = 0, run = 0;
  for (const d of days) {
    run = d.contributionCount > 0 ? run + 1 : 0;
    longest = Math.max(longest, run);
  }
  let i = days.length - 1;
  if (i >= 0 && days[i].contributionCount === 0) i--; // today may still be empty when the job runs
  let current = 0;
  while (i >= 0 && days[i].contributionCount > 0) { current++; i--; }

  const byWeekday = new Array(7).fill(0);
  for (const d of days) byWeekday[d.weekday] += d.contributionCount;
  const best = byWeekday.indexOf(Math.max(...byWeekday));
  const peak = byWeekday[best] > 0 ? best : -1;

  const bytes = {};
  for (const r of repos) {
    if (r.name.toLowerCase() === u.login.toLowerCase()) continue; // skip this profile repo
    for (const e of r.languages.edges) bytes[e.node.name] = (bytes[e.node.name] || 0) + e.size;
  }
  const total = Object.values(bytes).reduce((a, b) => a + b, 0) || 1;
  const langs = Object.entries(bytes).sort((a, b) => b[1] - a[1]).slice(0, 5)
    .map(([name, size]) => ({ name, pct: (size / total) * 100 }));

  return {
    login: u.login, since: new Date(u.createdAt).getUTCFullYear(),
    contributions: cal.totalContributions,
    commits: u.contributionsCollection.totalCommitContributions,
    prs: u.contributionsCollection.totalPullRequestContributions,
    repos: u.repositories.totalCount,
    stars: repos.reduce((a, r) => a + r.stargazerCount, 0),
    langs, longest, current, peak, weeks, date: new Date(),
  };
}

function fakeWeeks(seedStr, empty = false) {
  let seed = [...seedStr].reduce((a, c) => a * 31 + c.charCodeAt(0), 7) >>> 0;
  const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32);
  const start = new Date(Date.UTC(new Date().getUTCFullYear() - 1, new Date().getUTCMonth(), new Date().getUTCDate()));
  start.setUTCDate(start.getUTCDate() - start.getUTCDay());
  const weeks = [];
  for (let w = 0; w < 53; w++) {
    const col = [];
    for (let d = 0; d < 7; d++) {
      const date = new Date(start.getTime() + (w * 7 + d) * 864e5);
      const active = !empty && rnd() < (w > 30 ? 0.62 : 0.2);
      const level = active ? 1 + Math.floor(rnd() * 4) : 0;
      col.push({ date: date.toISOString().slice(0, 10), contributionCount: level * 2, level, weekday: d });
    }
    weeks.push(col);
  }
  return weeks;
}

const sampleStats = () => ({
  login: USER, since: 2026, contributions: 486, commits: 351, prs: 12, repos: 9, stars: 7,
  longest: 16, current: 4, peak: 4, weeks: fakeWeeks("sample"), date: new Date(), sample: true,
  langs: [{ name: "JavaScript", pct: 46.2 }, { name: "TypeScript", pct: 19.4 }, { name: "Python", pct: 14.1 }, { name: "CSS", pct: 12.3 }, { name: "HTML", pct: 8.0 }],
});

const placeholderStats = () => ({
  login: USER, since: "—", contributions: "—", commits: "—", prs: "—", repos: "—", stars: "—",
  longest: "—", current: "—", peak: -1, weeks: fakeWeeks("empty", true), langs: [], date: new Date(), placeholder: true,
});

// ------------------------------------------------------------------ svg helpers
const f = (n, d = 2) => {
  const s = Number(n).toFixed(d).replace(/\.?0+$/, "");
  return s === "-0" ? "0" : s;
};
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const used = new Map(); // id -> path

function width(str, font, size, ls = 0) {
  const F = G[font];
  const chars = [...String(str)];
  return chars.reduce((a, ch) => a + ((F.glyphs[ch] || F.glyphs["?"] || [null, F.upem * 0.6])[1] * size) / F.upem, 0) + ls * Math.max(0, chars.length - 1);
}

function text(str, x, y, size, { font = "pm", anchor = "start", fill = BONE, ls = 0, attrs = "" } = {}) {
  const F = G[font];
  const sc = size / F.upem;
  const w = width(str, font, size, ls);
  const x0 = anchor === "middle" ? x - w / 2 : anchor === "end" ? x - w : x;
  let cx = 0;
  let uses = "";
  for (const ch of String(str)) {
    const g = F.glyphs[ch] || F.glyphs["?"];
    if (!g) continue;
    const id = `${font}${ch.codePointAt(0).toString(16)}`;
    if (g[0]) {
      if (!used.has(id)) used.set(id, g[0]);
      uses += `<use href="#${id}" x="${f(cx / sc, 1)}"/>`;
    }
    cx += g[1] * sc + ls;
  }
  return `<g transform="translate(${f(x0)} ${f(y)}) scale(${f(sc, 5)})" fill="${fill}"${attrs ? " " + attrs : ""}>${uses}</g>`;
}

const fmt = (n) => (typeof n === "number" ? n.toLocaleString("en-US") : String(n));
const days = (n) => (typeof n === "number" ? `${n}D` : String(n));

// ------------------------------------------------------------------ render
export function render(s) {
  used.clear();
  const W = 1000, H = 392;
  const b = [];
  const iso = s.date.toISOString();
  const stamp = `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;

  // header
  b.push(`<rect x="28" y="31" width="7" height="7" fill="${RED}"/>`);
  b.push(text("TELEMETRY", 44, 39, 12, { font: "pm5", ls: 3 }));
  b.push(text("統計", 44 + width("TELEMETRY", "pm5", 12, 3) + 14, 39, 12, { font: "jp", fill: GREY, ls: 2 }));
  const upd = s.sample ? "SAMPLE DATA" : s.placeholder ? "SIGNAL LOST · RETRYING TONIGHT" : `UPDATED ${stamp}`;
  b.push(text(upd, W - 28, 39, 10.5, { fill: s.sample || s.placeholder ? RED : GREY, anchor: "end", ls: 1.6 }));
  const updW = width(upd, "pm", 10.5, 1.6);
  const liveW = width("LIVE", "pm5", 10.5, 2);
  const liveX = W - 28 - updW - 22 - liveW;
  b.push(`<circle class="blink" cx="${f(liveX - 11)}" cy="35" r="3.5" fill="${CYAN}"/>`);
  b.push(text("LIVE", liveX, 39, 10.5, { font: "pm5", fill: CYAN, ls: 2 }));
  b.push(`<path d="M28 58H${W - 28}" stroke="${BONE}" stroke-opacity=".12"/>`);

  // metrics
  const metrics = [
    ["貢献", "CONTRIBUTIONS", s.contributions, "LAST 12 MONTHS"],
    ["コミット", "COMMITS", s.commits, "LAST 12 MONTHS"],
    ["PR", "PULL REQUESTS", s.prs, "LAST 12 MONTHS"],
    ["リポジトリ", "PUBLIC REPOS", s.repos, `SINCE ${s.since}`],
    ["星", "STARS", s.stars, "ALL REPOS"],
  ];
  const mw = (W - 56) / metrics.length;
  metrics.forEach(([jp, en, val, sub], k) => {
    const x = 28 + k * mw + (k ? 22 : 0);
    const jpFont = /^[A-Z]+$/.test(jp) ? "pm5" : "jp";
    const g = [text(jp, x, 86, 11.5, { font: jpFont, fill: GREY, ls: 1.5 }),
      text(en, x + width(jp, jpFont, 11.5, 1.5) + 10, 86, 9.5, { fill: DIM, ls: 1.8 }),
      text(fmt(val), x, 132, 36, { font: "mich", fill: BONE, ls: 1.5 }),
      text(sub, x, 154, 9, { fill: DIM, ls: 1.6 })];
    b.push(`<g class="up" style="animation-delay:${f(0.1 + k * 0.08)}s">${g.join("")}</g>`);
    if (k) b.push(`<path d="M${f(28 + k * mw)} 72V156" stroke="${BONE}" stroke-opacity=".08"/>`);
  });
  b.push(`<path d="M28 174H${W - 28}" stroke="${BONE}" stroke-opacity=".08"/>`);

  // dot matrix
  const mx = 58, my = 214, step = 12.2;
  const weeks = s.weeks.slice(-53);
  let lastMonth = -1;
  weeks.forEach((col, w) => {
    const first = col[0];
    const m = Number(first.date.slice(5, 7)) - 1;
    if (m !== lastMonth && Number(first.date.slice(8, 10)) <= 7) {
      if (w < weeks.length - 2) b.push(text(["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"][m], mx + w * step - 3, my - 16, 8.5, { fill: DIM, ls: 1 }));
      lastMonth = m;
    }
    const dots = col.map((d) => {
      const lv = d.level;
      const r = [1.1, 2.2, 2.9, 3.5, 4.1][lv];
      const fill = lv ? RED : BONE;
      const op = [0.14, 0.42, 0.64, 0.85, 1][lv];
      return `<circle cx="${f(mx + w * step)}" cy="${f(my + d.weekday * step)}" r="${r}" fill="${fill}" fill-opacity="${op}"/>`;
    });
    b.push(`<g class="fl" style="animation-delay:${f(0.4 + w * 0.018, 3)}s">${dots.join("")}</g>`);
  });
  [[1, "月"], [3, "水"], [5, "金"]].forEach(([row, jp]) => b.push(text(jp, 32, my + row * step + 3.5, 9.5, { font: "jp", fill: DIM })));
  const legendX = mx + 52 * step;
  b.push(text("LESS", mx - 6, my + 7 * step + 16, 8.5, { fill: DIM, ls: 1 }));
  [0, 1, 2, 3, 4].forEach((lv, k) => b.push(`<circle cx="${f(mx + 30 + k * 11)}" cy="${f(my + 7 * step + 13)}" r="${[1.1, 2.2, 2.9, 3.5, 4.1][lv]}" fill="${lv ? RED : BONE}" fill-opacity="${[0.14, 0.42, 0.64, 0.85, 1][lv]}"/>`));
  b.push(text("MORE", mx + 30 + 5 * 11, my + 7 * step + 16, 8.5, { fill: DIM, ls: 1 }));
  void legendX;

  // languages
  const lx = 730, lw = W - 28 - lx;
  b.push(text("言語", lx, 206, 11.5, { font: "jp", fill: GREY, ls: 1.5 }));
  b.push(text("LANGUAGES", lx + width("言語", "jp", 11.5, 1.5) + 10, 206, 9.5, { fill: DIM, ls: 1.8 }));
  const shades = [RED, BONE, GREY, "#6E6E78", "#45454D"];
  let bx = lx;
  s.langs.forEach((l, k) => {
    const w = Math.max(2, (lw * l.pct) / 100);
    b.push(`<rect class="grow" x="${f(bx)}" y="216" width="${f(w - 1.5)}" height="6" fill="${shades[k]}" style="animation-delay:${f(0.6 + k * 0.1)}s"/>`);
    bx += w;
  });
  if (!s.langs.length) b.push(`<rect x="${lx}" y="216" width="${lw}" height="6" fill="${BONE}" fill-opacity=".1"/>`);
  s.langs.forEach((l, k) => {
    const y = 246 + k * 19;
    b.push(`<rect x="${lx}" y="${y - 7}" width="6" height="6" fill="${shades[k]}"/>`);
    b.push(text(l.name.length > 16 ? l.name.slice(0, 15) + "…" : l.name, lx + 14, y, 11, { fill: BONE, ls: 0.4 }));
    b.push(text(`${l.pct.toFixed(1)}%`, W - 28, y, 11, { fill: GREY, anchor: "end", ls: 0.4 }));
  });
  if (!s.langs.length) b.push(text(s.placeholder ? "AWAITING SIGNAL" : "NO DATA YET", lx, 250, 11, { fill: DIM, ls: 1.5 }));

  // streaks
  b.push(`<path d="M28 344H${W - 28}" stroke="${BONE}" stroke-opacity=".08"/>`);
  const peakTxt = s.peak >= 0 ? DAYS_EN[s.peak] : "—";
  const row = [
    ["最長", "LONGEST STREAK", days(s.longest)],
    ["現在", "CURRENT STREAK", days(s.current)],
    ["活動", "PEAK DAY", peakTxt, s.peak >= 0 ? `${DAYS_JP[s.peak]}曜日` : ""],
  ];
  let sx = 28;
  row.forEach(([jp, en, val, extra]) => {
    const g = [text(jp, sx, 370, 11.5, { font: "jp", fill: GREY, ls: 1.5 })];
    let x = sx + width(jp, "jp", 11.5, 1.5) + 10;
    g.push(text(en, x, 370, 9.5, { fill: DIM, ls: 1.8 }));
    x += width(en, "pm", 9.5, 1.8) + 14;
    g.push(text(val, x, 370, 12, { font: "pm5", fill: BONE, ls: 1.5 }));
    x += width(val, "pm5", 12, 1.5);
    if (extra) {
      g.push(text(extra, x + 10, 370, 11.5, { font: "jp", fill: RED, ls: 1 }));
      x += 10 + width(extra, "jp", 11.5, 1);
    }
    b.push(g.join(""));
    sx = x + 40;
  });
  b.push(text("↻ NIGHTLY · GITHUB ACTIONS", W - 28, 370, 9.5, { fill: DIM, anchor: "end", ls: 1.6 }));

  const css = `
.fl{animation:fl .5s linear both}@keyframes fl{0%{opacity:0}40%{opacity:.9}55%{opacity:.2}70%,100%{opacity:1}}
.up{animation:up .7s cubic-bezier(.2,.7,.2,1) both}@keyframes up{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.grow{animation:grow .9s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box;transform-origin:left}@keyframes grow{from{transform:scaleX(0)}to{transform:none}}
.blink{animation:blink 1.6s steps(1) infinite}@keyframes blink{0%,60%{opacity:1}61%,100%{opacity:.15}}
@media (prefers-reduced-motion: reduce){*{animation:none!important}}`;
  const defs = [...used.entries()].map(([id, p]) => `<path id="${id}" d="${p}"/>`).join("") +
    `<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0V40M0 40H40" fill="none" stroke="#FFFFFF" stroke-opacity=".022"/></pattern>` +
    `<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect y="3" width="4" height="1" fill="#000" fill-opacity=".16"/></pattern>`;
  const desc = `GitHub telemetry for ${s.login}: ${fmt(s.contributions)} contributions in the last 12 months, ${fmt(s.commits)} commits, ` +
    `${fmt(s.prs)} pull requests, ${fmt(s.repos)} public repositories, ${fmt(s.stars)} stars. Top languages: ` +
    `${s.langs.map((l) => `${l.name} ${l.pct.toFixed(1)}%`).join(", ") || "none yet"}. Longest streak ${s.longest} days, current ` +
    `${s.current} days, most active on ${s.peak >= 0 ? DAYS_EN[s.peak].toLowerCase() : "—"}.`;

  const L = 14;
  const br = `M10 ${10 + L}V10H${10 + L} M${W - 10 - L} 10H${W - 10}V${10 + L} M${W - 10} ${H - 10 - L}V${H - 10}H${W - 10 - L} M${10 + L} ${H - 10}H10V${H - 10 - L}`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-labelledby="t d">
<title id="t">Telemetry — ${esc(s.login)}'s GitHub stats</title><desc id="d">${esc(desc)}</desc>
<style>${css}</style>
<defs>${defs}</defs>
<rect x=".5" y=".5" width="${W - 1}" height="${H - 1}" rx="14" fill="${PANEL}" stroke="${EDGE}"/>
<rect width="${W}" height="${H}" rx="14" fill="url(#grid)"/>
${b.join("\n")}
<path d="${br}" fill="none" stroke="${RED}" stroke-opacity=".85" stroke-width="1.3"/>
<rect width="${W}" height="${H}" rx="14" fill="url(#scan)"/>
</svg>`;
}

// ------------------------------------------------------------------ main
function write(stats) {
  const svg = render(stats);
  fs.mkdirSync(path.dirname(path.resolve(OUT)), { recursive: true });
  fs.writeFileSync(OUT, svg);
  return svg;
}

async function main() {
  const stats = SAMPLE ? sampleStats() : summarize(await fetchUser(USER));
  const svg = write(stats);
  console.log(`📡 wrote ${OUT} (${(svg.length / 1024).toFixed(1)} KB) for @${stats.login}${SAMPLE ? " [sample]" : ""}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((err) => {
    console.error("❌ telemetry failed:", err.message);
    // keep yesterday's panel if there is one; otherwise write a placeholder so the README never shows a broken image
    if (!fs.existsSync(OUT) || fs.statSync(OUT).size < 200) {
      write(placeholderStats());
      console.error(`   wrote a placeholder panel to ${OUT}`);
    }
    process.exit(1);
  });
}
