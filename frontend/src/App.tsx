import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

import { BatchUploadModal } from './components/BatchUploadModal'
import { KnowledgeGraphPlaceholder } from './components/KnowledgeGraphPlaceholder'
import { LiteratureAgentView } from './components/LiteratureAgentView'
import { LiteratureStatsView } from './components/LiteratureStatsView'
import { PeriodicTable } from './components/PeriodicTable'
import { PropertyComparisonBoard } from './components/PropertyComparisonBoard'
import type { MaterialVariantRead, ObservationConflictGroup } from './types/batch'
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

export interface MaterialFilters {
  minTc: string
  maxTc: string
  minLatentHeat: string
  maxLatentHeat: string
  lowToxicityOnly: boolean
  costEffectiveOnly: boolean
}

const FILTER_STORAGE_KEY = 'pcm_material_filters_v1'

type Material = {
  id: string
  canonical_formula: string
  reduced_formula?: string | null
  chemical_system: string
  name: string | null
  description: string | null
  aliases?: string[]
  is_low_toxicity?: boolean
  is_cost_effective?: boolean
  variant_count?: number
  paper_count?: number
  typical_properties?: Record<string, { value: number; unit: string; display: string }>
  variants?: MaterialVariantRead[]
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
  variants?: MaterialVariantRead[]
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
  abstract?: string | null
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
    'overview' | 'materials' | 'papers' | 'workflow' | 'agent' | 'knowledge-graph' | 'property-compare'
  >('overview')

  const [showMaterialForm, setShowMaterialForm] = useState(false)
  const [showBatchUpload, setShowBatchUpload] = useState(false)
  const [selectedMaterialId, setSelectedMaterialId] = useState<string | null>(null)
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null)
  const [paperTab, setPaperTab] = useState<'list' | 'stats'>('list')
  const [paperYearFilter, setPaperYearFilter] = useState<number | null>(null)
  const [paperJournalFilter, setPaperJournalFilter] = useState<string | null>(null)
  const [paperSystemFilter, setPaperSystemFilter] = useState<string | null>(null)


  const [appConfig, setAppConfig] = useState<AppConfig>({
    app_title: 'PhaseChangeDB',
    app_description: '相变材料知识库',
    app_logo: '/logo.svg',
  })
  const [availableElements, setAvailableElements] = useState<string[]>([])
  const [selectedElements, setSelectedElements] = useState<string[]>([])
  const [materialFilters, setMaterialFilters] = useState<MaterialFilters>(() => {
    try {
      const saved = localStorage.getItem(FILTER_STORAGE_KEY)
      if (saved) return JSON.parse(saved)
    } catch {
      // ignore
    }
    return {
      minTc: '',
      maxTc: '',
      minLatentHeat: '',
      maxLatentHeat: '',
      lowToxicityOnly: false,
      costEffectiveOnly: false,
    }
  })

  const [configEditTarget, setConfigEditTarget] = useState<'logo' | 'title' | 'description' | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [editingDescription, setEditingDescription] = useState('')
  const [editingLogo, setEditingLogo] = useState('')
  const [configSaving, setConfigSaving] = useState(false)
  const [configError, setConfigError] = useState<string | null>(null)

  // 自动持久化筛选条件至 localStorage
  useEffect(() => {
    try {
      localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(materialFilters))
    } catch {
      // ignore
    }
  }, [materialFilters])

  const buildMaterialsUrl = useCallback(
    (elements: string[], filters: MaterialFilters, queryStr?: string) => {
      const params = new URLSearchParams()
      if (elements.length > 0) params.set('elements', elements.join(','))
      if (filters.minTc.trim()) params.set('min_tc', filters.minTc.trim())
      if (filters.maxTc.trim()) params.set('max_tc', filters.maxTc.trim())
      if (filters.minLatentHeat.trim()) params.set('min_latent_heat', filters.minLatentHeat.trim())
      if (filters.maxLatentHeat.trim()) params.set('max_latent_heat', filters.maxLatentHeat.trim())
      if (filters.lowToxicityOnly) params.set('low_toxicity', 'true')
      if (filters.costEffectiveOnly) params.set('cost_effective', 'true')
      if (queryStr?.trim()) params.set('query', queryStr.trim())
      params.set('limit', '50')
      const qs = params.toString()
      return qs ? `/v1/materials?${qs}` : '/v1/materials'
    },
    []
  )

  const loadData = useCallback(async () => {
    try {
      const matUrl = buildMaterialsUrl(selectedElements, materialFilters)
      const [stats, materialPage, paperPage, observationPage, configRes, elementsRes] = await Promise.all([
        request<Dashboard>('/v1/dashboard'),
        request<Page<Material>>(matUrl),
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
  }, [selectedElements, materialFilters, buildMaterialsUrl])

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
      const url = buildMaterialsUrl(next, materialFilters)
      const page = await request<Page<Material>>(url)
      setMaterials(page.items)
    } catch (err) {
      console.error('筛选材料失败:', err)
    }
  }

  const handleClearElements = async () => {
    setSelectedElements([])
    try {
      const url = buildMaterialsUrl([], materialFilters)
      const page = await request<Page<Material>>(url)
      setMaterials(page.items)
    } catch (err) {
      console.error('清空筛选失败:', err)
    }
  }

  const handleFilterChange = async (newFilters: Partial<MaterialFilters>) => {
    const updated = { ...materialFilters, ...newFilters }
    setMaterialFilters(updated)
    try {
      const url = buildMaterialsUrl(selectedElements, updated)
      const page = await request<Page<Material>>(url)
      setMaterials(page.items)
    } catch (err) {
      console.error('应用属性筛选失败:', err)
    }
  }

  const handleResetAllFilters = async () => {
    const empty: MaterialFilters = {
      minTc: '',
      maxTc: '',
      minLatentHeat: '',
      maxLatentHeat: '',
      lowToxicityOnly: false,
      costEffectiveOnly: false,
    }
    setMaterialFilters(empty)
    setSelectedElements([])
    try {
      const url = buildMaterialsUrl([], empty)
      const page = await request<Page<Material>>(url)
      setMaterials(page.items)
    } catch (err) {
      console.error('重置筛选失败:', err)
    }
  }

  const handleApplyPreset = async () => {
    const preset: MaterialFilters = {
      minTc: '300',
      maxTc: '500',
      minLatentHeat: '200',
      maxLatentHeat: '',
      lowToxicityOnly: true,
      costEffectiveOnly: true,
    }
    setMaterialFilters(preset)
    try {
      const url = buildMaterialsUrl(selectedElements, preset)
      const page = await request<Page<Material>>(url)
      setMaterials(page.items)
    } catch (err) {
      console.error('应用预设方案失败:', err)
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
          <button className={activeView === 'agent' ? 'active' : ''} onClick={() => setActiveView('agent')}>文献解析智能体</button>
          <button className={activeView === 'property-compare' ? 'active' : ''} onClick={() => setActiveView('property-compare')}>物性横向对比</button>
          <button className={activeView === 'knowledge-graph' ? 'active' : ''} onClick={() => setActiveView('knowledge-graph')}>知识图谱</button>
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
                : activeView === 'property-compare'
                ? '相变物性横向对比与证据对齐看板'
                : '科学数据录入与审核工作流'}
            </h1>
          </div>
          {(activeView === 'overview' || activeView === 'materials' || activeView === 'papers') && (
            <button className="primary" onClick={() => setShowMaterialForm(true)}>＋ 新建材料</button>
          )}
        </header>

        {activeView !== 'workflow' && activeView !== 'agent' && activeView !== 'knowledge-graph' && activeView !== 'property-compare' && (
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
        {hits.length > 0 && activeView !== 'workflow' && activeView !== 'agent' && activeView !== 'knowledge-graph' && activeView !== 'property-compare' && (

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
        {hasSearched && hits.length === 0 && activeView !== 'workflow' && activeView !== 'agent' && activeView !== 'knowledge-graph' && activeView !== 'property-compare' && (
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
              <span
                className="queue"
                title="数据已安全保存在 MySQL 权威数据库，等待外部搜索索引与图数据库异步消费"
              >
                {dashboard?.pending_outbox_events ?? 0} 条待同步读模型 (Outbox)
              </span>
            </div>
            <ObservationTable
              items={observations}
              materials={materials}
              selectedElements={selectedElements}
              onSelectMaterial={(formulaOrId) => {
                const found = materials.find(
                  (m) => m.id === formulaOrId || m.canonical_formula === formulaOrId
                )
                if (found) {
                  setSelectedMaterialId(found.id)
                }
              }}
              onClearElements={handleClearElements}
            />
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
            {/* 材料物性多维组合筛选控制台 */}
            <div className="material-filter-bar">
              <div className="filter-bar-header">
                <div className="filter-bar-title">
                  <span className="filter-icon">⚙️</span>
                  <strong>材料物性多维组合筛选</strong>
                  <span className="filter-subtitle">（数值单位严格统一，支持与周期表联动并自动记忆）</span>
                </div>
                <div className="filter-presets-group">
                  <button
                    type="button"
                    className="preset-btn"
                    onClick={() => void handleApplyPreset()}
                    title="快捷载入：相变温度 300~500 K，潜热 > 200 J/g，低毒且成本可控"
                  >
                    🎯 推荐目标优选（300–500 K、&gt;200 J/g、低毒可控）
                  </button>
                  <button
                    type="button"
                    className="reset-btn"
                    onClick={() => void handleResetAllFilters()}
                  >
                    🔄 清空全部条件
                  </button>
                </div>
              </div>

              <div className="filter-controls-grid">
                {/* 温度范围 */}
                <div className="filter-control-item">
                  <label htmlFor="filter-min-tc">
                    相变温度范围 (<em>T<sub>c</sub></em>, 单位: <strong>K</strong>):
                  </label>
                  <div className="range-input-group">
                    <input
                      id="filter-min-tc"
                      type="number"
                      placeholder="下限，如 300"
                      value={materialFilters.minTc}
                      onChange={(e) => void handleFilterChange({ minTc: e.target.value })}
                    />
                    <span className="range-separator">至</span>
                    <input
                      id="filter-max-tc"
                      type="number"
                      placeholder="上限，如 500"
                      value={materialFilters.maxTc}
                      onChange={(e) => void handleFilterChange({ maxTc: e.target.value })}
                    />
                    <span className="unit-label">K</span>
                  </div>
                </div>

                {/* 相变潜热 */}
                <div className="filter-control-item">
                  <label htmlFor="filter-min-latent-heat">
                    相变潜热下限 (<em>ΔH</em>, 单位: <strong>J/g</strong>):
                  </label>
                  <div className="single-input-group">
                    <input
                      id="filter-min-latent-heat"
                      type="number"
                      placeholder="下限，如 200"
                      value={materialFilters.minLatentHeat}
                      onChange={(e) => void handleFilterChange({ minLatentHeat: e.target.value })}
                    />
                    <span className="unit-label">J/g</span>
                  </div>
                </div>

                {/* 布尔选项 */}
                <div className="filter-control-item checkboxes">
                  <label className="checkbox-label" title="严格定义：排除含 Pb, Cd, Hg, As, Tl, Be 元素">
                    <input
                      type="checkbox"
                      checked={materialFilters.lowToxicityOnly}
                      onChange={(e) => void handleFilterChange({ lowToxicityOnly: e.target.checked })}
                    />
                    <span>🌿 仅看低毒环保材料（无重金属）</span>
                  </label>
                  <label className="checkbox-label" title="严格定义：排除含 Au, Pt, Pd, Ru, Rh, Ir, Sc 贵金属元素">
                    <input
                      type="checkbox"
                      checked={materialFilters.costEffectiveOnly}
                      onChange={(e) => void handleFilterChange({ costEffectiveOnly: e.target.checked })}
                    />
                    <span>💎 仅看成本可控材料（无贵金属）</span>
                  </label>
                </div>
              </div>

              {/* 激活状态统计指示 */}
              <div className="filter-status-indicator">
                <span>
                  当前聚合主材料：<strong>{materials.length}</strong> 种
                  {selectedElements.length > 0 && `（已选元素：${selectedElements.join(', ')}）`}
                </span>
                {(materialFilters.minTc || materialFilters.maxTc || materialFilters.minLatentHeat || materialFilters.lowToxicityOnly || materialFilters.costEffectiveOnly || selectedElements.length > 0) && (
                  <span className="active-filter-badge">
                    ⚡ 筛选已生效（已自动保存至本地缓存）
                  </span>
                )}
              </div>
            </div>

            <section className="card-grid">
              {materials.length === 0 ? (
                <div className="empty full-width">
                  {selectedElements.length > 0
                    ? `未找到同时包含所选元素（${selectedElements.join(', ')}）并满足物性筛选的材料`
                    : '未找到满足当前属性筛选条件的材料'}
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
                    <div className="card-top-header">
                      <div className="formula">{material.canonical_formula}</div>
                      <div className="sci-indicator-tags">
                        {material.is_low_toxicity ? (
                          <span className="sci-tag low-tox" title="不含 Pb, Cd, Hg, As, Tl, Be">🌿 低毒</span>
                        ) : (
                          <span className="sci-tag toxic" title="含剧毒或管制重金属元素">⚠️ 重金属</span>
                        )}
                        {material.is_cost_effective ? (
                          <span className="sci-tag cost-eff" title="不含 Au, Pt, Pd, Ru, Rh, Ir, Sc 等贵金属">💎 成本可控</span>
                        ) : (
                          <span className="sci-tag expensive" title="含贵金属/高成本元素">💰 贵金属</span>
                        )}
                      </div>
                    </div>

                    <h2>{material.name || '未命名材料'}</h2>
                    <p className="chem-system">体系: {material.chemical_system || '—/暂无'}</p>

                    {/* 典型物性展示 */}
                    <div className="typical-props-row">
                      <div className="prop-metric-chip" title="典型结晶转变温度">
                        <span className="chip-label">相变温度 (Tc):</span>
                        <span className="chip-val">
                          {material.typical_properties?.crystallization_temperature?.display || '—'}
                        </span>
                      </div>
                      <div className="prop-metric-chip" title="典型相变潜热">
                        <span className="chip-label">相变潜热 (ΔH):</span>
                        <span className="chip-val">
                          {material.typical_properties?.latent_heat?.display || '—'}
                        </span>
                      </div>
                    </div>

                    <div className="mat-counts-bar">
                      <span className="count-pill">🧪 <strong>{material.variant_count ?? 1}</strong> 个实验变体</span>
                      <span className="count-pill">📄 <strong>{material.paper_count ?? 0}</strong> 篇来源文献</span>
                    </div>

                    <small className="mat-desc">{material.description || '标准相变材料条目'}</small>
                    <div className="card-footer-hint">点击展开变体条件与科学观测 ↗</div>
                  </article>
                ))
              )}
            </section>
          </>
        )}

        {activeView === 'papers' && (
          <>
            <div className="view-toolbar">
              <div className="paper-tab-group">
                <button
                  type="button"
                  className={`paper-tab-btn ${paperTab === 'list' ? 'active' : ''}`}
                  onClick={() => setPaperTab('list')}
                >
                  📚 文献列表
                </button>
                <button
                  type="button"
                  className={`paper-tab-btn ${paperTab === 'stats' ? 'active' : ''}`}
                  onClick={() => setPaperTab('stats')}
                >
                  📊 统计分析与分布
                </button>
              </div>

              <div className="toolbar-right-actions">
                <span className="toolbar-info">收录权威文献共 {papers.length} 篇</span>
                <button
                  type="button"
                  className="btn-batch-upload"
                  onClick={() => setShowBatchUpload(true)}
                >
                  📄 批量上传文献 / 压缩包
                </button>
              </div>
            </div>

            {/* 下钻筛选状态条 */}
            {(paperYearFilter || paperJournalFilter || paperSystemFilter) && paperTab === 'list' && (
              <div className="filter-chip-bar">
                <span className="chip-label">当前下钻筛选：</span>
                {paperYearFilter && (
                  <span className="filter-chip">
                    年份: {paperYearFilter}
                    <button type="button" onClick={() => setPaperYearFilter(null)}>×</button>
                  </span>
                )}
                {paperJournalFilter && (
                  <span className="filter-chip">
                    期刊: {paperJournalFilter}
                    <button type="button" onClick={() => setPaperJournalFilter(null)}>×</button>
                  </span>
                )}
                {paperSystemFilter && (
                  <span className="filter-chip highlight-system">
                    体系: {paperSystemFilter}
                    <button type="button" onClick={() => setPaperSystemFilter(null)}>×</button>
                  </span>
                )}
                <button
                  type="button"
                  className="button small text-button"
                  onClick={() => {
                    setPaperYearFilter(null)
                    setPaperJournalFilter(null)
                    setPaperSystemFilter(null)
                  }}
                >
                  清空筛选
                </button>
              </div>
            )}

            {paperTab === 'stats' ? (
              <LiteratureStatsView
                currentYearFilter={paperYearFilter}
                currentJournalFilter={paperJournalFilter}
                currentSystemFilter={paperSystemFilter}
                onFilterByYear={(year) => {
                  setPaperYearFilter(year)
                  setPaperTab('list')
                }}
                onFilterByJournal={(journal) => {
                  setPaperJournalFilter(journal)
                  setPaperTab('list')
                }}
                onFilterBySystem={(system) => {
                  setPaperSystemFilter(system)
                  setPaperTab('list')
                }}
                onSwitchToList={() => setPaperTab('list')}
                onClearFilters={() => {
                  setPaperYearFilter(null)
                  setPaperJournalFilter(null)
                  setPaperSystemFilter(null)
                }}
              />
            ) : (
              <section className="paper-list">
                {papers
                  .filter((paper) => {
                    if (paperYearFilter && paper.publication_year !== paperYearFilter) return false
                    if (
                      paperJournalFilter &&
                      (!paper.journal ||
                        !paper.journal.toLowerCase().includes(paperJournalFilter.toLowerCase()))
                    ) {
                      return false
                    }
                    if (paperSystemFilter) {
                      const pCorpus = `${paper.title} ${paper.abstract || ''}`.toLowerCase()
                      const sysParts = paperSystemFilter.split('-').map((s) => s.toLowerCase().trim())
                      const matchSys = sysParts.every((part) => pCorpus.includes(part))
                      if (!matchSys && !pCorpus.includes(paperSystemFilter.toLowerCase())) return false
                    }
                    return true
                  })
                  .length === 0 ? (
                  <div className="empty full-width">
                    <p>未找到符合当前筛选条件的学术成果</p>
                    {(paperYearFilter || paperJournalFilter || paperSystemFilter) && (
                      <button
                        type="button"
                        className="button small secondary"
                        style={{ marginTop: 12 }}
                        onClick={() => {
                          setPaperYearFilter(null)
                          setPaperJournalFilter(null)
                          setPaperSystemFilter(null)
                        }}
                      >
                        清空下钻筛选条件
                      </button>
                    )}
                  </div>
                ) : (
                  papers
                    .filter((paper) => {
                      if (paperYearFilter && paper.publication_year !== paperYearFilter) return false
                      if (
                        paperJournalFilter &&
                        (!paper.journal ||
                          !paper.journal.toLowerCase().includes(paperJournalFilter.toLowerCase()))
                      ) {
                        return false
                      }
                      if (paperSystemFilter) {
                        const pCorpus = `${paper.title} ${paper.abstract || ''}`.toLowerCase()
                        const sysParts = paperSystemFilter.split('-').map((s) => s.toLowerCase().trim())
                        const matchSys = sysParts.every((part) => pCorpus.includes(part))
                        if (!matchSys && !pCorpus.includes(paperSystemFilter.toLowerCase())) return false
                      }
                      return true
                    })
                    .map((paper) => (
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
            )}
          </>
        )}

        {activeView === 'workflow' && <Workflow onDataChanged={() => void loadData()} />}

        {activeView === 'agent' && (
          <LiteratureAgentView onOpenBatchUpload={() => setShowBatchUpload(true)} />
        )}

        {activeView === 'knowledge-graph' && (
          <KnowledgeGraphPlaceholder
            onSelectMaterial={(mid) => void openMaterialModal(mid)}
            onSelectPaper={(pid) => void openPaperModal(pid)}
          />
        )}

        {activeView === 'property-compare' && (
          <PropertyComparisonBoard
            onSelectMaterial={(mid) => void openMaterialModal(mid)}
            onSelectPaper={(pid) => void openPaperModal(pid)}
          />
        )}
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

interface ObservationTableProps {
  items: Observation[]
  materials?: Material[]
  selectedElements?: string[]
  onSelectMaterial?: (materialIdOrFormula: string) => void
  onClearElements?: () => void
}

function ObservationTable({
  items,
  selectedElements = [],
  onSelectMaterial,
  onClearElements,
}: ObservationTableProps) {
  // 从 localStorage 恢复筛选条件
  const [filters, setFilters] = useState(() => {
    try {
      const saved = localStorage.getItem('phasechangedb_overview_filters')
      if (saved) {
        return JSON.parse(saved)
      }
    } catch {
      // ignore
    }
    return {
      material: '',
      property: '',
      status: 'ALL',
      sortDirection: 'none' as 'none' | 'asc' | 'desc',
    }
  })

  // 持久化到 localStorage
  useEffect(() => {
    try {
      localStorage.setItem('phasechangedb_overview_filters', JSON.stringify(filters))
    } catch {
      // ignore
    }
  }, [filters])

  const [linkPeriodic, setLinkPeriodic] = useState(true)

  // 提取可用材料列表与属性列表
  const materialOptions = useMemo(() => {
    const formulas = new Set<string>()
    for (const item of items) {
      if (item.material_formula) {
        formulas.add(item.material_formula)
      }
    }
    return Array.from(formulas).sort()
  }, [items])

  const propertyOptions = useMemo(() => {
    const props = new Map<string, string>()
    for (const item of items) {
      if (item.property_code) {
        props.set(item.property_code, item.property_name || item.property_code)
      }
    }
    return Array.from(props.entries()).map(([code, name]) => ({ code, name }))
  }, [items])

  // 数值解析辅助函数
  const getNumericValue = (item: Observation): number => {
    if (item.normalized_value != null) return Number(item.normalized_value)
    if (typeof item.value === 'number') return item.value
    if (typeof item.value === 'string') {
      const parsed = parseFloat(item.value)
      if (!isNaN(parsed)) return parsed
    }
    if (item.display_value) {
      const match = item.display_value.match(/[-+]?[0-9]*\.?[0-9]+/)
      if (match) {
        const parsed = parseFloat(match[0])
        if (!isNaN(parsed)) return parsed
      }
    }
    return 0
  }

  // 过滤与排序
  const filteredAndSortedItems = useMemo(() => {
    return items
      .filter((item) => {
        if (filters.material && item.material_formula !== filters.material) {
          return false
        }
        if (filters.property && item.property_code !== filters.property) {
          return false
        }
        if (filters.status && filters.status !== 'ALL') {
          if (item.verification_status !== filters.status) {
            return false
          }
        }
        if (linkPeriodic && selectedElements.length > 0) {
          const formula = item.material_formula || ''
          const hasSelected = selectedElements.some((el) => formula.includes(el))
          if (!hasSelected) return false
        }
        return true
      })
      .sort((a, b) => {
        if (filters.sortDirection === 'none') return 0
        const valA = getNumericValue(a)
        const valB = getNumericValue(b)
        return filters.sortDirection === 'asc' ? valA - valB : valB - valA
      })
  }, [items, filters, linkPeriodic, selectedElements])

  const handleClearFilters = () => {
    setFilters({
      material: '',
      property: '',
      status: 'ALL',
      sortDirection: 'none',
    })
  }

  const toggleSort = () => {
    setFilters((prev: any) => ({
      ...prev,
      sortDirection:
        prev.sortDirection === 'none' ? 'asc' : prev.sortDirection === 'asc' ? 'desc' : 'none',
    }))
  }

  const hasActiveFilters =
    filters.material !== '' ||
    filters.property !== '' ||
    filters.status !== 'ALL' ||
    filters.sortDirection !== 'none' ||
    (linkPeriodic && selectedElements.length > 0)

  return (
    <div className="table-wrap">
      {/* 顶部多维筛选与排序控制条 */}
      <div className="overview-controls-bar">
        <div className="overview-filter-group">
          {/* 材料筛选 */}
          <label className="filter-item">
            <span>材料:</span>
            <select
              value={filters.material}
              onChange={(e) => setFilters((prev: any) => ({ ...prev, material: e.target.value }))}
            >
              <option value="">全部材料 ({materialOptions.length})</option>
              {materialOptions.map((f: string) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>

          {/* 属性筛选 */}
          <label className="filter-item">
            <span>属性:</span>
            <select
              value={filters.property}
              onChange={(e) => setFilters((prev: any) => ({ ...prev, property: e.target.value }))}
            >
              <option value="">全部属性 ({propertyOptions.length})</option>
              {propertyOptions.map((p: { code: string; name: string }) => (
                <option key={p.code} value={p.code}>
                  {p.name} ({p.code})
                </option>
              ))}
            </select>
          </label>

          {/* 审核状态筛选 */}
          <label className="filter-item">
            <span>状态:</span>
            <select
              value={filters.status}
              onChange={(e) => setFilters((prev: any) => ({ ...prev, status: e.target.value }))}
            >
              <option value="ALL">全部状态</option>
              <option value="VERIFIED">VERIFIED (已验证)</option>
              <option value="HUMAN_REVIEWED">HUMAN_REVIEWED (人工审核)</option>
              <option value="AI_EXTRACTED">AI_EXTRACTED (AI提取)</option>
              <option value="DISPUTED">DISPUTED (争议中)</option>
              <option value="RETRACTED">RETRACTED (已撤回)</option>
            </select>
          </label>

          {/* 元素周期表联动指示 */}
          {selectedElements.length > 0 && (
            <div className="periodic-linkage-badge">
              <span>周期表联动: {selectedElements.join(', ')}</span>
              <button
                type="button"
                onClick={() => setLinkPeriodic(!linkPeriodic)}
                title={linkPeriodic ? '暂时关闭周期表联动' : '恢复周期表联动'}
              >
                {linkPeriodic ? '✓' : '×'}
              </button>
              {onClearElements && (
                <button type="button" onClick={onClearElements} title="清空周期表选中">
                  清空
                </button>
              )}
            </div>
          )}
        </div>

        <div className="overview-actions-group">
          {hasActiveFilters && (
            <button
              type="button"
              className="button small text-button"
              onClick={handleClearFilters}
              style={{ fontSize: 12, padding: '4px 8px' }}
            >
              🔄 清空筛选与排序
            </button>
          )}
        </div>
      </div>

      {filteredAndSortedItems.length === 0 ? (
        <div className="overview-empty-state">
          <div style={{ fontSize: 32 }}>🔍</div>
          <h4>未找到符合当前组合筛选条件的科学观测数据</h4>
          <p style={{ fontSize: 13, color: '#64748b' }}>
            您可以尝试放宽筛选条件、取消周期表元素限制或清空筛选。
          </p>
          <button
            type="button"
            className="button small secondary"
            onClick={() => {
              handleClearFilters()
              if (onClearElements) onClearElements()
            }}
          >
            重置所有筛选
          </button>
        </div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>材料</th>
              <th>属性</th>
              <th className="sortable-th" onClick={toggleSort} title="点击切换升序/降序/默认排序">
                数值（规范单位）
                <span className="sort-icon">
                  {filters.sortDirection === 'asc'
                    ? ' ▲'
                    : filters.sortDirection === 'desc'
                    ? ' ▼'
                    : ' ⇕'}
                </span>
              </th>
              <th>状态</th>
              <th>质量分数</th>
            </tr>
          </thead>
          <tbody>
            {filteredAndSortedItems.map((item: Observation) => (
              <tr key={item.id}>
                <td>
                  <strong
                    className={item.material_formula && onSelectMaterial ? 'clickable-cell' : ''}
                    onClick={() => {
                      if (item.material_formula && onSelectMaterial) {
                        onSelectMaterial(item.material_formula)
                      }
                    }}
                    title={item.material_formula ? '点击查看该材料完整档案' : undefined}
                  >
                    {item.material_formula || '计算/器件'}
                    {item.material_formula && onSelectMaterial && ' ↗'}
                  </strong>
                </td>
                <td>
                  {item.property_name}
                  <small>{item.property_code}</small>
                </td>
                <td className="numeric">
                  {item.display_value ||
                    (item.value != null ? `${item.value} ${item.unit || ''}`.trim() : '—/暂无')}
                </td>
                <td>
                  <span className={`badge ${item.verification_status.toLowerCase()}`}>
                    {item.verification_status}
                  </span>
                </td>
                <td>
                  {item.quality_score == null
                    ? '—/暂无'
                    : `${Math.round(item.quality_score * 100)}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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

            {/* 实验变体与条件追溯列表 */}
            <div className="detail-sub-section">
              <div className="section-title">
                <h3>🔬 实验变体与工艺条件追溯 ({material.variants?.length ?? 0} 个变体)</h3>
                <span className="section-subtitle">主材料聚合下不同样品制备工艺、退火温度与测量条件全链路留痕</span>
              </div>

              {!material.variants || material.variants.length === 0 ? (
                <div className="detail-empty">该材料暂无细分样品变体记录</div>
              ) : (
                <div className="variants-list">
                  {material.variants.map((v, idx) => {
                    const isConflictVariant = conflicts.some((c) =>
                      c.items.some(
                        (it) => it.paper_id === v.paper_id || (it.first_author && it.first_author === v.first_author)
                      )
                    )
                    return (
                      <div
                        key={v.sample_id || idx}
                        className={`variant-item-card ${isConflictVariant ? 'has-conflict' : ''}`}
                      >
                        <div className="variant-header">
                          <div className="variant-title-row">
                            <span className="variant-badge">变体 #{idx + 1}</span>
                            <span className="variant-name">
                              {v.sample_label || v.original_name || `${material.canonical_formula} 样品`}
                            </span>
                            {v.doping_element ? (
                              <span className="doping-pill">
                                🧪 掺杂: {v.doping_element}{' '}
                                {v.doping_concentration ? `(${v.doping_concentration})` : ''}
                              </span>
                            ) : (
                              <span className="doping-pill undoped">本征 / 未掺杂</span>
                            )}
                            {isConflictVariant && (
                              <span className="conflict-tag-badge">
                                ⚠️ 结论冲突 / 需人工复核
                              </span>
                            )}
                          </div>
                        </div>

                        {/* 条件字段明细网格 */}
                        <div className="conditions-grid">
                          <div className="cond-cell">
                            <span className="cond-label">制备方法:</span>
                            <span className="cond-val">{v.preparation_method || '—/未标明'}</span>
                          </div>
                          <div className="cond-cell">
                            <span className="cond-label">退火温度:</span>
                            <span className="cond-val">{v.annealing_temperature ? `${v.annealing_temperature} K` : '—'}</span>
                          </div>
                          <div className="cond-cell">
                            <span className="cond-label">压力:</span>
                            <span className="cond-val">{v.pressure ? `${v.pressure} GPa` : '—'}</span>
                          </div>
                          <div className="cond-cell">
                            <span className="cond-label">测试方法:</span>
                            <span className="cond-val">{v.test_method || '—'}</span>
                          </div>
                          <div className="cond-cell">
                            <span className="cond-label">晶体相态:</span>
                            <span className="cond-val">{v.crystal_phase || '—'}</span>
                          </div>
                          <div className="cond-cell">
                            <span className="cond-label">反应气氛:</span>
                            <span className="cond-val">{v.atmosphere || '—'}</span>
                          </div>
                          <div className="cond-cell">
                            <span className="cond-label">冷却速率:</span>
                            <span className="cond-val">{v.cooling_rate || '—'}</span>
                          </div>
                        </div>

                        {/* 来源文献信息 */}
                        <div className="variant-paper-box">
                          <div className="paper-info-title">
                            📖 来源文献: {v.paper_title || '未关联独立文献'}
                          </div>
                          <div className="paper-meta-cols">
                            <span>第一作者: <strong>{v.first_author || '—'}</strong></span>
                            <span>通讯作者: <strong>{v.corresponding_author || '—'}</strong></span>
                            <span>期刊年份: {v.journal || '—'} {v.publication_year ? `(${v.publication_year})` : ''}</span>
                            {v.paper_doi && (
                              <span>
                                DOI:{' '}
                                <a
                                  href={`https://doi.org/${encodeURIComponent(v.paper_doi.trim())}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="paper-doi-link"
                                >
                                  {v.paper_doi} ↗
                                </a>
                              </span>
                            )}
                          </div>
                        </div>

                        {/* 该变体实测观测值 */}
                        {v.observations && v.observations.length > 0 && (
                          <div className="variant-obs-section">
                            <div className="obs-mini-title">实测科学观测数据:</div>
                            <div className="variant-obs-badges">
                              {v.observations.map((obs) => (
                                <span key={obs.id} className="obs-chip">
                                  <strong>{obs.property_name}:</strong>{' '}
                                  {obs.display_value ||
                                    (obs.value != null ? `${obs.value} ${obs.unit || ''}`.trim() : '—')}
                                  <small className={`obs-badge ${obs.verification_status.toLowerCase()}`}>
                                    {obs.verification_status}
                                  </small>
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

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
