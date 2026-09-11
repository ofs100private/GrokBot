#!/usr/bin/env node
/**
 * Inject Trader_Classic snapshot into public/classic-portfolio.json
 * Usage: node scripts/inject-classic-snapshot.mjs <snapshot.json>
 *        cat snapshot.json | node scripts/inject-classic-snapshot.mjs
 * Vite serves public/ — no rebuild; refresh Real mode.
 */
import { readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const DEST = join(ROOT, "public", "classic-portfolio.json")
const MIRROR_ID = 11368142
async function readInput() {
  const arg = process.argv[2]
  if (arg && arg !== "-") return readFileSync(arg, "utf8")
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  const text = Buffer.concat(chunks).toString("utf8").trim()
  if (!text) { console.error("Usage: node scripts/inject-classic-snapshot.mjs <snapshot.json>"); process.exit(1) }
  return text
}
const raw = await readInput()
let data
try { data = JSON.parse(raw) } catch (e) { console.error("Invalid JSON:", e.message); process.exit(1) }
if (data?.status === "pending") { writeFileSync(DEST, JSON.stringify(data, null, 2) + "\n"); console.log("Wrote pending placeholder to", DEST); process.exit(0) }
const mirrorId = data?.account?.mirrorId
if (mirrorId !== MIRROR_ID) { console.error(`Refusing inject: account.mirrorId must be ${MIRROR_ID}, got ${mirrorId}`); process.exit(1) }
if (!data.asOf) { console.error("Refusing inject: missing asOf"); process.exit(1) }
if (!data.summary && !data.clientPortfolio) { console.error("Refusing inject: missing summary or clientPortfolio"); process.exit(1) }
writeFileSync(DEST, JSON.stringify(data, null, 2) + "\n")
console.log("Injected Classic snapshot →", DEST)
console.log(`  username=${data.account.username} mirrorId=${mirrorId} asOf=${data.asOf}`)
console.log("Refresh Real mode in the browser (no rebuild needed).")
