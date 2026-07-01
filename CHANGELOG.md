# Changelog

All notable changes to rf5g-sizing will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-07-01

### Added

#### Milestone 1: Core Trust & Product Coherence
- **CLI docs sync**: All CLI commands now have accurate `--help` documentation matching actual implementation
- **Golden regression tests**: 24 baseline scenario tests to prevent output drift (`test_golden_regression.py`)
- **Assumptions section**: Reports now include explicit model assumptions and limitations
- **Validity warnings**: Automatic detection and display of scenario validity issues (extreme values, inconsistencies)
- **Output schema tests**: 19 tests ensuring output schema contract across all surfaces

#### Milestone 2: Workflow Simplification & UX
- **Workflow documentation**: New `WORKFLOW.md` with canonical usage patterns
- **Preset library**: Example configurations for common scenarios (indoor hotspot, capacity hotspot)
- **Executive summary**: One-page summary for non-technical stakeholders
- **Rewritten user guide**: Simplified `USER_GUIDE.md` with clear getting-started path

#### Milestone 3: Geometry-Aware Planning as Flagship
- **Planning guide**: New `PLANNING_GUIDE.md` with complete geometry-aware workflow
- **Site explanations**: Output includes explanations for site placement decisions
- **Planning scorecard**: Summary metrics for planning quality assessment
- **Explanations field**: Output schema now supports `explanations` for transparency

#### Milestone 4: Equipment Realism & Catalog Trust
- **Equipment provenance**: CLI displays where equipment parameters come from (catalog vs override)
- **Antenna pattern validation**: Improved validation with warnings for incomplete patterns
- **Pattern preview**: Better handling of imported antenna patterns

#### Milestone 5: Decision Support & Release Readiness
- **Executive report mode**: CLI `rf5g report --format executive` for one-page business summary
- **Technical appendix mode**: CLI `rf5g report --format technical` for full engineering details
- **Scenario comparison highlights**: `/compare` API endpoint now includes decision support highlights
- **Release checklist**: `RELEASE_CHECKLIST.md` with pre-release verification steps

### Changed
- Improved output schema consistency across CLI, API, and UI surfaces
- Enhanced warning system with actionable messages
- Better documentation structure with clear workflow paths

### Fixed
- CLI documentation mismatches with actual commands
- Missing assumptions transparency in reports
- Inconsistent output schema across surfaces

## [1.4.1] - Previous Release

### Added
- Basic site estimation and sizing
- Propagation models (UMa, UMi, RMa, InH)
- Link budget calculations
- SINR/CQI mapping
- Capacity estimation
- QoS verification
- Coverage map generation
- Interactive Streamlit UI

---

## Version History Summary

| Version | Date | Focus |
|---------|------|-------|
| 1.5.0 | 2026-07-01 | Milestones 1-5: Trust, UX, Planning, Equipment, Decision Support |
| 1.4.1 | 2026-06 | Core sizing functionality |