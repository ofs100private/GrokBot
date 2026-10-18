#!/usr/bin/env node
/**
 * Inject Breakout TA feed into public/breakout-ta.json (and dist/ if present).
 * Usage: node scripts/inject-breakout-ta.mjs <breakout-ta.json>
 *        cat breakout-ta.json | node scripts/inject-breakout-ta.mjs
 * Analysis-only feed — never places. Vite serves public/ — refresh #/breakout-ta.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const DEST_PUBLIC = join(ROOT, "public", "breakout-ta.json")
const DEST_DIST = join(ROOT, "dist", "breakout-ta.json")

async function readInput() {
  const arg = process.argv[2]
  if (arg && arg !== "-") return readFileSync(arg, "utf8")
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  const text = Buffer.concat(chunks).toString("utf8").trim()
  if (!text) {
    console.error("Usage: node scripts/inject-breakout-ta.mjs <breakout-ta.json>")
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

const body = JSON.stringify(data, null, 2) + "\n"
writeFileSync(DEST_PUBLIC, body)
console.log("Injected breakout-ta →", DEST_PUBLIC)

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

const summary = data.summary ?? {}
console.log(
  `  schema=${data.schemaVersion} asOf=${data.asOf ?? "—"} run=${data.run_id ?? "—"} tf=${data.timeframe ?? "—"}`,
)
console.log(
  `  confirmed=${summary.confirmedCount ?? "—"} watch=${summary.watchCount ?? "—"} failed=${summary.failedCount ?? "—"} symbols=${summary.symbolCount ?? "—"}`,
)
console.log(
  `  doNotPlaceFromThisUi=${data.doNotPlaceFromThisUi !== false} methods=${Array.isArray(data.comparison?.methods) ? data.comparison.methods.length : 0}`,
)
console.log("Refresh Breakout TA (#/breakout-ta) — no rebuild needed.")
