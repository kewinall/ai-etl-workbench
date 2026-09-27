# Source-order requirement: implementation checkpoint

## Confirmed requirement

The operator explicitly requires preservation of source order for the full
projection recovery scenario. Add a source-position column and ordered-result
validation. Do not reinterpret the requirement as unordered projection.

The existing frozen cohort definition and prior NEEDS_REVIEW evidence remain
unchanged. A separately versioned extension is necessary; passing its ordered
test must not retroactively rewrite the original frozen definition.

## Implemented and checked

`compare_ordered_result` is a pure, bounded comparison primitive. It requires a
non-null INTEGER ordinal with contiguous one-based positions in the pinned
full-projection expectation. It compares the received sequence without sorting
away defects. It retains strict value/schema/content limits and never grants
QA or release approval. Existing EXACT_MULTISET behavior is unchanged.

Local test run: `test_ordered_result.py` plus `test_expected_result.py`,
27 passed. Includes shuffled input IDs, duplicate IDs, reversed result order,
missing/duplicate rows, invalid ordinal contracts, and empty results.

## Not yet accepted

This primitive is not yet connected to execution, persisted comparison evidence,
or release eligibility. No new Hop execution or model invocation was performed.
It is not evidence of end-to-end order preservation.

Next implementation steps:

1. Version an explicit full-projection source-order contract without changing
   historical specification checksums.
2. Assign one-based logical CSV data-row positions at ingestion, including
   quoted multiline-record tests; never derive order from record_id values.
3. Preserve the ordinal through deterministic Hop output and target DDL.
4. Pin an explicit ORDER BY ordinal query before execution. Database physical
   insertion order alone is not an ordering guarantee.
5. Version oracle/comparison storage, QA context, SDM and portable delivery to
   carry the ordered contract; reject unsupported combinations fail-closed.
6. Perform real new-revision Hop/Vertica and portable replay acceptance; preserve
   prior failure history and the frozen cohort denominator.

The knowledge-workspace checkout is unavailable locally. This checkpoint has
not been persisted to knowledge-workspace; its existing task must be updated
with this deidentified artifact reference when workspace access is restored.

## Compiler checkpoint

Added `EtlSpecificationV3` for single-CSV full-row projection with an explicit
`source_order_v1` input contract. V1/V2 serialized contracts remain unchanged.
The generated ordinal must have a separate BIGINT naming entry and be retained
in the output. Missing/mismatching confirmed order, omitted ordinal, filtering,
aggregation, invalid type, and arbitrary identifier text fail validation.

The compiler emits CSVInput `rownum_field`, one transform copy, no parallel
reading, a non-deduplicating ordinal SortRows, and the ordinal target column.
The pinned read plan explicitly uses ORDER BY ordinal ASC and advertises
EXACT_SOURCE_SEQUENCE. The public API/model schema still excludes V3 pending
oracle, storage, QA, portable-release and UI integration.

Evidence:

- Focused compiler/intent/regression tests: 73 passed.
- Isolated PostgreSQL backend suite: 1,327 passed, 46 skipped, one warning,
  27.20 seconds, exit 0. Optional native/model tests are not proven by this run.
- Separate opt-in native Hop probe: two passed in 9.75 seconds, exit 0.
  Actual generated HPL was used with only the DB sink replaced by a Dummy
  collector and the synthetic input filename bound. Network disabled; no model,
  database, Task revision or release writes. Header-present and header-absent
  CSVs both returned the exact source sequence, including a quoted multiline
  field, unsorted values and duplicate rows, with ordinals 1, 2, 3.

The native probe does not sort collected results before asserting them. It is
execution evidence for Hop ordinal semantics, not evidence for Vertica or ZIP
portability. Source-order storage/QA integration remains the next action.

Reference: [Apache Hop CSV input options](https://hop.apache.org/manual/latest/pipeline/transforms/csvinput.html)
documents the optional row-number output; the installed engine behavior was
verified separately by the native probe above rather than inferred from latest
documentation.

## Oracle and evidence persistence checkpoint

Added oracle document V2 and comparison evidence V2 for EXACT_SOURCE_SEQUENCE.
The pinned ordinal column and positional mismatch count are preserved; a
reversed sequence with the same multiset is MISMATCH, never MATCH. Public
evidence validation rejects inconsistent counts, forged MATCH labels and
incorrect comparison modes even when the submitted checksum is recalculated.
Oracle V1 and historical unordered evidence remain unchanged.

V3 specifications require the ordered oracle, including the exact ordinal
column and non-null contract. V1/V2 specifications reject the ordered oracle.
The editor context and historical review expose the ordered mode explicitly.

Verified in the isolated PostgreSQL test environment:

- Save and approve a synthetic V3 specification internally while the public V3
  API remains blocked (422) pending complete execution/QA/release support.
- Save the ordered oracle encrypted, read back the original bytes, preserve
  one-based row order in the review, and coalesce identical repeated saves.
- Reject a downgraded unordered oracle for that specification.
- Persist and read synthetic unverified MATCH and order-only MISMATCH packets;
  both retain absent provenance and cannot grant QA/release authority.
- Reject updates to immutable persisted comparison history.

Full isolated backend regression: 1,345 passed, 48 skipped, one warning,
27.47 seconds, exit 0. The native source-order tests are opt-in and skipped in
this suite; their separate successful execution is recorded above. An earlier
focused run found an incomplete mocked legacy document lacking its version;
the fixture was corrected to the actual V1 document format before full rerun.

No production migration, model invocation, original Task replay, Vertica write
or release approval occurred in this checkpoint. QA context, public editing,
ordered portable replay and the real corrected case still require integration.

## QA context checkpoint

QA context V13 now binds V3 specifications to ordered comparison evidence,
the independently pinned query checksum, the original Hop log checksum,
the generated ordinal mapping and the fully checked source record count.
The loader rechecks the executed HPL ordinal/sort options. An order-only
MISMATCH remains a deterministic FAIL that model PASS cannot override.
Existing unordered context serialization and summaries remain unchanged.

Tests cover substituted query/comparison/log checksums, absent order evidence,
changed source counts, generated-field mappings and sort columns, and modified
HPL options with recalculated HPL checksums. Focused QA tests: 28 passed.
Full isolated backend suite: 1,360 passed, 48 skipped, one warning,
27.80 seconds, exit 0.

This is deterministic QA-context validation, not a new real-model review or
end-to-end release. Public V3 creation remains closed. Next: integrate the
generated ordinal into SDM/portable replay, then input editing, model proposal
schema and UI before the real corrected-case acceptance. No previously
accepted Run or frozen cohort definition was changed.

## Portable replay contract checkpoint

Fixed source binding to distinguish specification version from source count:
V3 is a single CSV source, not three sources. The portable replay worker and
release approval gate now require portability evidence V3 for an ordered
specification. It binds the exact source-order contract, pinned result query,
ordered comparison mode, zero position mismatches and the existing artifact,
source, result checksum and row-count checks. Legacy unordered proof cannot
substitute for ordered proof. V1/V2 binding remains unchanged.

Focused Windows run: 28 passed, two setup errors caused by denied access to
the shared pytest temporary directory. No pass was inferred for those errors.
The complete isolated container rerun finished with 1,370 passed, 48 skipped,
one warning, 27.93 seconds, exit 0, including the replay-worker unit tests.

No actual ordered portable replay or release approval occurred. The SDM
generated-column representation and workbook visual inspection remain pending,
as do input/model/UI integration and real corrected-case acceptance. The
spreadsheet instructions were inspected, but no workbook was authored or
claimed visually verified in this checkpoint.

## Input revision checkpoint

Added typed `source_order_v1` to the existing revision API and persisted input
snapshot. Public run details show the contract and generated ordinal reference.
The deterministic requirement gate rejects unsupported source counts/types,
invalid order declarations, absent transformation intent, missing ordinal
output and filter/aggregation combinations. Absence retains legacy behavior;
order is never inferred from prose or ascending record IDs.

Actual isolated PostgreSQL/API test verified a new child revision, changed
input checksum, identical-request idempotency, conflicting request rejection,
unchanged parent snapshot, absent inherited approval, and the requirement gate
running only after new input approval. No ETL write occurred.

Focused tests: 23 passed. Full isolated backend suite: 1,380 passed,
48 skipped, one warning, 27.96 seconds, exit 0.

Public V3 specification/model execution is still unavailable. Remaining work
includes SA/Developer evidence and schema, UI controls, SDM generated-column
documentation, deployment and genuine ordered-case acceptance. This checkpoint
does not claim the user-facing feature is complete or that case 19 passed.

## SA and Developer handoff checkpoint

SA context V4 includes safe `source_order.conditions` evidence. READY_FOR_REVIEW
requires citing it and still cannot override deterministic requirement issues.
SA prompt V6 explicitly explains the logical source-record ordinal and current
stage responsibilities. Prior context bytes without order remain unchanged;
the newly selected prompt is versioned and does not rewrite historical traces.

Developer context/proposal V3 and prompt V6 require EtlSpecificationV3, explicit
order evidence, the confirmed generated BIGINT mapping, all source rows and
the exact projection. Legacy V1/V2 Developer materials remain unchanged.
Tests reject omitted citations, downgraded context/proposal/specification,
changed ordinal and omitted ordinal projection. No model approval is inferred.

Focused tests: 29 passed. First full run found the old explicit SA prompt-version
assertion (5 instead of the intentional new 6). Updated that assertion and added
checks for the new order instructions. Full rerun: 1,389 passed, 48 skipped,
one warning, 27.88 seconds, exit 0.

No provider calls, deployment or real corrected-case execution occurred.
Pending: user-facing order controls, naming/editor support, SDM generated-field
semantics and visual verification, public V3 API, deployment and real acceptance.

## Website editor checkpoint

Added an explicit source-order revision control, persisted-order summary and
generated ordinal naming action. Enabling order adds the ordinal output but
does not silently remove filters/aggregation. Conflicting intent is blocked
before submission. Generated ordinals are offered as projection outputs, not
as physical source fields for filtering/grouping. The naming action uses the
confirmed ordinal name, BIGINT and the stable generated-field reference, and
prevents duplicate insertion.

Frontend TypeScript/Vite build passed. Browser test: one passed in 5.0 seconds
against the freshly built preview with existing read-only navigation. Revision
and naming writes were intercepted and inspected; no real Task data or ETL was
modified. It exercised activation, blocked filtered intent, corrected submit,
persisted-summary rendering, naming insertion, duplicate prevention and 390,
768, 1440-pixel horizontal-overflow checks. This is UI wiring evidence, not a
claim of real write roundtrip or end-to-end acceptance. The temporary preview
was stopped after testing; the deployed platform was not replaced.

Still required: SDM generated-field semantics/visual verification, public V3
specification editor and oracle UI compatibility, deployment, genuine revised
case execution and independent portable replay. knowledge-workspace remains
unsynchronized.

## Ordered oracle editor serialization checkpoint

The browser serializer previously always emitted oracle document V1, dropping
the ordered context returned by the backend. It now preserves V2 comparison
and ordinal bindings, rejects unknown versions/downgrades and requires the
non-null INTEGER ordinal to equal each row's one-based position. It never
sorts answers or business keys. The editor explains these rules explicitly.
Legacy V1 documents retain their original field set and precision handling.

Five focused serialization tests passed (403 ms), including duplicate and
non-monotonic business IDs, reversed order, missing ordinal, nullable ordinal,
wrong comparison and version downgrade. TypeScript/Vite build passed.
These are frontend tests, not deployment, model or database acceptance.

## SDM source-order semantics checkpoint

SDM candidate V3 now carries the confirmed source-order contract. The ordinal
mapping is SOURCE_ORDINAL with no physical source columns, rather than DIRECT.
Expected workbook content distinguishes generated ordinals from row counts,
documents logical CSV records (including quoted newlines and excluded headers),
and requires explicit ascending ORDER BY when reading results. It does not
promise physical table order. V1/V2 mapping behavior remains unchanged.

Focused candidate/compiler checks: 19 passed. Full isolated backend regression:
1,393 passed, 48 skipped, one warning, 27.88 seconds, exit 0. Added tests cover
generated lineage, contract preservation, deterministic content, no mutation,
exact expected explanatory cells, invalid order binding and legacy isolation.
No ordered workbook visual inspection, live model calls, new Pilot writes,
deployment or portable replay was performed in this checkpoint. Public V3
specification endpoints remain closed pending the remaining delivery checks.

## Specification editor context checkpoint

The editor now recognizes the confirmed generated ordinal separately from
physical source and metric fields, binds specification V3 to the immutable
source-order contract and validates that naming has the exact required name
and BIGINT type. The frontend offers the ordinal only as a projection output,
displays the order contract and blocks filtered/aggregated/ordinal-free drafts.
No order or output selection is silently invented by the editor.

Focused context/compiler tests: 13 passed. Frontend build passed. Full isolated
backend regression: 1,395 passed, 48 skipped, one warning, 28.06 seconds, exit 0.
This checkpoint does not claim browser interaction or real save roundtrip.
Public V3 save remains closed pending ordered workbook verification; the
deployed platform has not been replaced. knowledge-workspace is still absent
at the expected local path and has not been synchronized.

## QA prompt checkpoint

QA prompt V10 explains source_order_evidence, generated logical-record ordinals,
the pinned ordered query, position mismatch counts and exact sequence comparison.
It distinguishes explicit ORDER BY from physical table order and uses existing
citation IDs rather than inventing a new evidence ID. Deterministic mismatches
still require FAIL; the presence of additional evidence never implies PASS.
Historical invocation prompts/results are not rewritten or reapproved.

Focused QA checks: 24 passed. The first full regression found the legacy citation
test's explicit V9 assertion; after updating it for the intended V10 change,
the full rerun passed: 1,396 passed, 48 skipped, one warning, 26.98 seconds,
exit 0. No real model call or deployment occurred.

Located the existing development-only scripts/sdm/inspect-native-render.mjs for
independent workbook visual inspection. The prior native-renderer verification
records the operator-approved existing openpyxl renderer. Next: generate an
ordered synthetic workbook through that renderer and inspect both sheets with
the bundled artifact runtime, including all newly added rule rows.

## Public V3 design API checkpoint

V3 validate/compile-preview/save now use the existing specification endpoints
and unchanged approval gate. The ordered encrypted-oracle integration test now
uses public specification save/approve rather than internal storage calls.
New real isolated PostgreSQL/API checks cover context binding, preview without
mutation, idempotent save, checksum-bound approval, exact historical readback,
and rejection of changed ordinal, omitted ordinal and V1 downgrade. Run state
does not change, and no Hop artifact or agent invocation is created.

Full backend regression: 1,397 passed, 48 skipped, one warning, 28.67 seconds,
exit 0. Historical specification UI also displays the source-order summary.
Opening the design API is not deployment or execution approval. Ordered XLSX
visual inspection, browser roundtrip, live execution and portable replay remain
required; no existing Pilot run or frozen oracle was changed.

## SDM browser display compatibility checkpoint

Found that SdmPreview rejected document V3 and described empty-source ordinal
mappings as row counts. It now accepts a structurally complete V3 order contract,
displays the confirmed order summary and labels the generated logical-record
position separately from COUNT_ROWS. Missing/wrong/duplicate ordinal mappings,
wrong type or physical-source lineage, filters and aggregation are rejected by
the display guard. Server validation remains authoritative.

Seven focused frontend logic tests passed (403 ms), covering ordered SDM guards
and oracle serialization regressions. TypeScript/Vite build passed. These tests
do not launch a browser or prove rendered layout, real API roundtrip or XLSX
visual correctness. The deployment and formal Pilot data remain unchanged.

## Ordered browser interaction checkpoint

Extended the existing read-only-navigation browser test with synthetic intercepted
specification history and SDM responses. It verifies the source-order summary,
generated ordinal label, absence of the incorrect row-count description, and
rejection of malformed ordinal lineage. A rejected SDM hides candidate creation.
Widths 390, 768 and 1440 have no horizontal document overflow.

The browser test passed (one test, 5.1 seconds) on the latest built frontend at
a temporary preview port. All writes remained intercepted; no real Task revision,
naming confirmation, model request, Hop execution or candidate creation occurred.
The preview process was identity-checked and stopped; deployed services remain
unchanged. This supplies UI interaction evidence, not ordered XLSX visual or
live end-to-end acceptance. Those gates remain pending.

## Ordered XLSX independent visual checkpoint

Generated one synthetic V3 candidate through the existing platform renderer in
its own dependency environment. The bundled Python could not import pytest or
psycopg; no dependencies were installed. The probe initially passed the renderer
result dictionary instead of its content bytes to the validator; corrected the
probe, not the production validator. Earlier failed attempts produced no XLSX.

Final candidate: 6,848 bytes, SHA-256
`0fc9228ef08d5637d8ef43dc1e4b9d3115b6094171ae2551ff2d949f006f4ce3`.
Structure gate: nine allowed parts; semantic equality CANDIDATE_LAYOUT_MATCHED;
portability NOT_VERIFIED; QA/release flags false. Local output is under
outputs/source-order-visual-20260927 (ignored, not published).

The independent bundled artifact runtime imported both sheets and found no
formulas. Expanded the existing inspection script's rules range to B24 so the
new rules and final checksum row are included. Both rendered images were
visually inspected: generated-field description wraps legibly, logical-record
and ORDER BY rules are readable, and all version fingerprints are visible.
No workbook content was rewritten by the independent tool. Native Microsoft
Excel behavior was not tested. This closes synthetic ordered-candidate visual
inspection only, not formal run, released workbook or portable replay acceptance.

## Deployment checkpoint

Built API, web and pilot-hop-worker images from commit 7134887. Before update,
two checks confirmed no active Task leases or queued/claimed Hop dispatches.
Historical unknown model outcomes remain untouched and were not retried.
Updated only API/control-worker/web with existing dispatch settings; no database
rebuild, migration, orphan removal or ETL execution was requested.

Running API module SHA-256 values match the local source:
- specification_api: 2343b8fe1ca2513a838ca03077a10d66c896e5511f0fe8b849b82a77894b2a04
- sdm_specification: ea49d71b4a57fde20a1fee2f7c25203d18acef2bbd2ccf95ea4e006b748f5eee
- qa_gateway: cab326fea61eee308949dc7fe5549236e026065365513135cfa60a8fcc979dcb

QA prompt reports V10. Health reports runtime_ready=true and 65 control tables.
Initial diagnostic used an incorrect module path; the subsequent check used
actual imported module locations. /api/openapi.json is not exposed and returned
404; this was not treated as schema acceptance. Deployed-site intercepted-write
browser regression passed (one test, 5.1 seconds). No revised formal case,
provider call, Vertica write or portable replay occurred in this checkpoint.

## Formal ordered revision preparation

Created a new child revision for the unresolved full-projection case using the
current checksum-bound QA correction offer and a new ai_sample target. The input
explicitly preserves logical CSV record order and adds source_position after
record_id. The original frozen unordered oracle and historical QA review remain
unchanged. The child is QUEUED/PREFLIGHT with no input approval and no write.
No model call was made. Private run identifiers remain in platform storage.

Before advancing, reconcile the ordinal non-null requirement with the generated
DDL: the existing delivery compiler emits types without NOT NULL constraints.
Do not ask the model to waive this mismatch or reinterpret physical table order.
Next action: implement/test V3-only ordinal nullability in DDL and verify the
QA target-contract inspection, then rebuild affected images before approving
and executing the prepared revision. Other legacy DDL must remain unchanged.
