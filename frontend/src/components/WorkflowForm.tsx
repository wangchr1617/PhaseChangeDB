import { useState } from 'react'
import type { FormEvent } from 'react'
import type {
  IntakeFormPayload,
  MaterialSummary,
  PaperSummary,
  PropertyOption,
  TermOption,
} from '../types/workflow'

interface WorkflowFormProps {
  papers: PaperSummary[]
  materials: MaterialSummary[]
  properties: PropertyOption[]
  sampleTypes: TermOption[]
  measurementTypes: TermOption[]
  reviewerToken: string
  onReviewerTokenChange: (token: string) => void
  onSubmit: (form: IntakeFormPayload) => Promise<void>
  isSubmitting: boolean
  errorMessage: string | null
}

export function WorkflowForm({
  papers,
  materials,
  properties,
  sampleTypes,
  measurementTypes,
  reviewerToken,
  onReviewerTokenChange,
  onSubmit,
  isSubmitting,
  errorMessage,
}: WorkflowFormProps) {
  const [paperMode, setPaperMode] = useState<'existing' | 'new'>('existing')
  const [existingPaperId, setExistingPaperId] = useState(papers[0]?.id || '')
  const [newPaperTitle, setNewPaperTitle] = useState('')
  const [newPaperDoi, setNewPaperDoi] = useState('')
  const [newPaperJournal, setNewPaperJournal] = useState('')
  const [newPaperYear, setNewPaperYear] = useState('')

  const [docStorageUri, setDocStorageUri] = useState('s3://phasechangedb/articles/demo-paper.pdf')
  const [docSha256, setDocSha256] = useState('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
  const [docType, setDocType] = useState('main_article')

  const [materialMode, setMaterialMode] = useState<'existing' | 'new'>('existing')
  const [existingMaterialId, setExistingMaterialId] = useState(materials[0]?.id || '')
  const [newMaterialFormula, setNewMaterialFormula] = useState('')
  const [newMaterialSystem, setNewMaterialSystem] = useState('')
  const [newMaterialName, setNewMaterialName] = useState('')

  const [sampleLabel, setSampleLabel] = useState('')
  const [sampleTypeTermId, setSampleTypeTermId] = useState(sampleTypes[0]?.id || '')
  const [sampleThickness, setSampleThickness] = useState('')
  const [sampleThicknessUnit, setSampleThicknessUnit] = useState('nm')
  const [sampleSubstrate, setSampleSubstrate] = useState('Si/SiO2')

  const [measTypeTermId, setMeasTypeTermId] = useState(measurementTypes[0]?.id || '')
  const [measInstrument, setMeasInstrument] = useState('')
  const [measTemp, setMeasTemp] = useState('')
  const [measTempUnit, setMeasTempUnit] = useState('K')

  const [propertyId, setPropertyId] = useState(properties[0]?.id || '')
  const [originalValue, setOriginalValue] = useState('')
  const [originalUnit, setOriginalUnit] = useState('K')
  const [uncertaintyLower, setUncertaintyLower] = useState('')
  const [uncertaintyUpper, setUncertaintyUpper] = useState('')

  const [evdPage, setEvdPage] = useState('1')
  const [evdSection, setEvdSection] = useState('')
  const [evdFigure, setEvdFigure] = useState('')
  const [evdTable, setEvdTable] = useState('')
  const [evdText, setEvdText] = useState('')

  const [validationError, setValidationError] = useState<string | null>(null)

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setValidationError(null)

    if (!reviewerToken.trim()) {
      setValidationError('必须输入 Reviewer Token 才能执行录入。')
      return
    }

    if (paperMode === 'existing' && !existingPaperId) {
      setValidationError('请选择已有论文，或切换为新建论文。')
      return
    }
    if (paperMode === 'new' && !newPaperTitle.trim()) {
      setValidationError('新建论文必须填写论文标题。')
      return
    }

    if (!docStorageUri.trim() || !docSha256.trim()) {
      setValidationError('请填写文档制品 URI 和 64 位 SHA-256 哈希。')
      return
    }

    if (docSha256.trim().length !== 64) {
      setValidationError('文档 SHA-256 必须为 64 位十六进制字符。')
      return
    }

    if (materialMode === 'existing' && !existingMaterialId) {
      setValidationError('请选择已有材料，或切换为新建材料。')
      return
    }
    if (materialMode === 'new' && (!newMaterialFormula.trim() || !newMaterialSystem.trim())) {
      setValidationError('新建材料必须填写化学式和材料体系。')
      return
    }

    if (!sampleLabel.trim()) {
      setValidationError('请填写实体样品标识（Sample Label）。')
      return
    }

    if (!propertyId) {
      setValidationError('请选择物理/化学属性（PropertyDefinition）。')
      return
    }

    if (!originalValue.trim() || !originalUnit.trim()) {
      setValidationError('请填写原始数值与原始单位。')
      return
    }

    if (!evdPage || parseInt(evdPage, 10) < 1) {
      setValidationError('证据页码必须大于等于 1。')
      return
    }

    if (!evdText.trim()) {
      setValidationError('请填写证据原文片段（Text Snippet）。')
      return
    }

    const payload: IntakeFormPayload = {
      paperMode,
      existingPaperId: existingPaperId || (papers[0]?.id ?? ''),
      newPaperTitle,
      newPaperDoi,
      newPaperJournal,
      newPaperYear,
      docStorageUri,
      docSha256,
      docType,
      materialMode,
      existingMaterialId: existingMaterialId || (materials[0]?.id ?? ''),
      newMaterialFormula,
      newMaterialSystem,
      newMaterialName,
      sampleLabel,
      sampleTypeTermId: sampleTypeTermId || (sampleTypes[0]?.id ?? ''),
      sampleThickness,
      sampleThicknessUnit,
      sampleSubstrate,
      measTypeTermId: measTypeTermId || (measurementTypes[0]?.id ?? ''),
      measInstrument,
      measTemp,
      measTempUnit,
      propertyId: propertyId || (properties[0]?.id ?? ''),
      originalValue,
      originalUnit,
      uncertaintyLower,
      uncertaintyUpper,
      evdPage,
      evdSection,
      evdFigure,
      evdTable,
      evdText,
    }

    void onSubmit(payload)
  }

  return (
    <form className="workflow-form card" onSubmit={handleSubmit} noValidate>
      <h2>人工登记正式科研记录（Human Intake）</h2>
      <p className="hint">
        单次原子事务提交：文献制品 → 材料与样品 → 实验测量 → 证据溯源片段 → 科学观测值（初始状态为 HUMAN_REVIEWED）。AI 提取候选数据必须通过提取暂存与人工晋升闭环入库。
      </p>

      {/* Reviewer Token 区域 */}
      <fieldset className="form-section highlight-box">
        <legend>审核员凭据（Reviewer Authorization）</legend>
        <div className="form-row">
          <label htmlFor="wf-reviewer-token">
            Reviewer Token <span className="required">*</span>
          </label>
          <input
            id="wf-reviewer-token"
            type="password"
            autoComplete="off"
            placeholder="输入本地 PCM_REVIEWER_TOKEN"
            value={reviewerToken}
            onChange={(e) => onReviewerTokenChange(e.target.value)}
            disabled={isSubmitting}
            required
          />
          <small className="help-text">仅在内存中用于请求 Bearer 认证，不持久化到 localStorage 或 URL。</small>
        </div>
      </fieldset>

      {/* 文献与文档 */}
      <fieldset className="form-section">
        <legend>1. 文献与文档制品元数据</legend>
        <div className="radio-group">
          <label>
            <input
              type="radio"
              name="paperMode"
              checked={paperMode === 'existing'}
              onChange={() => setPaperMode('existing')}
              disabled={isSubmitting}
            />
            选择已有论文
          </label>
          <label>
            <input
              type="radio"
              name="paperMode"
              checked={paperMode === 'new'}
              onChange={() => setPaperMode('new')}
              disabled={isSubmitting}
            />
            新建论文记录
          </label>
        </div>

        {paperMode === 'existing' ? (
          <div className="form-row">
            <label htmlFor="wf-existing-paper">已有论文列表</label>
            <select
              id="wf-existing-paper"
              value={existingPaperId}
              onChange={(e) => setExistingPaperId(e.target.value)}
              disabled={isSubmitting || papers.length === 0}
            >
              {papers.length === 0 && <option value="">暂无论文，请先切换新建</option>}
              {papers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} {p.doi ? `(${p.doi})` : ''}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="form-grid">
            <div className="form-row full-width">
              <label htmlFor="wf-paper-title">论文标题 <span className="required">*</span></label>
              <input
                id="wf-paper-title"
                type="text"
                placeholder="例如: Phase change material for rewritable storage"
                value={newPaperTitle}
                onChange={(e) => setNewPaperTitle(e.target.value)}
                disabled={isSubmitting}
              />
            </div>
            <div className="form-row">
              <label htmlFor="wf-paper-doi">DOI</label>
              <input
                id="wf-paper-doi"
                type="text"
                placeholder="10.1038/..."
                value={newPaperDoi}
                onChange={(e) => setNewPaperDoi(e.target.value)}
                disabled={isSubmitting}
              />
            </div>
            <div className="form-row">
              <label htmlFor="wf-paper-journal">期刊名称</label>
              <input
                id="wf-paper-journal"
                type="text"
                placeholder="Nature Materials"
                value={newPaperJournal}
                onChange={(e) => setNewPaperJournal(e.target.value)}
                disabled={isSubmitting}
              />
            </div>
            <div className="form-row">
              <label htmlFor="wf-paper-year">出版年份</label>
              <input
                id="wf-paper-year"
                type="number"
                placeholder="2024"
                value={newPaperYear}
                onChange={(e) => setNewPaperYear(e.target.value)}
                disabled={isSubmitting}
              />
            </div>
          </div>
        )}

        <div className="form-grid" style={{ marginTop: '0.75rem' }}>
          <div className="form-row full-width">
            <label htmlFor="wf-doc-uri">文档存储 URI (storage_uri) <span className="required">*</span></label>
            <input
              id="wf-doc-uri"
              type="text"
              value={docStorageUri}
              onChange={(e) => setDocStorageUri(e.target.value)}
              disabled={isSubmitting}
              placeholder="s3://... 或 https://..."
            />
          </div>
          <div className="form-row full-width">
            <label htmlFor="wf-doc-sha256">文档 SHA-256 (64 位小写) <span className="required">*</span></label>
            <input
              id="wf-doc-sha256"
              type="text"
              value={docSha256}
              onChange={(e) => setDocSha256(e.target.value)}
              disabled={isSubmitting}
              placeholder="64位十六进制哈希"
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-doc-type">文档类型</label>
            <select
              id="wf-doc-type"
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              disabled={isSubmitting}
            >
              <option value="main_article">正文 (main_article)</option>
              <option value="supplement">补充材料 (supplement)</option>
              <option value="dataset">数据集 (dataset)</option>
              <option value="preprint">预印本 (preprint)</option>
              <option value="other">其他 (other)</option>
            </select>
          </div>
        </div>
      </fieldset>

      {/* 材料与样品 */}
      <fieldset className="form-section">
        <legend>2. 材料与实体样品（Sample）</legend>
        <div className="radio-group">
          <label>
            <input
              type="radio"
              name="materialMode"
              checked={materialMode === 'existing'}
              onChange={() => setMaterialMode('existing')}
              disabled={isSubmitting}
            />
            选择已有材料
          </label>
          <label>
            <input
              type="radio"
              name="materialMode"
              checked={materialMode === 'new'}
              onChange={() => setMaterialMode('new')}
              disabled={isSubmitting}
            />
            新建材料记录
          </label>
        </div>

        {materialMode === 'existing' ? (
          <div className="form-row">
            <label htmlFor="wf-existing-material">已有材料列表</label>
            <select
              id="wf-existing-material"
              value={existingMaterialId}
              onChange={(e) => setExistingMaterialId(e.target.value)}
              disabled={isSubmitting || materials.length === 0}
            >
              {materials.length === 0 && <option value="">暂无材料，请先切换新建</option>}
              {materials.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.canonical_formula} ({m.chemical_system}) {m.name ? `- ${m.name}` : ''}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="form-grid">
            <div className="form-row">
              <label htmlFor="wf-mat-formula">规范化学式 <span className="required">*</span></label>
              <input
                id="wf-mat-formula"
                type="text"
                placeholder="Ge2Sb2Te5"
                value={newMaterialFormula}
                onChange={(e) => setNewMaterialFormula(e.target.value)}
                disabled={isSubmitting}
              />
            </div>
            <div className="form-row">
              <label htmlFor="wf-mat-system">化学体系 <span className="required">*</span></label>
              <input
                id="wf-mat-system"
                type="text"
                placeholder="Ge-Sb-Te"
                value={newMaterialSystem}
                onChange={(e) => setNewMaterialSystem(e.target.value)}
                disabled={isSubmitting}
              />
            </div>
            <div className="form-row full-width">
              <label htmlFor="wf-mat-name">常用别名 / 名称</label>
              <input
                id="wf-mat-name"
                type="text"
                placeholder="GST-225"
                value={newMaterialName}
                onChange={(e) => setNewMaterialName(e.target.value)}
                disabled={isSubmitting}
              />
            </div>
          </div>
        )}

        <div className="form-grid" style={{ marginTop: '0.75rem' }}>
          <div className="form-row">
            <label htmlFor="wf-sample-label">样品标识 (Sample Label) <span className="required">*</span></label>
            <input
              id="wf-sample-label"
              type="text"
              placeholder="例如: GST-FILM-01"
              value={sampleLabel}
              onChange={(e) => setSampleLabel(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-sample-type">样品形态类别</label>
            <select
              id="wf-sample-type"
              value={sampleTypeTermId}
              onChange={(e) => setSampleTypeTermId(e.target.value)}
              disabled={isSubmitting || sampleTypes.length === 0}
            >
              {sampleTypes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label} ({t.code})
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label htmlFor="wf-sample-thickness">厚度数值</label>
            <input
              id="wf-sample-thickness"
              type="number"
              step="any"
              placeholder="100"
              value={sampleThickness}
              onChange={(e) => setSampleThickness(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-sample-thick-unit">厚度单位</label>
            <input
              id="wf-sample-thick-unit"
              type="text"
              value={sampleThicknessUnit}
              onChange={(e) => setSampleThicknessUnit(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row full-width">
            <label htmlFor="wf-sample-substrate">衬底材料</label>
            <input
              id="wf-sample-substrate"
              type="text"
              placeholder="Si/SiO2 (300 nm)"
              value={sampleSubstrate}
              onChange={(e) => setSampleSubstrate(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
        </div>
      </fieldset>

      {/* 实验测量与观测 */}
      <fieldset className="form-section">
        <legend>3. 实验测量与科学观测值</legend>
        <div className="form-grid">
          <div className="form-row">
            <label htmlFor="wf-meas-type">测量方法/技术</label>
            <select
              id="wf-meas-type"
              value={measTypeTermId}
              onChange={(e) => setMeasTypeTermId(e.target.value)}
              disabled={isSubmitting || measurementTypes.length === 0}
            >
              {measurementTypes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label} ({t.code})
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label htmlFor="wf-meas-inst">仪器设备</label>
            <input
              id="wf-meas-inst"
              type="text"
              placeholder="DSC 8500"
              value={measInstrument}
              onChange={(e) => setMeasInstrument(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-meas-temp">实验温度</label>
            <input
              id="wf-meas-temp"
              type="number"
              step="any"
              placeholder="300"
              value={measTemp}
              onChange={(e) => setMeasTemp(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-meas-temp-unit">温度单位</label>
            <input
              id="wf-meas-temp-unit"
              type="text"
              value={measTempUnit}
              onChange={(e) => setMeasTempUnit(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row full-width">
            <label htmlFor="wf-property">性质定义 (Property) <span className="required">*</span></label>
            <select
              id="wf-property"
              value={propertyId}
              onChange={(e) => setPropertyId(e.target.value)}
              disabled={isSubmitting || properties.length === 0}
            >
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.code}) {p.canonical_unit ? `[${p.canonical_unit}]` : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label htmlFor="wf-orig-val">原始数值 <span className="required">*</span></label>
            <input
              id="wf-orig-val"
              type="text"
              placeholder="453"
              value={originalValue}
              onChange={(e) => setOriginalValue(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-orig-unit">原始单位 <span className="required">*</span></label>
            <input
              id="wf-orig-unit"
              type="text"
              placeholder="K"
              value={originalUnit}
              onChange={(e) => setOriginalUnit(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-unc-lower">不确定度下限</label>
            <input
              id="wf-unc-lower"
              type="number"
              step="any"
              placeholder="0.0"
              value={uncertaintyLower}
              onChange={(e) => setUncertaintyLower(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-unc-upper">不确定度上限</label>
            <input
              id="wf-unc-upper"
              type="number"
              step="any"
              placeholder="0.0"
              value={uncertaintyUpper}
              onChange={(e) => setUncertaintyUpper(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
        </div>
      </fieldset>

      {/* 证据溯源片段 */}
      <fieldset className="form-section">
        <legend>4. 证据溯源片段（Evidence Fragment）</legend>
        <div className="form-grid">
          <div className="form-row">
            <label htmlFor="wf-evd-page">页码 (Page) <span className="required">*</span></label>
            <input
              id="wf-evd-page"
              type="number"
              min="1"
              value={evdPage}
              onChange={(e) => setEvdPage(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-evd-section">章节 (Section)</label>
            <input
              id="wf-evd-section"
              type="text"
              placeholder="Results and Discussion"
              value={evdSection}
              onChange={(e) => setEvdSection(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-evd-fig">图号 (Figure)</label>
            <input
              id="wf-evd-fig"
              type="text"
              placeholder="Fig. 2b"
              value={evdFigure}
              onChange={(e) => setEvdFigure(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <label htmlFor="wf-evd-tbl">表号 (Table)</label>
            <input
              id="wf-evd-tbl"
              type="text"
              placeholder="Table 1"
              value={evdTable}
              onChange={(e) => setEvdTable(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row full-width">
            <label htmlFor="wf-evd-text">证据原文片段 (Text Snippet) <span className="required">*</span></label>
            <textarea
              id="wf-evd-text"
              rows={3}
              placeholder="粘贴文献中出现此数值的具体句子或段落..."
              value={evdText}
              onChange={(e) => setEvdText(e.target.value)}
              disabled={isSubmitting}
            />
          </div>
        </div>
      </fieldset>

      {validationError && (
        <div className="error-banner" role="alert">
          {validationError}
        </div>
      )}
      {errorMessage && (
        <div className="error-banner" role="alert">
          {errorMessage}
        </div>
      )}

      <div className="form-actions">
        <button type="submit" className="primary" disabled={isSubmitting}>
          {isSubmitting ? '正在提交事务入库…' : '提交完整记录入库'}
        </button>
      </div>
    </form>
  )
}
