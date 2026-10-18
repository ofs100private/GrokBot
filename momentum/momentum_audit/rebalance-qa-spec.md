# QA Bot spec: Momentum rebalance pack (place-QA)

Input: `momentum_audit/place_qa/rebalance-YYYYMMDD-*.json` plus the audit rows for that run_id in `momentum_audit/YYYY-MM-DD.jsonl`.
Verdict: PASS / PASS_WITH_GATE_OK / FAIL, with `authorize_place` set per action. Never PASS a pack that breaks any MUST.

## MUST
1. **Live data:** the snapshot was read in this wake. Keys positions and summary timestamps are ≤15 min old, and every proposed buy or discretionary sell has a quote ≤60s old (`quote.age_s`) and a spread at or under the limit. Otherwise FAIL `STALE_QUOTE` / `WIDE_SPREAD`.
2. **Books:** keys held set == mirror A held set, or the differences are explained. Every TRAIL/BE symbol is on mirror A (`NOT_ON_MIRROR_A` skip). Mirror A cash is never the authority for a buy.
3. **PM priority:** CLOSE (<SMA50 / LOSS_PCT_GE_4) > BE ≥2R > TRAIL ≥1R (new stop ≥ prior, ≤ entry, from the 10d low) > HOLD. Re-verify SMA50 and PnL independently on at least one name.
4. **Regime:** if EVENT_VOL_FREEZE, HARD_HALT, the 16:30–18:30 IL ban, or NYSE closed applies, there are 0 BUY / ROTATION_IN / DEPLOY rows with status PROPOSED. Closes are still allowed.
5. **Playbook:** x1 leverage, amount ≤ $1000, no DUPLICATE_HOLD_BUY, ≤1 new ETF, ETF slot dropped while an ETF is held, the only sector ETF never rotated out, no average-down top-up, SOFT regime allows breakouts only.
6. **Cost gate** on every discretionary row (ROTATION_PAIR, TRIM, TOPUP, DEPLOY_CASH, ROTATION_IN):
   - Recompute the cost: round-trip spread = amount × (ask−bid)/mid; plus fee_open from the costs route for that symbol (`fee_source` VERIFIED, otherwise flag ASSUMED); plus fee_close ($1.50, ASSUMED); plus overnight × holding_nights; plus FX; plus the sell leg for pairs; plus tax when tax_mode=full.
   - Recompute the benefit: notional × edge_used_pct. edge_used_pct must be ≤ edge_cap_pct, ≥ 0, and derived from the empirical history (n_trades, mean) plus the configured prior/haircut. The old leg of a rotation and any trim must credit 0.
   - PASS only if net > 0 **and** benefit ≥ cost_margin_mult × cost. Any row marked PROPOSED that fails this is a FAIL `COST_GATE_OVERSTATED`. Rejected rows must carry `COST_GATE_FAIL` and the numbers.
   - Protective PM closes must **not** be cost-gated or blocked by freeze or ban.
7. **Cash sequencing:** sells come before buys. Each PROPOSED buy has cash_before ≥ amount + fee + buffer, using **keys** availableCash. Buys that depend on sell proceeds are PROPOSED_CONDITIONAL and get `authorize_place=false` until a fresh place-QA after the fill.
8. **No self-authorization:** the pack has `authorize_place=false` and `planner_only=true`. QA sets authorize_place per action, and never for `--dryrun-eval-in-ban` output.
9. **Audit:** RUN_START, TRACE (context, edge_model, scores), one ACTION per trace row, and RUN_END, all under the same run_id.

## Execution ACK checks (after PASS)
- Trader re-reads keys availableCash and re-quotes before **each** place, and re-runs the gate on the fresh quote. A place_ack row (PLACED / WAITING_FOR_MARKET / SKIPPED_REASON) is written within ~15 min, otherwise `EOD_PLACE_NOT_ACKED`.
- A place without a matching QA PASS gets AVOID `PLACE_WITHOUT_QA_BOT_RECHECK`.

## SHOULD (flag, not FAIL)
- Unverified fee components (close fee, FX) are listed in the verdict.
- `edge_model.empirical_mean_net_pct < 0` → report "edge negative: discretionary trades will cost-gate fail".

## v2 additions
- Run `screener-venv/bin/python -m pytest -q tests/test_momentum_rebalance.py` (must be all green).
- `python momentum_rebalance.py verify --pack P --verdict V` must return ok before the executor places anything. A QA Bot verdict JSON must include: `checker:"QA Bot"`, `skill:"momentum-real-money-qa-gate"`, `verdict`, `run_id`, `pack_sha256`, `ts_utc` or `ts_il`, and `authorize_place:{action_id:true}`.
- The executor must call `preplace` for each action_id with fresh reads; any non-ok result means no place.

## v3 additions
- Verdict JSON must contain: `checker`, `skill`, `verdict`, `run_id`, `pack_sha256`, **`ts_utc`** (UTC, the only time used; `ts_il` optional but it must agree), **`nonce`** (≥16 random chars, unique per verdict), `authorize_place{action_id:true}`, and for BUYs `bound{action_id:{amount, stop_loss}}`. The verdict expires after 300s.
- Executor: discretionary actions go through `preplace --pack --verdict --action-id --keys-summary --keys-positions --quotes --history [--cost]` (all fresh). Protective closes go through `stopclose --position-id --keys-positions` (no verdict). Both are single-use.
- Check the PLACE_ACK rows (`PREPLACE_CONSUMED` / `STOPCLOSE_CONSUMED`) against place-close/place-trade results.
- Accepted-risk note on forgeability: see the design doc, v3 section.

## v4 additions
- `DISCRETIONARY_ENABLED` must be False unless there is a written decision from Ofer. With it False, the pack has no PROPOSED BUY/ROTATION/TRIM rows and preplace returns DISCRETIONARY_DISABLED.
- EDIT_SL: preplace must re-derive the stop from live risk_eval. Check that any SL edit equals the computed trail/BE stop and is below bid × 0.998.
- stopclose: always on; no marker. Retry after a failed place is allowed; a working close order means CLOSE_ALREADY_PENDING.
- Preplace inputs: cost and history must carry an xRequestId (recorded in PLACE_ACK). Rotation needs --buy-quotes and --buy-cost (live).
- Residual forgeability: see "PENDING OFER/SECURITY DECISION" in the design doc. These gaps are not accepted.
