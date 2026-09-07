-- PhaseChangeDB v0.2.0
-- Idempotency key tracking table
USE phasechangedb;

CREATE TABLE IF NOT EXISTS sys_idempotency_key (
  idempotency_key VARCHAR(255) NOT NULL,
  request_path VARCHAR(255) NOT NULL,
  request_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  response_status INT NOT NULL,
  response_json JSON NOT NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (idempotency_key),
  KEY ix_idempotency_created (created_at)
) ENGINE=InnoDB;
