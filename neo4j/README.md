# Neo4j projection rules v0.1

The graph is rebuildable. The projector consumes MySQL outbox events and
upserts nodes by the same canonical UUID string used by the API.

## Identity rules

- All entity node IDs are canonical lower-case UUID strings.
- `Element` is the exception: identity is the case-sensitive chemical symbol.
- Do not generate independent Neo4j-only scientific entities.

## Deletion / retraction

Prefer state projection over physical deletion for scientific records:
`RETRACTED`, `DISPUTED`, etc. Physical graph deletion is reserved for records
removed from the MySQL system of record.

## Idempotency

Every projector handler must be safe to retry:
use `MERGE` on the constrained identifier, then `SET` current properties and
`MERGE` relationships.

## Event examples

- `MaterialCreated`, `MaterialUpdated`
- `SampleCreated`, `SampleUpdated`
- `ObservationCreated`, `ObservationVerified`, `ObservationRetracted`
- `EvidenceCreated`
- `ClaimCreated`, `ClaimVerified`, `ClaimDisputed`
- `KnowledgeGapComputed`
