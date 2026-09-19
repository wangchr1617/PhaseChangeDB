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

export interface YearCountItem {
  year: number
  count: number
}

export interface JournalCountItem {
  journal: string
  count: number
}

export interface AuthorCountItem {
  author: string
  count: number
}

export interface SystemCountItem {
  chemical_system: string
  count: number
}

export interface LiteratureStatsResponse {
  total_papers: number
  year_distribution: YearCountItem[]
  journal_distribution: JournalCountItem[]
  author_distribution: AuthorCountItem[]
  system_distribution: SystemCountItem[]
}

export interface GraphNode {
  id: string
  label: string
  node_type:
    | 'material'
    | 'element'
    | 'system'
    | 'property'
    | 'paper'
    | 'first_author'
    | 'corresponding_author'
    | 'author'
    | 'journal'
    | 'dopant'
    | 'observation'
  properties?: Record<string, unknown>
  // 仿真动力学计算属性
  x?: number
  y?: number
  vx?: number
  vy?: number
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  edge_type: string
  label?: string | null
  properties?: Record<string, unknown>
}

export interface GraphSummary {
  total_nodes: number
  total_edges: number
  material_count: number
  paper_count: number
  element_count: number
  property_count: number
  system_count?: number
  author_count?: number
  journal_count?: number
  dopant_count?: number
  observation_count?: number
}

export interface KnowledgeGraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  summary: GraphSummary
}

export interface PropertyComparisonDataPoint {
  observation_id: string
  property_code: string
  property_name: string
  material_formula: string
  base_material: string
  dopant_element?: string | null
  dopant_at_pct?: number | null
  sample_formula?: string | null
  value?: number | null
  unit?: string | null
  normalized_value?: number | null
  normalized_unit?: string | null
  heating_rate_k_per_min?: number | null
  measurement_method?: string | null
  film_thickness_nm?: number | null
  substrate?: string | null
  paper_id?: string | null
  paper_title?: string | null
  paper_doi?: string | null
  paper_year?: number | null
  first_author?: string | null
  evidence_snippet?: string | null
  figure_or_table?: string | null
  page_number?: number | null
  verification_status: string
  quality_score?: number | null

  // 兼容旧字段
  material_id?: string
  sample_id?: string
  dopant_concentration?: number | null
  sample_label?: string | null
  value_numeric?: number | null
  original_unit?: string | null
  heating_rate_value?: number | null
  heating_rate_unit?: string | null
  publication_year?: number | null
  figure_reference?: string | null
  journal?: string | null
}

export interface PropertyBoxPlotStat {
  group_name: string
  count: number
  min_val: number
  q1: number
  median: number
  q3: number
  max_val: number
  min?: number
  max?: number
  mean?: number
  unit?: string
}

export interface PropertyComparisonResponse {
  property_code: string
  property_name: string
  display_unit: string
  total_count: number
  data_points: PropertyComparisonDataPoint[]
  box_plot_stats: PropertyBoxPlotStat[]
  available_properties: Array<{ code: string; name: string }>
  available_materials: string[]
  available_heating_rates: number[]
  unit?: string
  available_base_materials?: string[]
}

export interface VariantObservationRead {
  id: string
  property_code: string
  property_name: string
  value?: number | string | boolean | null
  unit?: string | null
  display_value?: string | null
  verification_status: string
}

export interface MaterialVariantRead {
  sample_id: string
  sample_label?: string | null
  nominal_formula: string
  original_name?: string | null
  doping_element?: string | null
  doping_concentration?: number | null
  preparation_method?: string | null
  annealing_temperature?: string | null
  pressure?: string | null
  test_method?: string | null
  crystal_phase?: string | null
  atmosphere?: string | null
  cooling_rate?: string | null
  paper_id?: string | null
  paper_title?: string | null
  paper_doi?: string | null
  first_author?: string | null
  corresponding_author?: string | null
  journal?: string | null
  publication_year?: number | null
  observations: VariantObservationRead[]
}
