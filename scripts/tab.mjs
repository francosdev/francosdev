#!/usr/bin/env node
/**
 * THE TAB 🧾 — prints a bar receipt (SVG) with live GitHub stats.
 * Runs every night in GitHub Actions (.github/workflows/nightly.yml).
 *
 *   node scripts/tab.mjs [--out dist/tab.svg] [--user francosdev] [--sample]
 *
 * Needs GITHUB_TOKEN (the default Actions token is enough: it only reads public data).
 * Zero dependencies. Text is drawn from JetBrains Mono outlines stored in glyphs.json,
 * so the receipt renders identically everywhere (GitHub serves README images under a
 * strict CSP, so web fonts can't be loaded).
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
const OUT = arg("out", "dist/tab.svg");
const USER = arg("user", process.env.GH_USER || "francosdev");
const TOKEN = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
const G = JSON.parse(fs.readFileSync(path.join(here, "glyphs.json"), "utf8"));

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
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount weekday } } }
    }
  }
}`;

async function fetchUser(login) {
  if (!TOKEN) throw new Error("GITHUB_TOKEN is not set (use --sample for a local preview)");
  const res = await fetch("https://api.github.com/graphql", {
    method: "POST",
    headers: {
      Authorization: `bearer ${TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": `${login}-the-tab`,
    },
    body: JSON.stringify({ query: QUERY, variables: { login } }),
  });
  if (!res.ok) throw new Error(`GitHub API ${res.status}: ${await res.text()}`);
  const json = await res.json();
  if (json.errors) throw new Error(JSON.stringify(json.errors));
  return json.data.user;
}

const WEEKDAYS = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"];

export function summarize(u) {
  const repos = u.repositories.nodes;
  const cc = u.contributionsCollection;
  const days = cc.contributionCalendar.weeks
    .flatMap((w) => w.contributionDays)
    .sort((a, b) => a.date.localeCompare(b.date));

  let longest = 0;
  let run = 0;
  for (const d of days) {
    run = d.contributionCount > 0 ? run + 1 : 0;
    longest = Math.max(longest, run);
  }
  // current streak: today may still be empty when the job runs, so start from yesterday then
  let i = days.length - 1;
  if (i >= 0 && days[i].contributionCount === 0) i--;
  let current = 0;
  while (i >= 0 && days[i].contributionCount > 0) {
    current++;
    i--;
  }

  const byWeekday = new Array(7).fill(0);
  for (const d of days) byWeekday[d.weekday] += d.contributionCount;
  const best = byWeekday.indexOf(Math.max(...byWeekday));
  const happyHour = byWeekday[best] > 0 ? WEEKDAYS[best] : "—";

  const bytes = {};
  for (const r of repos) {
    if (r.name.toLowerCase() === u.login.toLowerCase()) continue; // skip this profile repo
    for (const e of r.languages.edges) bytes[e.node.name] = (bytes[e.node.name] || 0) + e.size;
  }
  const total = Object.values(bytes).reduce((a, b) => a + b, 0) || 1;
  const langs = Object.entries(bytes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name, size]) => ({ name, pct: (size / total) * 100 }));

  return {
    login: u.login,
    name: u.name || u.login,
    since: new Date(u.createdAt).getUTCFullYear(),
    contributions: cc.contributionCalendar.totalContributions,
    commits: cc.totalCommitContributions,
    prs: cc.totalPullRequestContributions,
    repos: u.repositories.totalCount,
    stars: repos.reduce((a, r) => a + r.stargazerCount, 0),
    langs,
    longest,
    current,
    happyHour,
    date: new Date(),
  };
}

function sampleStats() {
  return {
    login: USER, name: "Carlos Franco", since: 2025, contributions: 486, commits: 351, prs: 12,
    repos: 9, stars: 7, longest: 16, current: 4, happyHour: "Thursdays", date: new Date(), sample: true,
    langs: [
      { name: "JavaScript", pct: 46.2 }, { name: "TypeScript", pct: 19.4 }, { name: "Python", pct: 14.1 },
      { name: "CSS", pct: 12.3 }, { name: "HTML", pct: 8.0 },
    ],
  };
}

function placeholderStats() {
  return {
    login: USER, name: USER, since: "—", contributions: "—", commits: "—", prs: "—", repos: "—", stars: "—",
    langs: [], longest: "—", current: "—", happyHour: "—", date: new Date(), placeholder: true,
  };
}

// ------------------------------------------------------------------ svg helpers
const f = (n, d = 2) => {
  const s = Number(n).toFixed(d).replace(/\.?0+$/, "");
  return s === "-0" ? "0" : s;
};
const used = new Map(); // id -> path

function glyphId(weight, ch) {
  const table = G.weights[weight];
  const c = ch in table ? ch : "?";
  const id = `${weight === "700" ? "b" : "r"}${c.codePointAt(0).toString(16)}`;
  if (!used.has(id)) used.set(id, table[c]);
  return id;
}

function text(str, x, y, size, { weight = "400", anchor = "start", fill = "#2B2620", ls = 0, attrs = "" } = {}) {
  const chars = [...String(str)];
  const adv = (G.advance * size) / G.upem + ls;
  const width = chars.length * adv - ls;
  const x0 = anchor === "middle" ? x - width / 2 : anchor === "end" ? x - width : x;
  const sc = size / G.upem;
  let uses = "";
  chars.forEach((ch, i) => {
    if (ch === " ") return;
    const id = glyphId(weight, ch);
    if (!used.get(id)) return; // whitespace-like glyph
    uses += `<use href="#${id}" x="${f((i * adv) / sc, 1)}"/>`;
  });
  return `<g transform="translate(${f(x0)} ${f(y)}) scale(${f(sc, 5)})" fill="${fill}"${attrs ? " " + attrs : ""}>${uses}</g>`;
}

const pad = (s, n) => String(s).padStart(n, " ");
const fmtInt = (n) => (typeof n === "number" ? n.toLocaleString("en-US") : String(n));
const days = (n) => (typeof n === "number" ? `${n} day${n === 1 ? "" : "s"}` : String(n));

// ------------------------------------------------------------------ render
export function render(s) {
  used.clear();
  const W = 480;
  const H = 660;
  const INK = "#2B2620";
  const FADE = "#6F665A";
  const RED = "#C8372D";
  const px = 58; // paper
  const pw = 364;
  const top = 40;
  const L = px + 22;
  const R = px + pw - 22;
  const body = [];
  let y = top + 40;
  const line = (h = 20) => (y += h);
  const rule = (dash = "4 3", w = 1) => {
    body.push(`<line x1="${L}" y1="${f(y)}" x2="${R}" y2="${f(y)}" stroke="${INK}" stroke-width="${w}" stroke-dasharray="${dash}" opacity=".55"/>`);
  };
  const lr = (left, right, o = {}) => {
    body.push(text(left, L, y, o.size || 13, { weight: o.lw || "400", fill: o.lf || INK }));
    body.push(text(right, R, y, o.size || 13, { weight: o.rw || "400", fill: o.rf || INK, anchor: "end" }));
  };
  const d = s.date;
  const iso = d.toISOString().slice(0, 10);
  const tabNo = iso.slice(5, 7) + iso.slice(8, 10);

  body.push(text("FRANCOSDEV · BAR & CODE", W / 2, y, 16, { weight: "700", anchor: "middle", fill: INK, ls: 0.4 }));
  line(18);
  body.push(text(s.placeholder ? "São Paulo · printing the tab…" : `São Paulo · on GitHub since ${s.since}`, W / 2, y, 12, { anchor: "middle", fill: FADE }));
  line(16);
  rule();
  line(22);
  lr(`TAB #${tabNo}`, `SERVER: ${s.name.split(" ")[0].toUpperCase()}`, { lw: "700" });
  line(18);
  lr(`${iso} UTC`, "TABLE: GITHUB", { lf: FADE, rf: FADE, size: 12 });
  line(14);
  rule();
  line(22);
  lr("QTY  ITEM", "", { lw: "700", size: 12 });
  const items = [
    [s.contributions, "contributions · 12 mo"],
    [s.commits, "commits"],
    [s.prs, "pull requests"],
    [s.repos, "public repos on tap"],
    [s.stars, "stars earned"],
  ];
  const itemsTop = y;
  for (const [q, label] of items) {
    line(19);
    body.push(text(pad(fmtInt(q), 4), L, y, 13, { weight: "700" }));
    body.push(text(label, L + 44, y, 13));
  }
  const itemsMid = (itemsTop + y) / 2;
  line(14);
  rule();
  line(22);
  body.push(text("HOUSE BLEND · top languages", L, y, 12, { weight: "700" }));
  const barX = L + 104;
  const barW = 132;
  if (!s.langs.length) {
    line(19);
    body.push(text(s.placeholder ? "— printing… —" : "— nothing on tap yet —", L, y, 13, { fill: FADE }));
  }
  for (const l of s.langs) {
    line(19);
    const name = l.name.length > 11 ? l.name.slice(0, 10) + "…" : l.name;
    body.push(text(name, L, y, 13));
    body.push(`<rect x="${barX}" y="${f(y - 9)}" width="${barW}" height="9" fill="none" stroke="${INK}" stroke-width=".8" opacity=".5"/>`);
    body.push(`<rect x="${barX}" y="${f(y - 9)}" width="${f((barW * Math.max(l.pct, 1.5)) / 100)}" height="9" fill="${INK}"/>`);
    body.push(text(`${l.pct.toFixed(1)}%`, R, y, 13, { anchor: "end" }));
  }
  line(14);
  rule();
  line(22);
  lr("LONGEST SHIFT", days(s.longest));
  line(19);
  lr("CURRENT SHIFT", days(s.current));
  line(19);
  lr("HAPPY HOUR", s.happyHour);
  line(12);
  rule("none", 1.2);
  line(4);
  rule("none", 1.2);
  line(22);
  lr("TOTAL", "1 developer, served neat", { lw: "700", rw: "700", size: 14 });
  line(26);
  body.push(text("THANK YOU · COME BACK TOMORROW", W / 2, y, 12.5, { weight: "700", anchor: "middle" }));
  line(16);
  body.push(text("this tab refreshes daily via GitHub Actions", W / 2, y, 11, { anchor: "middle", fill: FADE }));
  line(12);
  // barcode (deterministic from the date)
  let seed = [...iso].reduce((a, c) => a * 31 + c.charCodeAt(0), 7) >>> 0;
  const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32);
  let bx = W / 2 - 92;
  const bars = [];
  while (bx < W / 2 + 92) {
    const w = 1 + Math.floor(rnd() * 3);
    if (rnd() > 0.35) bars.push(`<rect x="${f(bx)}" y="${f(y)}" width="${w}" height="26"/>`);
    bx += w + 1 + Math.floor(rnd() * 2);
  }
  body.push(`<g fill="${INK}">${bars.join("")}</g>`);
  line(40);
  if (s.sample) body.push(text("SAMPLE DATA · real numbers print nightly", W / 2, y, 10.5, { anchor: "middle", fill: RED }));
  if (s.placeholder) body.push(text("the printer jammed · retrying tonight", W / 2, y, 10.5, { anchor: "middle", fill: RED }));
  const paperH = y - top + 26;

  // zig-zag torn bottom
  const zz = [];
  const zy = top + paperH;
  for (let x = px, k = 0; x <= px + pw; x += 8, k++) zz.push(`${f(x)} ${f(zy + (k % 2 ? 6 : 0))}`);
  const paperPath = `M${px} ${top} H${px + pw} V${f(zy)} L${zz.reverse().join(" L")} Z`;

  // stamp
  const sx = R - 62;
  const sy = itemsMid + 4;
  const stamp =
    `<g class="stamp" style="transform-origin:${f(sx)}px ${f(sy)}px"><g transform="rotate(-13 ${f(sx)} ${f(sy)})" mask="url(#ink)" opacity=".82">` +
    `<rect x="${f(sx - 72)}" y="${f(sy - 23)}" width="144" height="46" rx="6" fill="none" stroke="${RED}" stroke-width="2.6"/>` +
    `<rect x="${f(sx - 67)}" y="${f(sy - 18)}" width="134" height="36" rx="4" fill="none" stroke="${RED}" stroke-width="1.1"/>` +
    text("PAID IN", sx, sy - 3, 12, { weight: "700", anchor: "middle", fill: RED, ls: 2.6 }) +
    text("COMMITS", sx, sy + 12, 12, { weight: "700", anchor: "middle", fill: RED, ls: 2.6 }) +
    `</g></g>`;

  const defs =
    [...used.entries()].map(([id, p]) => `<path id="${id}" d="${p}"/>`).join("") +
    `<linearGradient id="paper" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E7E0D2"/><stop offset=".06" stop-color="#F6F1E7"/><stop offset="1" stop-color="#F1EBDF"/></linearGradient>` +
    `<linearGradient id="fg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7A5A24"/><stop offset=".45" stop-color="#FFF0C8"/><stop offset=".55" stop-color="#E6C27A"/><stop offset="1" stop-color="#6E5020"/></linearGradient>` +
    `<filter id="shadow" x="-20%" y="-10%" width="140%" height="130%"><feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#000" flood-opacity=".6"/></filter>` +
    `<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="5"/><feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .06 0"/></filter>` +
    `<filter id="inkf"><feTurbulence type="fractalNoise" baseFrequency=".7" numOctaves="2" seed="9"/><feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  2.4 0 0 0 -.7"/></filter>` +
    `<mask id="ink" maskUnits="userSpaceOnUse" x="0" y="0" width="${W}" height="${H}"><rect width="${W}" height="${H}" filter="url(#inkf)"/></mask>` +
    `<clipPath id="slot"><rect x="0" y="${top}" width="${W}" height="${H}"/></clipPath>`;

  const css = `
.print{animation:print 2.6s steps(26,end) .3s both}
@keyframes print{from{transform:translateY(-${f(paperH)}px)}to{transform:none}}
.stamp{animation:stamp .45s cubic-bezier(.3,1.6,.5,1) 3.1s both}
@keyframes stamp{from{opacity:0;transform:scale(1.9)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion: reduce){*{animation:none!important}}`;

  const desc = `Receipt-style GitHub stats for ${s.login}: ${s.contributions} contributions in the last 12 months, ` +
    `${s.commits} commits, ${s.prs} pull requests, ${s.repos} public repositories, ${s.stars} stars. Top languages: ` +
    `${s.langs.map((l) => `${l.name} ${l.pct.toFixed(1)}%`).join(", ")}. Longest streak ${s.longest} days, current streak ` +
    `${s.current} days, most active on ${s.happyHour}.`;

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-labelledby="t d">
<title id="t">The Tab — ${s.login}'s GitHub stats</title><desc id="d">${desc}</desc>
<style>${css}</style>
<defs>${defs}</defs>
<rect width="${W}" height="${H}" rx="16" fill="#0B0A09"/>
<rect x="7.5" y="7.5" width="${W - 15}" height="${H - 15}" rx="11" fill="none" stroke="url(#fg)" stroke-width=".8" opacity=".55"/>
<rect x="${px - 20}" y="${top - 16}" width="${pw + 40}" height="26" rx="10" fill="#1A1714" stroke="#3A3122"/>
<rect x="${px - 6}" y="${top - 5}" width="${pw + 12}" height="6" rx="3" fill="#050404"/>
<g clip-path="url(#slot)"><g class="print">
<path d="${paperPath}" fill="url(#paper)" filter="url(#shadow)"/>
<path d="${paperPath}" filter="url(#grain)"/>
${body.join("\n")}
${stamp}
</g></g>
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
  console.log(`🧾 printed ${OUT} (${(svg.length / 1024).toFixed(1)} KB) for @${stats.login}${SAMPLE ? " [sample]" : ""}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((err) => {
    console.error("❌ could not print the tab:", err.message);
    // keep yesterday's receipt if there is one; otherwise print a placeholder so the README never shows a broken image
    if (!fs.existsSync(OUT)) {
      write(placeholderStats());
      console.error(`   wrote a placeholder receipt to ${OUT}`);
    }
    process.exit(1);
  });
}
