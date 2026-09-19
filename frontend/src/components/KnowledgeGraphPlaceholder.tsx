import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import type { MouseEvent, WheelEvent } from 'react'
import type { GraphNode, KnowledgeGraphResponse } from '../types/batch'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

interface KnowledgeGraphProps {
  onSelectMaterial?: (materialId: string) => void
  onSelectPaper?: (paperId: string) => void
}

interface SimNode extends GraphNode {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  color: string
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
  const [data, setData] = useState<KnowledgeGraphResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedElement, setSelectedElement] = useState<string>('')
  const [selectedNode, setSelectedNode] = useState<SimNode | null>(null)

  // 关联子图聚焦模式：选择节点后仅展示其 1/2/3 级关联子图
  const [focusNode, setFocusNode] = useState<SimNode | null>(null)
  const [associationLevel, setAssociationLevel] = useState<1 | 2 | 3 | 'all'>('all')

  // 知识图谱分层模式：'macro' (宏观科学骨干) vs 'literature' (材料文献与作者证据子图谱) vs 'fine_grained' (细粒度物性证据链)
  const [graphMode, setGraphMode] = useState<'macro' | 'literature' | 'fine_grained'>('macro')
  const [activeMaterial, setActiveMaterial] = useState<{ id: string; formula: string } | null>(null)

  // 子图谱内的过滤条件
  const [subgraphSearch, setSubgraphSearch] = useState('')
  const [subgraphYearFilter, setSubgraphYearFilter] = useState<string>('')

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

  // 画布变换状态：平移与缩放
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 })
  const [isPanning, setIsPanning] = useState(false)
  const [isPhysicsRunning, setIsPhysicsRunning] = useState(true)
  const panStartRef = useRef({ x: 0, y: 0 })
  const draggedNodeRef = useRef<SimNode | null>(null)

  // 物理与渲染节点存储
  const [displayNodes, setDisplayNodes] = useState<SimNode[]>([])
  const nodesRef = useRef<SimNode[]>([])
  const animFrameRef = useRef<number | null>(null)
  const isRunningRef = useRef(true)

  // 画布尺寸
  const canvasWidth = 860
  const canvasHeight = 580

  // 获取后端图谱数据
  const fetchGraphData = useCallback(async (
    mode: 'macro' | 'literature' | 'fine_grained',
    elem?: string,
    targetMat?: { id: string; formula: string } | null
  ) => {
    setLoading(true)
    setError(null)
    setSelectedNode(null)
    try {
      let url = `${API_BASE}/v1/knowledge-graph/graph?limit=100`
      if (mode === 'fine_grained') {
        url += '&subgraph=fine_grained'
        if (targetMat) {
          url += `&material_id=${encodeURIComponent(targetMat.id)}`
        }
      } else if (mode === 'literature' && targetMat) {
        url += `&material_id=${encodeURIComponent(targetMat.id)}&subgraph=literature`
      } else {
        url += '&include_papers=false'
        if (elem) {
          url += `&element=${encodeURIComponent(elem)}`
        }
      }

      const res = await fetch(url)
      if (!res.ok) {
        throw new Error(`获取图谱失败: HTTP ${res.status}`)
      }
      const graphData: KnowledgeGraphResponse = await res.json()
      setData(graphData)

      // 初始化力导向节点坐标（环形发散分布）
      const count = graphData.nodes.length
      const centerX = canvasWidth / 2
      const centerY = canvasHeight / 2
      const radius = Math.min(centerX, centerY) * 0.68

      const simNodes: SimNode[] = graphData.nodes.map((n, i) => {
        // 若子图谱中有材料主节点，将其置于中心
        const isRootMat = (mode === 'literature' || mode === 'fine_grained') && n.node_type === 'material'
        const angle = (i / Math.max(count, 1)) * 2 * Math.PI
        const typeCfg = TYPE_CONFIG[n.node_type] || TYPE_CONFIG.material
        const jitter = (Math.random() - 0.5) * 35

        return {
          ...n,
          x: isRootMat ? centerX : centerX + (radius + jitter) * Math.cos(angle),
          y: isRootMat ? centerY : centerY + (radius + jitter) * Math.sin(angle),
          vx: 0,
          vy: 0,
          radius: isRootMat ? 28 : typeCfg.radius,
          color: typeCfg.color,
        }
      })

      nodesRef.current = simNodes
      setDisplayNodes(simNodes)
      isRunningRef.current = true
    } catch (err: any) {
      setError(err.message || '知识图谱数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  // 监听模式或元素过滤变化重新加载
  useEffect(() => {
    void fetchGraphData(graphMode, selectedElement || undefined, activeMaterial)
  }, [fetchGraphData, graphMode, selectedElement, activeMaterial])

  // 切换回宏观骨干主图谱
  const handleReturnToMacro = () => {
    setGraphMode('macro')
    setActiveMaterial(null)
    setSubgraphSearch('')
    setSubgraphYearFilter('')
    setTransform({ x: 0, y: 0, scale: 1 })
  }

  // 下钻进入指定材料的文献证据子图谱
  const handleExploreLiteratureSubgraph = (materialId: string, formula: string) => {
    setActiveMaterial({ id: materialId, formula })
    setGraphMode('literature')
    setSubgraphSearch('')
    setSubgraphYearFilter('')
    setTransform({ x: 0, y: 0, scale: 1 })
  }

  // 力导向物理引擎循环
  useEffect(() => {
    const kRepulse = graphMode === 'literature' ? 4200 : 3400 // 库仑斥力
    const kAttract = 0.048 // 弹簧引力
    const kCenter = 0.016 // 向心引力
    const damping = 0.88 // 速度阻尼
    const defaultDist = graphMode === 'literature' ? 125 : 110

    let stepCount = 0

    const tick = () => {
      if (!isRunningRef.current || !data) {
        animFrameRef.current = requestAnimationFrame(tick)
        return
      }

      const nodes = nodesRef.current
      const edges = data.edges
      const centerX = canvasWidth / 2
      const centerY = canvasHeight / 2

      // 1. 库仑斥力
      for (let i = 0; i < nodes.length; i++) {
        const n1 = nodes[i]
        for (let j = i + 1; j < nodes.length; j++) {
          const n2 = nodes[j]
          const dx = n2.x - n1.x
          const dy = n2.y - n1.y
          const distSq = dx * dx + dy * dy + 100
          const dist = Math.sqrt(distSq)
          const force = kRepulse / distSq
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force

          if (n1 !== draggedNodeRef.current) {
            n1.vx -= fx
            n1.vy -= fy
          }
          if (n2 !== draggedNodeRef.current) {
            n2.vx += fx
            n2.vy += fy
          }
        }
      }

      // 2. 边弹簧引力
      const nodeMap = new Map(nodes.map((n) => [n.id, n]))
      for (const e of edges) {
        const sourceNode = nodeMap.get(e.source)
        const targetNode = nodeMap.get(e.target)
        if (sourceNode && targetNode) {
          const dx = targetNode.x - sourceNode.x
          const dy = targetNode.y - sourceNode.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const displacement = dist - defaultDist
          const force = displacement * kAttract
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force

          if (sourceNode !== draggedNodeRef.current) {
            sourceNode.vx += fx
            sourceNode.vy += fy
          }
          if (targetNode !== draggedNodeRef.current) {
            targetNode.vx -= fx
            targetNode.vy -= fy
          }
        }
      }

      // 3. 向心力与位移更新
      let maxVelocity = 0
      for (const n of nodes) {
        if (n === draggedNodeRef.current) continue

        // 若子图谱中的材料根节点，保持靠近中心
        if (graphMode === 'literature' && n.node_type === 'material') {
          n.vx += (centerX - n.x) * (kCenter * 2.5)
          n.vy += (centerY - n.y) * (kCenter * 2.5)
        } else {
          n.vx += (centerX - n.x) * kCenter
          n.vy += (centerY - n.y) * kCenter
        }

        n.vx *= damping
        n.vy *= damping
        n.x += n.vx
        n.y += n.vy

        // 画布边界缓冲
        const pad = n.radius + 15
        if (n.x < pad) {
          n.x = pad
          n.vx = -n.vx * 0.5
        }
        if (n.x > canvasWidth - pad) {
          n.x = canvasWidth - pad
          n.vx = -n.vx * 0.5
        }
        if (n.y < pad) {
          n.y = pad
          n.vy = -n.vy * 0.5
        }
        if (n.y > canvasHeight - pad) {
          n.y = canvasHeight - pad
          n.vy = -n.vy * 0.5
        }

        const v = Math.sqrt(n.vx * n.vx + n.vy * n.vy)
        if (v > maxVelocity) maxVelocity = v
      }

      stepCount++
      if (stepCount % 2 === 0 || maxVelocity < 0.15) {
        setDisplayNodes([...nodes])
      }

      if (stepCount > 180 && maxVelocity < 0.12 && !draggedNodeRef.current) {
        isRunningRef.current = false
        setDisplayNodes([...nodes])
      }

      animFrameRef.current = requestAnimationFrame(tick)
    }

    animFrameRef.current = requestAnimationFrame(tick)
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [data, graphMode])

  // 画布平移与缩放
  const handleWheel = (e: WheelEvent) => {
    e.preventDefault()
    const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92
    setTransform((prev) => {
      const newScale = Math.min(2.5, Math.max(0.4, prev.scale * zoomFactor))
      return { ...prev, scale: newScale }
    })
  }

  const handleMouseDown = (e: MouseEvent) => {
    if (e.target === e.currentTarget || (e.target as HTMLElement).tagName === 'svg') {
      setIsPanning(true)
      panStartRef.current = { x: e.clientX - transform.x, y: e.clientY - transform.y }
    }
  }

  const handleMouseMove = (e: MouseEvent) => {
    if (isPanning) {
      setTransform((prev) => ({
        ...prev,
        x: e.clientX - panStartRef.current.x,
        y: e.clientY - panStartRef.current.y,
      }))
    } else if (draggedNodeRef.current) {
      const svgRect = e.currentTarget.getBoundingClientRect()
      const mouseX = (e.clientX - svgRect.left - transform.x) / transform.scale
      const mouseY = (e.clientY - svgRect.top - transform.y) / transform.scale
      draggedNodeRef.current.x = mouseX
      draggedNodeRef.current.y = mouseY
      setDisplayNodes([...nodesRef.current])
      isRunningRef.current = true
    }
  }

  const handleMouseUp = () => {
    setIsPanning(false)
    draggedNodeRef.current = null
  }

  const handleNodeMouseDown = (e: MouseEvent, node: SimNode) => {
    e.stopPropagation()
    draggedNodeRef.current = node
    setSelectedNode(node)
    setFocusNode(node)
    isRunningRef.current = true
  }

  const resetView = () => {
    setTransform({ x: 0, y: 0, scale: 1 })
    isRunningRef.current = true
  }

  const handleSelectLevel = (lvl: 1 | 2 | 3 | 'all') => {
    setAssociationLevel(lvl)
    isRunningRef.current = true
  }

  const handleClearFocus = () => {
    setFocusNode(null)
    setAssociationLevel('all')
    isRunningRef.current = true
  }

  const toggleTypeFilter = (t: string) => {
    setFilterTypes((prev) => ({ ...prev, [t]: !prev[t] }))
  }

  // 双向邻接表索引，O(1) 快速检索相邻节点与边
  const adjacencyIndex = useMemo(() => {
    const adj = new Map<string, Set<string>>()
    if (!data?.edges) return adj
    for (const e of data.edges) {
      if (!adj.has(e.source)) adj.set(e.source, new Set())
      if (!adj.has(e.target)) adj.set(e.target, new Set())
      adj.get(e.source)!.add(e.target)
      adj.get(e.target)!.add(e.source)
    }
    return adj
  }, [data])

  // 计算当前聚焦节点各层级邻居数量（用于按钮预览指示）
  const levelCounts = useMemo(() => {
    if (!focusNode || !data) return { l1: 0, l2: 0, l3: 0 }
    const l1Set = adjacencyIndex.get(focusNode.id) || new Set()
    const l2Set = new Set<string>()
    for (const nid of l1Set) {
      const nbs = adjacencyIndex.get(nid)
      if (nbs) {
        for (const nb of nbs) {
          if (nb !== focusNode.id && !l1Set.has(nb)) {
            l2Set.add(nb)
          }
        }
      }
    }
    const l3Set = new Set<string>()
    for (const nid of l2Set) {
      const nbs = adjacencyIndex.get(nid)
      if (nbs) {
        for (const nb of nbs) {
          if (nb !== focusNode.id && !l1Set.has(nb) && !l2Set.has(nb)) {
            l3Set.add(nb)
          }
        }
      }
    }
    return {
      l1: l1Set.size,
      l2: l1Set.size + l2Set.size,
      l3: l1Set.size + l2Set.size + l3Set.size,
    }
  }, [focusNode, data, adjacencyIndex])

  // BFS 关联子图提取与性能保护
  const MAX_SUBGRAPH_NODES = 80
  const { associatedNodeIds, isTruncated, computedDurationMs } = useMemo(() => {
    if (!focusNode || associationLevel === 'all' || !data) {
      return { associatedNodeIds: null, isTruncated: false, computedDurationMs: 0 }
    }

    const t0 = performance.now()
    const visited = new Set<string>([focusNode.id])
    let currentLayer = new Set<string>([focusNode.id])
    const maxDepth = associationLevel === 1 ? 1 : associationLevel === 2 ? 2 : 3

    for (let depth = 1; depth <= maxDepth; depth++) {
      const nextLayer = new Set<string>()
      for (const nid of currentLayer) {
        const nbs = adjacencyIndex.get(nid)
        if (!nbs) continue
        for (const nb of nbs) {
          if (!visited.has(nb)) {
            visited.add(nb)
            nextLayer.add(nb)
            if (visited.size >= MAX_SUBGRAPH_NODES) break
          }
        }
        if (visited.size >= MAX_SUBGRAPH_NODES) break
      }
      currentLayer = nextLayer
      if (currentLayer.size === 0 || visited.size >= MAX_SUBGRAPH_NODES) break
    }

    const duration = Number((performance.now() - t0).toFixed(2))
    return {
      associatedNodeIds: visited,
      isTruncated: visited.size >= MAX_SUBGRAPH_NODES,
      computedDurationMs: duration,
    }
  }, [focusNode, associationLevel, data, adjacencyIndex])

  // 子图谱年份选项
  const availableYears = useMemo(() => {
    if (!data || graphMode !== 'literature') return []
    const years = new Set<number>()
    for (const n of data.nodes) {
      if (n.node_type === 'paper' && n.properties?.year) {
        years.add(Number(n.properties.year))
      }
    }
    return Array.from(years).sort((a, b) => b - a)
  }, [data, graphMode])

  // 过滤后的可视化节点和边
  const visibleNodes = displayNodes.filter((n) => {
    // 0. 关联子图层级过滤（仅保留与聚焦节点相关的节点）
    if (associatedNodeIds && !associatedNodeIds.has(n.id)) {
      return false
    }

    // 1. 类型开关过滤
    if (!filterTypes[n.node_type]) return false

    // 2. 子图谱文字搜索过滤
    if (graphMode === 'literature' && subgraphSearch.trim()) {
      const q = subgraphSearch.toLowerCase().trim()
      const matchLabel = n.label.toLowerCase().includes(q)
      const matchTitle = String(n.properties?.title || '').toLowerCase().includes(q)
      const matchAuthor = String(n.properties?.first_author || '').toLowerCase().includes(q)
      const matchName = String(n.properties?.name || '').toLowerCase().includes(q)
      if (!matchLabel && !matchTitle && !matchAuthor && !matchName) return false
    }

    // 3. 子图谱年份过滤
    if (graphMode === 'literature' && subgraphYearFilter) {
      if (n.node_type === 'paper') {
        if (String(n.properties?.year) !== subgraphYearFilter) return false
      }
    }

    return true
  })

  const visibleNodeIds = new Set(visibleNodes.map((n) => n.id))
  const visibleEdges = (data?.edges || []).filter(
    (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
  )

  const nodeMap = new Map(displayNodes.map((n) => [n.id, n]))

  return (
    <div className="knowledge-graph-container">
      {/* 顶部控制栏与分层导航 */}
      <div className="kg-header-card">
        <div className="kg-header-row">
          <div>
            <div className="kg-badge">
              <span className="pulsing-dot" />
              <span>
                {graphMode === 'macro'
                  ? '宏观科学骨干知识网络 (Core Macro Graph)'
                  : graphMode === 'fine_grained'
                  ? '细粒度物性证据链拓扑 (Fine-Grained Evidence Graph)'
                  : `文献与作者证据子图谱 (Evidence Subgraph) · ${activeMaterial?.formula}`}
              </span>
            </div>
            <h2>
              {graphMode === 'macro'
                ? '相变存储材料多维科学知识图谱'
                : graphMode === 'fine_grained'
                ? '相变材料 — 掺杂 — 实测物性 — 文献证据链拓扑'
                : `材料 [${activeMaterial?.formula}] 的文献出处与作者星丛拓扑`}
            </h2>
            <p className="kg-subtitle">
              {graphMode === 'macro'
                ? '展示材料、元素与物性指标核心拓扑，支持按需展开文献证据。'
                : graphMode === 'fine_grained'
                ? '贯通基体材料、掺杂样品、实测物性与出处论文的全证据链路，支持精准溯源。'
                : '展示关联文献、作者与期刊，支持科研证据严谨溯源。'}
            </p>
          </div>

          {data && (
            <div className="kg-summary-badges">
              <span className="kg-tag material">材料: {data.summary.material_count}</span>
              {graphMode === 'macro' && (
                <>
                  <span className="kg-tag element">元素: {data.summary.element_count}</span>
                  <span className="kg-tag property">物性: {data.summary.property_count}</span>
                  {data.summary.system_count ? (
                    <span className="kg-tag system">体系: {data.summary.system_count}</span>
                  ) : null}
                </>
              )}
              {graphMode === 'fine_grained' && (
                <>
                  <span className="kg-tag element" style={{ background: '#f3e8ff', color: '#7e22ce' }}>
                    掺杂: {data.summary.dopant_count ?? 0}
                  </span>
                  <span className="kg-tag property" style={{ background: '#ecfdf5', color: '#047857' }}>
                    观测: {data.summary.observation_count ?? 0}
                  </span>
                  <span className="kg-tag paper">文献: {data.summary.paper_count}</span>
                  <span className="kg-tag author">作者: {data.summary.author_count}</span>
                </>
              )}
              {graphMode === 'literature' && (
                <>
                  <span className="kg-tag paper">文献: {data.summary.paper_count}</span>
                  <span className="kg-tag author">作者: {data.summary.author_count}</span>
                  <span className="kg-tag journal">期刊: {data.summary.journal_count}</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 控制与筛选工具条 */}
      <div className="kg-toolbar">
        {/* 图谱主视角切换器 */}
        <div className="toolbar-group">
          <span className="tool-label">图谱模式：</span>
          <button
            className={`button small ${graphMode === 'macro' ? 'primary' : 'secondary'}`}
            onClick={() => {
              setGraphMode('macro')
              setActiveMaterial(null)
              resetView()
            }}
          >
            🔬 宏观科学网络
          </button>
          <button
            className={`button small ${graphMode === 'fine_grained' ? 'primary' : 'secondary'}`}
            onClick={() => {
              setGraphMode('fine_grained')
              setActiveMaterial(null)
              resetView()
            }}
          >
            🔗 细粒度物性证据链
          </button>
          {activeMaterial && (
            <button
              className={`button small ${graphMode === 'literature' ? 'primary' : 'secondary'}`}
              onClick={() => {
                setGraphMode('literature')
                resetView()
              }}
            >
              📚 [{activeMaterial.formula}] 文献星丛
            </button>
          )}
        </div>

        {graphMode === 'literature' ? (
          <>
            <div className="toolbar-group">
              <button className="button small secondary" onClick={handleReturnToMacro}>
                ⬅️ 返回宏观
              </button>
            </div>
            <div className="toolbar-group">
              <span className="tool-label">🔎 搜索证据：</span>
              <input
                type="text"
                className="input small"
                placeholder="搜索文献标题或作者..."
                value={subgraphSearch}
                onChange={(e) => setSubgraphSearch(e.target.value)}
                style={{ width: 150, padding: '4px 8px', fontSize: 12 }}
              />
            </div>
            {availableYears.length > 0 && (
              <div className="toolbar-group">
                <span className="tool-label">📅 发表年份：</span>
                <select
                  value={subgraphYearFilter}
                  onChange={(e) => setSubgraphYearFilter(e.target.value)}
                  style={{ padding: '3px 8px', fontSize: 12, borderRadius: 4 }}
                >
                  <option value="">全部年份</option>
                  {availableYears.map((y) => (
                    <option key={y} value={String(y)}>
                      {y} 年
                    </option>
                  ))}
                </select>
              </div>
            )}
          </>
        ) : graphMode === 'macro' ? (
          <div className="toolbar-group">
            <span className="tool-label">🔍 元素子图：</span>
            {['', 'Ge', 'Sb', 'Te', 'Se', 'Bi', 'In'].map((el) => (
              <button
                key={el}
                className={`button small ${selectedElement === el ? 'primary' : 'secondary'}`}
                onClick={() => setSelectedElement(el)}
              >
                {el === '' ? '全部' : el}
              </button>
            ))}
          </div>
        ) : null}

        {/* 节点分类显示开关 */}
        <div className="toolbar-group">
          <span className="tool-label">节点显示：</span>
          {(graphMode === 'macro'
            ? ['material', 'element', 'system', 'property']
            : graphMode === 'fine_grained'
            ? ['material', 'dopant', 'observation', 'paper', 'first_author']
            : ['material', 'paper', 'first_author', 'corresponding_author', 'journal']
          ).map((typeKey) => {
            const cfg = TYPE_CONFIG[typeKey]
            if (!cfg) return null
            return (
              <label key={typeKey} className="type-toggle-label">
                <input
                  type="checkbox"
                  checked={filterTypes[typeKey] ?? true}
                  onChange={() => toggleTypeFilter(typeKey)}
                />
                <span className="dot-indicator" style={{ backgroundColor: cfg.color }} />
                {cfg.label}
              </label>
            )
          })}
        </div>

        <div className="toolbar-group right">
          <button className="button small secondary" onClick={resetView} title="重置画布平移与缩放">
            🎯 重置视角
          </button>
          <button
            className="button small secondary"
            onClick={() => {
              const nextState = !isRunningRef.current
              isRunningRef.current = nextState
              setIsPhysicsRunning(nextState)
            }}
          >
            {isPhysicsRunning ? '⏸️ 锁定物理' : '▶️ 恢复力场'}
          </button>
          <button
            className="button small secondary"
            onClick={() => void fetchGraphData(graphMode, selectedElement || undefined, activeMaterial)}
          >
            🔄 刷新
          </button>
        </div>
      </div>

      {/* 主视窗：力导向图 + 侧边详情 */}
      <div className="kg-main-layout">
        <div
          className="kg-graph-canvas interactive-canvas"
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          {/* 关联子图聚焦与层级控制浮条 */}
          {focusNode && (
            <div className="association-toolbar-banner">
              <div className="banner-left">
                <span className="focus-dot" style={{ backgroundColor: focusNode.color }} />
                <span className="focus-title">
                  聚焦节点：<strong>{focusNode.label}</strong>
                  <span className="focus-type-tag">
                    {TYPE_CONFIG[focusNode.node_type]?.label || focusNode.node_type}
                  </span>
                </span>
                {associationLevel !== 'all' ? (
                  <span className="level-status-pill">
                    已激活 {associationLevel} 级关联 (显示 {visibleNodes.length} 个节点)
                    {computedDurationMs > 0 && <small> · {computedDurationMs}ms</small>}
                  </span>
                ) : (
                  <span className="level-status-pill full">全图展示中 (点击切换关联层级)</span>
                )}
                {isTruncated && (
                  <span className="truncate-pill" title="关联节点达到上限">
                    ⚠️ 已限制前 80 节点
                  </span>
                )}
              </div>
              <div className="banner-actions">
                <span className="action-hint">关联层级：</span>
                <button
                  className={`level-btn ${associationLevel === 1 ? 'active' : ''}`}
                  onClick={() => handleSelectLevel(1)}
                  title="仅显示直接相连的节点与边"
                >
                  一级关联 ({levelCounts.l1})
                </button>
                <button
                  className={`level-btn ${associationLevel === 2 ? 'active' : ''}`}
                  onClick={() => handleSelectLevel(2)}
                  title="显示直接关联及其下一层节点"
                >
                  二级关联 ({levelCounts.l2})
                </button>
                <button
                  className={`level-btn ${associationLevel === 3 ? 'active' : ''}`}
                  onClick={() => handleSelectLevel(3)}
                  title="扩展至三级关联（限制 80 节点防卡死）"
                >
                  三级关联 ({levelCounts.l3})
                </button>
                <button
                  className={`level-btn ${associationLevel === 'all' ? 'active' : ''}`}
                  onClick={() => handleSelectLevel('all')}
                  title="显示全图所有节点"
                >
                  全部节点
                </button>
                <button
                  className="level-btn reset-btn"
                  onClick={handleClearFocus}
                  title="退出聚焦并返回全图"
                >
                  ✕ 返回全图
                </button>
              </div>
            </div>
          )}

          {loading && (
            <div className="canvas-overlay loading">
              <div className="spinner-large" />
              <p>
                {graphMode === 'macro'
                  ? '正在从 MySQL 权威数据源构建科学宏观图谱…'
                  : `正在构建 ${activeMaterial?.formula} 的文献与作者证据拓扑…`}
              </p>
            </div>
          )}

          {error && (
            <div className="canvas-overlay error">
              <p className="error-text">⚠️ {error}</p>
              <button
                className="button secondary"
                onClick={() => void fetchGraphData(graphMode, selectedElement || undefined, activeMaterial)}
              >
                重试
              </button>
            </div>
          )}

          {!loading && !error && visibleNodes.length === 0 && (
            <div className="canvas-overlay empty">
              <p>暂无符合当前筛选条件的图谱节点</p>
              <button
                className="button secondary"
                onClick={() => {
                  setSelectedElement('')
                  setSubgraphSearch('')
                  setSubgraphYearFilter('')
                  setFilterTypes({
                    material: true,
                    element: true,
                    system: true,
                    property: true,
                    paper: true,
                    first_author: true,
                    corresponding_author: true,
                    author: true,
                    journal: true,
                  })
                }}
              >
                重置所有筛选
              </button>
            </div>
          )}

          {/* SVG 力导向图层 */}
          <svg className="kg-svg-active" viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}>
            <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}>
              {/* 关系连线 */}
              {visibleEdges.map((e) => {
                const s = nodeMap.get(e.source)
                const t = nodeMap.get(e.target)
                if (!s || !t) return null

                const isEdgeActive =
                  selectedNode && (selectedNode.id === e.source || selectedNode.id === e.target)

                let strokeColor = '#cbd5e1'
                if (isEdgeActive) {
                  strokeColor = '#2563eb'
                } else if (e.edge_type === 'DOPED_WITH') {
                  strokeColor = '#8b5cf6'
                } else if (e.edge_type === 'MEASURED_AS') {
                  strokeColor = '#10b981'
                } else if (e.edge_type === 'EVIDENCED_BY') {
                  strokeColor = '#a78bfa'
                } else if (e.edge_type === 'FIRST_AUTHORED_BY') {
                  strokeColor = '#fcd34d'
                } else if (e.edge_type === 'CORRESPONDING_AUTHORED_BY') {
                  strokeColor = '#6ee7b7'
                } else if (e.edge_type === 'PUBLISHED_IN') {
                  strokeColor = '#f472b6'
                }

                return (
                  <g key={e.id} className={`edge-group ${isEdgeActive ? 'active' : ''}`}>
                    <line
                      x1={s.x}
                      y1={s.y}
                      x2={t.x}
                      y2={t.y}
                      stroke={strokeColor}
                      strokeWidth={isEdgeActive ? 2.5 : 1.5}
                      strokeDasharray={
                        e.edge_type === 'EVIDENCED_BY' ||
                        e.edge_type === 'MENTIONS' ||
                        e.edge_type === 'MEASURED_AS'
                          ? '4 3'
                          : undefined
                      }
                    />
                    {e.label && (
                      <text
                        x={(s.x + t.x) / 2}
                        y={(s.y + t.y) / 2 - 4}
                        textAnchor="middle"
                        fontSize={9}
                        fill="#94a3b8"
                        className="edge-label-text"
                      >
                        {e.label}
                      </text>
                    )}
                  </g>
                )
              })}

              {/* 实体节点 */}
              {visibleNodes.map((n) => {
                const isSelected = selectedNode?.id === n.id
                const cfg = TYPE_CONFIG[n.node_type] || TYPE_CONFIG.material

                return (
                  <g
                    key={n.id}
                    className={`node-group ${isSelected ? 'selected' : ''}`}
                    transform={`translate(${n.x}, ${n.y})`}
                    onMouseDown={(e) => handleNodeMouseDown(e, n)}
                    style={{ cursor: 'grab' }}
                  >
                    {isSelected && (
                      <circle
                        r={n.radius + 7}
                        fill="none"
                        stroke={n.color}
                        strokeWidth={3}
                        strokeDasharray="4 2"
                        className="selection-halo"
                      />
                    )}

                    <circle
                      r={n.radius}
                      fill={n.color}
                      className="node-circle"
                      stroke="#ffffff"
                      strokeWidth={2}
                    />

                    <text
                      textAnchor="middle"
                      dy="4"
                      fontSize={n.radius * 0.75}
                      fill="#ffffff"
                      style={{ pointerEvents: 'none' }}
                    >
                      {cfg.icon}
                    </text>

                    <text
                      textAnchor="middle"
                      dy={n.radius + 14}
                      fontSize={11}
                      fontWeight={isSelected ? 'bold' : '500'}
                      fill={isSelected ? '#1e3a8a' : '#334155'}
                      className="node-label-bg"
                    >
                      {n.label}
                    </text>
                  </g>
                )
              })}
            </g>
          </svg>

          {/* 画布操作提示 */}
          <div className="canvas-controls-hint">
            <span>
              💡 鼠标滚轮缩放 · 拖拽画布平移 · 单击节点查看属性与证据 · 点击材料可下钻文献子图谱
            </span>
          </div>
        </div>

        {/* 右侧节点详情抽屉 / 检查器 */}
        <div className="kg-side-panel">
          {selectedNode ? (
            <div className="node-detail-card">
              <div className="detail-head" style={{ borderLeftColor: selectedNode.color }}>
                <span className="type-badge" style={{ backgroundColor: selectedNode.color }}>
                  {TYPE_CONFIG[selectedNode.node_type]?.label || selectedNode.node_type}
                </span>
                <h3>{selectedNode.label}</h3>
              </div>

              {/* 节点关联子图层级控制 */}
              <div className="side-association-box">
                <div className="side-association-title-row">
                  <span className="sec-label">🎯 关联子图层级显示：</span>
                  {associationLevel !== 'all' && (
                    <button className="text-cancel-btn" onClick={handleClearFocus}>
                      恢复全图
                    </button>
                  )}
                </div>
                <div className="side-association-btn-grid">
                  <button
                    className={`side-lvl-btn ${associationLevel === 1 && focusNode?.id === selectedNode.id ? 'active' : ''}`}
                    onClick={() => {
                      setFocusNode(selectedNode)
                      handleSelectLevel(1)
                    }}
                    title="仅显示与当前节点直接相连的一级邻居与边"
                  >
                    1级关联 ({levelCounts.l1})
                  </button>
                  <button
                    className={`side-lvl-btn ${associationLevel === 2 && focusNode?.id === selectedNode.id ? 'active' : ''}`}
                    onClick={() => {
                      setFocusNode(selectedNode)
                      handleSelectLevel(2)
                    }}
                    title="显示一级及次级相连节点"
                  >
                    2级关联 ({levelCounts.l2})
                  </button>
                  <button
                    className={`side-lvl-btn ${associationLevel === 3 && focusNode?.id === selectedNode.id ? 'active' : ''}`}
                    onClick={() => {
                      setFocusNode(selectedNode)
                      handleSelectLevel(3)
                    }}
                    title="扩展至三级关联"
                  >
                    3级关联 ({levelCounts.l3})
                  </button>
                  <button
                    className={`side-lvl-btn ${associationLevel === 'all' ? 'active' : ''}`}
                    onClick={() => handleSelectLevel('all')}
                  >
                    全图展示
                  </button>
                </div>
              </div>

              <div className="detail-props">
                {selectedNode.node_type === 'material' && (
                  <>
                    <div className="prop-row">
                      <span className="label">化学系统：</span>
                      <span className="val">{String(selectedNode.properties?.chemical_system || '—')}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">材料名称：</span>
                      <span className="val">{String(selectedNode.properties?.name || selectedNode.label)}</span>
                    </div>

                    <div className="action-row" style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
                      {graphMode === 'macro' && Boolean(selectedNode.properties?.material_id) && (
                        <button
                          className="button small primary"
                          onClick={() =>
                            handleExploreLiteratureSubgraph(
                              String(selectedNode.properties?.material_id),
                              selectedNode.label
                            )
                          }
                        >
                          🔬 展开文献与作者证据子图谱
                        </button>
                      )}
                      {Boolean(selectedNode.properties?.material_id) && graphMode !== 'fine_grained' && (
                        <button
                          className="button small"
                          style={{ background: '#7c3aed', color: '#fff', border: 'none' }}
                          onClick={() => {
                            setActiveMaterial({
                              id: String(selectedNode.properties?.material_id),
                              formula: selectedNode.label,
                            })
                            setGraphMode('fine_grained')
                            resetView()
                          }}
                        >
                          🔗 展开该材料细粒度物性证据链
                        </button>
                      )}
                      {Boolean(selectedNode.properties?.material_id && onSelectMaterial) && (
                        <button
                          className="button small secondary"
                          onClick={() => onSelectMaterial?.(String(selectedNode.properties?.material_id))}
                        >
                          🧪 查看材料完整详情
                        </button>
                      )}
                    </div>
                  </>
                )}

                {selectedNode.node_type === 'element' && (
                  <>
                    <div className="prop-row">
                      <span className="label">元素符号：</span>
                      <span className="val font-mono">{String(selectedNode.properties?.symbol || selectedNode.label)}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">科学角色：</span>
                      <span className="val">相变基本骨干元素</span>
                    </div>
                  </>
                )}

                {selectedNode.node_type === 'system' && (
                  <>
                    <div className="prop-row">
                      <span className="label">体系分类：</span>
                      <span className="val font-mono">{String(selectedNode.properties?.chemical_system || selectedNode.label)}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">体系说明：</span>
                      <span className="val">多元相变材料化学体系，控制晶化速度与能带结构</span>
                    </div>
                  </>
                )}

                {selectedNode.node_type === 'paper' && (
                  <>
                    <div className="prop-row">
                      <span className="label">文献标题：</span>
                      <span className="val text-small">{String(selectedNode.properties?.title || selectedNode.label)}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">收录期刊：</span>
                      <span className="val">{String(selectedNode.properties?.journal || '—')}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">第一作者：</span>
                      <span className="val">{String(selectedNode.properties?.first_author || '—')}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">通讯作者：</span>
                      <span className="val">{String(selectedNode.properties?.corresponding_author || '—')}</span>
                    </div>
                    {selectedNode.properties?.year && (
                      <div className="prop-row">
                        <span className="label">出版年份：</span>
                        <span className="val">{String(selectedNode.properties.year)} 年</span>
                      </div>
                    )}
                    {selectedNode.properties?.doi && (
                      <div className="prop-row">
                        <span className="label">DOI：</span>
                        <a
                          href={`https://doi.org/${selectedNode.properties.doi}`}
                          target="_blank"
                          rel="noreferrer"
                          className="val link"
                        >
                          {String(selectedNode.properties.doi)} ↗
                        </a>
                      </div>
                    )}
                    {selectedNode.properties?.paper_id && onSelectPaper && (
                      <div className="action-row" style={{ marginTop: 10 }}>
                        <button
                          className="button small secondary"
                          onClick={() => onSelectPaper(String(selectedNode.properties?.paper_id))}
                        >
                          📄 查看文献详情
                        </button>
                      </div>
                    )}
                  </>
                )}

                {(selectedNode.node_type === 'first_author' ||
                  selectedNode.node_type === 'corresponding_author' ||
                  selectedNode.node_type === 'author') && (
                  <>
                    <div className="prop-row">
                      <span className="label">作者姓名：</span>
                      <span className="val font-semibold">{String(selectedNode.properties?.name || selectedNode.label)}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">署名角色：</span>
                      <span className="val">{String(selectedNode.properties?.role || '科研工作者')}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">证据地位：</span>
                      <span className="val">与文献同处于微观证据层，直接对研究结果与测量精度负责</span>
                    </div>
                  </>
                )}

                {selectedNode.node_type === 'journal' && (
                  <>
                    <div className="prop-row">
                      <span className="label">期刊名称：</span>
                      <span className="val font-semibold">{String(selectedNode.properties?.name || selectedNode.label)}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">出版载体：</span>
                      <span className="val">学术期刊 / 国际会议 / arXiv 预印本</span>
                    </div>
                  </>
                )}

                {selectedNode.node_type === 'property' && (
                  <>
                    <div className="prop-row">
                      <span className="label">属性定义：</span>
                      <span className="val">{String(selectedNode.properties?.property_name || selectedNode.label)}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">规范单位：</span>
                      <span className="val font-mono">{String(selectedNode.properties?.canonical_unit || '—')}</span>
                    </div>
                    {selectedNode.properties?.sample_value && (
                      <div className="prop-row">
                        <span className="label">测定观测：</span>
                        <span className="val highlight">{String(selectedNode.properties.sample_value)}</span>
                      </div>
                    )}
                  </>
                )}

                {selectedNode.node_type === 'dopant' && (
                  <>
                    <div className="prop-row">
                      <span className="label">掺杂元素：</span>
                      <span className="val font-semibold">{String(selectedNode.properties?.dopant_element || selectedNode.label)}</span>
                    </div>
                    {selectedNode.properties?.dopant_concentration !== undefined && (
                      <div className="prop-row">
                        <span className="label">掺杂浓度：</span>
                        <span className="val font-mono">{String(selectedNode.properties.dopant_concentration)} at.%</span>
                      </div>
                    )}
                    <div className="prop-row">
                      <span className="label">科学机制：</span>
                      <span className="val">通过空位填充或八面体/四面体局域畸变，有效调控结晶激活能与非晶态热稳定性</span>
                    </div>
                  </>
                )}

                {selectedNode.node_type === 'observation' && (
                  <>
                    <div className="prop-row">
                      <span className="label">物性代码：</span>
                      <span className="val font-mono">{String(selectedNode.properties?.property_code || selectedNode.label)}</span>
                    </div>
                    <div className="prop-row">
                      <span className="label">实测观测值：</span>
                      <span className="val highlight font-semibold" style={{ fontSize: 16 }}>
                        {String(selectedNode.properties?.value ?? '—')} {String(selectedNode.properties?.unit ?? '')}
                      </span>
                    </div>
                    {selectedNode.properties?.heating_rate_value && (
                      <div className="prop-row" style={{ background: '#fffbeb', padding: '6px 8px', borderRadius: 4, border: '1px solid #fef3c7' }}>
                        <span className="label" style={{ color: '#b45309' }}>🔥 升温速率：</span>
                        <span className="val" style={{ color: '#b45309', fontWeight: 700 }}>
                          {String(selectedNode.properties.heating_rate_value)} {String(selectedNode.properties.heating_rate_unit || 'K/min')}
                        </span>
                      </div>
                    )}
                    <div className="prop-row">
                      <span className="label">审核状态：</span>
                      <span className="val" style={{ color: '#059669', fontWeight: 600 }}>
                        ✓ {String(selectedNode.properties?.verification_status || 'HUMAN_REVIEWED')}
                      </span>
                    </div>
                    {selectedNode.properties?.paper_title && (
                      <div className="prop-row">
                        <span className="label">出处文献：</span>
                        <span className="val text-small">{String(selectedNode.properties.paper_title)}</span>
                      </div>
                    )}
                    {selectedNode.properties?.doi && (
                      <div className="prop-row">
                        <span className="label">DOI：</span>
                        <a
                          href={`https://doi.org/${selectedNode.properties.doi}`}
                          target="_blank"
                          rel="noreferrer"
                          className="val link"
                        >
                          {String(selectedNode.properties.doi)} ↗
                        </a>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* 关联拓扑 */}
              <div className="node-neighbors">
                <h4>🔗 关联拓扑 (Connections)</h4>
                <div className="neighbors-list">
                  {data?.edges
                    .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
                    .map((e) => {
                      const otherId = e.source === selectedNode.id ? e.target : e.source
                      const other = nodeMap.get(otherId)
                      return (
                        <div
                          key={e.id}
                          className="neighbor-item"
                          onClick={() => other && setSelectedNode(other)}
                        >
                          <span className="relation-type">[{e.label || e.edge_type}]</span>
                          <span className="relation-target">{other?.label || otherId}</span>
                        </div>
                      )
                    })}
                </div>
              </div>
            </div>
          ) : (
            <div className="kg-side-empty">
              <div className="empty-icon">🕸️</div>
              <h4>节点属性检查器</h4>
              <p>
                {graphMode === 'macro'
                  ? '在左侧宏观骨干图中点击任意材料节点，可在此查看材料详情并展开该材料的文献与作者证据子图谱。'
                  : '在左侧文献证据子图谱中点击文献、第一作者、通讯作者或期刊节点，查看科学事实溯源链。'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
