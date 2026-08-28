// CHI-112: owner-id keys must resolve to current franchise names, never NaN/dash.
const NAMES = {
  m18: "Feelers",
  m07: "Chupacabras",
  m14: "Pollywogs",
  m19: "Pounders",
  m22: "Gabagooners",
};
function franchiseName(id) {
  return NAMES[id] || "";
}
function tName(id) {
  if (id == null || id === "" || (typeof id === "number" && Number.isNaN(id))) {
    return "unavailable";
  }
  const named = franchiseName(id);
  if (named) return named;
  return "unavailable";
}

const txByTeam = {
  m18: { waiver: 10, fa: 2, trades: 1 },
  m07: { waiver: 8, fa: 1, trades: 0 },
  m14: { waiver: 4, fa: 0, trades: 0 },
  m19: { waiver: 3, fa: 1, trades: 0 },
};
const smashed = Object.entries(txByTeam).map(([tid, v]) => ({ tid: +tid, ...v }));
const smashedNames = smashed.map((r) => tName(r.tid));
if (smashedNames.some((n) => n !== "unavailable")) {
  console.error("expected +tid smash to be unavailable, got", smashedNames);
  process.exit(1);
}

const rows = Object.entries(txByTeam).map(([tid, v]) => ({ tid, ...v }));
const names = rows.map((r) => tName(r.tid));
for (const need of ["Feelers", "Chupacabras", "Pollywogs", "Pounders"]) {
  if (!names.includes(need)) {
    console.error("missing", need, "in", names);
    process.exit(1);
  }
}
if (names.some((n) => !n || n === "—" || n === "-" || n === "NaN")) {
  console.error("blank/dash label", names);
  process.exit(1);
}
if (tName(NaN) !== "unavailable" || tName("m99") !== "unavailable") {
  console.error("bad fallback", tName(NaN), tName("m99"));
  process.exit(1);
}
console.log("ok chi112 names", names.join(", "));
