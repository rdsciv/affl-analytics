#!/usr/bin/env node
/* CHI-112: execute the real trades.js tName against owner-id txByTeam keys. */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const trades = fs.readFileSync(path.join(ROOT, "site/trades.js"), "utf8");
const fails = [];
const fail = (m) => fails.push(m);

function grab(src, startNeedle) {
  const start = src.indexOf(startNeedle);
  if (start < 0) throw new Error("missing " + startNeedle);
  const brace = src.indexOf("{", start);
  let depth = 0;
  for (let i = brace; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") {
      depth--;
      if (depth === 0) return src.slice(start, i + 1);
    }
  }
  throw new Error("unclosed " + startNeedle);
}

if (/tid:\s*\+tid/.test(trades)) fail("trades.js still does tid: +tid");

const tNameSrc = grab(trades, "function tName(");
if (tNameSrc.includes("—") || /return\s+["']-["']/.test(tNameSrc)) {
  fail("extracted tName still falls back to a dash");
}
if (!tNameSrc.includes("unavailable")) fail("extracted tName missing unavailable");
if (!tNameSrc.includes("A.canon")) fail("extracted tName does not consult A.canon");

const NAMES = {
  m18: "Grand Teeton Feelers",
  m07: "Chula Vista Chupacabras",
  m14: "Poulsbo Pollywogs",
  m19: "Pasco Pounders",
  m22: "Central Oregon Gabagooners",
};
const MERGE = { m01: "m07", m03: "m08", m20: "m10" };
const A = {
  canon(id) {
    if (id == null || id === "") return id;
    return MERGE[String(id)] || String(id);
  },
  franchiseName(id) {
    const c = A.canon(id);
    return NAMES[c] || "";
  },
};
const T = {
  m18: { owner: "m18", name: "Grand Teeton Feelers" },
  m07: { owner: "m07", name: "Chula Vista Chupacabras" },
  m14: { owner: "m14", name: "Poulsbo Pollywogs" },
  m19: { owner: "m19", name: "Pasco Pounders" },
};

const tName = new Function("A", "T", tNameSrc + "\nreturn tName;")(A, T);

const txByTeam = {
  m18: { waiver: 1, fa: 0, trades: 0 },
  m07: { waiver: 2, fa: 1, trades: 0 },
};

const smashed = Object.entries(txByTeam).map(([tid, v]) => ({ tid: +tid, ...v }));
const smashedNames = smashed.map((r) => tName(r.tid));
if (smashedNames.some((n) => /Feelers|Chupacabras/.test(String(n)))) {
  fail("+tid smash unexpectedly resolved a franchise name: " + smashedNames.join(", "));
}
if (smashedNames.some((n) => n === "—" || n === "-" || n === "NaN" || !n)) {
  fail("+tid smash painted a dash/empty: " + JSON.stringify(smashedNames));
}

const rows = Object.entries(txByTeam).map(([tid, v]) => ({ tid, ...v }));
const names = rows.map((r) => tName(r.tid));
if (!names.some((n) => String(n).includes("Feelers"))) fail("names missing Feelers: " + names.join(", "));
if (!names.some((n) => String(n).includes("Chupacabras"))) fail("names missing Chupacabras: " + names.join(", "));
if (names.some((n) => !n || n === "—" || n === "-" || n === "NaN" || Number.isNaN(n))) {
  fail("blank/dash/NaN label: " + JSON.stringify(names));
}
if (names.some((n) => /Tittsburgh|Glory Holes|Gabagooners/i.test(String(n)))) {
  fail("historic or 2026-only name leaked: " + names.join(", "));
}
if (tName(NaN) !== "unavailable") fail("tName(NaN) => " + tName(NaN));
if (tName("m99") !== "unavailable") fail("tName(m99) => " + tName("m99"));
if (!String(tName("m01")).includes("Chupacabras")) fail("canon m01 did not resolve Chupacabras: " + tName("m01"));

if (fails.length) {
  console.log("FAIL");
  fails.forEach((f) => console.log(" -", f));
  process.exit(1);
}
console.log("ok chi112 names", names.join(", "));
