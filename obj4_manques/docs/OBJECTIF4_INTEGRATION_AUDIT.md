# Objectif 4 - integration audit

## Verified state

- The existing pipeline keeps candidate generation and numerical outfit counting
  separate. The Python counter remains the source of truth for marginal gains.
- [wardrobe_loader.py](../dressme_gap_agent/wardrobe_loader.py) accepts the
  Objective 1 array (`wardrobe.json`) and the historical `{"items": [...]}` shape.
- `shoes` is normalized to the orchestration slot `footwear`; the original slot
  is retained in `original_slot`. Traditional metadata is retained and ambiguous
  records are marked for human review.
- [compatibility_provider.py](../dressme_gap_agent/compatibility_provider.py)
  supplies a deterministic mock and a validated HTTP `/pairs` client with a
  bounded retry loop and optional persistent cache.
- [gap_result_v1.schema.json](../contracts/gap_result_v1.schema.json) defines
  the minimal consumer contract. `ranking_ready` is invalid while pairs remain.

## Data verification

The supplied `C:\\Users\\mariem\\Downloads\\wardrobe.json` is a top-level
array with 423 records and Objective 1 field names. Its image, crop, and
embedding paths are metadata references; they are not treated as loaded
resources. Missing resources are reported by the loader and do not silently
invalidate otherwise usable metadata.

## Objective 2 integration

The local `dressme_compat_service` now provides the real `/pairs` implementation.
It requires full items containing a 512-value FashionCLIP embedding and an
Objective 2 category. [embedding_inventory.py](../dressme_gap_agent/embedding_inventory.py)
joins the row-aligned FashionCLIP cache to the inventory, while
[compatibility_provider.py](../dressme_gap_agent/compatibility_provider.py)
maps common slots to Objective 2 categories and validates the score matrix.
The model was verified locally on real cached embeddings.

The remaining dependency is synthetic candidate representation. The LLM
candidate generator returns descriptions, not FashionCLIP image embeddings, so
those candidates cannot be sent to `/pairs` until the team agrees on candidate
registration, a prototype image, or another approved embedding strategy.

## Availability

`INTEGRATION_READY_FOR_EXISTING_EMBEDDED_ITEMS`: the local Objective 2 model,
embedding join, category mapping, score validation, and deterministic counter
are verified. The full gap ranking remains blocked until synthetic candidates
have a valid Objective 2 representation. It must not be called
`END_TO_END_VALIDATED`.
