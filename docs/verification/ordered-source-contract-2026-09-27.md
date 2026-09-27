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
