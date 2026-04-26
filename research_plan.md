&#x20;# Full 2026 Master Plan for `experimental-enhancements`



&#x20; ## Summary

&#x20; Evolve `experimental-enhancements` from a lightweight LLM paper-trading bot into a research-grade, calibration-first, uncertainty-aware,

&#x20; microstructure-aware forecasting and execution system for Polymarket-style binary event markets.



&#x20; The design principle is:

&#x20; - the LLM is a \*\*signal generator\*\*, not the final risk authority;

&#x20; - trading decisions are made only after \*\*calibration\*\*, \*\*uncertainty estimation\*\*, \*\*execution-cost modeling\*\*, and \*\*portfolio

&#x20; constraints\*\*;

&#x20; - every component must be \*\*replayable\*\*, \*\*time-correct\*\*, and \*\*versioned\*\*.



&#x20; The branch should become a single Python-first platform with six integrated subsystems:

&#x20; 1. canonical market/evidence data platform

&#x20; 2. forecast generation and model adaptation

&#x20; 3. calibration and uncertainty estimation

&#x20; 4. execution and portfolio/risk control

&#x20; 5. evaluation and continuous benchmarking

&#x20; 6. live operations, observability, and strategy governance



&#x20; Implementation order:

&#x20; 1. data foundation and replay correctness

&#x20; 2. executable-edge and realistic backtester

&#x20; 3. calibration and uncertainty subsystem

&#x20; 4. candidate ranking and retrieval-conditioned forecasting

&#x20; 5. sizing, exposure, and execution policies

&#x20; 6. online learning, governance, and live ops hardening



&#x20; Commit cadence:

&#x20; - Create a commit after every 5 numbered implementation items.

&#x20; - Expected checkpoints:

&#x20;   - after item 5

&#x20;   - after item 10

&#x20;   - after item 15

&#x20;   - after item 20

&#x20;   - after item 25

&#x20;   - after item 30

&#x20;   - final cleanup commit after items 31-37 if needed



&#x20; ## Architecture and Data Foundation

&#x20; ### 1. Establish a canonical event-market schema

&#x20; - Introduce a canonical internal schema for all market observations.

&#x20; - Each market snapshot should include:

&#x20;   - `market\\\_id`

&#x20;   - `event\\\_id`

&#x20;   - `token\\\_id`

&#x20;   - `title`

&#x20;   - `description`

&#x20;   - `resolution\\\_criteria`

&#x20;   - `category`

&#x20;   - `subcategory`

&#x20;   - `forecast\\\_timestamp`

&#x20;   - `expiry\\\_timestamp`

&#x20;   - `best\\\_bid`

&#x20;   - `best\\\_ask`

&#x20;   - `mid\\\_price`

&#x20;   - `last\\\_trade\\\_price`

&#x20;   - `spread`

&#x20;   - `depth\\\_bid`

&#x20;   - `depth\\\_ask`

&#x20;   - `tick\\\_size`

&#x20;   - `fee\\\_schedule`

&#x20;   - `volume`

&#x20;   - `open\\\_interest` if available

&#x20;   - `market\\\_status`

&#x20;   - `resolved\\\_outcome` when later known

&#x20; - Preserve raw provider payloads alongside normalized fields for auditability.



&#x20; ### 2. Split provider roles explicitly

&#x20; - Use Gamma for discovery and metadata.

&#x20; - Use CLOB/orderbook endpoints and websocket streams for executable market state.

&#x20; - Treat these as separate adapters with explicit merge logic.

&#x20; - Never use a discovery payload alone to make live execution decisions.



&#x20; ### 3. Create a replayable evidence store

&#x20; - Persist time-bounded evidence objects separately from market snapshots.

&#x20; - Evidence records should include:

&#x20;   - `evidence\\\_id`

&#x20;   - source URL / source type

&#x20;   - publication timestamp

&#x20;   - ingestion timestamp

&#x20;   - source credibility metadata

&#x20;   - extracted claims / summary

&#x20;   - linked `event\\\_id` / `market\\\_id`

&#x20; - Evidence must be versioned and frozen in replay mode.

&#x20; - No backtest should be allowed to access evidence published after the forecast timestamp.



&#x20; ### 4. Build a feature store for forecasting research

&#x20; - Maintain derived features separately from raw data.

&#x20; - Feature groups:

&#x20;   - market microstructure

&#x20;   - price history / momentum

&#x20;   - liquidity and spread metrics

&#x20;   - evidence counts and freshness

&#x20;   - category and horizon metadata

&#x20;   - calibration-context metadata

&#x20; - Feature computation must be deterministic and replayable.



&#x20; ### 5. Redefine the LLM’s role

&#x20; - Keep Bull/Bear/Judge as the initial forecast engine.

&#x20; - Treat its output as:

&#x20;   - raw forecast probability

&#x20;   - rationale bundle

&#x20;   - uncertainty clues

&#x20;   - evidence references

&#x20; - Do not allow the LLM to directly determine trade size or bypass gates.



&#x20; Commit checkpoint 1:

&#x20; - Commit after item 5 once schema, provider separation, evidence-store contracts, feature-store contracts, and LLM-role boundaries are

&#x20; implemented together.



&#x20; ## Forecast Generation and Model Adaptation

&#x20; ### 6. Require structured forecast output

&#x20; - Replace free-form final parsing with a strict structured response contract.

&#x20; - Required fields from the judge stage:

&#x20;   - `raw\\\_probability`

&#x20;   - `short\\\_rationale`

&#x20;   - `key\\\_drivers`

&#x20;   - `counter\\\_drivers`

&#x20;   - `invalidation\\\_condition`

&#x20;   - `confidence\\\_band` as raw model self-report only

&#x20;   - `evidence\\\_used`

&#x20; - Parsing failures must degrade gracefully to HOLD, not fallback to ad hoc extraction.



&#x20; ### 7. Add retrieval-conditioned forecasting

&#x20; - The forecaster should receive:

&#x20;   - current market state

&#x20;   - historical price/market features

&#x20;   - top-ranked evidence

&#x20;   - resolution/rules text

&#x20; - Retrieval policy:

&#x20;   - prefer recent, high-credibility, directly relevant evidence

&#x20;   - deduplicate near-identical reports

&#x20;   - limit context by timestamp and token budget

&#x20; - Maintain category-specific retrieval behavior because recent research suggests news helps selectively and can harm some domains.



&#x20; ### 8. Introduce domain-aware forecasting variants

&#x20; - Maintain separate strategy profiles by category or event family.

&#x20; - Examples:

&#x20;   - politics/elections

&#x20;   - macro/economics

&#x20;   - crypto

&#x20;   - tech/product launches

&#x20;   - court/legal

&#x20;   - sports/entertainment if included later

&#x20; - Each profile can vary:

&#x20;   - retrieval aggressiveness

&#x20;   - horizon preference

&#x20;   - uncertainty thresholds

&#x20;   - calibration model

&#x20;   - sizing limits

&#x20; - Default behavior: no global one-size-fits-all forecasting policy.



&#x20; ### 9. Add model adaptation and training tracks

&#x20; - Maintain three model layers:

&#x20;   - base inference LLM

&#x20;   - optional fine-tuned forecasting adapter

&#x20;   - separate lightweight calibration/uncertainty models

&#x20; - Build a resolved-market dataset pipeline with strict leakage prevention.

&#x20; - Training corpora should exclude:

&#x20;   - post-resolution explanations

&#x20;   - future evidence

&#x20;   - leaked market outcomes in summaries

&#x20; - Use fine-tuning or distillation only after the backtest and calibration infrastructure is trustworthy.

&#x20; - Default early focus: improve system architecture before model retraining.



&#x20; ### 10. Add a dedicated calibration subsystem

&#x20; - Calibration happens after raw LLM forecast aggregation and before risk/execution.

&#x20; - Support:

&#x20;   - isotonic regression

&#x20;   - beta calibration

&#x20;   - logistic/temperature scaling baseline

&#x20; - Calibrators are trained per time window and optionally per category.

&#x20; - Use walk-forward fitting only.

&#x20; - Persist calibrator artifacts with:

&#x20;   - version

&#x20;   - training period

&#x20;   - feature set

&#x20;   - category scope

&#x20;   - sample count



&#x20; Commit checkpoint 2:

&#x20; - Commit after item 10 once structured outputs, retrieval, domain profiles, dataset/training pipeline scaffolding, and calibration

&#x20; artifact plumbing are integrated.



&#x20; ## Calibration and Uncertainty Estimation

&#x20; ### 11. Define uncertainty as a composite estimate

&#x20; - Do not use one model-emitted confidence score as the uncertainty estimate.

&#x20; - Default uncertainty components:

&#x20;   - repeated-sample forecast dispersion

&#x20;   - prompt-paraphrase sensitivity

&#x20;   - evidence-subset sensitivity

&#x20;   - semantic disagreement between outputs

&#x20;   - calibration residual history for similar cases

&#x20;   - belief-update instability under new evidence

&#x20; - Produce:

&#x20;   - `uncertainty\\\_score`

&#x20;   - `forecast\\\_variance`

&#x20;   - `semantic\\\_disagreement\\\_score`

&#x20;   - `update\\\_instability\\\_score`



&#x20; ### 12. Add belief-updating diagnostics

&#x20; - Reforecast selected markets when meaningful new evidence arrives.

&#x20; - Track:

&#x20;   - probability shift magnitude

&#x20;   - direction consistency

&#x20;   - update delay

&#x20;   - sensitivity to evidence quality

&#x20; - Penalize:

&#x20;   - underreaction to strong evidence

&#x20;   - overreaction to noisy evidence

&#x20; - Use these metrics both for research and trade gating.



&#x20; ### 13. Use conformal methods as guardrails, not primary probabilities

&#x20; - Conformal-style methods may be used for:

&#x20;   - abstain / no-trade gating

&#x20;   - coverage-aware confidence bands

&#x20;   - covariate-shift-aware reliability checks

&#x20; - They should not replace the primary calibrated scalar probability in v1.

&#x20; - Under dynamic shift, treat conformal outputs as protective overlays, especially for evidence-heavy cases.



&#x20; ## Market Selection, Edge, and Execution

&#x20; ### 14. Add a candidate ranking funnel

&#x20; - Introduce a two-stage workflow:

&#x20;   - cheap market ranking

&#x20;   - expensive LLM forecasting only on shortlisted candidates

&#x20; - Ranking factors:

&#x20;   - spread

&#x20;   - depth

&#x20;   - volume

&#x20;   - time to resolution

&#x20;   - price movement regime

&#x20;   - category

&#x20;   - rule clarity

&#x20;   - historical category profitability

&#x20;   - expected evidence quality

&#x20; - Hard exclusions:

&#x20;   - missing tradability identifiers

&#x20;   - excessive spread

&#x20;   - insufficient depth

&#x20;   - stale orderbook

&#x20;   - ambiguous or low-integrity market rules



&#x20; ### 15. Redefine edge around executable economics

&#x20; - Replace naive edge with:

&#x20;   - `edge\\\_after\\\_costs = calibrated\\\_probability - expected\\\_fill\\\_price - fees - slippage\\\_haircut - uncertainty\\\_haircut`

&#x20; - Expected fill price should depend on:

&#x20;   - maker vs taker path

&#x20;   - book depth

&#x20;   - assumed queue / partial-fill model

&#x20;   - order timeout behavior

&#x20; - No live trade should be triggered on midpoint-style edge alone.



&#x20; Commit checkpoint 3:

&#x20; - Commit after item 15 once uncertainty, belief-update, conformal gating hooks, candidate ranking, and executable-edge calculations are

&#x20; working together.



&#x20; ### 16. Add maker-first execution policies

&#x20; - Default live mode:

&#x20;   - place maker orders first

&#x20;   - monitor queue and market movement

&#x20;   - optionally cross spread only if residual edge remains positive

&#x20; - Execution policy fields:

&#x20;   - `execution\\\_mode`

&#x20;   - `maker\\\_timeout\\\_sec`

&#x20;   - `cancel\\\_replace\\\_policy`

&#x20;   - `max\\\_cross\\\_spread\\\_bps`

&#x20;   - `min\\\_remaining\\\_edge\\\_after\\\_cross`

&#x20; - Explicitly model cancel/replace behavior in backtests.



&#x20; ### 17. Add inventory and unwind logic

&#x20; - Support optional pre-resolution inventory reduction when:

&#x20;   - edge collapses

&#x20;   - uncertainty spikes

&#x20;   - event correlation limits are exceeded

&#x20;   - drawdown policies trigger

&#x20; - Define whether the strategy is:

&#x20;   - entry-only to resolution

&#x20;   - entry-plus-active-management

&#x20; - Default v1: support inventory reduction, but do not require frequent intraday churn unless backed by replay evidence.



&#x20; ## Portfolio Construction and Risk

&#x20; ### 18. Replace fixed stake sizing with constrained fractional Kelly

&#x20; - Base position size on post-cost calibrated edge.

&#x20; - Apply uncertainty and liquidity haircuts before sizing.

&#x20; - Default to fractional Kelly, never full Kelly.

&#x20; - Enforce:

&#x20;   - min trade size

&#x20;   - max trade size

&#x20;   - category caps

&#x20;   - event-family caps

&#x20;   - unresolved inventory caps

&#x20;   - drawdown-based throttling



&#x20; ### 19. Add thesis-level and correlation-aware exposure control

&#x20; - Build a thesis registry that clusters related markets by entity, event, and dependency.

&#x20; - Multiple titles about the same underlying event must share one exposure budget.

&#x20; - Maintain both:

&#x20;   - event-family exposure

&#x20;   - category-wide exposure

&#x20; - Add a simple correlation graph initially based on shared metadata, then upgrade to empirical co-movement later.



&#x20; ### 20. Add kill switches and circuit breakers

&#x20; - Pause trading automatically when:

&#x20;   - stale data exceeds threshold

&#x20;   - calibration artifact missing or invalid

&#x20;   - uncertainty unexpectedly spikes across many markets

&#x20;   - live fill behavior deviates materially from modeled slippage

&#x20;   - drawdown exceeds configured limit

&#x20; - Expose both automatic and manual global pause controls.



&#x20; Commit checkpoint 4:

&#x20; - Commit after item 20 once execution policy, unwind logic, Kelly sizing, exposure controls, and circuit breakers are implemented as a

&#x20; coherent risk layer.



&#x20; ## Evaluation, Benchmarking, and Research Loop

&#x20; ### 21. Upgrade replay into a realistic event-driven backtester

&#x20; - Replay engine must support:

&#x20;   - timestamped snapshots

&#x20;   - orderbook state

&#x20;   - evidence availability by time

&#x20;   - maker/taker fills

&#x20;   - partial fills

&#x20;   - stale quote handling

&#x20;   - settlement timing

&#x20; - No random splits; all evaluation is chronological.



&#x20; ### 22. Expand evaluation metrics beyond PnL

&#x20; - Forecast-quality metrics:

&#x20;   - Brier score

&#x20;   - log loss

&#x20;   - ECE / reliability

&#x20;   - calibration curves

&#x20;   - update quality metrics

&#x20; - Trade-quality metrics:

&#x20;   - post-cost PnL

&#x20;   - drawdown

&#x20;   - Sharpe-like risk-adjusted stats if stable enough

&#x20;   - hit rate

&#x20;   - inventory turnover

&#x20;   - realized slippage

&#x20;   - win/loss by uncertainty bucket

&#x20; - Strategy-quality diagnostics:

&#x20;   - category performance

&#x20;   - horizon performance

&#x20;   - evidence-on vs evidence-off

&#x20;   - maker vs taker

&#x20;   - raw vs calibrated



&#x20; ### 23. Adopt continuous benchmarking methodology

&#x20; - Use a rolling resolved-window benchmark inspired by ForecastBench-style continuous evaluation.

&#x20; - Track baseline and challenger versions over time.

&#x20; - Because question sets differ over time, compare versions using:

&#x20;   - matched-question subsets when available

&#x20;   - difficulty-aware or fixed-effect-adjusted comparisons when not

&#x20; - Preserve raw metrics as well as adjusted comparisons.



&#x20; ### 24. Add statistical decision rules for promotion

&#x20; - A strategy version may be promoted only if it:

&#x20;   - improves walk-forward post-cost PnL over baseline

&#x20;   - does not materially worsen calibration

&#x20;   - does not increase drawdown beyond configured tolerance

&#x20;   - remains robust across major categories rather than winning only on one narrow slice

&#x20; - Require repeated outperformance across multiple windows, not one lucky period.



&#x20; ### 25. Introduce champion-challenger governance

&#x20; - Maintain one production champion and multiple challengers.

&#x20; - Challengers can run:

&#x20;   - offline only

&#x20;   - paper shadow mode

&#x20;   - limited live capital mode later

&#x20; - Every run must log exact:

&#x20;   - model version

&#x20;   - prompt version

&#x20;   - calibrator version

&#x20;   - uncertainty version

&#x20;   - ranker version

&#x20;   - execution version



&#x20; Commit checkpoint 5:

&#x20; - Commit after item 25 once the realistic backtester, expanded metrics, rolling benchmark framework, promotion rules, and champion-

&#x20; challenger tracking are in place.



&#x20; ## Online Learning and Maintenance

&#x20; ### 26. Add periodic recalibration and rolling retraining

&#x20; - Refit calibration on a rolling schedule:

&#x20;   - default daily or weekly depending on resolution volume

&#x20; - Use recency-aware windows with decay or rolling truncation.

&#x20; - Keep category-specific calibrators if data suffices; otherwise back off to pooled calibrators.

&#x20; - Store old artifacts for reproducibility.



&#x20; ### 27. Add post-trade/post-resolution learning loops

&#x20; - After resolution, label each trade and forecast with:

&#x20;   - correctness

&#x20;   - calibration error

&#x20;   - uncertainty miss

&#x20;   - execution miss

&#x20;   - evidence miss

&#x20;   - category/horizon tags

&#x20; - Use this to drive:

&#x20;   - recalibration

&#x20;   - feature improvement

&#x20;   - retrieval heuristics

&#x20;   - prompt or adapter adjustments

&#x20; - Do not allow direct online prompt mutation in production without governance.



&#x20; ## Operations, Observability, and Product Surface

&#x20; ### 28. Build robust observability and audit logging

&#x20; - Structured logs should capture:

&#x20;   - market snapshot ID

&#x20;   - evidence bundle ID

&#x20;   - forecast artifact ID

&#x20;   - calibration artifact ID

&#x20;   - trade decision ID

&#x20;   - execution result ID

&#x20; - Every live trade must be reconstructible from stored artifacts.



&#x20; ### 29. Add dashboards for operators and research

&#x20; - Dashboard should expose:

&#x20;   - current positions and exposures

&#x20;   - candidate markets

&#x20;   - forecast probability vs calibrated probability

&#x20;   - uncertainty score

&#x20;   - edge after costs

&#x20;   - execution mode chosen

&#x20;   - reason for hold / rejection

&#x20;   - recent calibration drift

&#x20;   - PnL and drawdown

&#x20; - Research views should expose:

&#x20;   - reliability plots

&#x20;   - uncertainty bucket analysis

&#x20;   - category-level diagnostics

&#x20;   - version comparisons



&#x20; ### 30. Add operational failure handling

&#x20; - Handle:

&#x20;   - API outages

&#x20;   - websocket disconnects

&#x20;   - stale orderbook

&#x20;   - missing token IDs

&#x20;   - fee schedule changes

&#x20;   - collateral or platform migration changes

&#x20; - Add reconciliation jobs for:

&#x20;   - wallet state

&#x20;   - open orders

&#x20;   - settlements

&#x20;   - expected vs actual fills



&#x20; Commit checkpoint 6:

&#x20; - Commit after item 30 once recalibration cadence, post-resolution learning, audit logging, dashboards, and operational failure/

&#x20; reconciliation flows are complete.



&#x20; ### 31. Align with current Polymarket platform reality

&#x20; - Keep live-trading assumptions configurable because Polymarket’s platform details changed around late April 2026.

&#x20; - Do not hardcode legacy collateral or fee assumptions.

&#x20; - Add platform capability/version flags so the system can adapt to future migration events without invasive rewrites.



&#x20; ## Public Interfaces and Types

&#x20; ### 32. Expand core config and types

&#x20; - `StrategyConfig` should grow grouped settings for:

&#x20;   - provider/data

&#x20;   - retrieval

&#x20;   - calibration

&#x20;   - uncertainty

&#x20;   - market filters

&#x20;   - execution

&#x20;   - sizing

&#x20;   - exposure

&#x20;   - evaluation

&#x20;   - ops/circuit breakers

&#x20; - `SignalDecision` should be replaced or extended into a structured forecast-decision type with calibrated, uncertain, and execution-

&#x20; aware fields.

&#x20; - Replay file format should support:

&#x20;   - timestamped market state

&#x20;   - orderbook state

&#x20;   - optional evidence references

&#x20;   - optional resolution data

&#x20; - Report schema should support both forecasting metrics and trading metrics.



&#x20; ## Test Plan

&#x20; ### 33. Core correctness tests

&#x20; - schema normalization and merge correctness for Gamma + CLOB

&#x20; - no-lookahead guarantees in replay and evidence retrieval

&#x20; - structured-response parsing and safe HOLD fallback

&#x20; - calibration artifact load/version compatibility

&#x20; - uncertainty aggregation behavior under repeated samples



&#x20; ### 34. Economic realism tests

&#x20; - fee-aware edge calculation

&#x20; - maker/taker branch correctness

&#x20; - slippage and depth handling

&#x20; - partial-fill behavior

&#x20; - cancel/replace logic

&#x20; - stale quote rejection

&#x20; - inventory unwind behavior



&#x20; ### 35. Forecast-quality tests

&#x20; - Brier, log loss, ECE correctness

&#x20; - pre/post calibration comparison

&#x20; - category-specific calibrator fallback logic

&#x20; - uncertainty monotonicity checks

&#x20; - update-delta behavior under new evidence



&#x20; ### 36. Risk and portfolio tests

&#x20; - Kelly sizing bounds

&#x20; - event-family and category cap enforcement

&#x20; - drawdown-triggered throttling

&#x20; - kill-switch activation on stale data and broken dependencies



&#x20; ### 37. End-to-end acceptance tests

&#x20; - current baseline strategy vs upgraded strategy on walk-forward replay

&#x20; - calibration uplift on held-out resolved questions

&#x20; - positive relation between lower uncertainty and better realized performance

&#x20; - live-mode dry-run auditability from decision to simulated fill

&#x20; Final commit checkpoint:

&#x20; - After items 31-37, make a final integration commit for platform-compatibility updates, type/schema expansions, and the full test/

&#x20; acceptance harness.



&#x20; ## Assumptions and Defaults

&#x20; - Profitability is the primary objective; complexity is acceptable if it improves expected edge robustly.

&#x20; - Implementation stays Python-first and monolithic initially.

&#x20; - Bull/Bear/Judge remains the initial forecaster, but all serious decision authority moves to the surrounding system.

&#x20; - Default calibration order:

&#x20;   - isotonic when enough category-specific resolved data exists

&#x20;   - beta calibration otherwise

&#x20;   - logistic/temperature as baseline comparator

&#x20; - Default uncertainty policy:

&#x20;   - 5-9 judge samples

&#x20;   - composite uncertainty score

&#x20;   - no-trade gate above threshold

&#x20; - Default execution policy:

&#x20;   - maker-first

&#x20;   - taker only when residual post-cost edge remains positive

&#x20; - Default sizing policy:

&#x20;   - conservative fractional Kelly with hard exposure caps

&#x20; - Default governance policy:

&#x20;   - champion/challenger

&#x20;   - walk-forward-only promotion

&#x20;   - no live rollout without post-cost and calibration win over baseline

