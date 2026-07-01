# Beta Release Checklist

> This checklist defines the criteria for moving rf5g-sizing from alpha to beta quality.

## Pre-Release Verification

### 1. Code Quality

- [ ] All tests pass: `pytest rf5g/tests/ -v`
- [ ] No critical or high severity warnings
- [ ] Code coverage ≥ 80% for core modules
- [ ] No hardcoded secrets or credentials
- [ ] Dependencies are pinned with versions

### 2. Documentation

- [ ] README.md is accurate and up to date
- [ ] USER_GUIDE.md matches current CLI/UI
- [ ] INSTALL_GUIDE.md matches current version
- [ ] WORKFLOW.md reflects current workflow
- [ ] PLANNING_GUIDE.md reflects current planning features
- [ ] CHANGELOG.md is updated with this version's changes

### 3. Tests

- [ ] Golden regression tests pass (`test_golden_regression.py`)
- [ ] Output schema tests pass (`test_output_schema.py`)
- [ ] Warning tests pass (`test_warnings.py`)
- [ ] Integration tests pass (`test_integration.py`)
- [ ] Phase tests pass (`test_phase*.py`)

### 4. CLI & API

- [ ] All CLI commands work with `--help`
- [ ] API endpoints return expected schemas
- [ ] Error messages are clear and actionable
- [ ] Warnings appear for edge cases

### 5. Reports

- [ ] HTML report generates without errors
- [ ] Markdown report generates without errors
- [ ] Executive report generates without errors
- [ ] Technical appendix generates without errors
- [ ] Assumptions section is present in reports
- [ ] Equipment provenance is visible in reports

### 6. Examples & Presets

- [ ] All example configs load without errors
- [ ] Preset library covers common scenarios (5+ presets)
- [ ] Examples run successfully from CLI

### 7. Installation

- [ ] Package installs from source (`pip install -e .`)
- [ ] Package installs from wheel
- [ ] CLI is accessible after installation
- [ ] Streamlit UI launches without errors
- [ ] No import errors in fresh environment

---

## Functional Requirements

### 1. Quick Sizing Workflow

- [ ] User can complete sizing from preset in < 5 minutes
- [ ] Executive summary is clear and actionable
- [ ] Warnings appear for problematic scenarios
- [ ] Results export to JSON/HTML/Markdown

### 2. Planning Workflow

- [ ] User can define service area polygon
- [ ] Exclusion zones work correctly
- [ ] Alignments work correctly
- [ ] Planning scorecard displays correctly
- [ ] Site explanations are visible

### 3. Equipment Catalog

- [ ] Radio catalog entries resolve correctly
- [ ] Antenna catalog entries resolve correctly
- [ ] Catalog overrides are visible in output
- [ ] Pattern import works for supported formats

---

## Known Limitations

The following limitations should be documented in the release notes:

1. **Propagation Model**: Statistical models (UMa/UMi/RMa/InH) based on 3GPP TR 38.901. Does not account for specific terrain or clutter data.

2. **Throughput Approximation**: TDD throughput approximated from peak using TDD ratio. FDD throughput approximated without HARQ modeling.

3. **Capacity Model**: Per-cell throughput estimated from spectral efficiency at cell edge. Assumes uniform user distribution.

4. **FR2/mmWave**: Not supported in current version.

5. **3D Ray-tracing**: Not supported. Planning uses simplified coverage model.

6. **Pattern Import**: Custom antenna patterns require specific formats (.ant, .csv, .json, .msi, .txt). Incomplete patterns may use fallback cosine model.

---

## Release Notes Template

```markdown
# rf5g-sizing vX.Y.Z (YYYY-MM-DD)

## New Features

- [Feature 1]
- [Feature 2]

## Improvements

- [Improvement 1]
- [Improvement 2]

## Bug Fixes

- [Fix 1]
- [Fix 2]

## Breaking Changes

- [Breaking change 1]

## Known Issues

- [Known issue 1]
```

---

## Release Process

### Step 1: Pre-Release

```bash
# Run all tests
pytest rf5g/tests/ -v

# Check coverage
pytest rf5g/tests/ --cov=rf5g --cov-report=term-missing

# Lint check
ruff check rf5g/
```

### Step 2: Version Bump

```bash
# Update version in pyproject.toml
# Update version in rf5g/__init__.py
# Update version in INSTALL_GUIDE.md
```

### Step 3: Build

```bash
# Build wheel
pip install build
python -m build

# Test wheel install
pip install dist/rf5g_sizing-*.whl
```

### Step 4: Tag and Release

```bash
# Create git tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# Push tag
git push origin vX.Y.Z

# Create GitHub release
gh release create vX.Y.Z --generate-notes
```

### Step 5: Post-Release

- [ ] Create GitHub release with release notes
- [ ] Update documentation website (if applicable)
- [ ] Announce release on relevant channels
- [ ] Close milestone tracking issue

---

## Rollback Plan

If critical issues are found after release:

1. Create hotfix branch from release tag
2. Fix issue and update version (X.Y.Z+1)
3. Run tests and verification
4. Tag and release hotfix
5. Update CHANGELOG.md

---

## Success Criteria

Beta release is ready when:

- [ ] All pre-release verification items pass
- [ ] All functional requirements are met
- [ ] Known limitations are documented
- [ ] Release notes are ready
- [ ] Installation tested on clean environment
- [ ] At least 3 users have tested the release candidate