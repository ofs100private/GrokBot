# eToroView
A polished, read-only eToro-style portfolio dashboard built with Vite + React + TypeScript.
## Features
- **Demo / Real account choice** — large, accessible tiles with keyboard selection and persistent localStorage state.
- **Portfolio dashboard** — equity, available cash, total invested, and profit/loss summary cards plus a positions table with copy-trader mirror rows.
- **Morning market briefing** — Asia/Jerusalem timestamped desk note with overnight headlines and a watchlist.
- **Sample data only** — no API keys, OAuth, or live trading. Data is structured to mirror the eToro Public API `GET /trading/info/{env}/pnl` response shape so a live integration can be swapped in later.
## Run locally
```bash
npm install
npm run dev
```
Then open the printed local URL (default `http://localhost:4731`).
## Project structure
src/
  components/       React UI components
  data/
    portfolio.ts    Sample Demo + Real portfolios (eToro API shape)
    briefing.ts     Morning briefing static copy
  utils/format.ts   Currency / percentage formatting
  App.tsx           App shell with mode persistence
  App.css           eToro-style dark theme
```
## Notes

- This is a design demo. No real trades, payments, or credentials are implemented.
- The data layer uses eToro-style field names (`positionID`, `instrumentID`, `mirrorID`, `unrealizedPnL.pnL`) to match the public API response shape.
