export interface ParsedPaperPreview {
  file_id: string
  filename: string
  file_size: number
  title: string
  journal?: string | null
  publication_year?: number | null
  first_author?: string | null
  corresponding_author?: string | null
  doi?: string | null
  abstract?: string | null
  status: 'parsed' | 'failed'
  error_message?: string | null
}

export interface BatchUploadResponse {
  total_files: number
  parsed_count: number
  failed_count: number
  items: ParsedPaperPreview[]
}

export interface BatchIngestItem {
  title: string
  journal?: string | null
  publication_year?: number | null
  first_author?: string | null
  corresponding_author?: string | null
  doi?: string | null
  abstract?: string | null
  metadata?: Record<string, unknown> | null
}

export interface BatchIngestRequest {
  items: BatchIngestItem[]
}

export interface BatchIngestResponse {
  total: number
  succeeded: number
  skipped: number
  failed: number
  papers: Array<{
    id: string
    title: string
    doi: string | null
    journal: string | null
    publication_year: number | null
    first_author?: string | null
    corresponding_author?: string | null
  }>
}

export interface ConflictObservationItem {
  observation_id: string
  property_code: string
  property_name: string
  value?: number | string | boolean | null
  display_value: string
  normalized_value?: number | null
  normalized_unit?: string | null
  condition_temperature?: string | null
  condition_pressure?: string | null
  measurement_instrument?: string | null
  paper_id?: string | null
  paper_title?: string | null
  paper_doi?: string | null
  first_author?: string | null
  corresponding_author?: string | null
  journal?: string | null
  publication_year?: number | null
  verification_status: string
  quality_score?: number | null
}

export interface ObservationConflictGroup {
  material_id: string
  material_formula: string
  property_code: string
  property_name: string
  conflict_type: 'condition_discrepancy' | 'explicit_dispute'
  discrepancy_description: string
  items: ConflictObservationItem[]
}

export interface LiteratureAgentConfig {
  agent_name: string
  version: string
  enabled: boolean
  available_models: string[]
  default_model: string
  prompt_version: string
  ontology_version: string
  auto_staging_enabled: boolean
  require_human_review: boolean
}
