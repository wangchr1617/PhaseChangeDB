// Example: GeTe variants with Tx evidence but no SET_time observations.
// Exact variant modeling depends on the projector; this query assumes
// Material nodes representing explicit compositions and shared chemical-system metadata.

MATCH (m:Material)-[:HAS_SAMPLE]->(:Sample)
MATCH (oTx:Observation)-[:OF_PROPERTY]->(pTx:Property {code: 'crystallization_temperature'})
MATCH (oTx)<-[:PRODUCED]-(:Measurement)-[:MEASURES]->(:Sample)<-[:HAS_SAMPLE]-(m)
WHERE oTx.verification_status IN ['HUMAN_REVIEWED', 'VERIFIED']
WITH DISTINCT m, count(DISTINCT oTx) AS tx_count
OPTIONAL MATCH (m)-[:HAS_SAMPLE]->(:Sample)<-[:USES_SAMPLE]-(:Device)
               -[:HAS_TEST]->(:DeviceTest)-[:PRODUCED]->(oSet:Observation)
               -[:OF_PROPERTY]->(pSet:Property {code: 'SET_time'})
WHERE oSet.verification_status IN ['HUMAN_REVIEWED', 'VERIFIED']
WITH m, tx_count, count(DISTINCT oSet) AS set_count
WHERE tx_count > 0 AND set_count = 0
RETURN m.id, m.canonical_formula, tx_count, set_count
ORDER BY tx_count DESC;
