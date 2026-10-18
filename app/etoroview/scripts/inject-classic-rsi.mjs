#!/usr/bin/env node
/**
 * Inject Classic RSI feed into public/classic-rsi.json (and dist/ if present).
 * Usage: node scripts/inject-classic-rsi.mjs <classic-rsi.json>
 *        cat classic-rsi.json | node scripts/inject-classic-rsi.mjs
 * Classic OfersClaw5-PRIYN / mirror 11368142 ONLY — refuses Momentum blends.
 * Vite serves public/ — no rebuild; refresh Classic Bot (#/classic-bot).
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const DEST_PUBLIC = join(ROOT, "public", "classic-rsi.json")
const DEST_DIST = join(ROOT, "dist", "classic-rsi.json")
const CLASSIC_MIRROR = 11368142

async function readInput() {
  const arg = process.argv[2]
  if (arg && arg !== "-") return readFileSync(arg, "utf8")
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  const text = Buffer.concat(chunks).toString("utf8").trim()
  if (!text) {
    console.error("Usage: node scripts/inject-classic-rsi.mjs <classic-rsi.json>")
    process.exit(1)
  }
  return text
}

const raw = await readInput()
let data
try {
  data = JSON.parse(raw)
} catch (e) {
  console.error("Invalid JSON:", e.message)
  process.exit(1)
}

if (!data?.schemaVersion) {
  console.error("Refusing inject: missing schemaVersion")
  process.exit(1)
}
if (!data?.portfolio) {
  console.error("Refusing inject: missing portfolio")
  process.exit(1)
}

const key = String(data.portfolio.key || "").toLowerCase()
const name = String(data.portfolio.name || "").toLowerCase()
const mirrorId = data.portfolio.mirrorId
if (key.includes("momentum") || name.includes("momentum")) {
  console.error("Refusing inject: Momentum portfolio not allowed in classic-rsi.json")
  process.exit(1)
}
if (mirrorId != null && Number(mirrorId) !== CLASSIC_MIRROR) {
  console.error(
    `Refusing inject: portfolio.mirrorId must be ${CLASSIC_MIRROR} (Classic), got ${mirrorId}`,
  )
  process.exit(1)
}

const body = JSON.stringify(data, null, 2) + "\n"
writeFileSync(DEST_PUBLIC, body)
console.log("Injected classic-rsi →", DEST_PUBLIC)

if (existsSync(dirname(DEST_DIST))) {
  try {
    writeFileSync(DEST_DIST, body)
    console.log("Dual-wrote →", DEST_DIST)
  } catch (e) {
    console.warn("Could not write dist copy:", e.message)
  }
} else {
  mkdirSync(dirname(DEST_DIST), { recursive: true })
  writeFileSync(DEST_DIST, body)
  console.log("Dual-wrote →", DEST_DIST)
}

const auto = data.latestAuto
const bt = data.backtestSummary?.aggregate
console.log(
  `  schema=${data.schemaVersion} asOf=${data.asOf ?? "—"} mirror=${mirrorId ?? "—"}`,
)
console.log(
  `  auto=${auto?.status ?? "—"} run=${auto?.run_id ?? "—"} packs=${Array.isArray(auto?.buy_packs) ? auto.buy_packs.length : "—"}`,
)
console.log(
  `  backtest n_trades=${bt?.n_trades ?? "—"} win_rate=${bt?.win_rate ?? "—"} expectancy_R=${bt?.expectancy_R ?? "—"}`,
)
console.log(
  `  auditIndex=${Array.isArray(data.auditIndex) ? data.auditIndex.length : 0}`,
)
console.log("Refresh Classic Bot (#/classic-bot) — no rebuild needed.")
