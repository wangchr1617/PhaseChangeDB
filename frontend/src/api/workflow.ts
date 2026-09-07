import type {
  IntakeFormPayload,
  MaterialSummary,
  ObservationDetail,
  PaperSummary,
  ProblemDetail,
  PropertyOption,
  TermOption,
  VerificationStatus,
} from '../types/workflow'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  status: number
  problem?: ProblemDetail

  constructor(message: string, status: number, problem?: ProblemDetail) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.problem = problem
  }
}

async function apiFetch<T>(path: string, init?: RequestInit, token?: string): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
  }
  if (token?.trim()) {
    headers['Authorization'] = `Bearer ${token.trim()}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    let problem: ProblemDetail | undefined
    let message = `请求失败（${response.status}）`
    try {
      const data = await response.json()
      problem = data as ProblemDetail
      if (problem.detail) {
        message = `${problem.title ? problem.title + ': ' : ''}${problem.detail}`
      }
    } catch {
      // 无法解析 JSON
    }
    throw new ApiError(message, response.status, problem)
  }

  return response.json() as Promise<T>
}

export async function fetchPapers(): Promise<PaperSummary[]> {
  const res = await apiFetch<{ items: PaperSummary[] }>('/v1/papers?limit=100')
  return res.items
}

export async function fetchMaterials(): Promise<MaterialSummary[]> {
  const res = await apiFetch<{ items: MaterialSummary[] }>('/v1/materials?limit=100')
  return res.items
}

export async function fetchProperties(): Promise<PropertyOption[]> {
  return apiFetch<PropertyOption[]>('/v1/properties')
}

export async function fetchTerms(namespace: string): Promise<TermOption[]> {
  return apiFetch<TermOption[]>(`/v1/workflow/terms?namespace=${encodeURIComponent(namespace)}`)
}

export async function fetchObservationDetail(observationId: string): Promise<ObservationDetail> {
  return apiFetch<ObservationDetail>(`/v1/workflow/observations/${observationId}`)
}

export async function submitIntake(
  form: IntakeFormPayload,
  idempotencyKey: string,
  reviewerToken: string
): Promise<{ observation_id: string; row_version: number }> {
  const numericVal = parseFloat(form.originalValue)
  const isNum = !isNaN(numericVal)

  const body: Record<string, unknown> = {
    document: {
      storage_uri: form.docStorageUri.trim(),
      sha256: form.docSha256.trim().toLowerCase(),
      document_type: form.docType || 'main_article',
    },
    sample: {
      sample_label: form.sampleLabel.trim(),
      sample_type_term_id: form.sampleTypeTermId,
      thickness_value: form.sampleThickness ? parseFloat(form.sampleThickness) : null,
      thickness_unit: form.sampleThicknessUnit.trim() || null,
      substrate_material: form.sampleSubstrate.trim() || null,
    },
    evidence: {
      page_number: parseInt(form.evdPage, 10),
      section: form.evdSection.trim() || null,
      figure_number: form.evdFigure.trim() || null,
      table_number: form.evdTable.trim() || null,
      text_snippet: form.evdText.trim(),
      fragment_type: 'paragraph',
    },
    measurement: {
      measurement_type_term_id: form.measTypeTermId,
      instrument: form.measInstrument.trim() || null,
      temperature_value: form.measTemp ? parseFloat(form.measTemp) : null,
      temperature_unit: form.measTempUnit.trim() || null,
    },
    observation: {
      property_definition_id: form.propertyId,
      value_kind: 'scalar',
      value_numeric: isNum ? numericVal : null,
      original_value_text: form.originalValue.trim(),
      normalized_value: null,
      normalized_unit_term_id: null,
      uncertainty_lower: form.uncertaintyLower ? parseFloat(form.uncertaintyLower) : null,
      uncertainty_upper: form.uncertaintyUpper ? parseFloat(form.uncertaintyUpper) : null,
      condition_temperature_value: form.measTemp ? parseFloat(form.measTemp) : null,
      condition_temperature_unit: form.measTempUnit.trim() || null,
      verification_status: 'HUMAN_REVIEWED',
    },
  }

  if (form.paperMode === 'existing') {
    body.paper_id = form.existingPaperId
  } else {
    body.paper = {
      title: form.newPaperTitle.trim(),
      doi: form.newPaperDoi.trim() || null,
      journal: form.newPaperJournal.trim() || null,
      publication_year: form.newPaperYear ? parseInt(form.newPaperYear, 10) : null,
    }
  }

  if (form.materialMode === 'existing') {
    body.material_id = form.existingMaterialId
  } else {
    body.material = {
      canonical_formula: form.newMaterialFormula.trim(),
      reduced_formula: form.newMaterialFormula.trim(),
      chemical_system: form.newMaterialSystem.trim(),
      name: form.newMaterialName.trim() || null,
      aliases: [],
    }
  }

  return apiFetch<{ observation_id: string; row_version: number }>(
    '/v1/workflow/intake',
    {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(body),
    },
    reviewerToken
  )
}

export async function submitReview(
  observationId: string,
  decision: VerificationStatus,
  comment: string | null,
  reviewer: string,
  rowVersion: number,
  reviewerToken: string
): Promise<{ observation_id: string; new_status: VerificationStatus; row_version: number }> {
  return apiFetch<{ observation_id: string; new_status: VerificationStatus; row_version: number }>(
    `/v1/workflow/observations/${observationId}/review`,
    {
      method: 'POST',
      headers: {
        'If-Match': `W/"${rowVersion}"`,
      },
      body: JSON.stringify({
        decision,
        comment: comment?.trim() || null,
        reviewer: reviewer.trim(),
      }),
    },
    reviewerToken
  )
}
