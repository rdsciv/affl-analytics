/* CHI-142: paint the shared Team picker for All / 2014 / 2025.
   Fails the Python wrapper if Gabagooners is an option on a year. */
import { createContext, runInContext } from "node:vm";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const site = join(root, "site");
const DATA = JSON.parse(readFileSync(join(site, "data.json"), "utf8"));
const commonSrc = readFileSync(join(site, "common.js"), "utf8");
const seasonKeys = Object.keys(DATA.seasons || {}).map(Number).sort((a, b) => a - b);

function mockSelect() {
  return {
    tagName: "SELECT",
    classList: { add() {} },
    innerHTML: "",
    value: "",
    onchange: null,
    addEventListener() {},
    setAttribute() {},
    querySelector(sel) { return sel === "select" ? this : null; },
  };
}

function mockDiv() {
  const sel = mockSelect();
  let html = "";
  return {
    tagName: "DIV",
    _sel: sel,
    querySelector(s) { return s === "select" ? sel : null; },
    set innerHTML(v) { html = String(v); sel.innerHTML = html; },
    get innerHTML() { return html; },
  };
}

const context = createContext({
  window: {},
  fetch: async (url) => ({
    ok: true,
    json: async () => {
      const u = String(url);
      if (u.includes("data.json")) return DATA;
      if (u.includes("index_years.json")) return { years: seasonKeys.map((y) => ({ year: y })) };
      return {};
    },
  }),
  Date, Number, String, Object, Array, JSON, Math, Map, Promise, console,
  location: { href: "http://127.0.0.1:8765/history.html", search: "", pathname: "/history.html" },
  document: {
    querySelectorAll: () => [],
    querySelector: () => null,
    getElementById: () => null,
    documentElement: { classList: { toggle() {} } },
    dispatchEvent() {},
    createElement() { return { className: "", id: "", style: {} }; },
    readyState: "complete",
    addEventListener() {},
  },
  history: { replaceState() {} },
  URL, URLSearchParams,
  localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
  CustomEvent: class CustomEvent {},
});
runInContext(commonSrc, context);
await runInContext("window.AFFL.boot()", context);
const A = context.window.AFFL;

function optionNames(year) {
  const el = mockDiv();
  if (typeof A.teamSelect === "function") A.teamSelect(el, "", () => {}, year);
  else A.squadPicker(el, "", () => {}, year);
  const html = el.innerHTML || "";
  return Array.from(html.matchAll(/<option[^>]*>([^<]*)<\/option>/g)).map((m) => m[1]);
}

const out = {
  all: optionNames(null),
  y2014: optionNames(2014),
  y2025: optionNames(2025),
  viaForSeason: {
    all: (A.squadsForSeason(null) || []).map((f) => f.currentName),
    y2014: (A.squadsForSeason(2014) || []).map((f) => f.currentName),
    y2025: (A.squadsForSeason(2025) || []).map((f) => f.currentName),
  },
};
process.stdout.write(JSON.stringify(out));
