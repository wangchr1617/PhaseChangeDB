import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import cytoscape from 'cytoscape'
import type { Core, NodeSingular, EventObject } from 'cytoscape'
import type { GraphNode, KnowledgeGraphResponse } from '../types/batch'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

interface KnowledgeGraphProps {
  onSelectMaterial?: (materialId: string) => void
  onSelectPaper?: (paperId: string) => void
}

const TYPE_CONFIG: Record<
  string,
  { label: string; color: string; radius: number; icon: string }
> = {
  material: { label: '相变材料', color: '#2563eb', radius: 24, icon: '🧪' },
  element: { label: '构成元素', color: '#d97706', radius: 18, icon: '⚛️' },
  system: { label: '化学体系', color: '#0891b2', radius: 20, icon: '🌐' },
  property: { label: '物性指标', color: '#059669', radius: 19, icon: '⚡' },
  paper: { label: '学术文献', color: '#7c3aed', radius: 21, icon: '📄' },
  first_author: { label: '第一作者', color: '#f59e0b', radius: 18, icon: '👤' },
  corresponding_author: { label: '通讯作者', color: '#10b981', radius: 18, icon: '✉️' },
  author: { label: '科研作者', color: '#eab308', radius: 18, icon: '👤' },
  journal: { label: '收录期刊', color: '#ec4899', radius: 19, icon: '📖' },
  dopant: { label: '掺杂元素', color: '#8b5cf6', radius: 18, icon: '🧪' },
  observation: { label: '实测物性', color: '#10b981', radius: 17, icon: '⚡' },
}

export function KnowledgeGraphPlaceholder({ onSelectMaterial, onSelectPaper }: KnowledgeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)

  const [data, setData] = useState<KnowledgeGraphResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedElement, setSelectedElement] = useState<string>('')
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  // 关联子图聚焦模式
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null)
  const [associationLevel, setAssociationLevel] = useState<1 | 2 | 3 | 'all'>('all')
  const [levelCounts, setLevelCounts] = useState({ l1: 0, l2: 0, l3: 0 })

  // 知识图谱分层模式：'macro' vs 'literature' vs 'fine_grained'
  const [graphMode, setGraphMode] = useState<'macro' | 'literature' | 'fine_grained'>('macro')
  const [activeMaterial, setActiveMaterial] = useState<{ id: string; formula: string } | null>(null)

  // 子图谱内的过滤条件
  const [subgraphSearch, setSubgraphSearch] = useState('')

  // 节点分类过滤状态
  const [filterTypes, setFilterTypes] = useState<Record<string, boolean>>({
    material: true,
    element: true,
    system: true,
    property: true,
    paper: true,
    first_author: true,
    corresponding_author: true,
    author: true,
    journal: true,
    dopant: true,
    observation: true,
  })

  // 获取后端图谱数据
  const fetchGraphData = useCallback(async (
    mode: 'macro' | 'literature' | 'fine_grained',
    elem?: string,
    targetMat?: { id: string; formula: string } | null
  ) => {
    setLoading(true)
    setError(null)
    setSelectedNode(null)
    setFocusNodeId(null)
    setAssociationLevel('all')

    try {
      let url = `${API_BASE}/v1/knowledge-graph/graph?limit=100`
      if (mode === 'fine_grained') {
        const matParam = targetMat?.formula ? `&material=${encodeURIComponent(targetMat.formula)}` : ''
        url = `${API_BASE}/v1/knowledge-graph/graph?subgraph=fine_grained${matParam}&limit=120`
      } else if (mode === 'literature') {
        const matId = targetMat?.id || ''
        url = `${API_BASE}/v1/knowledge-graph/graph?material_id=${encodeURIComponent(matId)}&include_papers=true&limit=100`
      } else if (elem) {
        url += `&element=${encodeURIComponent(elem)}`
      }

      const res = await fetch(url)
      if (!res.ok) {
        throw new Error(`获取知识图谱数据失败: HTTP ${res.status}`)
      }
      const json: KnowledgeGraphResponse = await res.json()
      setData(json)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '加载图谱失败'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchGraphData(graphMode, selectedElement, activeMaterial)
  }, [graphMode, selectedElement, activeMaterial, fetchGraphData])

  // 节点类型过滤与关键词搜索后的可视节点与边
  const filteredElements = useMemo(() => {
    if (!data) return { nodes: [], edges: [] }

    const visibleNodeMap = new Map<string, GraphNode>()
    data.nodes.forEach((n) => {
      // 1. 类型开关过滤
      if (!filterTypes[n.node_type]) return

      // 2. 搜索过滤
      if (subgraphSearch.trim()) {
        const q = subgraphSearch.trim().toLowerCase()
        const matchLabel = n.label.toLowerCase().includes(q)
        const matchProp = JSON.stringify(n.properties || {}).toLowerCase().includes(q)
        if (!matchLabel && !matchProp) return
      }

      visibleNodeMap.set(n.id, n)
    })

    const visibleEdges = data.edges.filter((e) => {
      return visibleNodeMap.has(e.source) && visibleNodeMap.has(e.target)
    })

    return {
      nodes: Array.from(visibleNodeMap.values()),
      edges: visibleEdges,
    }
  }, [data, filterTypes, subgraphSearch])

  // 初始化并更新 Cytoscape 实例
  useEffect(() => {
    if (!containerRef.current) return

    // 转换成 Cytoscape 数据格式
    const cyElements: cytoscape.ElementDefinition[] = [
      ...filteredElements.nodes.map((n) => {
        const conf = TYPE_CONFIG[n.node_type] || { color: '#64748b', radius: 18 }
        return {
          group: 'nodes' as const,
          data: {
            id: n.id,
            label: n.label,
            node_type: n.node_type,
            properties: n.properties,
            bgColor: conf.color,
            nodeSize: conf.radius * 2,
          },
        }
      }),
      ...filteredElements.edges.map((e, idx) => ({
        group: 'edges' as const,
        data: {
          id: `edge_${e.source}_${e.target}_${idx}`,
          source: e.source,
          target: e.target,
          label: e.label || e.edge_type || '',
          edge_type: e.edge_type,
        },
      })),
    ]

    // 创建或重置 Cytoscape
    if (!cyRef.current) {
      const cy = cytoscape({
        container: containerRef.current,
        elements: cyElements,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': 'data(bgColor)',
              label: 'data(label)',
              width: 'data(nodeSize)',
              height: 'data(nodeSize)',
              color: '#1e293b',
              'font-size': '11px',
              'font-weight': 'bold',
              'text-valign': 'bottom',
              'text-margin-y': 4,
              'text-background-opacity': 0.8,
              'text-background-color': '#ffffff',
              'text-background-padding': '2px',
              'text-background-shape': 'roundrectangle',
              'transition-property': 'opacity, border-width, border-color',
              'transition-duration': 0.25,
            },
          },
          {
            selector: 'edge',
            style: {
              width: 1.5,
              'line-color': '#cbd5e1',
              'target-arrow-color': '#94a3b8',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              'arrow-scale': 0.8,
              opacity: 0.75,
              'transition-property': 'opacity, line-color, width',
              'transition-duration': 0.25,
            },
          },
          {
            selector: '.highlighted',
            style: {
              opacity: 1,
              'z-index': 99,
            },
          },
          {
            selector: 'edge.highlighted',
            style: {
              'line-color': '#2563eb',
              'target-arrow-color': '#2563eb',
              width: 2.5,
              opacity: 1,
            },
          },
          {
            selector: '.dimmed',
            style: {
              opacity: 0.15,
            },
          },
          {
            selector: '.selected-node',
            style: {
              'border-width': 4,
              'border-color': '#f59e0b',
              'border-opacity': 1,
            },
          },
        ],
        layout: {
          name: 'cose',
          animate: false,
          randomize: false,
          componentSpacing: 60,
          nodeOverlap: 20,
          idealEdgeLength: () => 70,
        },
        wheelSensitivity: 0.3,
        minZoom: 0.2,
        maxZoom: 3.5,
      })

      // 绑定节点点击
      cy.on('tap', 'node', (evt: EventObject) => {
        const target = evt.target as NodeSingular
        const nodeData = target.data()
        setSelectedNode({
          id: nodeData.id,
          label: nodeData.label,
          node_type: nodeData.node_type,
          properties: nodeData.properties || {},
        })
        const n1 = target.neighborhood().nodes()
        const n2 = target.neighborhood().nodes().neighborhood().nodes().difference(target)
        const n3 = n2.neighborhood().nodes().difference(target)
        setLevelCounts({
          l1: n1.length,
          l2: n2.length,
          l3: n3.length,
        })
      })

      // 点击空白处取消高亮与选中
      cy.on('tap', (evt: EventObject) => {
        if (evt.target === cy) {
          setSelectedNode(null)
          setFocusNodeId(null)
          setAssociationLevel('all')
          setLevelCounts({ l1: 0, l2: 0, l3: 0 })
          cy.elements().removeClass('highlighted dimmed selected-node')
        }
      })

      cyRef.current = cy
    } else {
      const cy = cyRef.current
      cy.elements().remove()
      cy.add(cyElements)
      const layout = cy.layout({
        name: 'cose',
        animate: false,
        componentSpacing: 60,
        idealEdgeLength: () => 70,
      })
      layout.run()
    }
  }, [filteredElements])

  // 多级关联子图高亮（1/2/3 级邻居）
  const applyAssociationLevel = useCallback((level: 1 | 2 | 3 | 'all', rootId: string | null) => {
    if (!cyRef.current) return
    const cy = cyRef.current

    if (level === 'all' || !rootId) {
      cy.elements().removeClass('highlighted dimmed selected-node')
      return
    }

    const root = cy.$id(rootId)
    if (!root || root.length === 0) return

    let neighborhood: cytoscape.CollectionReturnValue = root
    let frontier: cytoscape.NodeCollection = root

    for (let i = 0; i < level; i++) {
      const nextHop = frontier.neighborhood()
      neighborhood = neighborhood.union(nextHop)
      frontier = nextHop.nodes()
    }

    cy.elements().addClass('dimmed').removeClass('highlighted selected-node')
    neighborhood.removeClass('dimmed').addClass('highlighted')
    root.addClass('selected-node')
  }, [])

  // 监听 focusNodeId 与 associationLevel 改变
  useEffect(() => {
    applyAssociationLevel(associationLevel, focusNodeId)
  }, [associationLevel, focusNodeId, applyAssociationLevel])

  // 重置视角居中
  const handleFit = () => {
    cyRef.current?.fit(undefined, 30)
  }

  // 重新计算力导向布局
  const handleRelayout = () => {
    if (!cyRef.current) return
    const layout = cyRef.current.layout({
      name: 'cose',
      animate: true,
      animationDuration: 400,
      componentSpacing: 60,
      idealEdgeLength: () => 70,
    })
    layout.run()
  }

  // 导出图谱高清 PNG 图片
  const handleExportPng = () => {
    if (!cyRef.current) return
    const pngUri = cyRef.current.png({ full: true, scale: 2, bg: '#ffffff' })
    const link = document.createElement('a')
    link.href = pngUri
    link.download = `PhaseChangeDB_KnowledgeGraph_${graphMode}.png`
    link.click()
  }

  // 下钻探索文献子图
  const handleExploreLiteratureSubgraph = (materialId: string, formula: string) => {
    setActiveMaterial({ id: materialId, formula })
    setGraphMode('literature')
  }

  return (
    <div className="knowledge-graph-container">
      {/* 顶部标题栏与模式切换 */}
      <div className="kg-header">
        <div>
          <div className="kg-badge">
            <span className="pulse-indicator" />
            <span>KNOWLEDGE TOPOLOGY · 科学拓扑物理引擎 (Cytoscape.js)</span>
          </div>
          <h2>相变材料全景知识图谱与证据星丛</h2>
          <p className="kg-subtitle">
            融合材料组成、晶态物理、实测物性与文献作者证据网络，支持 1/2/3 级邻居拓扑高亮与子图下钻。
          </p>
        </div>

        {/* 模式选择 */}
        <div className="kg-mode-selector">
          <button
            className={`mode-btn ${graphMode === 'macro' ? 'active' : ''}`}
            onClick={() => {
              setGraphMode('macro')
              setActiveMaterial(null)
            }}
          >
            🌐 宏观科学骨干网络
          </button>
          <button
            className={`mode-btn ${graphMode === 'literature' ? 'active' : ''}`}
            onClick={() => setGraphMode('literature')}
          >
            📚 文献作者星丛
          </button>
          <button
            className={`mode-btn ${graphMode === 'fine_grained' ? 'active' : ''}`}
            onClick={() => setGraphMode('fine_grained')}
          >
            ⚡ 细粒度物性证据链
          </button>
        </div>
      </div>

      {/* 统计指标面板 */}
      {data?.summary && (
        <div className="kg-stats-grid">
          <div className="stat-card">
            <span className="stat-num">{filteredElements.nodes.length}</span>
            <span className="stat-lbl">可视节点</span>
          </div>
          <div className="stat-card">
            <span className="stat-num">{filteredElements.edges.length}</span>
            <span className="stat-lbl">关联拓扑边</span>
          </div>
          <div className="stat-card">
            <span className="stat-num">{data.summary.material_count}</span>
            <span className="stat-lbl">相变材料</span>
          </div>
          <div className="stat-card">
            <span className="stat-num">{data.summary.paper_count}</span>
            <span className="stat-lbl">学术论文</span>
          </div>
          <div className="stat-card">
            <span className="stat-num">{data.summary.property_count}</span>
            <span className="stat-lbl">物性指标</span>
          </div>
        </div>
      )}

      {/* 控制工具条：元素过滤、类型筛选、视角控制、图片导出 */}
      <div className="kg-toolbar" style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, padding: '10px 14px', backgroundColor: '#f8fafc', borderRadius: 8, margin: '12px 0' }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* 元素筛选 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 13, color: '#475569', fontWeight: 500 }}>主干元素:</span>
            <select
              value={selectedElement}
              onChange={(e) => setSelectedElement(e.target.value)}
              style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 13 }}
            >
              <option value="">全部元素</option>
              <option value="Te">碲 (Te)</option>
              <option value="Sb">锑 (Sb)</option>
              <option value="Ge">锗 (Ge)</option>
              <option value="Bi">铋 (Bi)</option>
              <option value="In">铟 (In)</option>
              <option value="Ti">钛 (Ti)</option>
            </select>
          </div>

          {/* 关键字搜索 */}
          <input
            type="text"
            placeholder="搜索节点名称/属性..."
            value={subgraphSearch}
            onChange={(e) => setSubgraphSearch(e.target.value)}
            style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 13, width: 160 }}
          />

          {/* 节点类型过滤器 */}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            {(['material', 'element', 'property', 'paper'] as const).map((type) => (
              <label key={type} style={{ fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 3, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={filterTypes[type]}
                  onChange={(e) => setFilterTypes((prev) => ({ ...prev, [type]: e.target.checked }))}
                />
                <span style={{ color: TYPE_CONFIG[type]?.color }}>{TYPE_CONFIG[type]?.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* 视角控制与导出 */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            onClick={handleFit}
            style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #cbd5e1', backgroundColor: '#fff', fontSize: 13, cursor: 'pointer' }}
            title="居中适应画布"
          >
            🎯 自适应居中
          </button>
          <button
            onClick={handleRelayout}
            style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #cbd5e1', backgroundColor: '#fff', fontSize: 13, cursor: 'pointer' }}
            title="重新执行物理力导向"
          >
            🔄 重新排布
          </button>
          <button
            onClick={handleExportPng}
            style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #cbd5e1', backgroundColor: '#fff', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}
            title="导出当前知识图谱高清 PNG"
          >
            📷 导出高清图 (PNG)
          </button>
        </div>
      </div>

      {/* 主画布与侧边抽屉 */}
      <div className="kg-workspace" style={{ display: 'flex', gap: 16, minHeight: 600 }}>
        {/* Cytoscape 容器 */}
        <div
          style={{
            flex: 1,
            position: 'relative',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            backgroundColor: '#ffffff',
            overflow: 'hidden',
          }}
        >
          {loading && (
            <div style={{ position: 'absolute', top: '40%', left: '45%', zIndex: 10, fontSize: 14, color: '#64748b' }}>
              正在加载图谱拓扑...
            </div>
          )}
          {error && (
            <div style={{ position: 'absolute', top: 20, left: 20, zIndex: 10, color: '#dc2626', fontSize: 14 }}>
              ⚠️ {error}
            </div>
          )}
          <div ref={containerRef} style={{ width: '100%', height: '600px' }} />

          <div
            style={{
              position: 'absolute',
              bottom: 8,
              left: 12,
              fontSize: 12,
              color: '#94a3b8',
              pointerEvents: 'none',
            }}
          >
            💡 滚轮平滑缩放 · 拖动画布平移 · 单击节点高亮邻居并在右侧查看属性
          </div>
        </div>

        {/* 右侧节点详情抽屉 */}
        <div
          className="kg-side-panel"
          style={{
            width: 320,
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            padding: 16,
            backgroundColor: '#f8fafc',
          }}
        >
          {selectedNode ? (
            <div className="node-detail-card">
              <div
                style={{
                  borderLeft: `4px solid ${TYPE_CONFIG[selectedNode.node_type]?.color || '#64748b'}`,
                  paddingLeft: 10,
                  marginBottom: 12,
                }}
              >
                <span
                  style={{
                    display: 'inline-block',
                    padding: '2px 8px',
                    borderRadius: 4,
                    fontSize: 11,
                    color: '#fff',
                    backgroundColor: TYPE_CONFIG[selectedNode.node_type]?.color || '#64748b',
                  }}
                >
                  {TYPE_CONFIG[selectedNode.node_type]?.label || selectedNode.node_type}
                </span>
                <h3 style={{ margin: '6px 0 0 0', fontSize: 16 }}>{selectedNode.label}</h3>
              </div>

              {/* 关联子图层级控制 */}
              <div style={{ margin: '12px 0', padding: '10px', backgroundColor: '#fff', borderRadius: 6, border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                  🎯 邻居拓扑关联层级：
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                  <button
                    style={{
                      padding: '4px 6px',
                      fontSize: 11,
                      borderRadius: 4,
                      border: '1px solid #cbd5e1',
                      backgroundColor: associationLevel === 1 ? '#2563eb' : '#fff',
                      color: associationLevel === 1 ? '#fff' : '#334155',
                      cursor: 'pointer',
                    }}
                    onClick={() => setAssociationLevel(1)}
                  >
                    1级邻居 ({levelCounts.l1})
                  </button>
                  <button
                    style={{
                      padding: '4px 6px',
                      fontSize: 11,
                      borderRadius: 4,
                      border: '1px solid #cbd5e1',
                      backgroundColor: associationLevel === 2 ? '#2563eb' : '#fff',
                      color: associationLevel === 2 ? '#fff' : '#334155',
                      cursor: 'pointer',
                    }}
                    onClick={() => setAssociationLevel(2)}
                  >
                    2级邻居 ({levelCounts.l2})
                  </button>
                  <button
                    style={{
                      padding: '4px 6px',
                      fontSize: 11,
                      borderRadius: 4,
                      border: '1px solid #cbd5e1',
                      backgroundColor: associationLevel === 3 ? '#2563eb' : '#fff',
                      color: associationLevel === 3 ? '#fff' : '#334155',
                      cursor: 'pointer',
                    }}
                    onClick={() => setAssociationLevel(3)}
                  >
                    3级邻居 ({levelCounts.l3})
                  </button>
                  <button
                    style={{
                      padding: '4px 6px',
                      fontSize: 11,
                      borderRadius: 4,
                      border: '1px solid #cbd5e1',
                      backgroundColor: associationLevel === 'all' ? '#2563eb' : '#fff',
                      color: associationLevel === 'all' ? '#fff' : '#334155',
                      cursor: 'pointer',
                    }}
                    onClick={() => setAssociationLevel('all')}
                  >
                    全图高亮
                  </button>
                </div>
              </div>

              {/* 科学属性 */}
              <div style={{ fontSize: 13 }}>
                {selectedNode.node_type === 'material' && (
                  <div>
                    <div style={{ margin: '6px 0' }}>
                      <strong>化学体系：</strong> {String(selectedNode.properties?.chemical_system || '—')}
                    </div>
                    <div style={{ margin: '6px 0' }}>
                      <strong>材料名称：</strong> {String(selectedNode.properties?.name || selectedNode.label)}
                    </div>
                    <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {graphMode === 'macro' && Boolean(selectedNode.properties?.material_id) && (
                        <button
                          style={{ padding: '6px 10px', fontSize: 12, cursor: 'pointer', borderRadius: 4, border: 'none', backgroundColor: '#2563eb', color: '#fff' }}
                          onClick={() => handleExploreLiteratureSubgraph(String(selectedNode.properties?.material_id), selectedNode.label)}
                        >
                          🔬 展开文献星丛子图
                        </button>
                      )}
                      {Boolean(selectedNode.properties?.material_id) && onSelectMaterial && (
                        <button
                          style={{ padding: '6px 10px', fontSize: 12, cursor: 'pointer', borderRadius: 4, border: '1px solid #cbd5e1', backgroundColor: '#fff' }}
                          onClick={() => onSelectMaterial(String(selectedNode.properties?.material_id))}
                        >
                          🧪 查看材料物性详情
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {selectedNode.node_type === 'paper' && (
                  <div>
                    <div style={{ margin: '6px 0' }}>
                      <strong>标题：</strong> {String(selectedNode.properties?.title || selectedNode.label)}
                    </div>
                    <div style={{ margin: '6px 0' }}>
                      <strong>期刊：</strong> {String(selectedNode.properties?.journal || '—')}
                    </div>
                    <div style={{ margin: '6px 0' }}>
                      <strong>第一作者：</strong> {String(selectedNode.properties?.first_author || '—')}
                    </div>
                    {Boolean(selectedNode.properties?.doi) && (
                      <div style={{ margin: '6px 0' }}>
                        <strong>DOI：</strong>
                        <a
                          href={`https://doi.org/${selectedNode.properties?.doi}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: '#2563eb', marginLeft: 4 }}
                        >
                          {String(selectedNode.properties?.doi)} ↗
                        </a>
                      </div>
                    )}
                    {Boolean(selectedNode.properties?.paper_id && onSelectPaper) && (
                      <button
                        style={{ marginTop: 10, padding: '6px 10px', fontSize: 12, cursor: 'pointer', borderRadius: 4, border: '1px solid #cbd5e1', backgroundColor: '#fff', width: '100%' }}
                        onClick={() => onSelectPaper?.(String(selectedNode.properties?.paper_id))}
                      >
                        📄 查看文献详情
                      </button>
                    )}
                  </div>
                )}

                {selectedNode.node_type === 'element' && (
                  <div>
                    <div style={{ margin: '6px 0' }}>
                      <strong>元素符号：</strong> <span style={{ fontFamily: 'monospace' }}>{selectedNode.label}</span>
                    </div>
                    <div style={{ margin: '6px 0' }}>
                      <strong>角色说明：</strong> 相变材料基本组分元素
                    </div>
                  </div>
                )}

                {selectedNode.node_type === 'property' && (
                  <div>
                    <div style={{ margin: '6px 0' }}>
                      <strong>物性名称：</strong> {String(selectedNode.properties?.name || selectedNode.label)}
                    </div>
                    <div style={{ margin: '6px 0' }}>
                      <strong>物性代号：</strong> <span style={{ fontFamily: 'monospace' }}>{String(selectedNode.properties?.code || '—')}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: '#94a3b8', paddingTop: 60, fontSize: 13 }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
              请在左侧点击任意节点，<br />
              查看详细科学元数据与证据拓扑。
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
