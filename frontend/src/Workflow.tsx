import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  fetchMaterials,
  fetchObservationDetail,
  fetchPapers,
  fetchProperties,
  fetchTerms,
  submitIntake,
  submitReview,
} from './api/workflow'
import { ObservationDetailView } from './components/ObservationDetailView'
import { WorkflowForm } from './components/WorkflowForm'
import type {
  IntakeFormPayload,
  MaterialSummary,
  ObservationDetail,
  PaperSummary,
  PropertyOption,
  TermOption,
  VerificationStatus,
} from './types/workflow'

interface WorkflowProps {
  onDataChanged?: () => void
}

export function Workflow({ onDataChanged }: WorkflowProps) {
  const [reviewerToken, setReviewerToken] = useState('')
  const [papers, setPapers] = useState<PaperSummary[]>([])
  const [materials, setMaterials] = useState<MaterialSummary[]>([])
  const [properties, setProperties] = useState<PropertyOption[]>([])
  const [sampleTypes, setSampleTypes] = useState<TermOption[]>([])
  const [measurementTypes, setMeasurementTypes] = useState<TermOption[]>([])

  const [currentObservation, setCurrentObservation] = useState<ObservationDetail | null>(null)
  const [observationHistory, setObservationHistory] = useState<string[]>([])
  const [lookupId, setLookupId] = useState('')

  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isReviewing, setIsReviewing] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // 幂等键：只在成功提交或用户重置时刷新
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())

  const loadInitialData = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const [papersList, matsList, propsList, sTypes, mTypes] = await Promise.all([
        fetchPapers(),
        fetchMaterials(),
        fetchProperties(),
        fetchTerms('sample_type'),
        fetchTerms('measurement_type'),
      ])
      setPapers(papersList)
      setMaterials(matsList)
      setProperties(propsList)
      setSampleTypes(sTypes)
      setMeasurementTypes(mTypes)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : '加载选项数据失败')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadInitialData()
  }, [loadInitialData])

  async function openObservation(id: string) {
    if (!id.trim()) return
    setReviewError(null)
    setErrorMessage(null)
    try {
      const detail = await fetchObservationDetail(id.trim())
      setCurrentObservation(detail)
      setObservationHistory((prev) => Array.from(new Set([detail.id, ...prev])))
      setSuccessMessage(`已加载观测 ${detail.id}`)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : '加载观测详情失败')
    }
  }

  async function handleIntakeSubmit(form: IntakeFormPayload) {
    setIsSubmitting(true)
    setErrorMessage(null)
    setSuccessMessage(null)
    try {
      const result = await submitIntake(form, idempotencyKey, reviewerToken)
      setSuccessMessage(`科学数据入库成功！观测 ID: ${result.observation_id}`)
      // 生成新的幂等键供下一次提交使用
      setIdempotencyKey(crypto.randomUUID())

      // 刷新外部数据列表与概览
      onDataChanged?.()
      await loadInitialData()

      // 自动加载新建观测详情
      await openObservation(result.observation_id)
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(`提交失败 [${err.status}]: ${err.message}`)
      } else {
        setErrorMessage(err instanceof Error ? err.message : '网络或服务异常')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleReviewSubmit(
    decision: VerificationStatus,
    comment: string | null,
    reviewer: string
  ) {
    if (!currentObservation) return
    setIsReviewing(true)
    setReviewError(null)
    setSuccessMessage(null)
    try {
      const result = await submitReview(
        currentObservation.id,
        decision,
        comment,
        reviewer,
        currentObservation.row_version,
        reviewerToken
      )
      setSuccessMessage(`审核状态已更新为 ${result.new_status} (新版本 W/"${result.row_version}")`)
      onDataChanged?.()
      // 重新加载该观测的最新详情
      await openObservation(currentObservation.id)
    } catch (err) {
      if (err instanceof ApiError) {
        setReviewError(`审核失败 [${err.status}]: ${err.message}`)
      } else {
        setReviewError(err instanceof Error ? err.message : '审核请求失败')
      }
    } finally {
      setIsReviewing(false)
    }
  }

  if (isLoading) {
    return <div className="loading-container">正在加载工作流元数据及下拉选项…</div>
  }

  return (
    <div className="workflow-container">
      {successMessage && <div className="success-banner">{successMessage}</div>}

      <div className="workflow-lookup-bar card">
        <label htmlFor="wf-lookup-input">根据 ID 查看已有观测及证据链：</label>
        <div className="lookup-input-group">
          <input
            id="wf-lookup-input"
            type="text"
            placeholder="输入观测 UUID（例如: 01a06670-0000-7000-8000-000000000009）"
            value={lookupId}
            onChange={(e) => setLookupId(e.target.value)}
          />
          <button type="button" onClick={() => void openObservation(lookupId)}>
            查询详情
          </button>
        </div>
        {observationHistory.length > 0 && (
          <div className="history-tags">
            <span className="hint">最近打开:</span>
            {observationHistory.map((id) => (
              <button
                key={id}
                type="button"
                className="chip-button"
                onClick={() => {
                  setLookupId(id)
                  void openObservation(id)
                }}
              >
                {id.slice(0, 8)}…
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="workflow-split-layout">
        {/* 左侧：完整录入表单 */}
        <div className="workflow-form-pane">
          <WorkflowForm
            papers={papers}
            materials={materials}
            properties={properties}
            sampleTypes={sampleTypes}
            measurementTypes={measurementTypes}
            reviewerToken={reviewerToken}
            onReviewerTokenChange={setReviewerToken}
            onSubmit={handleIntakeSubmit}
            isSubmitting={isSubmitting}
            errorMessage={errorMessage}
          />
        </div>

        {/* 右侧：观测详情与审核控制 */}
        <div className="workflow-detail-pane">
          {currentObservation ? (
            <ObservationDetailView
              observation={currentObservation}
              reviewerToken={reviewerToken}
              onReviewerTokenChange={setReviewerToken}
              onReviewSubmit={handleReviewSubmit}
              isReviewing={isReviewing}
              reviewError={reviewError}
            />
          ) : (
            <div className="card placeholder-card">
              <h3>观测溯源与审核面板</h3>
              <p className="hint">
                在左侧提交完整科学记录，或在上方输入已有观测 UUID 查询，即可在此查看完整证据原文、论文出处、页码并执行人工审核流转。
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
