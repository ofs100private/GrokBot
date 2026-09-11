#!/usr/bin/env node
/**
 * Inject trading-qa feed into public/trading-qa.json
 * Usage: node scripts/inject-trading-qa.mjs <qa.json>
 *        cat qa.json | node scripts/inject-trading-qa.mjs
 * Vite serves public/ — no rebuild; refresh QA & Lessons view.
 */
import { readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const DEST = join(ROOT, "public", "trading-qa.json")

async function readInput() {
  const arg = process.argv[2]
  if (arg && arg !== "-") return readFileSync(arg, "utf8")
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  const text = Buffer.concat(chunks).toString("utf8").trim()
  if (!text) {
    console.error("Usage: node scripts/inject-trading-qa.mjs <qa.json>")
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
if (!Array.isArray(data.portfolios)) {
  console.error("Refusing inject: missing portfolios[]")
  process.exit(1)
}

const keys = new Set(data.portfolios.map((p) => p?.key).filter(Boolean))
if (keys.has("classic") && keys.has("momentum")) {
  // ok — keep books separate in UI
} else if (data.portfolios.length === 0) {
  console.error("Refusing inject: portfolios[] is empty")
  process.exit(1)
}

writeFileSync(DEST, JSON.stringify(data, null, 2) + "\n")
console.log("Injected trading-qa →", DEST)
console.log(`  schema=${data.schemaVersion} asOf=${data.asOf ?? "—"} portfolios=${data.portfolios.length}`)
for (const p of data.portfolios) {
  const actions = Array.isArray(p.actions) ? p.actions.length : 0
  const days = Array.isArray(p.days) ? p.days.length : 0
  const cases = Array.isArray(p.classicCases) ? p.classicCases.length : 0
  console.log(`  · ${p.key}: actions=${actions} days=${days} classicCases=${cases}`)
}
console.log("Refresh QA & Lessons (#/qa) — no rebuild needed.")
