import { useState } from 'react'
import type { ChangeEvent, DragEvent, FormEvent } from 'react'
import type { BatchIngestRequest, BatchIngestResponse, BatchUploadResponse, ParsedPaperPreview } from '../types/batch'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

interface BatchUploadModalProps {
  onClose: () => void
  onSuccess: () => void
}

export function BatchUploadModal({ onClose, onSuccess }: BatchUploadModalProps) {
  const [isUploading, setIsUploading] = useState(false)
  const [isIngesting, setIsIngesting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<string | null>(null)
  const [previews, setPreviews] = useState<ParsedPaperPreview[]>([])
  const [ingestSummary, setIngestSummary] = useState<BatchIngestResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)

  // 处理文件选择
  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const filesArray = Array.from(e.target.files)
      setError(null)
      void handleUploadFiles(filesArray)
    }
  }

  // 处理拖拽
  const handleDragOver = (e: DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e: DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const filesArray = Array.from(e.dataTransfer.files)
      setError(null)
      void handleUploadFiles(filesArray)
    }
  }


  // 调用 /v1/literature/batch-upload 进行解析
  const handleUploadFiles = async (files: File[]) => {
    if (files.length === 0) return
    setIsUploading(true)
    setUploadProgress(`正在上传并解析 ${files.length} 个文献文件…`)
    setError(null)

    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))

    try {
      const res = await fetch(`${API_BASE}/v1/literature/batch-upload`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => null)
        throw new Error(errJson?.detail ?? `上传解析失败 (${res.status})`)
      }
      const data: BatchUploadResponse = await res.json()
      setPreviews(data.items)
      setUploadProgress(`解析完成：成功 ${data.parsed_count} 个，需注意 ${data.failed_count} 个`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传发生错误')
    } finally {
      setIsUploading(false)
    }
  }

  // 行内修改字段
  const updateField = (index: number, field: keyof ParsedPaperPreview, value: string | number | null) => {
    setPreviews((prev) => {
      const copy = [...prev]
      copy[index] = { ...copy[index], [field]: value }
      return copy
    })
  }

  // 移除单行
  const removeRow = (index: number) => {
    setPreviews((prev) => prev.filter((_, i) => i !== index))
  }

  // 提交批量入库
  const handleBatchIngest = async (e: FormEvent) => {
    e.preventDefault()
    if (previews.length === 0) {
      setError('没有可入库的文献')
      return
    }

    setIsIngesting(true)
    setError(null)

    const payload: BatchIngestRequest = {
      items: previews.map((p) => ({
        title: p.title.trim(),
        journal: p.journal ? p.journal.trim() : null,
        publication_year: p.publication_year ? Number(p.publication_year) : null,
        first_author: p.first_author ? p.first_author.trim() : null,
        corresponding_author: p.corresponding_author ? p.corresponding_author.trim() : null,
        doi: p.doi ? p.doi.trim() : null,
        abstract: p.abstract ? p.abstract.trim() : null,
      })),
    }

    try {
      const res = await fetch(`${API_BASE}/v1/literature/batch-ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => null)
        throw new Error(errJson?.detail ?? `批量入库失败 (${res.status})`)
      }
      const data: BatchIngestResponse = await res.json()
      setIngestSummary(data)
      onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : '入库处理失败')
    } finally {
      setIsIngesting(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="modal batch-modal"
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="batch-modal-header">
          <div>
            <span className="eyebrow">多文件快速入库</span>
            <h2>批量上传文献与智能解析核验</h2>
          </div>
          <button className="close-btn" onClick={onClose} aria-label="关闭">×</button>
        </div>

        <div className="batch-modal-body">
          {/* 入库成功报表 */}
          {ingestSummary && (
            <div className="ingest-result-banner">
              <div className="result-header">
                <h3>🎉 批量入库处理完成</h3>
                <span className="result-total">共处理 {ingestSummary.total} 篇文献</span>
              </div>
              <div className="result-stats-row">
                <div className="stat-pill success">
                  <strong>{ingestSummary.succeeded}</strong> 篇成功入库
                </div>
                <div className="stat-pill skipped">
                  <strong>{ingestSummary.skipped}</strong> 篇重复已跳过
                </div>
                {ingestSummary.failed > 0 && (
                  <div className="stat-pill failed">
                    <strong>{ingestSummary.failed}</strong> 篇异常
                  </div>
                )}
              </div>
              <p className="result-hint">数据已同步至 MySQL 权威数据库并写入 Outbox 投影事件，主文献目录已自动刷新。</p>
              <div className="result-actions">
                <button type="button" className="primary" onClick={onClose}>
                  完成并关闭
                </button>
              </div>
            </div>
          )}

          {!ingestSummary && (
            <>
              {/* 上传区域 */}
              <div
                className={`batch-dropzone ${isDragOver ? 'drag-over' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <div className="dropzone-icon">📄</div>
                <div className="dropzone-text">
                  <strong>点击选择或将文献文件拖拽至此</strong>
                  <p>支持批量多选 PDF、arXiv XML、BibTeX (.bib)、JSON 或纯文本文献源</p>
                </div>
                <label className="file-select-btn">
                  <span>选择本地文件 (支持多选)</span>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.xml,.json,.bib,.txt"
                    onChange={handleFileChange}
                    className="file-input-hidden"
                  />
                </label>
              </div>

              {/* 上传状态条 */}
              {isUploading && (
                <div className="batch-progress-bar">
                  <div className="spinner-small" />
                  <span>{uploadProgress || '正在读取并启发式抽取文献元数据…'}</span>
                </div>
              )}

              {error && <div className="error-banner">⚠️ {error}</div>}

              {/* 预览与人工核验表格 */}
              {previews.length > 0 && (
                <div className="batch-preview-section">
                  <div className="preview-header">
                    <h3>
                      📋 解析结果核验与修正预览 ({previews.length} 篇)
                    </h3>
                    <span className="preview-sub">
                      请核对抽取的标题、期刊、第一作者、通讯作者与 DOI。点击单元格可直接修正。
                    </span>
                  </div>

                  <div className="table-wrap batch-table-wrap">
                    <table className="batch-table">
                      <thead>
                        <tr>
                          <th style={{ width: '40px' }}>#</th>
                          <th style={{ width: '24%' }}>文献标题 (Title) *</th>
                          <th style={{ width: '15%' }}>期刊 (Journal)</th>
                          <th style={{ width: '13%' }}>第一作者</th>
                          <th style={{ width: '13%' }}>通讯作者</th>
                          <th style={{ width: '17%' }}>DOI 号</th>
                          <th style={{ width: '8%' }}>年份</th>
                          <th style={{ width: '60px' }}>操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {previews.map((p, idx) => (
                          <tr key={p.file_id || idx} className={p.status === 'failed' ? 'row-warning' : ''}>
                            <td className="row-num">{idx + 1}</td>
                            <td>
                              <input
                                className="cell-input"
                                value={p.title}
                                placeholder="输入文献标题"
                                required
                                onChange={(e) => updateField(idx, 'title', e.target.value)}
                              />
                              {p.error_message && (
                                <small className="cell-error">{p.error_message}</small>
                              )}
                            </td>
                            <td>
                              <input
                                className="cell-input"
                                value={p.journal ?? ''}
                                placeholder="期刊名称"
                                onChange={(e) => updateField(idx, 'journal', e.target.value)}
                              />
                            </td>
                            <td>
                              <input
                                className="cell-input"
                                value={p.first_author ?? ''}
                                placeholder="第一作者"
                                onChange={(e) => updateField(idx, 'first_author', e.target.value)}
                              />
                            </td>
                            <td>
                              <input
                                className="cell-input"
                                value={p.corresponding_author ?? ''}
                                placeholder="通讯作者"
                                onChange={(e) => updateField(idx, 'corresponding_author', e.target.value)}
                              />
                            </td>
                            <td>
                              <input
                                className="cell-input mono-font"
                                value={p.doi ?? ''}
                                placeholder="10.xxxx/..."
                                onChange={(e) => updateField(idx, 'doi', e.target.value)}
                              />
                            </td>
                            <td>
                              <input
                                className="cell-input num-input"
                                type="number"
                                value={p.publication_year ?? ''}
                                placeholder="年份"
                                onChange={(e) =>
                                  updateField(idx, 'publication_year', e.target.value ? Number(e.target.value) : null)
                                }
                              />
                            </td>
                            <td>
                              <button
                                type="button"
                                className="btn-table-del"
                                onClick={() => removeRow(idx)}
                                title="从本次导入列表中移除"
                              >
                                ✕
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {!ingestSummary && (
          <div className="batch-modal-footer">
            <div className="footer-left-info">
              {previews.length > 0 ? (
                <span>已就绪 <strong>{previews.length}</strong> 篇文献，入库前系统将自动执行 DOI 及标题去重</span>
              ) : (
                <span>请先选择或拖拽文献文件</span>
              )}
            </div>
            <div className="footer-right-buttons">
              <button type="button" className="btn-secondary" onClick={onClose} disabled={isIngesting}>
                取消
              </button>
              <button
                type="button"
                className="primary btn-submit-ingest"
                disabled={previews.length === 0 || isUploading || isIngesting}
                onClick={handleBatchIngest}
              >
                {isIngesting ? '正在入库处理…' : `确认批量入库 (${previews.length} 篇)`}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
