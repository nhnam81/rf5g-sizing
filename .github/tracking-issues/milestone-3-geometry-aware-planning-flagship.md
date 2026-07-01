# Milestone 3 — Geometry-Aware Planning as Flagship

> Tracking issue for milestone execution
> Priority: P1
> Source docs: `ROADMAP.md`, `BACKLOG.md`

## Goal

Turn geometry-aware planning into the product's most differentiated capability.

## Outcomes to deliver

- Planning workflow is fully documented and first-class
- Selected sites include human-readable explanations
- Planning scorecard exposes coverage, demand, and overload metrics
- Manual override and re-run flows are clearer

## Child issues to open and track

- [ ] Productize planning workflow  
  Template: `Feature / Implementation`  
  Labels: `priority:P1`, `type:planning`, `type:docs`, `type:ui`  
  Issue: #____

- [ ] Expose planner explanations per selected site  
  Template: `Feature / Implementation`  
  Labels: `priority:P1`, `type:planning`, `type:api`, `type:ui`, `type:reporting`  
  Issue: #____

- [ ] Add planning scorecard  
  Template: `Feature / Implementation`  
  Labels: `priority:P1`, `type:planning`, `type:reporting`  
  Issue: #____

- [ ] Support manual override and re-run flow  
  Template: `Feature / Implementation`  
  Labels: `priority:P1`, `type:planning`, `type:ui`  
  Issue: #____

- [ ] Compare auto plan vs adjusted plan  
  Template: `Feature / Implementation`  
  Labels: `priority:P2`, `type:planning`, `type:reporting`  
  Issue: #____

## Exit criteria

- [ ] Planner outputs are explainable enough for engineering review
- [ ] Users can compare auto-generated and manually adjusted plans
- [ ] Planning workflow is documented end-to-end

## Notes

- Keep planner outputs auditable; do not optimize for hidden automation over explainability.
- Treat geometry-aware planning as an advanced workflow built on top of stable core sizing behavior.
