#!/usr/bin/env node
/**
 * Inject daily_brief v1.0 into public/daily-brief.json
 * Usage: node scripts/inject-daily-brief.mjs <brief.json>
 *        cat snapshot.json | node scripts/inject-daily-brief.mjs
 * Vite serves public/ — no rebuild; refresh Real mode.
 */
import { readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const DEST = join(ROOT, "public", "daily-brief.json")
const SLOTS = new Set(["morning_0530", "afternoon_1530", "weekend_adhoc"])
async function readInput() {
  const arg = process.argv[2]
  if (arg && arg !== "-") return readFileSync(arg, "utf8")
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  const text = Buffer.concat(chunks).toString("utf8").trim()
  if (!text) { console.error("Usage: node scripts/inject-daily-brief.mjs <brief.json>"); process.exit(1) }
  return text
}
const raw = await readInput()
let data
try { data = JSON.parse(raw) } catch (e) { console.error("Invalid JSON:", e.message); process.exit(1) }
if (data?.status === "pending" || data?.payloadKind === "pending") { writeFileSync(DEST, JSON.stringify(data, null, 2) + "\n"); console.log("Wrote pending placeholder to", DEST); process.exit(0) }
if (data?.schemaVersion !== "1.0") { console.error("Refusing inject: schemaVersion must be 1.0"); process.exit(1) }
const slot = data?.slot
if (!SLOTS.has(slot)) { console.error(`Refusing inject: slot must be morning_0530|afternoon_1530|weekend_adhoc, got ${slot}`); process.exit(1) }
if (!data.asOf) { console.error("Refusing inject: missing asOf"); process.exit(1) }
if (typeof data?.fearAndGreed?.score !== "number") { console.error("Refusing inject: missing fearAndGreed.score"); process.exit(1) }
if (!data.commodities?.oil || !data.dailySignals || !Array.isArray(data.portfolios)) { console.error("Refusing inject: missing commodities/dailySignals/portfolios"); process.exit(1) }
writeFileSync(DEST, JSON.stringify(data, null, 2) + "\n")
console.log("Injected daily brief v1.0 →", DEST)
console.log(`  slot=${slot} asOf=${data.asOf} FG=${data.fearAndGreed.score}`)
console.log("Refresh Real mode in the browser (no rebuild needed).")
