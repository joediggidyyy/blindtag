# BlindTag Packaging and Publication Checklist

**Status:** Complete — BlindTag `1.0.0` packaging/publication lane closed  
**Primary planning reference:** `projects/blindtag/docs/REVIEW_AND_MATURITY_PLAN.md` — Section 11  
**Current release posture:** Packaging/publication completed with retained artifact/build/install/publication evidence across local audit, installer sandbox validation, TestPyPI staging, and production PyPI publication.

---

## Purpose

Use this checklist to guide BlindTag from package remediation through staged publication and the Windows widget installer release lane.

## Closeout receipt (2026-06-01 UTC)

- Local package audit receipt: `projects/blindtag/report_tmp/pass_s_package_audit.json`
- Installer sandbox receipt: `projects/blindtag/report_tmp/windows_installer_sandbox_validation/windows_installer_sandbox_validation.{json,md}`
- TestPyPI project page: `https://test.pypi.org/project/blindtag/1.0.0/`
- Production PyPI project page: `https://pypi.org/project/blindtag/1.0.0/`
- Published wheel: `blindtag-1.0.0-py3-none-any.whl` — `SHA256 2f7531a02146f7811dc6a56c6c09a0b7a9b435f40619a711b26a62cc07a5f25e`
- Published sdist: `blindtag-1.0.0.tar.gz` — `SHA256 a56179cefa9b41214531eae7c24a32782b1935f46199e5dadf6a9bf6238b6826`
- Windows installer: `BlindTagInstaller.exe` — `SHA256 59a671828e1e63f04dcb5cd7c198f97947763e7f4b676a460cf58bda0bfa8946`
- Fresh staged-install validation root: `projects/blindtag/report_tmp/testpypi_validation/.venv`
- Fresh production-install validation root: `projects/blindtag/report_tmp/pypi_validation/.venv`
- Fresh-install sanity check result from staged + production artifacts: `TEST123`

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

- [x] Do not publish anything while Pass S package blockers remain unresolved.
- [x] Treat built artifacts as the truth surface; do not infer package readiness from source files alone.
- [x] Keep publication evidence names-only and publication-safe.
- [x] Use a staged release sequence: build -> inspect -> sandbox install -> TestPyPI -> install/retest -> production publish.
- [x] Treat the Windows `.exe` installer as a first-class BlindTag release surface, not a nice-to-have extra.

---

## Phase 1 — Clear the known package blockers

- [x] Restore required asset inclusion in the wheel.
- [x] Restore required asset inclusion in the sdist.
- [x] Add/lock an explicit package-inclusion contract for non-Python assets.
- [x] Fix malformed packaged README/long-description rendering.
- [x] Resolve any packaging-hygiene warnings that materially affect publication trust.
- [x] Rebuild artifacts after each relevant packaging fix.

### Exit criteria

- [x] Built wheel includes the runtime/documentation assets BlindTag actually depends on.
- [x] Built sdist includes the same required asset tree.
- [x] Packaged metadata renders cleanly and truthfully.

---

## Phase 2 — Rebuild and inspect release artifacts

- [x] Clean prior build outputs.
- [x] Build `sdist` and `wheel`.
- [x] Verify both artifacts exist and are current.
- [x] Inspect wheel contents.
- [x] Inspect sdist contents.
- [x] Verify entry points match the documented product surface.
- [x] Verify local-only/generated roots remain excluded (`.env`, `.blindtag`, `.calamum`, `report_tmp`, signing material, other machine-local overlays).
- [x] Verify metadata fields, version, README rendering, and dependency declarations.

### Exit criteria

- [x] Artifact contents match the intended shipped product.
- [x] No required runtime asset is missing.
- [x] No local-only artifact leaked into the build.

---

## Phase 3 — Windows installer contract

### Installer experience

- [x] Provide **Default (Recommended)** as the primary install choice.
- [x] Aim Default at recreational/everyday BlindTag use.
- [x] Keep the Default path calm and low-friction.
- [x] Keep mainstream user burden near `click OK`; prerequisite/runtime setup must remain installer-owned.
- [x] Provide **Advanced** as a secondary/custom path.
- [x] Use warning language on Advanced indicating it is for users who specifically need custom setup behavior.

### Required installer options

- [x] `Create shortcut`
- [x] `Enable quick launch`
- [x] `Display README.md after install`

### Installer truthfulness

- [x] Default mode installs the standard BlindTag package surface.
- [x] Default mode installs the terminal-free widget launch surface.
- [x] Default mode includes the runtime asset set required by widget behavior and packaged docs.
- [x] The installer validates the bundled package payload hashes automatically and fails closed on any integrity mismatch.
- [x] Default mode installs Python automatically when missing and satisfies package/runtime dependencies without manual terminal work.
- [x] The installer auto-elevates only when Windows prerequisite setup genuinely requires elevated execution.
- [x] Downloaded Python bootstrap installers are trust-checked before execution.
- [x] Advanced mode exposes custom install choices without making Default ambiguous.
- [x] Installer copy makes the ordinary post-install launch path obvious.

### Exit criteria

- [x] The `.exe` installer exists.
- [x] The installer surface matches the locked Default-vs-Advanced plan.
- [x] The installer options are explicit and testable.

---

## Phase 4 — Sandbox install validation

- [x] Install the built package artifacts into a sandbox/simulated environment.
- [x] Install the `.exe` installer into a sandbox/simulated environment.
- [x] Validate actual installed-file content, not just install completion.
- [x] Validate widget launch from the installed surface.
- [x] Validate shortcut behavior.
- [x] Validate quick-launch behavior.
- [x] Validate `Display README.md after install` behavior.
- [x] Validate the missing-Python bootstrap lane or a faithful simulation of that lane.
- [x] Validate that elevation prompts appear only when prerequisite setup genuinely needs them.
- [x] Validate package-hash mismatch fail-closed behavior in the sandbox simulation/report packet.
- [x] Validate output content and handoff-completion posture, not just process exit codes.
- [x] Record retained evidence for the sandbox results.
- [x] Emit names-only sandbox evidence artifacts (JSON + Markdown) under `report_tmp/windows_installer_sandbox_validation/` so the scenario simulation and handoff packet are preserved.

### Exit criteria

- [x] Installed behavior matches installer claims.
- [x] Installed widget path is truthful and usable.
- [x] Sandbox evidence shows real content/handoff validation.
- [x] The sandbox evidence packet includes scenario outcomes, output traces, and a handoff summary.

---

## Phase 5 — Publication staging lane

- [x] Run package validation checks against the final built artifacts.
- [x] Stage the package to TestPyPI.
- [x] Verify the TestPyPI project page/version/artifact set.
- [x] Install BlindTag from TestPyPI into a fresh environment.
- [x] Re-run release sanity checks from the staged publication artifact.
- [x] Confirm the staged artifact behaves the same way as the locally audited build.

### Exit criteria

- [x] TestPyPI upload succeeded.
- [x] TestPyPI installation succeeded.
- [x] Fresh-install validation from TestPyPI passed.

---

## Phase 6 — Production publication lane

- [x] Confirm TestPyPI validation is complete.
- [x] Confirm sandbox installer validation is complete.
- [x] Confirm package blockers remain closed in the exact artifacts being published.
- [x] Upload to production PyPI.
- [x] Verify the production project page/version/artifact set.
- [x] Record the final publish verdict and retained evidence references.

### Exit criteria

- [x] Production publication succeeded.
- [x] Published artifacts match the validated staged artifacts.

---

## Phase 7 — Post-publish recording and support surfaces

- [x] Record artifact names, versions, and checksums.
- [x] Record installer artifact identity/version.
- [x] Record the TestPyPI validation receipt.
- [x] Record the production publish receipt.
- [x] Confirm README/install guidance matches the shipped reality.
- [x] Confirm release notes/publication notes do not overstate any guarantee not actually verified.

---

## Final go/no-go gate

Do not mark this release lane complete until every statement below is true.

- [x] Pass S findings have been remediated and re-verified from built artifacts.
- [x] Wheel and sdist are both truthful and complete.
- [x] The Windows installer is built and validated in a sandbox.
- [x] Default and Advanced installer modes behave as documented.
- [x] The installer exposes `Create shortcut`, `Enable quick launch`, and `Display README.md after install`.
- [x] The installer owns prerequisite/runtime setup for ordinary Windows users, including Python bootstrap when needed.
- [x] TestPyPI validation passed before production upload.
- [x] Final release judgment is backed by retained evidence, not informal confidence.
