-- PhaseChangeDB v0.2.0
-- Extraction staging and promotion support
USE phasechangedb;

ALTER TABLE ext_candidate
  ADD COLUMN row_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER promoted_entity_id;

ALTER TABLE ext_review
  ADD COLUMN reviewer_name VARCHAR(255) NULL AFTER reviewer_id,
  ADD COLUMN observation_id BINARY(16) NULL AFTER reviewer_name,
  ADD CONSTRAINT fk_review_observation FOREIGN KEY (observation_id) REFERENCES obs_observation(id) ON DELETE SET NULL;
