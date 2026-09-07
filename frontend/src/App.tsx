import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

import { Workflow } from './Workflow'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

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
  chemical_system: string
  name: string | null
  description: string | null
}

type Paper = {
  id: string
  title: string
  doi: string | null
  journal: string | null
  publication_year: number | null
}

type Observation = {
  id: string
  material_formula: string | null
  property_name: string
  property_code: string
  value: number | string | boolean | null
  unit: string | null
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
  const [hits, setHits] = useState<SearchHit[]>([])
  const [status, setStatus] = useState('正在连接本地 API…')
  const [activeView, setActiveView] = useState<'overview' | 'materials' | 'papers' | 'workflow'>('overview')
  const [showMaterialForm, setShowMaterialForm] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [stats, materialPage, paperPage, observationPage] = await Promise.all([
        request<Dashboard>('/v1/dashboard'),
        request<Page<Material>>('/v1/materials'),
        request<Page<Paper>>('/v1/papers'),
        request<Page<Observation>>('/v1/observations'),
      ])
      setDashboard(stats)
      setMaterials(materialPage.items)
      setPapers(paperPage.items)
      setObservations(observationPage.items)
      setStatus('数据库已连接')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : '无法连接 API')
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  async function search(event: FormEvent) {
    event.preventDefault()
    if (!query.trim()) return
    try {
      const result = await request<{ hits: SearchHit[] }>('/v1/search', {
        method: 'POST',
        body: JSON.stringify({ query, targets: ['materials', 'papers'], mode: 'lexical', limit: 20 }),
      })
      setHits(result.hits)
      setStatus(`找到 ${result.hits.length} 条结果`)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : '搜索失败')
    }
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
          <span className="brand-mark">PC</span>
          <div><strong>PhaseChangeDB</strong><small>相变材料知识库</small></div>
        </div>
        <nav aria-label="主导航">
          <button className={activeView === 'overview' ? 'active' : ''} onClick={() => setActiveView('overview')}>概览</button>
          <button className={activeView === 'materials' ? 'active' : ''} onClick={() => setActiveView('materials')}>材料库 <span>{dashboard?.materials ?? '—'}</span></button>
          <button className={activeView === 'papers' ? 'active' : ''} onClick={() => setActiveView('papers')}>文献 <span>{dashboard?.papers ?? '—'}</span></button>
          <button className={activeView === 'workflow' ? 'active' : ''} onClick={() => setActiveView('workflow')}>录入与审核工作流</button>
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
                : '科学数据录入与审核工作流'}
            </h1>
          </div>
          {activeView !== 'workflow' && (
            <button className="primary" onClick={() => setShowMaterialForm(true)}>＋ 新建材料</button>
          )}
        </header>

        {activeView !== 'workflow' && (
          <form className="search" onSubmit={search}>
            <span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索化学式、体系、论文标题或 DOI…" /><button>搜索</button>
          </form>
        )}

        {hits.length > 0 && activeView !== 'workflow' && (
          <section className="search-results">
            <div className="section-title"><h2>搜索结果</h2><button onClick={() => setHits([])}>清除</button></div>
            {hits.map(hit => (
              <article key={hit.id}>
                <span>{hit.target === 'materials' ? '材料' : '文献'}</span>
                <div><strong>{hit.title}</strong><p>{hit.snippet || '暂无摘要'}</p></div>
              </article>
            ))}
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
            <div className="section-title"><div><p className="eyebrow">LATEST EVIDENCE</p><h2>最新观测</h2></div><span className="queue">{dashboard?.pending_outbox_events ?? 0} 个投影事件待处理</span></div>
            <ObservationTable items={observations} />
          </section>
        </>}

        {activeView === 'materials' && <section className="card-grid">{materials.map(material => <article className="entity-card" key={material.id}><div className="formula">{material.canonical_formula}</div><h2>{material.name || '未命名材料'}</h2><p>{material.chemical_system}</p><small>{material.description || '尚无材料说明'}</small></article>)}</section>}

        {activeView === 'papers' && <section className="paper-list">{papers.map(paper => <article key={paper.id}><div className="year">{paper.publication_year ?? '—'}</div><div><h2>{paper.title}</h2><p>{[paper.journal, paper.doi].filter(Boolean).join(' · ') || '暂无出版信息'}</p></div></article>)}</section>}

        {activeView === 'workflow' && <Workflow onDataChanged={() => void loadData()} />}
      </main>

      {showMaterialForm && <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowMaterialForm(false)}><form className="modal" onSubmit={createMaterial} onMouseDown={event => event.stopPropagation()}><div className="section-title"><h2>新建材料</h2><button type="button" onClick={() => setShowMaterialForm(false)}>×</button></div><label>规范化学式<input name="formula" required placeholder="例如 Ge2Sb2Te5" /></label><label>化学体系<input name="system" required placeholder="例如 Ge-Sb-Te" /></label><label>材料名称<input name="name" placeholder="可选" /></label><label>说明<textarea name="description" rows={3} placeholder="可选" /></label><button className="primary" type="submit">保存材料</button></form></div>}
    </div>
  )
}

function Metric({ label, value, accent }: { label: string; value: number | undefined; accent: string }) {
  return <article className={`metric ${accent}`}><span>{label}</span><strong>{value ?? '—'}</strong><small>权威数据源 · MySQL</small></article>
}

function ObservationTable({ items }: { items: Observation[] }) {
  if (items.length === 0) return <div className="empty">暂无观测数据</div>
  return <div className="table-wrap"><table><thead><tr><th>材料</th><th>属性</th><th>数值</th><th>状态</th><th>质量</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td><strong>{item.material_formula || '计算/器件'}</strong></td><td>{item.property_name}<small>{item.property_code}</small></td><td className="numeric">{String(item.value ?? '—')} {item.unit}</td><td><span className={`badge ${item.verification_status.toLowerCase()}`}>{item.verification_status}</span></td><td>{item.quality_score == null ? '—' : `${Math.round(item.quality_score * 100)}%`}</td></tr>)}</tbody></table></div>
}

export default App
