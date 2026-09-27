# Pilot printable report — initial implementation

## Scope

Existing platform route `GET /api/projects/{project_id}/pilot-report` renders the
read-only measurement result as printable HTML. The project evaluation page links
to it in a new tab. No new framework, model request, ETL execution, or database
migration is introduced.

The report preserves the fixed 20-case population, separates release readiness
from frozen-scenario evidence, retains revision counts, identifies the checked
time interval and evidence IDs/checksums, and labels unavailable human effort,
baseline, first-pass, cost and improvement measures. It serializes allowlisted
fields only, escapes text, and returns no-store and restrictive CSP headers.

## Verified

- Renderer and API tests: **3 passed** (scope, safe failures, escaping, population,
  nonmutation, unavailable measurements and server headers).
- Frontend production build passed. Existing bundle-size warning remains
  (506.07 kB main JavaScript); it was not suppressed.
- Built API/web images and deployed **only to the isolated UI regression stack**.
- Real browser opened the report from the project page, rendered all 20 synthetic
  cases, retained unavailable labels, and had no horizontal overflow at
  390/768/1440 pixels. Print-media article break rules passed. Full-page output was
  visually inspected; this is not a paginated PDF acceptance test.

## Unresolved acceptance

The complete browser test **failed** on its final CSP assertion: the Windows
HTTP path returned a policy containing `local.adguard.org`, whereas direct API
container HTTP returned the exact configured restrictive policy. This identifies
an environment-path difference; no system security software was disabled or
reconfigured. Keep the failing assertion until an appropriate inspection path
is agreed or separately documented. Do not claim full end-to-end acceptance.

Report work remains partial: model-usage coverage, partial effort coverage,
explicit problem/treatment narrative, formal-cohort read-only acceptance and
paginated visual checks remain. Formal platform containers have not been updated
with this report feature. No accepted ETL writes were replayed.

## Next action

Complete the report's bounded evidence sections using existing measurement data,
then test both server-origin headers and the actual Windows client path explicitly.
Perform read-only formal-cohort reconciliation before deploying the feature.

## Follow-up: coverage and formal data reconciliation

Added model-usage coverage for every existing metric, including missing counts,
partial totals and unavailable complete totals; added self-declared effort interval
coverage, excluded nonhuman sessions and abandoned/open intervals. These remain
distinct from full-case human effort and cost. Per-case text now explains the
scenario's acceptance question and shows source/oracle/precondition checks without
claiming that the expected treatment occurred when evidence is absent.

- Renderer/API plus measurement tests: **16 passed** before the narrative addition.
- Isolated real-browser functional report test: **passed**, including both new
  sections and 390/768/1440 widths.
- Separate Windows exact-CSP test: **failed** with the same AdGuard-path difference.
  The assertion is retained, not weakened or skipped.
- Fresh read-only formal API result rendered in memory: **20 cases, 20 releases,
  19 frozen-scenario matches, one model group**. Usage observation denominators
  reconciled. No private snapshot was committed and no model/ETL was run.
- This reconciliation verifies the renderer against live measurements, not formal
  deployment or printed pagination. Those checks remain open.

Final backend regression after the scenario narrative addition: **1,437 passed,
48 skipped, one warning in 30.05 seconds**. Skipped live/model/host checks are not
counted as acceptance. Isolated test services were stopped, with volumes retained.

The operator explicitly deferred the real human baseline on 2026-09-27. Keep it
unmeasured, along with improvement rate; do not substitute agent operation time.
This is a deferred evaluation dependency, not evidence that P3 value comparison
has been completed. Continue the remaining engineering and acceptance work.
