---
phase: 01
slug: distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-17
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Phase 01 delivers a portable Windows distribution (unsigned PyInstaller zip), a
splash screen, an update checker that hits the GitHub Releases API, and local
user-data directory handling under `%LOCALAPPDATA%\BluOpticalSim`. The security
surface is narrow: one outbound HTTPS call, JSON parsing of the response, local
filesystem reads/writes, and the distribution trust model of an unsigned binary.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| App ↔ GitHub API | HTTPS GET to `api.github.com/repos/Ozgur-al/blu-optical-simulation/releases/latest` on startup | Outbound: `User-Agent: BluOpticalSim/<version>`. Inbound: untrusted JSON (parsed for `tag_name`, `html_url`). |
| App ↔ Local FS | User data dir at `%LOCALAPPDATA%\BluOpticalSim\` (or `~/.bluopticalsim`) | Future settings/preferences files (directory created, not yet populated in phase 01). |
| User ↔ Distribution | Unsigned zip downloaded from GitHub Releases, extracted to user-chosen folder | Executable + `_internal/` bundle + sample `.blu` files + README. |
| OS ↔ Executable | SmartScreen reputation gate on first run | User decision to "Run anyway" documented in README. |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-01-01 | Tampering | `update_checker.check_for_update` | mitigate | HTTPS-only URL; `urllib.request` validates TLS certificates by default on Python 3.12+ Windows; no fallback to HTTP. | closed |
| T-01-02 | Denial of Service | `update_checker.check_for_update_async` | mitigate | 5-second `timeout` passed to `urlopen`; runs on daemon thread; result is only surfaced via callback, never blocks splash/main window. | closed |
| T-01-03 | Information Disclosure | `update_checker` User-Agent header | accept | Outbound request leaks current app version and GitHub-default client IP/TLS fingerprint. Required for version comparison; no PII. Documented below. | closed |
| T-01-04 | Tampering / DoS | `update_checker._compare_versions` and JSON parse | mitigate | Broad `except Exception` around full request + parse returns `UpdateInfo(available=False, error=...)`; `_compare_versions` catches `ValueError`/`AttributeError` on malformed tags; app never raises from update path. | closed |
| T-01-05 | Spoofing | Distribution channel (unsigned zip) | accept | Binary ships unsigned per phase decision. Mitigated by (a) Windows SmartScreen reputation warning on first run, (b) README instructions for bypass that inform the user this is expected, (c) GitHub Releases as authoritative distribution source over HTTPS. Documented below. | closed |
| T-01-06 | Tampering | Local user-data dir write | mitigate | `config.user_data_dir()` resolves `%LOCALAPPDATA%` from env or falls back to `Path.home() / "AppData/Local/BluOpticalSim"`; no user-controlled path input. `ensure_user_data_dir()` uses `Path.mkdir(parents=True, exist_ok=True)` — no traversal surface. | closed |
| T-01-07 | Information Disclosure | Error string propagated from `update_checker` | mitigate | `UpdateInfo.error` carries `str(exc)` which may include local network details. Only displayed in log dock / status text, never sent outbound. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-01-A | T-01-03 | Update check necessarily discloses current version to GitHub. No authentication, no account data, no user identifiers beyond standard HTTPS client metadata. Disabling the check would regress the phase goal. | Project owner (phase spec) | 2026-04-17 |
| R-01-B | T-01-05 | Code signing certificates are out of scope for this distribution; phase scope is "run on admin-locked PCs without admin rights" which does not require signing. Compensating controls: HTTPS delivery, SmartScreen warning, README bypass instructions directing users to verify the source. | Project owner (phase spec, line 37 of 01-CONTEXT.md: "Ship unsigned — accept SmartScreen warning") | 2026-04-17 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-17 | 7 | 7 | 0 | /gsd-secure-phase (Claude) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-17
