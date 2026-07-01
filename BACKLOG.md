# rf5g-sizing Backlog

> Last updated: 2026-06-30
> Purpose: issue-ready backlog for continuing work across future sessions

This backlog is organized by milestone and priority. It is intended to be concrete enough to implement incrementally without re-discovering the roadmap each time.

## GitHub issue flow

Use this file as the backlog source of truth, then open execution items with the GitHub Issue Forms under `.github/ISSUE_TEMPLATE/`.

When converting a backlog item into a GitHub issue:
- Copy the backlog heading into the issue title or backlog reference field
- Preserve the existing **Why**, **Scope**, and **Acceptance criteria** structure
- Apply `priority:*` and `type:*` labels based on the bracket tags in the heading
- Keep `ROADMAP.md` as the milestone/sequence reference and GitHub issues as the execution/tracking unit

Suggested template mapping:
- Feature / Implementation — default for most engine, API, UI, planning, and reporting work
- Docs / Workflow Alignment — docs sync, canonical workflow, and product-coherence work
- Test / Regression — golden scenarios, warning coverage, and output contract protection
- Release / Checklist — release readiness, verification, and milestone closeout work

## Labels

Suggested GitHub labels:
- `priority:P0`
- `priority:P1`
- `priority:P2`
- `type:docs`
- `type:engine`
- `type:api`
- `type:ui`
- `type:planning`
- `type:test`
- `type:reporting`
- `type:release`
- `blocked`

## Definition of Done

An issue is only done when:
1. The implementation works end-to-end for its intended surface.
2. Relevant tests are added or updated.
3. Docs/examples are updated if behavior changed.
4. The change does not create drift between CLI, API, and UI.
5. Any new assumptions, warnings, or limitations are surfaced clearly where relevant.

---

# Milestone 1 — Core Trust & Product Coherence

## [P0][docs] Sync CLI docs with actual commands
**Why**
Some docs still refer to outdated CLI usage patterns while the current CLI uses `size`, `plan`, `map`, `report`, `charts`, and `sites`.

**Scope**
- Update `README.md`
- Update `USER_GUIDE.md`
- Audit `INSTALL_GUIDE.md`
- Remove outdated command examples
- Add canonical examples for current commands

**Acceptance criteria**
- No main docs contain obsolete CLI examples
- Copy/paste examples in docs run against the current CLI
- Docs distinguish Quick Sizing vs Planning where relevant

---

## [P0][test][engine] Add golden scenario regression suite
**Why**
Core outputs should not drift silently as the engine evolves.

**Scope**
- Use baseline scenarios from `examples/`
- Freeze expected outputs for core fields such as:
  - cell radius
  - site count
  - limiting link
  - SINR/CQI
  - capacity summary
- Add regression tests and update instructions for intentional baseline changes

**Acceptance criteria**
- At least 3 baseline scenarios are covered
- Regressions fail clearly
- Intentional updates to baselines are documented

---

## [P0][reporting][api][ui] Expose model assumptions and approximations
**Why**
Some parts of the system are standards-based while others are planning-level approximations or heuristics.

**Scope**
- Add assumptions/limitations section to reports
- Add structured assumptions metadata to outputs where appropriate
- Mark calculations as standards-based, approximate, or heuristic where useful
- Surface warnings in CLI/API/UI for approximation-sensitive cases

**Acceptance criteria**
- HTML/Markdown reports include assumptions/limitations
- Output metadata captures important approximations
- Users can tell what to trust at what level

---

## [P0][engine][ui][api] Add scenario validity warnings
**Why**
Users need guardrails when inputs or assumptions push the tool beyond comfortable planning bounds.

**Scope**
- Detect suspicious or weak-confidence scenarios
- Warn for cases such as:
  - FDD throughput approximation edge cases
  - unusual MIMO override combinations
  - planner inputs with weak geometry assumptions
  - extreme parameter combinations that deserve caution

**Acceptance criteria**
- Warnings appear in CLI and UI, and are available via API
- Warnings explain the issue without blocking the workflow
- At least 5 warning cases are tested

---

## [P0][api][ui][docs] Align output schema semantics across surfaces
**Why**
The same input should lead to the same summary meaning regardless of entrypoint.

**Scope**
- Audit CLI/API/UI result summaries
- Normalize naming and semantics
- Ensure QoS, capacity, and recommendation summaries are consistent

**Acceptance criteria**
- Equivalent summaries across CLI/API/UI for the same input
- Snapshot or contract tests exist for the main API output shape
- No obvious naming drift remains for shared concepts

---

# Milestone 2 — Workflow Simplification & UX

## [P0][docs][ui] Define canonical user workflow
**Why**
The project needs one official path from input to result.

**Scope**
Define and document the default workflow:
1. choose scenario/preset
2. run sizing
3. inspect QoS/capacity
4. optionally move into planning
5. export reports/maps/sites

**Acceptance criteria**
- The workflow appears consistently in docs and UI
- A new user can complete the path without reading source code

---

## [P0][ui][docs] Split product modes: Quick Sizing vs Planning
**Why**
Simple sizing and advanced geometry-aware planning should not feel like the same complexity tier.

**Scope**
- Reframe UI and docs into two distinct modes
- Reduce overload in guided flows
- Clarify required vs optional inputs for each mode

**Acceptance criteria**
- Quick Sizing works with minimal inputs
- Planning mode exposes advanced geometry/constraint inputs only when needed
- Users are not forced through planning complexity for simple sizing tasks

---

## [P1][ui][docs] Build curated preset library
**Why**
Better presets improve onboarding and reproducibility.

**Scope**
Add practical presets such as:
- Dense Urban n78
- Suburban mid-band
- Rural low-band
- Indoor hotspot
- Capacity hotspot

Each preset should include a short note on when to use it.

**Acceptance criteria**
- At least 5 curated presets exist
- Presets are visible in docs and relevant UI flows
- Each preset explains its intended use case

---

## [P1][ui][reporting] Improve results summary for decision-making
**Why**
Users should understand the bottom line before reading detailed engineering output.

**Scope**
Add summary sections such as:
- coverage-limited vs capacity-limited
- estimated sites
- main bottleneck
- recommended next action

**Acceptance criteria**
- Reports and UI show a concise top-level summary
- Users can answer “how many sites, why, and what next?” quickly

---

# Milestone 3 — Geometry-Aware Planning as Flagship

## [P1][planning][docs][ui] Productize planning workflow
**Why**
Geometry-aware planning is the strongest differentiator beyond a sizing calculator.

**Scope**
Define and document a first-class planning flow:
- import/draw service area
- define exclusion zones
- define alignments/corridors
- choose planning objective
- generate plan
- export sites/report

**Acceptance criteria**
- Planning flow is documented end-to-end
- Users can run the planner without reading implementation code

---

## [P1][planning][api][ui][reporting] Expose planner explanations per selected site
**Why**
Planner choices should not be a black box.

**Scope**
Surface human-readable reasons for site selection, including:
- coverage gain
- demand relief
- alignment-based selection
- locked/manual retention

**Acceptance criteria**
- Each selected site has an explanation in relevant outputs
- Reports and UI preserve the explanation
- Planner output is auditable by a human reviewer

---

## [P1][planning][reporting] Add planning scorecard
**Why**
Users need standard metrics to evaluate and compare plans.

**Scope**
Expose a common scorecard with metrics such as:
- coverage ratio
- covered area
- unserved DL/UL demand
- overloaded sites
- locked sites
- alignment length

**Acceptance criteria**
- Planning output includes a consistent scorecard
- Two plans can be compared using the same metrics

---

## [P1][planning][ui] Support manual override and re-run flow
**Why**
Real planning workflows require iteration, not one-shot automation.

**Scope**
Improve flows for:
- locking sites
- moving sites
- removing sites
- re-running planning while preserving context

**Acceptance criteria**
- Manual edits do not destroy provenance
- Re-run flow is usable and understandable
- Output clearly distinguishes manual vs auto-selected sites

---

## [P2][planning][reporting] Compare auto plan vs adjusted plan
**Why**
Users should be able to tell whether manual adjustments improved the result.

**Scope**
- Compare two planning runs
- Highlight metric deltas and site deltas

**Acceptance criteria**
- Users can compare baseline auto plan and edited plan side by side
- Reports summarize meaningful changes

---

# Milestone 4 — Equipment Realism & Catalog Trust

## [P1][engine][ui][api] Add catalog provenance and override visibility
**Why**
Users need to know where effective parameters came from.

**Scope**
Distinguish and expose:
- built-in defaults
- catalog-derived values
- imported antenna patterns
- manual overrides

**Acceptance criteria**
- Output shows the source of important effective values
- Fallbacks and overrides are visible

---

## [P1][ui][engine] Improve antenna pattern validation and preview
**Why**
Imported pattern quality should be obvious before it affects results.

**Scope**
- Validate imported pattern completeness
- Warn when cosine or other fallback logic is used
- Provide a preview before applying the pattern

**Acceptance criteria**
- Import problems are reported clearly
- Preview is available before final run
- Fallbacks are no longer silent

---

## [P2][reporting][ui] Add equipment impact comparison
**Why**
Users should understand how a radio/antenna choice changes the outcome.

**Scope**
Compare baseline vs selected equipment and highlight deltas in:
- EIRP
- radius
- coverage sites
- capacity

**Acceptance criteria**
- Users can see the practical impact of equipment choices
- Reports present deltas clearly

---

# Milestone 5 — Decision Support & Release Readiness

## [P2][reporting][ui][api] Improve scenario comparison workflow
**Why**
Comparison should support decisions, not just dump side-by-side values.

**Scope**
Improve comparisons across:
- band
- antenna config
- planning objective
- coverage/capacity tradeoffs

**Acceptance criteria**
- Comparison results highlight tradeoffs and likely winner scenarios
- Users do not need to manually inspect raw output tables line by line

---

## [P2][reporting] Add executive report mode
**Why**
Non-technical stakeholders need a short summary rather than full engineering detail.

**Scope**
Create a concise report mode with:
- one-page summary
- key assumptions
- risks
- recommended next action

**Acceptance criteria**
- A pre-sales or management audience can use the report directly
- The summary mode does not replace the detailed technical report

---

## [P2][reporting] Add technical appendix report mode
**Why**
Detailed engineering review should remain available when needed.

**Scope**
Create a full-detail appendix mode with:
- assumptions
- model basis
- link budget breakdown
- QoS/capacity details
- planner metrics

**Acceptance criteria**
- RF engineers can review the calculation basis from the report package
- Summary and appendix modes are clearly separated

---

## [P2][release][docs][test] Prepare beta release checklist
**Why**
The project needs an explicit path from alpha toward beta-quality release discipline.

**Scope**
- release notes checklist
- verification checklist
- installer/docs sanity checklist
- known limitations section
- beta readiness criteria

**Acceptance criteria**
- A repeatable release checklist exists in the repo
- The project has explicit criteria for moving beyond alpha

---

# Recommended Execution Order

## Do now
- Sync CLI/docs
- Add golden regression tests
- Expose assumptions/limitations
- Add scenario warnings
- Align output semantics
- Define canonical workflow

## Do next
- Split Quick Sizing vs Planning
- Add curated presets
- Improve results summary
- Productize planning workflow
- Add planner explanations
- Add planning scorecard

## Do later
- Improve manual override compare flow
- Add catalog provenance
- Improve pattern preview/validation
- Add equipment impact comparison
- Improve scenario comparison
- Add executive/technical reporting
- Prepare beta release checklist
