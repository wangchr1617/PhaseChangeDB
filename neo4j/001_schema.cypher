// PhaseChangeDB Neo4j projection schema v0.1
// Target: Neo4j 2026.x / Cypher 25
// MySQL remains the system of record. Neo4j is a rebuildable projection.

// ---------------------------
// Uniqueness constraints
// ---------------------------
CREATE CONSTRAINT material_id_unique IF NOT EXISTS
FOR (n:Material) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT element_symbol_unique IF NOT EXISTS
FOR (n:Element) REQUIRE n.symbol IS UNIQUE;

CREATE CONSTRAINT sample_id_unique IF NOT EXISTS
FOR (n:Sample) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT phase_id_unique IF NOT EXISTS
FOR (n:Phase) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT phase_assignment_id_unique IF NOT EXISTS
FOR (n:PhaseAssignment) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT process_run_id_unique IF NOT EXISTS
FOR (n:ProcessRun) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT process_step_id_unique IF NOT EXISTS
FOR (n:ProcessStep) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT measurement_id_unique IF NOT EXISTS
FOR (n:Measurement) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT property_id_unique IF NOT EXISTS
FOR (n:Property) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT observation_id_unique IF NOT EXISTS
FOR (n:Observation) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT device_id_unique IF NOT EXISTS
FOR (n:Device) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT device_test_id_unique IF NOT EXISTS
FOR (n:DeviceTest) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT paper_id_unique IF NOT EXISTS
FOR (n:Paper) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS
FOR (n:Evidence) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT claim_id_unique IF NOT EXISTS
FOR (n:Claim) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT structure_id_unique IF NOT EXISTS
FOR (n:Structure) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT calculation_id_unique IF NOT EXISTS
FOR (n:Calculation) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT knowledge_gap_id_unique IF NOT EXISTS
FOR (n:KnowledgeGap) REQUIRE n.id IS UNIQUE;

// ---------------------------
// Range indexes for graph filters
// ---------------------------
CREATE INDEX material_formula_idx IF NOT EXISTS
FOR (n:Material) ON (n.canonical_formula);

CREATE INDEX material_system_idx IF NOT EXISTS
FOR (n:Material) ON (n.chemical_system);

CREATE INDEX phase_state_idx IF NOT EXISTS
FOR (n:Phase) ON (n.phase_state_code);

CREATE INDEX property_code_idx IF NOT EXISTS
FOR (n:Property) ON (n.code);

CREATE INDEX observation_verification_idx IF NOT EXISTS
FOR (n:Observation) ON (n.verification_status);

CREATE INDEX observation_numeric_value_idx IF NOT EXISTS
FOR (n:Observation) ON (n.normalized_value);

CREATE INDEX paper_doi_idx IF NOT EXISTS
FOR (n:Paper) ON (n.doi);

CREATE INDEX paper_year_idx IF NOT EXISTS
FOR (n:Paper) ON (n.publication_year);

CREATE INDEX evidence_fragment_type_idx IF NOT EXISTS
FOR (n:Evidence) ON (n.fragment_type);

CREATE INDEX claim_verification_idx IF NOT EXISTS
FOR (n:Claim) ON (n.verification_status);

CREATE INDEX gap_status_score_idx IF NOT EXISTS
FOR (n:KnowledgeGap) ON (n.status, n.gap_score);

CREATE INDEX calculation_status_idx IF NOT EXISTS
FOR (n:Calculation) ON (n.status);

// No full-text or vector indexes in Neo4j v0.1.
// Elasticsearch owns lexical + semantic retrieval.

// ---------------------------
// Projection relationship contract (documentation, not schema DDL)
// ---------------------------
// (:Material)-[:CONTAINS_COMPONENT {
//     role_code, amount, atomic_fraction, concentration_value, concentration_unit
// }]->(:Element)
//
// (:Material)-[:HAS_SAMPLE]->(:Sample)
// (:Material)-[:HAS_PHASE]->(:Phase)
//
// (:Sample)-[:UNDERWENT]->(:ProcessRun)
// (:ProcessRun)-[:HAS_STEP]->(:ProcessStep)
//
// (:Sample)-[:HAS_PHASE_ASSIGNMENT]->(:PhaseAssignment)
// (:PhaseAssignment)-[:ASSIGNS]->(:Phase)
// (:PhaseAssignment)-[:SUPPORTED_BY]->(:Evidence)
//
// (:Measurement)-[:MEASURES]->(:Sample)
// (:Measurement)-[:PRODUCED]->(:Observation)
//
// (:Observation)-[:OF_PROPERTY]->(:Property)
// (:Observation)-[:SUPPORTED_BY {role, confidence}]->(:Evidence)
//
// (:Evidence)-[:FROM_PAPER]->(:Paper)
//
// (:Device)-[:USES_SAMPLE]->(:Sample)
// (:Device)-[:HAS_TEST]->(:DeviceTest)
// (:DeviceTest)-[:PRODUCED]->(:Observation)
//
// (:Structure)-[:REPRESENTS]->(:Material)
// (:Calculation)-[:USES_STRUCTURE]->(:Structure)
// (:Calculation)-[:PRODUCED]->(:Observation)
//
// (:Claim)-[:ABOUT_MATERIAL {role}]->(:Material)
// (:Claim)-[:ABOUT_PROPERTY {role}]->(:Property)
// (:Claim)-[:SUPPORTED_BY {confidence}]->(:Evidence)
// (:Claim)-[:CONTRADICTED_BY {confidence}]->(:Evidence)
// (:Claim)-[:QUALIFIED_BY {confidence}]->(:Evidence)
//
// (:KnowledgeGap)-[:ABOUT_MATERIAL]->(:Material)
// (:KnowledgeGap)-[:ABOUT_PROPERTY]->(:Property)
