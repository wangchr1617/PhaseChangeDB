USE phasechangedb;

-- MVP 演示数据。固定 UUID 便于本地环境重复识别，所有科学观测均关联原始证据。
INSERT INTO ont_term (id, namespace, code, label, definition)
VALUES (UNHEX(REPLACE('01a06670-0000-7000-8000-000000000007','-','')), 'measurement_type', 'dsc', '差示扫描量热法', 'Differential scanning calorimetry');

INSERT INTO lit_paper (id, doi, title, journal, publication_year, abstract)
VALUES (
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000001','-','')),
  '10.1038/nmat2009',
  'Phase-change materials for rewriteable data storage',
  'Nature Materials',
  2008,
  '用于本地 MVP 演示的相变材料综述记录。'
);

INSERT INTO sys_artifact (id, storage_uri, sha256_hex, mime_type, original_filename)
VALUES (
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000002','-','')),
  'demo://paper/nmat2009',
  '93a44bbbb96c751ca06b526fe571763aa6113791b97777227b0998b8f1f5d8c3',
  'application/pdf',
  'phase-change-materials-demo.pdf'
);

INSERT INTO lit_document (id, paper_id, document_type, artifact_id, parse_status)
VALUES (
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000003','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000001','-','')),
  'main_article',
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000002','-','')),
  'parsed'
);

INSERT INTO evd_fragment (id, paper_id, document_id, fragment_type, page_number, section, text_snippet)
VALUES (
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000004','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000001','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000003','-','')),
  'paragraph',
  1,
  'Introduction',
  'MVP 演示证据片段；不能作为真实科研结论引用。'
);

INSERT INTO mat_material (id, canonical_formula, reduced_formula, chemical_system, name, description)
VALUES
  (UNHEX(REPLACE('01a06670-0000-7000-8000-000000000005','-','')), 'Ge2Sb2Te5', 'Ge2Sb2Te5', 'Ge-Sb-Te', 'GST-225', '典型硫属化物相变材料。'),
  (UNHEX(REPLACE('01a06670-0000-7000-8000-000000000010','-','')), 'GeTe', 'GeTe', 'Ge-Te', '碲化锗', '二元相变材料。'),
  (UNHEX(REPLACE('01a06670-0000-7000-8000-000000000011','-','')), 'Sb2Te3', 'Sb2Te3', 'Sb-Te', '碲化锑', '常见相变材料组分。');

INSERT INTO sam_sample (id, nominal_material_id, source_paper_id, sample_label, sample_type_term_id, description)
VALUES (
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000006','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000005','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000001','-','')),
  'GST-DEMO-01',
  UNHEX(REPLACE('01a06666-3c71-7d4e-9cb8-edf582d577fd','-','')),
  '仅用于验证本地 MVP 数据链路。'
);

INSERT INTO exp_measurement (id, sample_id, measurement_type_term_id, temperature_value, temperature_unit, source_paper_id, evidence_id)
VALUES (
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000008','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000006','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000007','-','')),
  300,
  'K',
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000001','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000004','-',''))
);

INSERT INTO obs_observation (
  id, sample_id, property_definition_id, measurement_id, value_kind,
  value_numeric, original_value_text, original_unit_text, normalized_value,
  normalized_unit_term_id, quality_score, verification_status
)
VALUES (
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000009','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000006','-','')),
  UNHEX(REPLACE('01a06666-90fe-7a0f-88d7-afad67e17652','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000008','-','')),
  'scalar',
  453,
  '453 K',
  'K',
  453,
  UNHEX(REPLACE('01a06666-3c71-7c33-ab52-f93946c91c5b','-','')),
  0.85,
  'HUMAN_REVIEWED'
);

INSERT INTO evd_observation_link (observation_id, evidence_fragment_id, evidence_role, confidence)
VALUES (
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000009','-','')),
  UNHEX(REPLACE('01a06670-0000-7000-8000-000000000004','-','')),
  'primary',
  0.85
);
