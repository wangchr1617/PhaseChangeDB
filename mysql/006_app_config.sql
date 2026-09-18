-- PhaseChangeDB v0.3.0
-- Application configuration persistence (app title, description, custom logo)
USE phasechangedb;

CREATE TABLE IF NOT EXISTS sys_app_config (
  config_key VARCHAR(64) NOT NULL,
  config_value MEDIUMTEXT NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (config_key)
) ENGINE=InnoDB;

INSERT INTO sys_app_config (config_key, config_value)
VALUES
  ('app_title', 'PhaseChangeDB'),
  ('app_description', '相变材料知识库'),
  ('app_logo', '/logo.svg')
ON DUPLICATE KEY UPDATE config_value = config_value;
