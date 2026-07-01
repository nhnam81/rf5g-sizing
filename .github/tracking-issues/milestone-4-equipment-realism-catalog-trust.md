# Milestone 4 — Equipment Realism & Catalog Trust

> Tracking issue for milestone execution
> Priority: P1
> Source docs: `ROADMAP.md`, `BACKLOG.md`

## Goal

Make equipment-driven planning more trustworthy and easier to interpret.

## Outcomes to deliver

- Users can see where effective parameters came from
- Imported antenna patterns are validated and previewable
- Fallbacks are visible instead of silent
- Equipment comparisons show impact on coverage/capacity

## Child issues to open and track

- [ ] Add catalog provenance and override visibility  
  Template: `Feature / Implementation`  
  Labels: `priority:P1`, `type:engine`, `type:ui`, `type:api`  
  Issue: #____

- [ ] Improve antenna pattern validation and preview  
  Template: `Feature / Implementation`  
  Labels: `priority:P1`, `type:ui`, `type:engine`  
  Issue: #____

- [ ] Add equipment impact comparison  
  Template: `Feature / Implementation`  
  Labels: `priority:P2`, `type:reporting`, `type:ui`  
  Issue: #____

## Exit criteria

- [ ] Output provenance is clear for built-in defaults, catalog values, imports, and manual overrides
- [ ] Import problems and fallback behaviors are visible to the user
- [ ] Equipment-driven deltas can be interpreted without reading raw internals

## Notes

- Favor provenance and transparency over extra catalog breadth.
- Keep fallback behavior explicit anywhere imported data is incomplete.
