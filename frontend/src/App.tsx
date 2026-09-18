import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

import { BatchUploadModal } from './components/BatchUploadModal'
import { KnowledgeGraphPlaceholder } from './components/KnowledgeGraphPlaceholder'
import { LiteratureAgentView } from './components/LiteratureAgentView'
import { PeriodicTable } from './components/PeriodicTable'
import type { ObservationConflictGroup } from './types/batch'
import { Workflow } from './Workflow'


const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

type AppConfig = {
  app_title: string
  app_description: string
  app_logo: string
}

type Dashboard = {
  materials: number
  papers: number
  observations: number
  verified_observations: number
  pending_outbox_events: number
}

type Material = {
  id: string
  canonical_formula: string
  reduced_formula?: string | null
  chemical_system: string
  name: string | null
  description: string | null
  aliases?: string[]
}

type MaterialDetail = Material & {
  row_version?: number
  created_at?: string
  updated_at?: string
  aliases: string[]
  components?: Array<{
    element: string
    coefficient: number
    valence_state?: string | null
  }>
}

type Paper = {
  id: string
  title: string
  doi: string | null
  journal: string | null
  publication_year: number | null
  first_author?: string | null
  corresponding_author?: string | null
  authors?: string[]
}

type PaperDetail = Paper & {
  volume?: string | null
  issue?: string | null
  pages?: string | null
  publisher?: string | null
  abstract?: string | null
  metadata?: Record<string, unknown> | null
  row_version?: number
  created_at?: string
  updated_at?: string
}

type Observation = {
  id: string
  material_formula: string | null
  property_name: string
  property_code: string
  value: number | string | boolean | null
  unit: string | null
  display_value?: string | null
  normalized_value?: number | null
  normalized_unit?: string | null
  verification_status: string
  quality_score: number | null
}

type Page<T> = { items: T[]; has_more: boolean; next_cursor: string | null }
type SearchHit = { id: string; target: string; title: string | null; snippet: string | null }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const error = await response.json().catch(() => null)
    throw new Error(error?.detail ?? `请求失败（${response.status}）`)
  }
  return response.json() as Promise<T>
}

function App() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [materials, setMaterials] = useState<Material[]>([])
  const [papers, setPapers] = useState<Paper[]>([])
  const [observations, setObservations] = useState<Observation[]>([])
  const [query, setQuery] = useState('')
  const [lastSearchedQuery, setLastSearchedQuery] = useState('')
  const [hasSearched, setHasSearched] = useState(false)
  const [hits, setHits] = useState<SearchHit[]>([])
  const [status, setStatus] = useState('正在连接本地 API…')
  const [activeView, setActiveView] = useState<
    'overview' | 'materials' | 'papers' | 'workflow' | 'agent' | 'knowledge-graph'
  >('overview')

  const [showMaterialForm, setShowMaterialForm] = useState(false)
  const [showBatchUpload, setShowBatchUpload] = useState(false)
  const [selectedMaterialId, setSelectedMaterialId] = useState<string | null>(null)
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null)


  const [appConfig, setAppConfig] = useState<AppConfig>({
    app_title: 'PhaseChangeDB',
    app_description: '相变材料知识库',
    app_logo: '/logo.svg',
  })
  const [availableElements, setAvailableElements] = useState<string[]>([])
  const [selectedElements, setSelectedElements] = useState<string[]>([])
  const [configEditTarget, setConfigEditTarget] = useState<'logo' | 'title' | 'description' | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [editingDescription, setEditingDescription] = useState('')
  const [editingLogo, setEditingLogo] = useState('')
  const [configSaving, setConfigSaving] = useState(false)
  const [configError, setConfigError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      const [stats, materialPage, paperPage, observationPage, configRes, elementsRes] = await Promise.all([
        request<Dashboard>('/v1/dashboard'),
        request<Page<Material>>(selectedElements.length > 0 ? `/v1/materials?elements=${selectedElements.join(',')}` : '/v1/materials'),
        request<Page<Paper>>('/v1/papers'),
        request<Page<Observation>>('/v1/observations'),
        request<AppConfig>('/v1/config').catch(() => ({
          app_title: 'PhaseChangeDB',
          app_description: '相变材料知识库',
          app_logo: '/logo.svg',
        })),
        request<string[]>('/v1/materials/elements').catch(() => []),
      ])
      setDashboard(stats)
      setMaterials(materialPage.items)
      setPapers(paperPage.items)
      setObservations(observationPage.items)
      setAppConfig(configRes)
      setAvailableElements(elementsRes)
      setStatus('数据库已连接')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : '无法连接 API')
    }
  }, [selectedElements])

  useEffect(() => {
    void loadData()
  }, [loadData])

  useEffect(() => {
    document.title = `${appConfig.app_title} - ${appConfig.app_description}`
  }, [appConfig])

  const handleToggleElement = async (symbol: string) => {
    const next = selectedElements.includes(symbol)
      ? selectedElements.filter((s) => s !== symbol)
      : [...selectedElements, symbol]
    setSelectedElements(next)
    try {
      const url = next.length > 0 ? `/v1/materials?elements=${next.join(',')}` : '/v1/materials'
      const page = await request<Page<Material>>(url)
      setMaterials(page.items)
    } catch (err) {
      console.error('筛选材料失败:', err)
    }
  }

  const handleClearElements = async () => {
    setSelectedElements([])
    try {
      const page = await request<Page<Material>>('/v1/materials')
      setMaterials(page.items)
    } catch (err) {
      console.error('清空筛选失败:', err)
    }
  }

  const openConfigModal = (target: 'logo' | 'title' | 'description') => {
    setConfigEditTarget(target)
    setEditingTitle(appConfig.app_title)
    setEditingDescription(appConfig.app_description)
    setEditingLogo(appConfig.app_logo)
    setConfigError(null)
  }

  const handleSaveConfig = async (e: FormEvent) => {
    e.preventDefault()
    setConfigError(null)
    if (configEditTarget === 'title' && !editingTitle.trim()) {
      setConfigError('数据库名称不能为空')
      return
    }
    setConfigSaving(true)
    try {
      const payload: Partial<AppConfig> = {}
      if (configEditTarget === 'title') payload.app_title = editingTitle.trim()
      else if (configEditTarget === 'description') payload.app_description = editingDescription.trim()
      else if (configEditTarget === 'logo') payload.app_logo = editingLogo.trim() || '/logo.svg'

      const updated = await request<AppConfig>('/v1/config', {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      setAppConfig(updated)
      setConfigEditTarget(null)
      setStatus('数据库配置已更新并保存')
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : '保存配置失败')
    } finally {
      setConfigSaving(false)
    }
  }

  const handleLogoFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 2 * 1024 * 1024) {
      setConfigError('图片文件过大，请选择小于 2MB 的图片')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setEditingLogo(reader.result)
        setConfigError(null)
      }
    }
    reader.onerror = () => {
      setConfigError('读取图片文件失败')
    }
    reader.readAsDataURL(file)
  }

  // 监听 Hash 变化（浏览器前进/后退）
  useEffect(() => {
    function handleHashChange() {
      const hash = window.location.hash
      if (hash.startsWith('#material=')) {
        const id = decodeURIComponent(hash.replace('#material=', ''))
        setSelectedMaterialId(id)
        setSelectedPaperId(null)
      } else if (hash.startsWith('#paper=')) {
        const id = decodeURIComponent(hash.replace('#paper=', ''))
        setSelectedPaperId(id)
        setSelectedMaterialId(null)
      } else {
        setSelectedMaterialId(null)
        setSelectedPaperId(null)
      }
    }

    handleHashChange()
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  // 状态同步至 URL Hash
  useEffect(() => {
    if (selectedMaterialId) {
      const targetHash = `#material=${encodeURIComponent(selectedMaterialId)}`
      if (window.location.hash !== targetHash) {
        window.location.hash = targetHash
      }
    } else if (selectedPaperId) {
      const targetHash = `#paper=${encodeURIComponent(selectedPaperId)}`
      if (window.location.hash !== targetHash) {
        window.location.hash = targetHash
      }
    } else if (window.location.hash.startsWith('#material=') || window.location.hash.startsWith('#paper=')) {
      history.pushState(null, '', window.location.pathname + window.location.search)
    }
  }, [selectedMaterialId, selectedPaperId])

  function openMaterialModal(id: string) {
    setSelectedMaterialId(id)
    setSelectedPaperId(null)
  }

  function openPaperModal(id: string) {
    setSelectedPaperId(id)
    setSelectedMaterialId(null)
  }

  function closeModal() {
    setSelectedMaterialId(null)
    setSelectedPaperId(null)
  }

  async function search(event: FormEvent) {
    event.preventDefault()
    const q = query.trim()
    if (!q) return
    setHasSearched(true)
    setLastSearchedQuery(q)
    try {
      const result = await request<{ hits: SearchHit[] }>('/v1/search', {
        method: 'POST',
        body: JSON.stringify({ query: q, targets: ['materials', 'papers'], mode: 'lexical', limit: 20 }),
      })
      setHits(result.hits)
      setStatus(`找到 ${result.hits.length} 条结果`)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : '搜索失败')
    }
  }

  function clearSearch() {
    setHits([])
    setHasSearched(false)
    setLastSearchedQuery('')
    setQuery('')
    setStatus('已清除搜索')
  }

  async function createMaterial(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    try {
      await request('/v1/materials', {
        method: 'POST',
        body: JSON.stringify({
          canonical_formula: data.get('formula'),
          chemical_system: data.get('system'),
          name: data.get('name') || null,
          description: data.get('description') || null,
          aliases: [],
          components: [],
        }),
      })
      form.reset()
      setShowMaterialForm(false)
      await loadData()
      setStatus('材料已创建，Outbox 事件已入队')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : '创建失败')
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div
            className="brand-logo-wrap clickable-brand"
            onClick={() => openConfigModal('logo')}
            title="点击更换数据库 LOGO"
          >
            <img src={appConfig.app_logo || '/logo.svg'} alt={appConfig.app_title} className="brand-logo-img" />
            <span className="brand-edit-badge">✎</span>
          </div>
          <div className="brand-info">
            <strong
              className="clickable-brand brand-title"
              onClick={() => openConfigModal('title')}
              title="点击修改数据库名称"
            >
              {appConfig.app_title} <span className="brand-edit-pencil">✎</span>
            </strong>
            <small
              className="clickable-brand brand-desc"
              onClick={() => openConfigModal('description')}
              title="点击修改数据库描述"
            >
              {appConfig.app_description} <span className="brand-edit-pencil">✎</span>
            </small>
          </div>
        </div>
        <nav aria-label="主导航">
          <button className={activeView === 'overview' ? 'active' : ''} onClick={() => setActiveView('overview')}>概览</button>
          <button className={activeView === 'materials' ? 'active' : ''} onClick={() => setActiveView('materials')}>材料库 <span>{dashboard?.materials ?? '—'}</span></button>
          <button className={activeView === 'papers' ? 'active' : ''} onClick={() => setActiveView('papers')}>文献 <span>{dashboard?.papers ?? '—'}</span></button>
          <button className={activeView === 'workflow' ? 'active' : ''} onClick={() => setActiveView('workflow')}>录入与审核工作流</button>
          <button className={activeView === 'agent' ? 'active' : ''} onClick={() => setActiveView('agent')}>
            文献解析智能体 <span className="nav-badge-ai">AI</span>
          </button>
          <button className={activeView === 'knowledge-graph' ? 'active' : ''} onClick={() => setActiveView('knowledge-graph')}>
            知识图谱 <span className="nav-badge-plan">建设中</span>
          </button>
        </nav>
        <div className="system-state"><i />{status}</div>
      </aside>

      <main>
        <header>
          <div>
            <p className="eyebrow">EVIDENCE-GROUNDED MATERIALS DATA</p>
            <h1>
              {activeView === 'overview'
                ? '研究数据概览'
                : activeView === 'materials'
                ? '材料目录'
                : activeView === 'papers'
                ? '文献目录'
                : activeView === 'agent'
                ? '文献智能解析智能体'
                : activeView === 'knowledge-graph'
                ? '科学知识图谱'
                : '科学数据录入与审核工作流'}
            </h1>
          </div>
          {(activeView === 'overview' || activeView === 'materials' || activeView === 'papers') && (
            <button className="primary" onClick={() => setShowMaterialForm(true)}>＋ 新建材料</button>
          )}
        </header>

        {activeView !== 'workflow' && activeView !== 'agent' && activeView !== 'knowledge-graph' && (
          <form className="search" onSubmit={search}>
            <span>⌕</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索化学式（如 GeTe、Ge2Sb2Te5）、体系、论文标题或 DOI…"
            />
            <button type="submit">搜索</button>
          </form>
        )}

        {/* 搜索结果区域 */}
        {hits.length > 0 && activeView !== 'workflow' && activeView !== 'agent' && activeView !== 'knowledge-graph' && (

          <section className="search-results">
            <div className="section-title">
              <h2>搜索结果（共 {hits.length} 条）</h2>
              <button className="btn-clear" type="button" onClick={clearSearch}>清除结果</button>
            </div>
            <div className="search-hit-list">
              {hits.map((hit) => (
                <article
                  key={`${hit.target}-${hit.id}`}
                  className="search-hit-card clickable"
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    if (hit.target === 'materials') openMaterialModal(hit.id)
                    else if (hit.target === 'papers') openPaperModal(hit.id)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      if (hit.target === 'materials') openMaterialModal(hit.id)
                      else if (hit.target === 'papers') openPaperModal(hit.id)
                    }
                  }}
                >
                  <span className={`target-badge ${hit.target}`}>
                    {hit.target === 'materials' ? '材料' : '文献'}
                  </span>
                  <div className="hit-content">
                    <strong className="hit-title">{hit.title || '未命名'}</strong>
                    <p className="hit-snippet">{hit.snippet || '暂无描述'}</p>
                    <small className="click-hint">点击打开详情 ↗</small>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {/* 搜索无结果友好空状态 */}
        {hasSearched && hits.length === 0 && activeView !== 'workflow' && (
          <section className="search-results empty-results">
            <div className="search-empty-state">
              <div className="empty-icon">🔍</div>
              <h3>未找到与“{lastSearchedQuery}”相关的材料或文献</h3>
              <p>
                您可以尝试输入规范化学式（如 <code>GeTe</code>、<code>Ge2Sb2Te5</code>）、化学体系（如 <code>Ge-Te</code>）或文献标题/DOI。
              </p>
              <button type="button" className="btn-secondary" onClick={clearSearch}>重置搜索</button>
            </div>
          </section>
        )}

        {activeView === 'overview' && <>
          <section className="metrics">
            <Metric label="材料实体" value={dashboard?.materials} accent="teal" />
            <Metric label="文献记录" value={dashboard?.papers} accent="amber" />
            <Metric label="观测数据" value={dashboard?.observations} accent="blue" />
            <Metric label="已验证观测" value={dashboard?.verified_observations} accent="green" />
          </section>
          <section className="panel observations">
            <div className="section-title">
              <div>
                <p className="eyebrow">LATEST EVIDENCE</p>
                <h2>最新观测</h2>
              </div>
              <span className="queue">{dashboard?.pending_outbox_events ?? 0} 个投影事件待处理</span>
            </div>
            <ObservationTable items={observations} />
          </section>
        </>}

        {activeView === 'materials' && (
          <>
            <PeriodicTable
              availableElements={availableElements}
              selectedElements={selectedElements}
              onToggleElement={handleToggleElement}
              onClearSelection={handleClearElements}
            />
            <section className="card-grid">
              {materials.length === 0 ? (
                <div className="empty full-width">
                  {selectedElements.length > 0
                    ? `未找到同时包含所选元素（${selectedElements.join(', ')}）的材料`
                    : '暂无材料数据'}
                </div>
              ) : (
                materials.map((material) => (
                  <article
                    className="entity-card clickable"
                    key={material.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => openMaterialModal(material.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        openMaterialModal(material.id)
                      }
                    }}
                  >
                    <div className="formula">{material.canonical_formula}</div>
                    <h2>{material.name || '未命名材料'}</h2>
                    <p className="chem-system">{material.chemical_system || '—/暂无'}</p>
                    <small className="mat-desc">{material.description || '尚无材料说明'}</small>
                    <div className="card-footer-hint">点击查看详情与关联观测 ↗</div>
                  </article>
                ))
              )}
            </section>
          </>
        )}

        {activeView === 'papers' && (
          <>
            <div className="view-toolbar">
              <span className="toolbar-info">已收录权威文献共 {papers.length} 篇</span>
              <button
                type="button"
                className="btn-batch-upload"
                onClick={() => setShowBatchUpload(true)}
              >
                📄 批量上传文献（多选解析）
              </button>
            </div>
            <section className="paper-list">
              {papers.length === 0 ? (
                <div className="empty full-width">暂无文献记录</div>
              ) : (
                papers.map((paper) => (
                  <article
                    key={paper.id}
                    className="paper-card clickable"
                    role="button"
                    tabIndex={0}
                    onClick={() => openPaperModal(paper.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        openPaperModal(paper.id)
                      }
                    }}
                  >
                    <div className="year">{paper.publication_year ?? '—'}</div>
                    <div className="paper-content">
                      <h2 className="paper-title">{paper.title}</h2>
                      <div className="paper-meta-row">
                        <span className="meta-item">
                          <strong className="meta-label">期刊:</strong> {paper.journal || '—/暂无'}
                        </span>
                        <span className="meta-item">
                          <strong className="meta-label">第一作者:</strong> {paper.first_author || '—/暂无'}
                        </span>
                        <span className="meta-item">
                          <strong className="meta-label">通讯作者:</strong> {paper.corresponding_author || '—/暂无'}
                        </span>
                        <span className="meta-item meta-doi">
                          <strong className="meta-label">DOI:</strong>{' '}
                          {paper.doi ? (
                            <a
                              href={`https://doi.org/${encodeURIComponent(paper.doi.trim())}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="doi-link"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {paper.doi} ↗
                            </a>
                          ) : (
                            '—/暂无'
                          )}
                        </span>
                      </div>
                      <div className="paper-card-footer">
                        <span className="click-hint">点击查看文献完整元数据与摘要 ↗</span>
                      </div>
                    </div>
                  </article>
                ))
              )}
            </section>
          </>
        )}

        {activeView === 'workflow' && <Workflow onDataChanged={() => void loadData()} />}

        {activeView === 'agent' && (
          <LiteratureAgentView onOpenBatchUpload={() => setShowBatchUpload(true)} />
        )}

        {activeView === 'knowledge-graph' && <KnowledgeGraphPlaceholder />}
      </main>

      {showBatchUpload && (
        <BatchUploadModal
          onClose={() => setShowBatchUpload(false)}
          onSuccess={() => {
            void loadData()
          }}
        />
      )}


      {/* 新建材料弹窗 */}
      {showMaterialForm && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowMaterialForm(false)}>
          <form className="modal" onSubmit={createMaterial} onMouseDown={(event) => event.stopPropagation()}>
            <div className="section-title">
              <h2>新建材料</h2>
              <button type="button" onClick={() => setShowMaterialForm(false)}>×</button>
            </div>
            <label>规范化学式<input name="formula" required placeholder="例如 Ge2Sb2Te5" /></label>
            <label>化学体系<input name="system" required placeholder="例如 Ge-Sb-Te" /></label>
            <label>材料名称<input name="name" placeholder="可选" /></label>
            <label>说明<textarea name="description" rows={3} placeholder="可选" /></label>
            <button className="primary" type="submit">保存材料</button>
          </form>
        </div>
      )}

      {/* 材料详情弹窗 */}
      {selectedMaterialId && (
        <MaterialDetailModal
          materialId={selectedMaterialId}
          onClose={closeModal}
        />
      )}

      {/* 文献详情弹窗 */}
      {selectedPaperId && (
        <PaperDetailModal
          paperId={selectedPaperId}
          onClose={closeModal}
        />
      )}

      {/* 数据库配置修改弹窗 */}
      {configEditTarget && (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={() => setConfigEditTarget(null)}
        >
          <form
            className="modal config-modal"
            onSubmit={handleSaveConfig}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="config-modal-header">
              <h2>
                {configEditTarget === 'title' && '修改数据库名称'}
                {configEditTarget === 'description' && '修改数据库描述'}
                {configEditTarget === 'logo' && '更换数据库主题 LOGO'}
              </h2>
              <button
                type="button"
                className="close-btn"
                onClick={() => setConfigEditTarget(null)}
              >
                ×
              </button>
            </div>

            <div className="config-modal-body">
              {configEditTarget === 'title' && (
                <div className="form-row full-width">
                  <label htmlFor="config-title-input">
                    数据库系统名称 <span className="required">*</span>
                  </label>
                  <input
                    id="config-title-input"
                    value={editingTitle}
                    maxLength={64}
                    autoFocus
                    required
                    placeholder="请输入系统名称（如 PhaseChangeDB）"
                    onChange={(e) => setEditingTitle(e.target.value)}
                  />
                  <div className="char-count">{editingTitle.length} / 64 字</div>
                </div>
              )}

              {configEditTarget === 'description' && (
                <div className="form-row full-width">
                  <label htmlFor="config-desc-input">
                    副标题与描述说明
                  </label>
                  <textarea
                    id="config-desc-input"
                    value={editingDescription}
                    maxLength={255}
                    rows={3}
                    autoFocus
                    placeholder="请输入系统描述（如 相变材料知识库）"
                    onChange={(e) => setEditingDescription(e.target.value)}
                  />
                  <div className="char-count">{editingDescription.length} / 255 字</div>
                </div>
              )}

              {configEditTarget === 'logo' && (
                <div className="logo-preview-area">
                  <div className="logo-preview-box">
                    <img
                      src={editingLogo || '/logo.svg'}
                      alt="LOGO预览"
                      className="logo-preview-img"
                    />
                  </div>
                  <div className="logo-upload-controls">
                    <label className="file-upload-btn">
                      <span>📁 选择本地新图标 (SVG / PNG / JPG)</span>
                      <input
                        type="file"
                        accept="image/svg+xml,image/png,image/jpeg,image/webp"
                        className="file-input-hidden"
                        onChange={handleLogoFileChange}
                      />
                    </label>
                    <button
                      type="button"
                      className="btn-reset-default"
                      onClick={() => setEditingLogo('/logo.svg')}
                    >
                      ↺ 恢复系统相变材料矢量 LOGO
                    </button>
                    <span className="help-text">支持上传 2MB 以内的高清矢量 SVG 或图片，保存后持久化至数据库。</span>
                  </div>
                </div>
              )}

              {configError && <div className="error-banner">{configError}</div>}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn-secondary"
                disabled={configSaving}
                onClick={() => setConfigEditTarget(null)}
              >
                取消
              </button>
              <button
                type="submit"
                className="primary"
                disabled={configSaving}
              >
                {configSaving ? '正在保存…' : '确认保存'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

function Metric({ label, value, accent }: { label: string; value: number | undefined; accent: string }) {
  return (
    <article className={`metric ${accent}`}>
      <span>{label}</span>
      <strong>{value ?? '—'}</strong>
      <small>权威数据源 · MySQL</small>
    </article>
  )
}

function ObservationTable({ items }: { items: Observation[] }) {
  if (items.length === 0) return <div className="empty">暂无观测数据</div>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>材料</th>
            <th>属性</th>
            <th>数值（规范单位）</th>
            <th>状态</th>
            <th>质量</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td><strong>{item.material_formula || '计算/器件'}</strong></td>
              <td>
                {item.property_name}
                <small>{item.property_code}</small>
              </td>
              <td className="numeric">
                {item.display_value || (item.value != null ? `${item.value} ${item.unit || ''}`.trim() : '—/暂无')}
              </td>
              <td>
                <span className={`badge ${item.verification_status.toLowerCase()}`}>
                  {item.verification_status}
                </span>
              </td>
              <td>{item.quality_score == null ? '—/暂无' : `${Math.round(item.quality_score * 100)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface MaterialDetailModalProps {
  materialId: string
  onClose: () => void
}

function MaterialDetailModal({ materialId, onClose }: MaterialDetailModalProps) {
  const [material, setMaterial] = useState<MaterialDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [relatedObservations, setRelatedObservations] = useState<Observation[]>([])

  const [conflicts, setConflicts] = useState<ObservationConflictGroup[]>([])

  const fetchDetail = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [mat, obsPage, conflictList] = await Promise.all([
        request<MaterialDetail>(`/v1/materials/${materialId}`),
        request<Page<Observation>>('/v1/observations?limit=100').catch(() => ({ items: [] as Observation[] })),
        request<ObservationConflictGroup[]>(`/v1/materials/${materialId}/conflicts`).catch(
          () => [] as ObservationConflictGroup[]
        ),
      ])
      setMaterial(mat)
      setConflicts(conflictList)
      const matchedObs = obsPage.items.filter(
        (o) => o.material_formula === mat.canonical_formula
      )
      setRelatedObservations(matchedObs)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载材料详情失败')
    } finally {
      setLoading(false)
    }
  }, [materialId])


  useEffect(() => {
    void fetchDetail()
  }, [fetchDetail])

  // ESC 键关闭
  useEffect(() => {
    function handleKeyDown(e: globalThis.KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="modal detail-modal"
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="detail-modal-header">
          <div>
            <p className="eyebrow">材料实体详情</p>
            <h2>{material?.canonical_formula || '材料详情'}</h2>
          </div>
          <button className="close-btn" type="button" onClick={onClose} aria-label="关闭">×</button>
        </div>

        {loading && <div className="detail-loading">正在获取材料科学数据…</div>}

        {error && (
          <div className="detail-error">
            <p>⚠️ {error}</p>
            <button className="btn-secondary" type="button" onClick={() => void fetchDetail()}>重试</button>
          </div>
        )}

        {!loading && !error && material && (
          <div className="detail-body">
            <div className="detail-grid">
              <div className="detail-field">
                <span className="field-label">规范化学式</span>
                <span className="field-value formula-highlight">{material.canonical_formula || '—/暂无'}</span>
              </div>
              <div className="detail-field">
                <span className="field-label">简化化学式</span>
                <span className="field-value">{material.reduced_formula || '—/暂无'}</span>
              </div>
              <div className="detail-field">
                <span className="field-label">化学体系</span>
                <span className="field-value">{material.chemical_system || '—/暂无'}</span>
              </div>
              <div className="detail-field">
                <span className="field-label">常用名称</span>
                <span className="field-value">{material.name || '—/暂无'}</span>
              </div>
              <div className="detail-field full-width">
                <span className="field-label">别名列表</span>
                <span className="field-value">
                  {material.aliases && material.aliases.length > 0
                    ? material.aliases.join('、')
                    : '—/暂无'}
                </span>
              </div>
              <div className="detail-field full-width">
                <span className="field-label">材料说明</span>
                <span className="field-value text-desc">{material.description || '—/暂无'}</span>
              </div>
              <div className="detail-field">
                <span className="field-label">乐观锁版本</span>
                <span className="field-value mono-val">W/"{material.row_version ?? 1}"</span>
              </div>
              <div className="detail-field">
                <span className="field-label">入库时间</span>
                <span className="field-value">
                  {material.created_at ? new Date(material.created_at).toLocaleString() : '—/暂无'}
                </span>
              </div>
            </div>

            {material.components && material.components.length > 0 && (
              <div className="detail-sub-section">
                <h3>元素化学组分比例</h3>
                <div className="component-badges">
                  {material.components.map((c, idx) => (
                    <span key={idx} className="comp-badge">
                      <strong>{c.element}</strong>: {c.coefficient}
                      {c.valence_state ? ` (${c.valence_state})` : ''}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {conflicts.length > 0 && (
              <div className="conflict-section">
                <div className="conflict-alert-banner">
                  <span className="conflict-alert-icon">⚠️</span>
                  <div className="conflict-alert-text">
                    <strong>学术争议与相近测试条件结论冲突提醒 ({conflicts.length} 组)</strong>
                    <p>
                      在相同或相近实验条件下，不同独立文献报告的数值存在明显差异（相对偏差 &gt; 5%）或被标记为争议数据（DISPUTED）。
                      本系统遵循证据保真与科学不变量原则，不抹平差异或静默覆盖，现将独立文献、测试仪器、实验条件与作者信息并列呈现以供科研复核与仲裁。
                    </p>
                  </div>
                </div>

                {conflicts.map((grp, gIdx) => (
                  <div key={gIdx} className="conflict-group-box">
                    <div className="conflict-group-header">
                      <span className="conflict-prop-title">
                        📊 属性对比：{grp.property_name} ({grp.property_code})
                      </span>
                      <span
                        className={`conflict-diff-badge ${
                          grp.conflict_type === 'explicit_dispute' ? 'disputed' : 'discrepancy'
                        }`}
                      >
                        {grp.conflict_type === 'explicit_dispute' ? '存在学术争议 (DISPUTED)' : '相近条件数值显著偏差'}
                      </span>
                    </div>
                    <p className="conflict-group-desc">{grp.discrepancy_description}</p>

                    <div className="conflict-cards-grid">
                      {grp.items.map((item) => (
                        <div
                          key={item.observation_id}
                          className={`conflict-card ${
                            item.verification_status === 'DISPUTED' ? 'is-disputed' : ''
                          }`}
                        >
                          <div className="conflict-val-hero">
                            {item.display_value}
                            {item.condition_temperature && (
                              <div className="conflict-cond-pill">
                                🌡️ {item.condition_temperature}
                              </div>
                            )}
                            {item.condition_pressure && (
                              <div className="conflict-cond-pill">
                                💨 {item.condition_pressure}
                              </div>
                            )}
                          </div>

                          <div className="conflict-meta-list">
                            <div className="conflict-meta-item">
                              <strong>实验仪器:</strong> {item.measurement_instrument || '—/未标明'}
                            </div>
                            <div className="conflict-meta-item">
                              <strong>第一作者:</strong> {item.first_author || '—'}
                            </div>
                            <div className="conflict-meta-item">
                              <strong>通讯作者:</strong> {item.corresponding_author || '—'}
                            </div>
                            <div className="conflict-meta-item">
                              <strong>来源文献:</strong> {item.paper_title || '—'}
                            </div>
                            <div className="conflict-meta-item">
                              <strong>期刊年份:</strong> {item.journal || '—'}{' '}
                              {item.publication_year ? `(${item.publication_year})` : ''}
                            </div>
                            <div className="conflict-meta-item">
                              <strong>DOI:</strong>{' '}
                              {item.paper_doi ? (
                                <a
                                  href={`https://doi.org/${encodeURIComponent(item.paper_doi.trim())}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="conflict-paper-link"
                                >
                                  {item.paper_doi} ↗
                                </a>
                              ) : (
                                '—'
                              )}
                            </div>
                          </div>

                          <div className="conflict-card-footer">
                            <span className={`badge ${item.verification_status.toLowerCase()}`}>
                              {item.verification_status}
                            </span>
                            <span>
                              质量得分:{' '}
                              {item.quality_score != null ? `${Math.round(item.quality_score * 100)}%` : '—'}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="detail-sub-section">
              <div className="section-title">
                <h3>关联科学观测 ({relatedObservations.length} 条)</h3>
              </div>

              {relatedObservations.length === 0 ? (
                <div className="detail-empty">该材料暂无关联的观测数据记录</div>
              ) : (
                <div className="table-wrap mini-table">
                  <table>
                    <thead>
                      <tr>
                        <th>属性</th>
                        <th>数值（规范单位）</th>
                        <th>状态</th>
                        <th>质量</th>
                      </tr>
                    </thead>
                    <tbody>
                      {relatedObservations.map((obs) => (
                        <tr key={obs.id}>
                          <td>
                            <strong>{obs.property_name}</strong>
                            <small>{obs.property_code}</small>
                          </td>
                          <td className="numeric">
                            {obs.display_value ||
                              (obs.value != null ? `${obs.value} ${obs.unit || ''}`.trim() : '—/暂无')}
                          </td>
                          <td>
                            <span className={`badge ${obs.verification_status.toLowerCase()}`}>
                              {obs.verification_status}
                            </span>
                          </td>
                          <td>
                            {obs.quality_score == null
                              ? '—/暂无'
                              : `${Math.round(obs.quality_score * 100)}%`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="detail-modal-footer">
          <button className="btn-secondary" type="button" onClick={onClose}>返回 / 关闭</button>
        </div>
      </div>
    </div>
  )
}

interface PaperDetailModalProps {
  paperId: string
  onClose: () => void
}

function PaperDetailModal({ paperId, onClose }: PaperDetailModalProps) {
  const [paper, setPaper] = useState<PaperDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchDetail = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await request<PaperDetail>(`/v1/papers/${paperId}`)
      setPaper(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载文献详情失败')
    } finally {
      setLoading(false)
    }
  }, [paperId])

  useEffect(() => {
    void fetchDetail()
  }, [fetchDetail])

  // ESC 键关闭
  useEffect(() => {
    function handleKeyDown(e: globalThis.KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="modal detail-modal"
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="detail-modal-header">
          <div>
            <p className="eyebrow">科学文献详情</p>
            <h2>{paper?.title || '文献详情'}</h2>
          </div>
          <button className="close-btn" type="button" onClick={onClose} aria-label="关闭">×</button>
        </div>

        {loading && <div className="detail-loading">正在获取文献科学元数据…</div>}

        {error && (
          <div className="detail-error">
            <p>⚠️ {error}</p>
            <button className="btn-secondary" type="button" onClick={() => void fetchDetail()}>重试</button>
          </div>
        )}

        {!loading && !error && paper && (
          <div className="detail-body">
            <div className="detail-grid">
              <div className="detail-field full-width">
                <span className="field-label">文献标题 (Title)</span>
                <span className="field-value title-val">{paper.title || '—/暂无'}</span>
              </div>
              <div className="detail-field">
                <span className="field-label">发表期刊 (Journal)</span>
                <span className="field-value">{paper.journal || '—/暂无'}</span>
              </div>
              <div className="detail-field">
                <span className="field-label">出版年份 (Year)</span>
                <span className="field-value">
                  {paper.publication_year ? `${paper.publication_year} 年` : '—/暂无'}
                </span>
              </div>
              <div className="detail-field">
                <span className="field-label">第一作者 (First Author)</span>
                <span className="field-value author-name">{paper.first_author || '—/暂无'}</span>
              </div>
              <div className="detail-field">
                <span className="field-label">通讯作者 (Corresponding Author)</span>
                <span className="field-value author-name">{paper.corresponding_author || '—/暂无'}</span>
              </div>
              <div className="detail-field full-width">
                <span className="field-label">DOI 标识 (Digital Object Identifier)</span>
                <span className="field-value">
                  {paper.doi ? (
                    <a
                      href={`https://doi.org/${encodeURIComponent(paper.doi.trim())}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="doi-link-btn"
                    >
                      <span>https://doi.org/{paper.doi}</span>
                      <span className="doi-external-icon">↗</span>
                    </a>
                  ) : (
                    '—/暂无'
                  )}
                </span>
              </div>
              <div className="detail-field full-width">
                <span className="field-label">完整作者列表 (All Authors)</span>
                <span className="field-value">
                  {paper.authors && paper.authors.length > 0
                    ? paper.authors.join('，')
                    : (paper.first_author || '—/暂无')}
                </span>
              </div>
              <div className="detail-field">
                <span className="field-label">卷 / 期 / 页码</span>
                <span className="field-value">
                  {[paper.volume ? `卷 ${paper.volume}` : null, paper.issue ? `期 ${paper.issue}` : null, paper.pages ? `页 ${paper.pages}` : null]
                    .filter(Boolean)
                    .join(' · ') || '—/暂无'}
                </span>
              </div>
              <div className="detail-field">
                <span className="field-label">出版机构 (Publisher)</span>
                <span className="field-value">{paper.publisher || '—/暂无'}</span>
              </div>
              <div className="detail-field full-width">
                <span className="field-label">论文摘要 (Abstract)</span>
                <div className="field-value abstract-box">{paper.abstract || '—/暂无'}</div>
              </div>
              <div className="detail-field">
                <span className="field-label">数据版本</span>
                <span className="field-value mono-val">W/"{paper.row_version ?? 1}"</span>
              </div>
              <div className="detail-field">
                <span className="field-label">入库时间</span>
                <span className="field-value">
                  {paper.created_at ? new Date(paper.created_at).toLocaleString() : '—/暂无'}
                </span>
              </div>
            </div>
          </div>
        )}

        <div className="detail-modal-footer">
          <button className="btn-secondary" type="button" onClick={onClose}>返回 / 关闭</button>
        </div>
      </div>
    </div>
  )
}

export default App
