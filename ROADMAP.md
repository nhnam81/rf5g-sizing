# rf5g-sizing Roadmap

> Last updated: 2026-06-30
> Current package version: 1.4.1 (`pyproject.toml`)
> Current maturity: Alpha

## Purpose

This roadmap turns the current project into a trackable development plan that can be resumed in later sessions.

The current product already spans multiple surfaces:
- Core RF sizing engine
- CLI commands (`size`, `plan`, `map`, `report`, `charts`, `sites`)
- FastAPI endpoints
- Streamlit basic UI
- Streamlit guided UI
- Geometry-aware placement planning

The next stage should prioritize **trust, coherence, and planning workflow quality** before large scope expansion.

## Product Direction

Position `rf5g-sizing` as an **open-source 5G RF pre-planning tool** for:
- coverage sizing
- QoS/capacity sanity checks
- geometry-aware site planning
- report/map export for engineering and pre-sales workflows

Non-goal for the near term:
- replacing full commercial radio-planning suites
- FR2/mmWave expansion
- 3D/ray-tracing workflows
- large speculative architecture refactors

## Strategic Priorities

1. **Increase trust in the core engine**
   - Make assumptions explicit
   - Strengthen regression coverage
   - Reduce ambiguity around approximations

2. **Make the product coherent across surfaces**
   - Align CLI, API, guided UI, and docs
   - Define one canonical workflow
   - Reduce user confusion between sizing and planning flows

3. **Promote geometry-aware planning to a flagship capability**
   - Make planning explainable, auditable, and easier to use
   - Improve site-selection transparency and iteration loops

4. **Improve equipment/catalog realism**
   - Make antenna/radio provenance clearer
   - Expose fallbacks and overrides explicitly

5. **Upgrade decision support and release readiness**
   - Better comparisons, better reports, better release discipline

## Milestones

---

## Milestone 1 — Core Trust & Product Coherence
**Priority:** P0  
**Target duration:** 2-3 weeks

### Goal
Stabilize the foundation so the product is easier to trust and easier to understand.

### Outcomes
- Documentation matches the real CLI and product surfaces
- Golden regression scenarios protect key outputs
- Assumptions and limitations appear in reports and/or result metadata
- Warnings exist for approximation-sensitive scenarios
- Output semantics are aligned across CLI, API, and UI

### Success criteria
- No outdated CLI examples remain in the main docs
- Regression tests cover baseline scenarios from `examples/`
- Users can tell which outputs are standards-based vs heuristic/planning-level

---

## Milestone 2 — Workflow Simplification & UX
**Priority:** P0  
**Target duration:** 2 weeks

### Goal
Define one canonical user journey and reduce unnecessary complexity.

### Outcomes
- Clear split between **Quick Sizing** and **Planning** workflows
- A curated preset library for common scenarios
- Results pages/reports summarize bottlenecks and next actions
- The official docs and UI follow the same step-by-step flow

### Success criteria
- A new user can go from preset to usable result without reading code
- The guided UI no longer mixes simple sizing and advanced planning prematurely

---

## Milestone 3 — Geometry-Aware Planning as Flagship
**Priority:** P1  
**Target duration:** 3-4 weeks

### Goal
Turn geometry-aware planning into the product's most differentiated capability.

### Outcomes
- Planning workflow is fully documented and first-class
- Selected sites include human-readable explanations
- Planning scorecard exposes coverage, demand, and overload metrics
- Manual override and re-run flows are clearer

### Success criteria
- Planner outputs are explainable enough for engineering review
- Users can compare auto-generated and manually adjusted plans

---

## Milestone 4 — Equipment Realism & Catalog Trust
**Priority:** P1  
**Target duration:** 2-3 weeks

### Goal
Make equipment-driven planning more trustworthy and easier to interpret.

### Outcomes
- Users can see where effective parameters came from
- Imported antenna patterns are validated and previewable
- Fallbacks are visible instead of silent
- Equipment comparisons show impact on coverage/capacity

### Success criteria
- Output provenance is clear for built-in defaults, catalog values, imports, and manual overrides

---

## Milestone 5 — Decision Support & Release Readiness
**Priority:** P2  
**Target duration:** 2-3 weeks

### Goal
Turn outputs into decision-ready artifacts and prepare for a beta-quality release process.

### Outcomes
- Scenario comparisons are easier to interpret
- Executive and technical report modes are separated
- Beta release checklist exists
- Known limitations and verification expectations are explicit

### Success criteria
- A planner or pre-sales user can compare options without reading raw model output line by line
- The repo has a repeatable release checklist before moving beyond alpha

## Suggested Sequence

### Sprint 1
- Sync docs with actual CLI/API/UI behavior
- Add golden scenario regression coverage
- Expose assumptions and limitations in outputs/reports

### Sprint 2
- Add scenario validity warnings
- Align output semantics across surfaces
- Define canonical workflow

### Sprint 3
- Split Quick Sizing vs Planning
- Add curated presets
- Improve results summary

### Sprint 4-5
- Productize planning workflow
- Expose planner explanations
- Add planning scorecard

### Sprint 6
- Improve manual override/re-run flow
- Add catalog provenance
- Improve antenna pattern validation/preview

### Sprint 7+
- Add equipment impact comparison
- Improve scenario comparison
- Add executive/technical report modes
- Prepare beta release checklist

## What Not to Prioritize Yet

These items are intentionally deferred unless priorities change:
- FR2/mmWave support
- 3D visualization
- advanced optimization/ML planner replacement
- large plugin architecture refactors
- mobile-first experiences

## Tracking Notes

- Use `BACKLOG.md` as the issue-level execution list.
- Update this roadmap only when milestone scope or sequencing changes.
- Keep implementation details, blockers, and completed work in issues/PRs or a future implementation log if needed.
