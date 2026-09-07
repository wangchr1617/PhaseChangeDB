import { useState } from 'react'
import type { ObservationDetail, VerificationStatus } from '../types/workflow'

interface ObservationDetailViewProps {
  observation: ObservationDetail
  reviewerToken: string
  onReviewerTokenChange: (token: string) => void
  onReviewSubmit: (
    decision: VerificationStatus,
    comment: string | null,
    reviewer: string
  ) => Promise<void>
  isReviewing: boolean
  reviewError: string | null
}

export function ObservationDetailView({
  observation,
  reviewerToken,
  onReviewerTokenChange,
  onReviewSubmit,
  isReviewing,
  reviewError,
}: ObservationDetailViewProps) {
  const [reviewer, setReviewer] = useState('Dr. Scientist')
  const [comment, setComment] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  const isRetracted = observation.verification_status === 'RETRACTED'

  async function handleReview(decision: VerificationStatus) {
    setLocalError(null)
    if (!reviewerToken.trim()) {
      setLocalError('必须提供 Reviewer Token 才能执行审核。')
      return
    }
    if (!reviewer.trim()) {
      setLocalError('必须填写审核人姓名。')
      return
    }
    await onReviewSubmit(decision, comment, reviewer)
    setComment('')
  }

  return (
    <section className="observation-detail-panel card" aria-label="观测值溯源与审核">
      <div className="panel-header">
        <div>
          <h2>观测详情与完整证据链</h2>
          <p className="hint">ID: {observation.id}</p>
        </div>
        <div className="status-badges">
          <span className={`status-badge status-${observation.verification_status.toLowerCase()}`}>
            {observation.verification_status}
          </span>
          <span className="version-badge">版本: W/"{observation.row_version}"</span>
        </div>
      </div>

      {/* 核心观测数值卡片 */}
      <div className="obs-summary-grid">
        <div className="obs-summary-card">
          <span className="label">材料 (Material)</span>
          <strong>{observation.material.canonical_formula}</strong>
          <small>{observation.material.chemical_system} {observation.material.name ? `· ${observation.material.name}` : ''}</small>
        </div>

        <div className="obs-summary-card">
          <span className="label">属性 (Property)</span>
          <strong>{observation.property.name} ({observation.property.code})</strong>
          <small>标准单位: {observation.property.canonical_unit ?? '无'}</small>
        </div>

        <div className="obs-summary-card">
          <span className="label">原始报告值 (Original)</span>
          <strong className="accent-val">{observation.original_value_text} {observation.original_unit_text}</strong>
          <small>
            归一化: {observation.normalized_value ?? '—'} {observation.normalized_unit ?? ''}
          </small>
        </div>

        <div className="obs-summary-card">
          <span className="label">样品与测量条件</span>
          <strong>{observation.sample.sample_label} ({observation.sample.sample_type_label})</strong>
          <small>
            温度: {observation.condition_temperature_value ?? '—'} {observation.condition_temperature_unit ?? ''}
            {observation.uncertainty_lower !== null && observation.uncertainty_upper !== null
              ? ` · 不确定度: ±[${observation.uncertainty_lower}, ${observation.uncertainty_upper}]`
              : ''}
          </small>
        </div>
      </div>

      {/* 证据溯源片段列表 */}
      <div className="evidence-section">
        <h3>关联原始科学证据 ({observation.evidence.length} 条)</h3>
        {observation.evidence.length === 0 ? (
          <p className="empty-hint">此观测记录尚未关联任何证据片段（无法晋升为 VERIFIED）。</p>
        ) : (
          <div className="evidence-cards">
            {observation.evidence.map((evd, idx) => (
              <div key={evd.id || idx} className="evidence-card">
                <div className="evidence-meta">
                  <span className="evidence-source">
                    📄 <strong>{evd.paper_title}</strong>
                    {evd.paper_doi ? ` (DOI: ${evd.paper_doi})` : ''}
                  </span>
                  <span className="evidence-loc">
                    第 {evd.page_number} 页
                    {evd.section ? ` · 章节: ${evd.section}` : ''}
                    {evd.figure_number ? ` · 图号: ${evd.figure_number}` : ''}
                    {evd.table_number ? ` · 表号: ${evd.table_number}` : ''}
                  </span>
                </div>
                {evd.storage_uri && (
                  <div className="evidence-uri">
                    <small>制品存储 URI: <code>{evd.storage_uri}</code></small>
                  </div>
                )}
                <blockquote className="evidence-quote">
                  “{evd.text_snippet}”
                </blockquote>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 审核控制面板 */}
      <div className="review-action-box highlight-box">
        <h3>人工审核流转（Human Review & Verification）</h3>
        <p className="hint">
          受乐观锁 <code>If-Match: W/"{observation.row_version}"</code> 与 Reviewer Token 严格保护。
        </p>

        {isRetracted ? (
          <div className="warning-banner">
            ⚠️ 此观测已被撤回（RETRACTED）。已撤回科学记录为终态，不可逆。
          </div>
        ) : (
          <div className="review-controls">
            <div className="form-grid">
              <div className="form-row">
                <label htmlFor="rd-reviewer-token">Reviewer Token <span className="required">*</span></label>
                <input
                  id="rd-reviewer-token"
                  type="password"
                  placeholder="PCM_REVIEWER_TOKEN"
                  value={reviewerToken}
                  onChange={(e) => onReviewerTokenChange(e.target.value)}
                  disabled={isReviewing}
                />
              </div>
              <div className="form-row">
                <label htmlFor="rd-reviewer">审核人员标识 (Reviewer) <span className="required">*</span></label>
                <input
                  id="rd-reviewer"
                  type="text"
                  value={reviewer}
                  onChange={(e) => setReviewer(e.target.value)}
                  disabled={isReviewing}
                  placeholder="例如: 张三 (Reviewer #1)"
                />
              </div>
              <div className="form-row full-width">
                <label htmlFor="rd-comment">审核意见 / 说明 (Comment)</label>
                <input
                  id="rd-comment"
                  type="text"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  disabled={isReviewing}
                  placeholder="说明审核决定与科学核实理由..."
                />
              </div>
            </div>

            {localError && <div className="error-banner">{localError}</div>}
            {reviewError && <div className="error-banner">{reviewError}</div>}

            <div className="button-group">
              {observation.verification_status === 'AI_EXTRACTED' && (
                <button
                  type="button"
                  className="btn-review"
                  onClick={() => void handleReview('HUMAN_REVIEWED')}
                  disabled={isReviewing}
                >
                  {isReviewing ? '处理中…' : '标记为人工已审核 (HUMAN_REVIEWED)'}
                </button>
              )}

              {observation.verification_status === 'HUMAN_REVIEWED' && (
                <button
                  type="button"
                  className="btn-verify"
                  onClick={() => void handleReview('VERIFIED')}
                  disabled={isReviewing}
                >
                  {isReviewing ? '处理中…' : '验证通过 (VERIFIED)'}
                </button>
              )}

              {['AI_EXTRACTED', 'HUMAN_REVIEWED', 'VERIFIED'].includes(observation.verification_status) && (
                <button
                  type="button"
                  className="btn-dispute"
                  onClick={() => void handleReview('DISPUTED')}
                  disabled={isReviewing}
                >
                  标记为存疑/争议 (DISPUTED)
                </button>
              )}

              {observation.verification_status === 'DISPUTED' && (
                <button
                  type="button"
                  className="btn-review"
                  onClick={() => void handleReview('HUMAN_REVIEWED')}
                  disabled={isReviewing}
                >
                  重新复核 (HUMAN_REVIEWED)
                </button>
              )}

              <button
                type="button"
                className="btn-retract"
                onClick={() => void handleReview('RETRACTED')}
                disabled={isReviewing}
              >
                撤回观测记录 (RETRACTED)
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
