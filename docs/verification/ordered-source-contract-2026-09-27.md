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
