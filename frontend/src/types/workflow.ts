export type VerificationStatus =
  | 'AI_EXTRACTED'
  | 'AI_VALIDATED'
  | 'HUMAN_REVIEWED'
  | 'VERIFIED'
  | 'DISPUTED'
  | 'RETRACTED'

export type TermOption = {
  id: string
  namespace: string
  code: string
  label: string
  definition: string | null
}

export type PropertyOption = {
  id: string
  code: string
  name: string
  canonical_unit: string | null
}

export type MaterialSummary = {
  id: string
  canonical_formula: string
  chemical_system: string
  name: string | null
}

export type PaperSummary = {
  id: string
  title: string
  doi: string | null
  publication_year: number | null
}

export type EvidenceItem = {
  id: string
  paper_id: string
  paper_title: string
  paper_doi: string | null
  document_id: string
  storage_uri: string
  page_number: number
  section: string | null
  figure_number: string | null
  table_number: string | null
  text_snippet: string
}

export type ObservationDetail = {
  id: string
  verification_status: VerificationStatus
  row_version: number
  created_at: string
  updated_at: string
  value_kind: string
  value_numeric: number | null
  value_min: number | null
  value_max: number | null
  value_text: string | null
  value_boolean: boolean | null
  original_value_text: string | null
  original_unit_text: string | null
  normalized_value: number | null
  normalized_unit: string | null
  uncertainty_lower: number | null
  uncertainty_upper: number | null
  condition_temperature_value: number | null
  condition_temperature_unit: string | null
  quality_score: number | null
  property: {
    code: string
    name: string
    canonical_unit: string | null
  }
  material: {
    id: string
    canonical_formula: string
    chemical_system: string
    name: string | null
  }
  sample: {
    id: string
    sample_label: string
    sample_type_label: string
    thickness_value: number | null
    thickness_unit: string | null
  }
  measurement: {
    id: string
    measurement_type_label: string
    temperature_value: number | null
    temperature_unit: string | null
  } | null
  evidence: EvidenceItem[]
}

export type IntakeFormPayload = {
  paperMode: 'existing' | 'new'
  existingPaperId: string
  newPaperTitle: string
  newPaperDoi: string
  newPaperJournal: string
  newPaperYear: string

  docStorageUri: string
  docSha256: string
  docType: string

  materialMode: 'existing' | 'new'
  existingMaterialId: string
  newMaterialFormula: string
  newMaterialSystem: string
  newMaterialName: string

  sampleLabel: string
  sampleTypeTermId: string
  sampleThickness: string
  sampleThicknessUnit: string
  sampleSubstrate: string

  measTypeTermId: string
  measInstrument: string
  measTemp: string
  measTempUnit: string

  propertyId: string
  originalValue: string
  originalUnit: string
  uncertaintyLower: string
  uncertaintyUpper: string

  evdPage: string
  evdSection: string
  evdFigure: string
  evdTable: string
  evdText: string
}

export type ProblemDetail = {
  type?: string
  title?: string
  status: number
  detail?: string
  request_id?: string
  errors?: Array<{ loc: string[]; msg: string; type: string }>
}
