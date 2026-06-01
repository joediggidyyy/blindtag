# BlindTag Packaging and Publication Checklist

**Status:** Active planning checklist  
**Primary planning reference:** `projects/blindtag/docs/REVIEW_AND_MATURITY_PLAN.md` — Section 11  
**Current release posture:** Packaging/publication remains blocked until the Pass S package-surface findings are remediated and re-verified from built artifacts.

---

## Purpose

Use this checklist to guide BlindTag from package remediation through staged publication and the Windows widget installer release lane.

This checklist is grounded in:

- `projects/blindtag/docs/REVIEW_AND_MATURITY_PLAN.md`
- `projects/blindtag/docs/WIDGET_SCHEMA.md`
- `projects/blindtag/docs/CLI_IMPLEMENTATION_CHECKLIST.md`
- `docs/installation/SHIPPED_CODESENTINEL_OFFLINE_INSTALL_PACKAGE_20260104.md`
- `docs/installation/INSTALLATION.md`
- `docs/installation/INSTALL_PROFILES.md`
- `docs/architecture/general/PACKAGING_PIPELINE_DIRECTIVE.md`
- `projects/unc-data-science-notes/temp/seam_offline_bundle_1.1.5-py3-none-any.whl/howtos/docs/guides/QUICK_PUBLISH_REFERENCE.md`

---

## Standing rules

- [ ] Do not publish anything while Pass S package blockers remain unresolved.
- [ ] Treat built artifacts as the truth surface; do not infer package readiness from source files alone.
- [ ] Keep publication evidence names-only and publication-safe.
- [ ] Use a staged release sequence: build -> inspect -> sandbox install -> TestPyPI -> install/retest -> production publish.
- [ ] Treat the Windows `.exe` installer as a first-class BlindTag release surface, not a nice-to-have extra.

---

## Phase 1 — Clear the known package blockers

- [ ] Restore required asset inclusion in the wheel.
- [ ] Restore required asset inclusion in the sdist.
- [ ] Add/lock an explicit package-inclusion contract for non-Python assets.
- [ ] Fix malformed packaged README/long-description rendering.
- [ ] Resolve any packaging-hygiene warnings that materially affect publication trust.
- [ ] Rebuild artifacts after each relevant packaging fix.

### Exit criteria

- [ ] Built wheel includes the runtime/documentation assets BlindTag actually depends on.
- [ ] Built sdist includes the same required asset tree.
- [ ] Packaged metadata renders cleanly and truthfully.

---

## Phase 2 — Rebuild and inspect release artifacts

- [ ] Clean prior build outputs.
- [ ] Build `sdist` and `wheel`.
- [ ] Verify both artifacts exist and are current.
- [ ] Inspect wheel contents.
- [ ] Inspect sdist contents.
- [ ] Verify entry points match the documented product surface.
- [ ] Verify local-only/generated roots remain excluded (`.env`, `.blindtag`, `.calamum`, `report_tmp`, signing material, other machine-local overlays).
- [ ] Verify metadata fields, version, README rendering, and dependency declarations.

### Exit criteria

- [ ] Artifact contents match the intended shipped product.
- [ ] No required runtime asset is missing.
- [ ] No local-only artifact leaked into the build.

---

## Phase 3 — Windows installer contract

### Installer experience

- [ ] Provide **Default (Recommended)** as the primary install choice.
- [ ] Aim Default at recreational/everyday BlindTag use.
- [ ] Keep the Default path calm and low-friction.
- [ ] Provide **Advanced** as a secondary/custom path.
- [ ] Use warning language on Advanced indicating it is for users who specifically need custom setup behavior.

### Required installer options

- [ ] `Create shortcut`
- [ ] `Enable quick launch`
- [ ] `Display README.md after install`

### Installer truthfulness

- [ ] Default mode installs the standard BlindTag package surface.
- [ ] Default mode installs the terminal-free widget launch surface.
- [ ] Default mode includes the runtime asset set required by widget behavior and packaged docs.
- [ ] Advanced mode exposes custom install choices without making Default ambiguous.
- [ ] Installer copy makes the ordinary post-install launch path obvious.

### Exit criteria

- [ ] The `.exe` installer exists.
- [ ] The installer surface matches the locked Default-vs-Advanced plan.
- [ ] The installer options are explicit and testable.

---

## Phase 4 — Sandbox install validation

- [ ] Install the built package artifacts into a sandbox/simulated environment.
- [ ] Install the `.exe` installer into a sandbox/simulated environment.
- [ ] Validate actual installed-file content, not just install completion.
- [ ] Validate widget launch from the installed surface.
- [ ] Validate shortcut behavior.
- [ ] Validate quick-launch behavior.
- [ ] Validate `Display README.md after install` behavior.
- [ ] Validate output content and handoff-completion posture, not just process exit codes.
- [ ] Record retained evidence for the sandbox results.

### Exit criteria

- [ ] Installed behavior matches installer claims.
- [ ] Installed widget path is truthful and usable.
- [ ] Sandbox evidence shows real content/handoff validation.

---

## Phase 5 — Publication staging lane

- [ ] Run package validation checks against the final built artifacts.
- [ ] Stage the package to TestPyPI.
- [ ] Verify the TestPyPI project page/version/artifact set.
- [ ] Install BlindTag from TestPyPI into a fresh environment.
- [ ] Re-run release sanity checks from the staged publication artifact.
- [ ] Confirm the staged artifact behaves the same way as the locally audited build.

### Exit criteria

- [ ] TestPyPI upload succeeded.
- [ ] TestPyPI installation succeeded.
- [ ] Fresh-install validation from TestPyPI passed.

---

## Phase 6 — Production publication lane

- [ ] Confirm TestPyPI validation is complete.
- [ ] Confirm sandbox installer validation is complete.
- [ ] Confirm package blockers remain closed in the exact artifacts being published.
- [ ] Upload to production PyPI.
- [ ] Verify the production project page/version/artifact set.
- [ ] Record the final publish verdict and retained evidence references.

### Exit criteria

- [ ] Production publication succeeded.
- [ ] Published artifacts match the validated staged artifacts.

---

## Phase 7 — Post-publish recording and support surfaces

- [ ] Record artifact names, versions, and checksums.
- [ ] Record installer artifact identity/version.
- [ ] Record the TestPyPI validation receipt.
- [ ] Record the production publish receipt.
- [ ] Confirm README/install guidance matches the shipped reality.
- [ ] Confirm release notes/publication notes do not overstate any guarantee not actually verified.

---

## Final go/no-go gate

Do not mark this release lane complete until every statement below is true.

- [ ] Pass S findings have been remediated and re-verified from built artifacts.
- [ ] Wheel and sdist are both truthful and complete.
- [ ] The Windows installer is built and validated in a sandbox.
- [ ] Default and Advanced installer modes behave as documented.
- [ ] The installer exposes `Create shortcut`, `Enable quick launch`, and `Display README.md after install`.
- [ ] TestPyPI validation passed before production upload.
- [ ] Final release judgment is backed by retained evidence, not informal confidence.
