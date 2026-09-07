-- PhaseChangeDB v0.1
-- Target: MySQL 8.4 LTS / InnoDB / utf8mb4
-- UUIDv7 values are generated in the application and stored byte-for-byte in BINARY(16).
-- Do NOT use UUID_TO_BIN(uuid, 1) for UUIDv7; MySQL's swap_flag optimization is for UUIDv1.

SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE DATABASE IF NOT EXISTS phasechangedb
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
USE phasechangedb;

-- ---------------------------------------------------------------------------
-- Ontology
-- ---------------------------------------------------------------------------
CREATE TABLE ont_term (
  id BINARY(16) NOT NULL,
  namespace VARCHAR(64) NOT NULL,
  code VARCHAR(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL,
  label VARCHAR(255) NOT NULL,
  definition TEXT NULL,
  parent_id BINARY(16) NULL,
  aliases_json JSON NULL,
  ontology_version VARCHAR(32) NOT NULL DEFAULT '0.1',
  deprecated BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_ont_namespace_code (namespace, code),
  KEY ix_ont_parent (parent_id),
  CONSTRAINT fk_ont_parent FOREIGN KEY (parent_id) REFERENCES ont_term(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- System / artifacts / events
-- ---------------------------------------------------------------------------
CREATE TABLE sys_artifact (
  id BINARY(16) NOT NULL,
  storage_uri VARCHAR(1024) NOT NULL,
  sha256_hex CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  mime_type VARCHAR(255) NULL,
  byte_size BIGINT UNSIGNED NULL,
  original_filename VARCHAR(512) NULL,
  metadata_json JSON NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_artifact_sha256 (sha256_hex),
  KEY ix_artifact_uri (storage_uri(512))
) ENGINE=InnoDB;

CREATE TABLE sys_outbox_event (
  id BINARY(16) NOT NULL,
  aggregate_type VARCHAR(64) NOT NULL,
  aggregate_id BINARY(16) NOT NULL,
  event_type VARCHAR(128) NOT NULL,
  payload_json JSON NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  retry_count INT UNSIGNED NOT NULL DEFAULT 0,
  available_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  processed_at TIMESTAMP(6) NULL,
  last_error TEXT NULL,
  PRIMARY KEY (id),
  KEY ix_outbox_dispatch (status, available_at, created_at),
  KEY ix_outbox_aggregate (aggregate_type, aggregate_id),
  CONSTRAINT ck_outbox_status CHECK (status IN ('pending','processing','processed','failed'))
) ENGINE=InnoDB;

CREATE TABLE sys_audit_log (
  id BINARY(16) NOT NULL,
  actor_id BINARY(16) NULL,
  actor_type VARCHAR(32) NOT NULL DEFAULT 'user',
  action VARCHAR(64) NOT NULL,
  entity_type VARCHAR(64) NOT NULL,
  entity_id BINARY(16) NOT NULL,
  before_json JSON NULL,
  after_json JSON NULL,
  request_id VARCHAR(128) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_audit_entity (entity_type, entity_id, created_at),
  KEY ix_audit_actor (actor_id, created_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Literature
-- ---------------------------------------------------------------------------
CREATE TABLE lit_paper (
  id BINARY(16) NOT NULL,
  doi VARCHAR(255) NULL,
  title TEXT NOT NULL,
  journal VARCHAR(255) NULL,
  publication_year SMALLINT UNSIGNED NULL,
  volume VARCHAR(64) NULL,
  issue VARCHAR(64) NULL,
  pages VARCHAR(64) NULL,
  publisher VARCHAR(255) NULL,
  abstract MEDIUMTEXT NULL,
  metadata_json JSON NULL,
  row_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_paper_doi (doi),
  KEY ix_paper_year (publication_year),
  KEY ix_paper_journal_year (journal, publication_year)
) ENGINE=InnoDB;

CREATE TABLE lit_author (
  id BINARY(16) NOT NULL,
  name VARCHAR(255) NOT NULL,
  orcid VARCHAR(32) NULL,
  affiliation_json JSON NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_author_orcid (orcid),
  KEY ix_author_name (name)
) ENGINE=InnoDB;

CREATE TABLE lit_paper_author (
  paper_id BINARY(16) NOT NULL,
  author_id BINARY(16) NOT NULL,
  author_order SMALLINT UNSIGNED NOT NULL,
  corresponding BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (paper_id, author_id),
  UNIQUE KEY uq_paper_author_order (paper_id, author_order),
  CONSTRAINT fk_paper_author_paper FOREIGN KEY (paper_id) REFERENCES lit_paper(id) ON DELETE CASCADE,
  CONSTRAINT fk_paper_author_author FOREIGN KEY (author_id) REFERENCES lit_author(id)
) ENGINE=InnoDB;

CREATE TABLE lit_document (
  id BINARY(16) NOT NULL,
  paper_id BINARY(16) NOT NULL,
  document_type VARCHAR(32) NOT NULL,
  artifact_id BINARY(16) NOT NULL,
  parser_version VARCHAR(64) NULL,
  parse_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  checksum_sha256_hex CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  metadata_json JSON NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_document_paper (paper_id, document_type),
  KEY ix_document_parse_status (parse_status),
  CONSTRAINT fk_document_paper FOREIGN KEY (paper_id) REFERENCES lit_paper(id) ON DELETE CASCADE,
  CONSTRAINT fk_document_artifact FOREIGN KEY (artifact_id) REFERENCES sys_artifact(id),
  CONSTRAINT ck_document_type CHECK (document_type IN ('main_article','supplement','dataset','preprint','other')),
  CONSTRAINT ck_document_parse_status CHECK (parse_status IN ('pending','processing','parsed','failed'))
) ENGINE=InnoDB;

CREATE TABLE evd_fragment (
  id BINARY(16) NOT NULL,
  paper_id BINARY(16) NOT NULL,
  document_id BINARY(16) NOT NULL,
  fragment_type VARCHAR(32) NOT NULL,
  page_number INT UNSIGNED NULL,
  section VARCHAR(512) NULL,
  figure_number VARCHAR(64) NULL,
  table_number VARCHAR(64) NULL,
  text_snippet MEDIUMTEXT NULL,
  bounding_box_json JSON NULL,
  artifact_id BINARY(16) NULL,
  content_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_evidence_paper (paper_id, page_number),
  KEY ix_evidence_document (document_id, fragment_type),
  KEY ix_evidence_figure (paper_id, figure_number),
  KEY ix_evidence_table (paper_id, table_number),
  CONSTRAINT fk_evidence_paper FOREIGN KEY (paper_id) REFERENCES lit_paper(id) ON DELETE CASCADE,
  CONSTRAINT fk_evidence_document FOREIGN KEY (document_id) REFERENCES lit_document(id) ON DELETE CASCADE,
  CONSTRAINT fk_evidence_artifact FOREIGN KEY (artifact_id) REFERENCES sys_artifact(id),
  CONSTRAINT ck_evidence_fragment_type CHECK (
    fragment_type IN ('paragraph','sentence','figure','figure_caption','table','table_cell','supplement','other')
  )
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Materials
-- ---------------------------------------------------------------------------
CREATE TABLE mat_material (
  id BINARY(16) NOT NULL,
  canonical_formula VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL,
  reduced_formula VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NULL,
  chemical_system VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL,
  material_family_term_id BINARY(16) NULL,
  name VARCHAR(255) NULL,
  description TEXT NULL,
  row_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_material_formula_system (canonical_formula, chemical_system),
  KEY ix_material_family (material_family_term_id),
  KEY ix_material_chemical_system (chemical_system),
  CONSTRAINT fk_material_family FOREIGN KEY (material_family_term_id) REFERENCES ont_term(id)
) ENGINE=InnoDB;

CREATE TABLE mat_material_alias (
  id BINARY(16) NOT NULL,
  material_id BINARY(16) NOT NULL,
  alias VARCHAR(255) NOT NULL,
  alias_type VARCHAR(32) NOT NULL DEFAULT 'common',
  source VARCHAR(255) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_material_alias (material_id, alias),
  KEY ix_alias_lookup (alias),
  CONSTRAINT fk_alias_material FOREIGN KEY (material_id) REFERENCES mat_material(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE mat_composition_component (
  id BINARY(16) NOT NULL,
  material_id BINARY(16) NOT NULL,
  element_symbol CHAR(3) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  amount_decimal DECIMAL(20,10) NULL,
  atomic_fraction DECIMAL(18,12) NULL,
  role_term_id BINARY(16) NOT NULL,
  concentration_value DECIMAL(20,10) NULL,
  concentration_unit VARCHAR(32) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_material_element_role (material_id, element_symbol, role_term_id),
  KEY ix_component_element (element_symbol),
  KEY ix_component_role (role_term_id),
  CONSTRAINT fk_component_material FOREIGN KEY (material_id) REFERENCES mat_material(id) ON DELETE CASCADE,
  CONSTRAINT fk_component_role FOREIGN KEY (role_term_id) REFERENCES ont_term(id),
  CONSTRAINT ck_atomic_fraction CHECK (atomic_fraction IS NULL OR (atomic_fraction >= 0 AND atomic_fraction <= 1)),
  CONSTRAINT ck_component_concentration CHECK (concentration_value IS NULL OR concentration_value >= 0)
) ENGINE=InnoDB;

CREATE TABLE mat_phase (
  id BINARY(16) NOT NULL,
  material_id BINARY(16) NOT NULL,
  phase_name VARCHAR(255) NOT NULL,
  phase_state_term_id BINARY(16) NOT NULL,
  crystal_system_term_id BINARY(16) NULL,
  space_group VARCHAR(64) NULL,
  prototype VARCHAR(255) NULL,
  description TEXT NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_material_phase (material_id, phase_name),
  KEY ix_phase_state (phase_state_term_id),
  CONSTRAINT fk_phase_material FOREIGN KEY (material_id) REFERENCES mat_material(id) ON DELETE CASCADE,
  CONSTRAINT fk_phase_state FOREIGN KEY (phase_state_term_id) REFERENCES ont_term(id),
  CONSTRAINT fk_phase_crystal_system FOREIGN KEY (crystal_system_term_id) REFERENCES ont_term(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Samples / processes / measurements
-- ---------------------------------------------------------------------------
CREATE TABLE sam_sample (
  id BINARY(16) NOT NULL,
  nominal_material_id BINARY(16) NOT NULL,
  source_paper_id BINARY(16) NULL,
  sample_label VARCHAR(255) NULL,
  sample_type_term_id BINARY(16) NOT NULL,
  thickness_value DECIMAL(20,10) NULL,
  thickness_unit VARCHAR(32) NULL,
  substrate_material VARCHAR(255) NULL,
  geometry_json JSON NULL,
  description TEXT NULL,
  row_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_sample_material (nominal_material_id),
  KEY ix_sample_paper (source_paper_id),
  KEY ix_sample_type (sample_type_term_id),
  CONSTRAINT fk_sample_material FOREIGN KEY (nominal_material_id) REFERENCES mat_material(id),
  CONSTRAINT fk_sample_paper FOREIGN KEY (source_paper_id) REFERENCES lit_paper(id),
  CONSTRAINT fk_sample_type FOREIGN KEY (sample_type_term_id) REFERENCES ont_term(id),
  CONSTRAINT ck_sample_thickness CHECK (thickness_value IS NULL OR thickness_value >= 0)
) ENGINE=InnoDB;

CREATE TABLE sam_composition_analysis (
  id BINARY(16) NOT NULL,
  sample_id BINARY(16) NOT NULL,
  measurement_method_term_id BINARY(16) NULL,
  composition_json JSON NOT NULL,
  uncertainty_json JSON NULL,
  evidence_id BINARY(16) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_sample_comp_sample (sample_id),
  CONSTRAINT fk_sample_comp_sample FOREIGN KEY (sample_id) REFERENCES sam_sample(id) ON DELETE CASCADE,
  CONSTRAINT fk_sample_comp_method FOREIGN KEY (measurement_method_term_id) REFERENCES ont_term(id),
  CONSTRAINT fk_sample_comp_evidence FOREIGN KEY (evidence_id) REFERENCES evd_fragment(id)
) ENGINE=InnoDB;

CREATE TABLE exp_process_run (
  id BINARY(16) NOT NULL,
  sample_id BINARY(16) NOT NULL,
  process_name VARCHAR(255) NULL,
  start_state VARCHAR(255) NULL,
  end_state VARCHAR(255) NULL,
  source_paper_id BINARY(16) NULL,
  evidence_id BINARY(16) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_process_sample (sample_id),
  CONSTRAINT fk_process_sample FOREIGN KEY (sample_id) REFERENCES sam_sample(id) ON DELETE CASCADE,
  CONSTRAINT fk_process_paper FOREIGN KEY (source_paper_id) REFERENCES lit_paper(id),
  CONSTRAINT fk_process_evidence FOREIGN KEY (evidence_id) REFERENCES evd_fragment(id)
) ENGINE=InnoDB;

CREATE TABLE exp_process_step (
  id BINARY(16) NOT NULL,
  process_run_id BINARY(16) NOT NULL,
  sequence_number SMALLINT UNSIGNED NOT NULL,
  process_type_term_id BINARY(16) NOT NULL,
  temperature_value DECIMAL(20,10) NULL,
  temperature_unit VARCHAR(32) NULL,
  duration_value DECIMAL(20,10) NULL,
  duration_unit VARCHAR(32) NULL,
  pressure_value DECIMAL(20,10) NULL,
  pressure_unit VARCHAR(32) NULL,
  atmosphere VARCHAR(255) NULL,
  heating_rate_value DECIMAL(20,10) NULL,
  heating_rate_unit VARCHAR(32) NULL,
  cooling_rate_value DECIMAL(20,10) NULL,
  cooling_rate_unit VARCHAR(32) NULL,
  parameters_json JSON NULL,
  evidence_id BINARY(16) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_process_sequence (process_run_id, sequence_number),
  KEY ix_process_step_type (process_type_term_id),
  CONSTRAINT fk_step_process FOREIGN KEY (process_run_id) REFERENCES exp_process_run(id) ON DELETE CASCADE,
  CONSTRAINT fk_step_type FOREIGN KEY (process_type_term_id) REFERENCES ont_term(id),
  CONSTRAINT fk_step_evidence FOREIGN KEY (evidence_id) REFERENCES evd_fragment(id),
  CONSTRAINT ck_step_duration CHECK (duration_value IS NULL OR duration_value >= 0),
  CONSTRAINT ck_step_pressure CHECK (pressure_value IS NULL OR pressure_value >= 0)
) ENGINE=InnoDB;

CREATE TABLE sam_phase_assignment (
  id BINARY(16) NOT NULL,
  sample_id BINARY(16) NOT NULL,
  phase_id BINARY(16) NOT NULL,
  phase_fraction DECIMAL(8,6) NULL,
  assignment_method_term_id BINARY(16) NULL,
  confidence DECIMAL(5,4) NULL,
  temperature_value DECIMAL(20,10) NULL,
  temperature_unit VARCHAR(32) NULL,
  time_point_value DECIMAL(20,10) NULL,
  time_point_unit VARCHAR(32) NULL,
  evidence_id BINARY(16) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_phase_assignment_sample (sample_id),
  KEY ix_phase_assignment_phase (phase_id),
  CONSTRAINT fk_assignment_sample FOREIGN KEY (sample_id) REFERENCES sam_sample(id) ON DELETE CASCADE,
  CONSTRAINT fk_assignment_phase FOREIGN KEY (phase_id) REFERENCES mat_phase(id),
  CONSTRAINT fk_assignment_method FOREIGN KEY (assignment_method_term_id) REFERENCES ont_term(id),
  CONSTRAINT fk_assignment_evidence FOREIGN KEY (evidence_id) REFERENCES evd_fragment(id),
  CONSTRAINT ck_phase_fraction CHECK (phase_fraction IS NULL OR (phase_fraction >= 0 AND phase_fraction <= 1)),
  CONSTRAINT ck_phase_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
) ENGINE=InnoDB;

CREATE TABLE exp_measurement (
  id BINARY(16) NOT NULL,
  sample_id BINARY(16) NOT NULL,
  measurement_type_term_id BINARY(16) NOT NULL,
  instrument VARCHAR(255) NULL,
  temperature_value DECIMAL(20,10) NULL,
  temperature_unit VARCHAR(32) NULL,
  pressure_value DECIMAL(20,10) NULL,
  pressure_unit VARCHAR(32) NULL,
  heating_rate_value DECIMAL(20,10) NULL,
  heating_rate_unit VARCHAR(32) NULL,
  frequency_value DECIMAL(20,10) NULL,
  frequency_unit VARCHAR(32) NULL,
  wavelength_value DECIMAL(20,10) NULL,
  wavelength_unit VARCHAR(32) NULL,
  parameters_json JSON NULL,
  source_paper_id BINARY(16) NULL,
  evidence_id BINARY(16) NULL,
  performed_at DATETIME(6) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_measurement_sample_type (sample_id, measurement_type_term_id),
  KEY ix_measurement_temperature (temperature_value),
  CONSTRAINT fk_measurement_sample FOREIGN KEY (sample_id) REFERENCES sam_sample(id) ON DELETE CASCADE,
  CONSTRAINT fk_measurement_type FOREIGN KEY (measurement_type_term_id) REFERENCES ont_term(id),
  CONSTRAINT fk_measurement_paper FOREIGN KEY (source_paper_id) REFERENCES lit_paper(id),
  CONSTRAINT fk_measurement_evidence FOREIGN KEY (evidence_id) REFERENCES evd_fragment(id),
  CONSTRAINT ck_measurement_pressure CHECK (pressure_value IS NULL OR pressure_value >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Property definitions
-- ---------------------------------------------------------------------------
CREATE TABLE obs_property_definition (
  id BINARY(16) NOT NULL,
  code VARCHAR(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL,
  name VARCHAR(255) NOT NULL,
  category_term_id BINARY(16) NULL,
  symbol VARCHAR(64) NULL,
  description TEXT NULL,
  dimension VARCHAR(64) NULL,
  canonical_unit_term_id BINARY(16) NULL,
  value_kind VARCHAR(32) NOT NULL DEFAULT 'scalar',
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_property_code (code),
  KEY ix_property_category (category_term_id),
  CONSTRAINT fk_property_category FOREIGN KEY (category_term_id) REFERENCES ont_term(id),
  CONSTRAINT fk_property_canonical_unit FOREIGN KEY (canonical_unit_term_id) REFERENCES ont_term(id),
  CONSTRAINT ck_property_value_kind CHECK (value_kind IN ('scalar','range','text','boolean','categorical','curve'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Computational structures / calculations
-- ---------------------------------------------------------------------------
CREATE TABLE cmp_structure (
  id BINARY(16) NOT NULL,
  material_id BINARY(16) NOT NULL,
  sample_id BINARY(16) NULL,
  structure_type VARCHAR(64) NOT NULL,
  space_group VARCHAR(64) NULL,
  artifact_id BINARY(16) NOT NULL,
  structure_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  source VARCHAR(255) NULL,
  metadata_json JSON NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_structure_hash (structure_hash),
  KEY ix_structure_material (material_id),
  CONSTRAINT fk_structure_material FOREIGN KEY (material_id) REFERENCES mat_material(id),
  CONSTRAINT fk_structure_sample FOREIGN KEY (sample_id) REFERENCES sam_sample(id),
  CONSTRAINT fk_structure_artifact FOREIGN KEY (artifact_id) REFERENCES sys_artifact(id)
) ENGINE=InnoDB;

CREATE TABLE cmp_calculation (
  id BINARY(16) NOT NULL,
  structure_id BINARY(16) NOT NULL,
  calculation_type_term_id BINARY(16) NOT NULL,
  method VARCHAR(128) NOT NULL,
  code VARCHAR(128) NOT NULL,
  code_version VARCHAR(128) NULL,
  functional VARCHAR(128) NULL,
  pseudopotential VARCHAR(255) NULL,
  parameters_json JSON NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'created',
  started_at DATETIME(6) NULL,
  completed_at DATETIME(6) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_calculation_structure (structure_id),
  KEY ix_calculation_type (calculation_type_term_id),
  KEY ix_calculation_status (status),
  CONSTRAINT fk_calculation_structure FOREIGN KEY (structure_id) REFERENCES cmp_structure(id),
  CONSTRAINT fk_calculation_type FOREIGN KEY (calculation_type_term_id) REFERENCES ont_term(id),
  CONSTRAINT ck_calculation_status CHECK (status IN ('created','queued','running','succeeded','failed','cancelled'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Devices
-- ---------------------------------------------------------------------------
CREATE TABLE dev_device (
  id BINARY(16) NOT NULL,
  source_paper_id BINARY(16) NULL,
  device_type_term_id BINARY(16) NOT NULL,
  active_material_sample_id BINARY(16) NOT NULL,
  geometry_json JSON NULL,
  electrode_materials_json JSON NULL,
  device_dimensions_json JSON NULL,
  fabrication_description TEXT NULL,
  evidence_id BINARY(16) NULL,
  row_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_device_sample (active_material_sample_id),
  KEY ix_device_type (device_type_term_id),
  CONSTRAINT fk_device_paper FOREIGN KEY (source_paper_id) REFERENCES lit_paper(id),
  CONSTRAINT fk_device_type FOREIGN KEY (device_type_term_id) REFERENCES ont_term(id),
  CONSTRAINT fk_device_sample FOREIGN KEY (active_material_sample_id) REFERENCES sam_sample(id),
  CONSTRAINT fk_device_evidence FOREIGN KEY (evidence_id) REFERENCES evd_fragment(id)
) ENGINE=InnoDB;

CREATE TABLE dev_device_layer (
  id BINARY(16) NOT NULL,
  device_id BINARY(16) NOT NULL,
  sequence_number SMALLINT UNSIGNED NOT NULL,
  role_term_id BINARY(16) NOT NULL,
  material_id BINARY(16) NULL,
  material_text VARCHAR(255) NULL,
  thickness_value DECIMAL(20,10) NULL,
  thickness_unit VARCHAR(32) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_device_layer_sequence (device_id, sequence_number),
  CONSTRAINT fk_layer_device FOREIGN KEY (device_id) REFERENCES dev_device(id) ON DELETE CASCADE,
  CONSTRAINT fk_layer_role FOREIGN KEY (role_term_id) REFERENCES ont_term(id),
  CONSTRAINT fk_layer_material FOREIGN KEY (material_id) REFERENCES mat_material(id),
  CONSTRAINT ck_layer_material CHECK (material_id IS NOT NULL OR material_text IS NOT NULL),
  CONSTRAINT ck_layer_thickness CHECK (thickness_value IS NULL OR thickness_value >= 0)
) ENGINE=InnoDB;

CREATE TABLE dev_test (
  id BINARY(16) NOT NULL,
  device_id BINARY(16) NOT NULL,
  test_type_term_id BINARY(16) NOT NULL,
  pulse_width_value DECIMAL(20,10) NULL,
  pulse_width_unit VARCHAR(32) NULL,
  pulse_voltage_value DECIMAL(20,10) NULL,
  pulse_voltage_unit VARCHAR(32) NULL,
  pulse_current_value DECIMAL(20,10) NULL,
  pulse_current_unit VARCHAR(32) NULL,
  ambient_temperature_value DECIMAL(20,10) NULL,
  ambient_temperature_unit VARCHAR(32) NULL,
  parameters_json JSON NULL,
  evidence_id BINARY(16) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_device_test_device_type (device_id, test_type_term_id),
  CONSTRAINT fk_test_device FOREIGN KEY (device_id) REFERENCES dev_device(id) ON DELETE CASCADE,
  CONSTRAINT fk_test_type FOREIGN KEY (test_type_term_id) REFERENCES ont_term(id),
  CONSTRAINT fk_test_evidence FOREIGN KEY (evidence_id) REFERENCES evd_fragment(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Observations
-- ---------------------------------------------------------------------------
CREATE TABLE obs_observation (
  id BINARY(16) NOT NULL,

  sample_id BINARY(16) NULL,
  device_id BINARY(16) NULL,
  calculation_id BINARY(16) NULL,

  property_definition_id BINARY(16) NOT NULL,
  measurement_id BINARY(16) NULL,
  device_test_id BINARY(16) NULL,
  phase_assignment_id BINARY(16) NULL,

  value_kind VARCHAR(32) NOT NULL DEFAULT 'scalar',
  value_numeric DECIMAL(30,12) NULL,
  value_min DECIMAL(30,12) NULL,
  value_max DECIMAL(30,12) NULL,
  value_text TEXT NULL,
  value_boolean BOOLEAN NULL,

  original_value_text VARCHAR(255) NULL,
  original_unit_text VARCHAR(64) NULL,

  normalized_value DECIMAL(30,12) NULL,
  normalized_unit_term_id BINARY(16) NULL,

  uncertainty_lower DECIMAL(30,12) NULL,
  uncertainty_upper DECIMAL(30,12) NULL,

  condition_temperature_value DECIMAL(20,10) NULL,
  condition_temperature_unit VARCHAR(32) NULL,
  condition_pressure_value DECIMAL(20,10) NULL,
  condition_pressure_unit VARCHAR(32) NULL,

  quality_score DECIMAL(5,4) NULL,
  verification_status VARCHAR(32) NOT NULL DEFAULT 'AI_EXTRACTED',
  row_version BIGINT UNSIGNED NOT NULL DEFAULT 1,

  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

  PRIMARY KEY (id),
  KEY ix_observation_sample_property (sample_id, property_definition_id),
  KEY ix_observation_device_property (device_id, property_definition_id),
  KEY ix_observation_calculation_property (calculation_id, property_definition_id),
  KEY ix_observation_property_value (property_definition_id, normalized_value),
  KEY ix_observation_verification (verification_status, property_definition_id),
  KEY ix_observation_measurement (measurement_id),
  KEY ix_observation_phase (phase_assignment_id),

  CONSTRAINT fk_observation_sample FOREIGN KEY (sample_id) REFERENCES sam_sample(id),
  CONSTRAINT fk_observation_device FOREIGN KEY (device_id) REFERENCES dev_device(id),
  CONSTRAINT fk_observation_calculation FOREIGN KEY (calculation_id) REFERENCES cmp_calculation(id),
  CONSTRAINT fk_observation_property FOREIGN KEY (property_definition_id) REFERENCES obs_property_definition(id),
  CONSTRAINT fk_observation_measurement FOREIGN KEY (measurement_id) REFERENCES exp_measurement(id),
  CONSTRAINT fk_observation_device_test FOREIGN KEY (device_test_id) REFERENCES dev_test(id),
  CONSTRAINT fk_observation_phase FOREIGN KEY (phase_assignment_id) REFERENCES sam_phase_assignment(id),
  CONSTRAINT fk_observation_unit FOREIGN KEY (normalized_unit_term_id) REFERENCES ont_term(id),

  CONSTRAINT ck_observation_exactly_one_subject CHECK (
    (sample_id IS NOT NULL) + (device_id IS NOT NULL) + (calculation_id IS NOT NULL) = 1
  ),
  CONSTRAINT ck_observation_value_kind CHECK (
    value_kind IN ('scalar','range','text','boolean','categorical','curve')
  ),
  CONSTRAINT ck_observation_scalar CHECK (
    value_kind <> 'scalar' OR value_numeric IS NOT NULL OR normalized_value IS NOT NULL
  ),
  CONSTRAINT ck_observation_range CHECK (
    value_kind <> 'range' OR (value_min IS NOT NULL AND value_max IS NOT NULL AND value_min <= value_max)
  ),
  CONSTRAINT ck_observation_text CHECK (
    value_kind NOT IN ('text','categorical') OR value_text IS NOT NULL
  ),
  CONSTRAINT ck_observation_boolean CHECK (
    value_kind <> 'boolean' OR value_boolean IS NOT NULL
  ),
  CONSTRAINT ck_observation_quality CHECK (
    quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)
  ),
  CONSTRAINT ck_observation_verification CHECK (
    verification_status IN ('AI_EXTRACTED','AI_VALIDATED','HUMAN_REVIEWED','VERIFIED','DISPUTED','RETRACTED')
  ),
  CONSTRAINT ck_observation_sample_measurement CHECK (
    measurement_id IS NULL OR sample_id IS NOT NULL
  ),
  CONSTRAINT ck_observation_device_test CHECK (
    device_test_id IS NULL OR device_id IS NOT NULL
  )
) ENGINE=InnoDB;

CREATE TABLE obs_dataset (
  id BINARY(16) NOT NULL,
  observation_id BINARY(16) NOT NULL,
  dataset_type VARCHAR(32) NOT NULL,
  x_property_id BINARY(16) NULL,
  y_property_id BINARY(16) NULL,
  artifact_id BINARY(16) NOT NULL,
  number_of_points BIGINT UNSIGNED NULL,
  metadata_json JSON NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_dataset_observation (observation_id),
  CONSTRAINT fk_dataset_observation FOREIGN KEY (observation_id) REFERENCES obs_observation(id) ON DELETE CASCADE,
  CONSTRAINT fk_dataset_x_property FOREIGN KEY (x_property_id) REFERENCES obs_property_definition(id),
  CONSTRAINT fk_dataset_y_property FOREIGN KEY (y_property_id) REFERENCES obs_property_definition(id),
  CONSTRAINT fk_dataset_artifact FOREIGN KEY (artifact_id) REFERENCES sys_artifact(id),
  CONSTRAINT ck_dataset_type CHECK (dataset_type IN ('curve','timeseries','spectrum','iv_curve','table','other'))
) ENGINE=InnoDB;

CREATE TABLE evd_observation_link (
  observation_id BINARY(16) NOT NULL,
  evidence_fragment_id BINARY(16) NOT NULL,
  evidence_role VARCHAR(32) NOT NULL DEFAULT 'primary',
  confidence DECIMAL(5,4) NULL,
  PRIMARY KEY (observation_id, evidence_fragment_id),
  KEY ix_obs_evidence_evidence (evidence_fragment_id),
  CONSTRAINT fk_obs_evidence_observation FOREIGN KEY (observation_id) REFERENCES obs_observation(id) ON DELETE CASCADE,
  CONSTRAINT fk_obs_evidence_fragment FOREIGN KEY (evidence_fragment_id) REFERENCES evd_fragment(id) ON DELETE CASCADE,
  CONSTRAINT ck_obs_evidence_role CHECK (evidence_role IN ('primary','supporting','derived','context')),
  CONSTRAINT ck_obs_evidence_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Extraction / human review staging
-- ---------------------------------------------------------------------------
CREATE TABLE ext_run (
  id BINARY(16) NOT NULL,
  document_id BINARY(16) NOT NULL,
  parser_version VARCHAR(64) NULL,
  model_name VARCHAR(255) NOT NULL,
  model_version VARCHAR(128) NULL,
  prompt_version VARCHAR(64) NULL,
  ontology_version VARCHAR(32) NOT NULL DEFAULT '0.1',
  status VARCHAR(32) NOT NULL DEFAULT 'created',
  started_at DATETIME(6) NULL,
  completed_at DATETIME(6) NULL,
  metrics_json JSON NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_ext_run_document (document_id, created_at),
  KEY ix_ext_run_status (status),
  CONSTRAINT fk_ext_run_document FOREIGN KEY (document_id) REFERENCES lit_document(id) ON DELETE CASCADE,
  CONSTRAINT ck_ext_run_status CHECK (status IN ('created','running','completed','failed','cancelled'))
) ENGINE=InnoDB;

CREATE TABLE ext_candidate (
  id BINARY(16) NOT NULL,
  extraction_run_id BINARY(16) NOT NULL,
  candidate_type VARCHAR(64) NOT NULL,
  candidate_payload_json JSON NOT NULL,
  confidence DECIMAL(5,4) NULL,
  evidence_fragment_id BINARY(16) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  promoted_entity_type VARCHAR(64) NULL,
  promoted_entity_id BINARY(16) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_candidate_run_status (extraction_run_id, status),
  KEY ix_candidate_evidence (evidence_fragment_id),
  CONSTRAINT fk_candidate_run FOREIGN KEY (extraction_run_id) REFERENCES ext_run(id) ON DELETE CASCADE,
  CONSTRAINT fk_candidate_evidence FOREIGN KEY (evidence_fragment_id) REFERENCES evd_fragment(id),
  CONSTRAINT ck_candidate_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  CONSTRAINT ck_candidate_status CHECK (status IN ('pending','accepted','modified','rejected'))
) ENGINE=InnoDB;

CREATE TABLE ext_review (
  id BINARY(16) NOT NULL,
  candidate_id BINARY(16) NOT NULL,
  reviewer_id BINARY(16) NOT NULL,
  decision VARCHAR(32) NOT NULL,
  before_json JSON NULL,
  after_json JSON NULL,
  comment TEXT NULL,
  reviewed_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_review_candidate (candidate_id, reviewed_at),
  KEY ix_review_reviewer (reviewer_id, reviewed_at),
  CONSTRAINT fk_review_candidate FOREIGN KEY (candidate_id) REFERENCES ext_candidate(id) ON DELETE CASCADE,
  CONSTRAINT ck_review_decision CHECK (decision IN ('accept','modify','reject'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Knowledge / claims / gaps
-- ---------------------------------------------------------------------------
CREATE TABLE knw_claim (
  id BINARY(16) NOT NULL,
  claim_type_term_id BINARY(16) NOT NULL,
  claim_text TEXT NOT NULL,
  structured_claim_json JSON NULL,
  confidence DECIMAL(5,4) NULL,
  verification_status VARCHAR(32) NOT NULL DEFAULT 'AI_EXTRACTED',
  source_type VARCHAR(32) NOT NULL DEFAULT 'human',
  row_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  created_by BINARY(16) NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_claim_type (claim_type_term_id),
  KEY ix_claim_verification (verification_status),
  CONSTRAINT fk_claim_type FOREIGN KEY (claim_type_term_id) REFERENCES ont_term(id),
  CONSTRAINT ck_claim_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  CONSTRAINT ck_claim_verification CHECK (
    verification_status IN ('AI_EXTRACTED','AI_VALIDATED','HUMAN_REVIEWED','VERIFIED','DISPUTED','RETRACTED')
  ),
  CONSTRAINT ck_claim_source_type CHECK (source_type IN ('human','ai','derived','imported'))
) ENGINE=InnoDB;

CREATE TABLE knw_claim_evidence (
  claim_id BINARY(16) NOT NULL,
  evidence_fragment_id BINARY(16) NOT NULL,
  stance VARCHAR(32) NOT NULL,
  confidence DECIMAL(5,4) NULL,
  PRIMARY KEY (claim_id, evidence_fragment_id),
  KEY ix_claim_evidence_fragment (evidence_fragment_id),
  CONSTRAINT fk_claim_evidence_claim FOREIGN KEY (claim_id) REFERENCES knw_claim(id) ON DELETE CASCADE,
  CONSTRAINT fk_claim_evidence_fragment FOREIGN KEY (evidence_fragment_id) REFERENCES evd_fragment(id) ON DELETE CASCADE,
  CONSTRAINT ck_claim_stance CHECK (stance IN ('supports','contradicts','qualifies')),
  CONSTRAINT ck_claim_evidence_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
) ENGINE=InnoDB;

CREATE TABLE knw_claim_material (
  claim_id BINARY(16) NOT NULL,
  material_id BINARY(16) NOT NULL,
  role VARCHAR(32) NOT NULL DEFAULT 'about',
  PRIMARY KEY (claim_id, material_id, role),
  CONSTRAINT fk_claim_material_claim FOREIGN KEY (claim_id) REFERENCES knw_claim(id) ON DELETE CASCADE,
  CONSTRAINT fk_claim_material_material FOREIGN KEY (material_id) REFERENCES mat_material(id)
) ENGINE=InnoDB;

CREATE TABLE knw_claim_property (
  claim_id BINARY(16) NOT NULL,
  property_definition_id BINARY(16) NOT NULL,
  role VARCHAR(32) NOT NULL DEFAULT 'about',
  PRIMARY KEY (claim_id, property_definition_id, role),
  CONSTRAINT fk_claim_property_claim FOREIGN KEY (claim_id) REFERENCES knw_claim(id) ON DELETE CASCADE,
  CONSTRAINT fk_claim_property_property FOREIGN KEY (property_definition_id) REFERENCES obs_property_definition(id)
) ENGINE=InnoDB;

CREATE TABLE knw_gap (
  id BINARY(16) NOT NULL,
  material_id BINARY(16) NOT NULL,
  property_definition_id BINARY(16) NOT NULL,
  gap_type VARCHAR(32) NOT NULL,
  gap_score DECIMAL(5,4) NOT NULL,
  evidence_count INT UNSIGNED NOT NULL DEFAULT 0,
  observation_count INT UNSIGNED NOT NULL DEFAULT 0,
  paper_count INT UNSIGNED NOT NULL DEFAULT 0,
  condition_coverage_score DECIMAL(5,4) NULL,
  conflict_score DECIMAL(5,4) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  algorithm_version VARCHAR(64) NOT NULL,
  generated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  resolved_at TIMESTAMP(6) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_gap_material_property_type_version (
    material_id, property_definition_id, gap_type, algorithm_version
  ),
  KEY ix_gap_score (status, gap_score),
  CONSTRAINT fk_gap_material FOREIGN KEY (material_id) REFERENCES mat_material(id),
  CONSTRAINT fk_gap_property FOREIGN KEY (property_definition_id) REFERENCES obs_property_definition(id),
  CONSTRAINT ck_gap_type CHECK (gap_type IN ('missing','sparse','conflicting','condition_gap','composition_gap','method_gap')),
  CONSTRAINT ck_gap_score CHECK (gap_score >= 0 AND gap_score <= 1),
  CONSTRAINT ck_gap_coverage CHECK (condition_coverage_score IS NULL OR (condition_coverage_score >= 0 AND condition_coverage_score <= 1)),
  CONSTRAINT ck_gap_conflict CHECK (conflict_score IS NULL OR (conflict_score >= 0 AND conflict_score <= 1)),
  CONSTRAINT ck_gap_status CHECK (status IN ('open','acknowledged','resolved','dismissed'))
) ENGINE=InnoDB;
