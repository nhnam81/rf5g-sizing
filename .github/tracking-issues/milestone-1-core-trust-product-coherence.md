# Milestone 1 — Core Trust & Product Coherence

> Tracking issue for milestone execution
> Priority: P0
> Source docs: `ROADMAP.md`, `BACKLOG.md`

## Goal

Stabilize the foundation so the product is easier to trust and easier to understand.

## Outcomes to deliver

- Documentation matches the real CLI and product surfaces
- Golden regression scenarios protect key outputs
- Assumptions and limitations appear in reports and/or result metadata
- Warnings exist for approximation-sensitive scenarios
- Output semantics are aligned across CLI, API, and UI

## Child issues to open and track

- [ ] Sync CLI docs with actual commands  
  Template: `Docs / Workflow Alignment`  
  Labels: `priority:P0`, `type:docs`  
  Issue: #____

- [ ] Add golden scenario regression suite  
  Template: `Test / Regression`  
  Labels: `priority:P0`, `type:test`, `type:engine`  
  Issue: #____

- [ ] Expose model assumptions and approximations  
  Template: `Feature / Implementation`  
  Labels: `priority:P0`, `type:reporting`, `type:api`, `type:ui`  
  Issue: #____

- [ ] Add scenario validity warnings  
  Template: `Feature / Implementation`  
  Labels: `priority:P0`, `type:engine`, `type:ui`, `type:api`  
  Issue: #____

- [ ] Align output schema semantics across surfaces  
  Template: `Feature / Implementation`  
  Labels: `priority:P0`, `type:api`, `type:ui`, `type:docs`  
  Issue: #____

## Exit criteria

- [ ] No outdated CLI examples remain in the main docs
- [ ] Regression tests cover baseline scenarios from `examples/`
- [ ] Users can tell which outputs are standards-based vs heuristic/planning-level
- [ ] Milestone outcomes are reflected consistently across CLI, API, UI, and docs

## Notes

- Start with docs sync and regression coverage first.
- Keep `BACKLOG.md` as the planning source of truth; use this issue only for milestone-level tracking.
