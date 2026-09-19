import { useState, useEffect, useCallback, useMemo } from 'react'
import type { PropertyComparisonResponse, PropertyComparisonDataPoint, PropertyBoxPlotStat } from '../types/batch'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

interface PropertyComparisonBoardProps {
  onSelectPaper?: (paperId: string) => void
  onSelectMaterial?: (materialId: string) => void
}

interface PropertyMeta {
  code: string
  name: string
  defaultUnit: string
  altUnit: string
}

const SUPPORTED_PROPERTIES: PropertyMeta[] = [
  { code: 'crystallization_temperature', name: '结晶温度 (Tc)', defaultUnit: 'K', altUnit: '°C' },
  { code: 'activation_energy', name: '结晶活化能 (Ea)', defaultUnit: 'eV', altUnit: 'kJ/mol' },
  { code: 'melting_temperature', name: '熔点 (Tm)', defaultUnit: 'K', altUnit: '°C' },
  { code: 'crystallization_time', name: '结晶时间 (tcryst)', defaultUnit: 's', altUnit: 'ns' },
  { code: 'electrical_resistivity', name: '电阻率 (ρ)', defaultUnit: 'Ω·cm', altUnit: 'Ω·m' },
  { code: 'latent_heat', name: '相变潜热 (ΔH)', defaultUnit: 'J/g', altUnit: 'kJ/kg' },
  { code: 'threshold_field', name: '阈值电场 (Eth)', defaultUnit: 'V/μm', altUnit: 'MV/m' },
  { code: 'threshold_voltage', name: '阈值电压 (Vth)', defaultUnit: 'V', altUnit: 'mV' },
  { code: 'glass_transition_temperature', name: '玻璃化转变温度 (Tg)', defaultUnit: 'K', altUnit: '°C' },
]

export interface RenderPoint extends PropertyComparisonDataPoint {
  displayVal: number
  conc: number
  color: string
}

export function PropertyComparisonBoard({ onSelectPaper, onSelectMaterial }: PropertyComparisonBoardProps) {
  const [selectedPropCode, setSelectedPropCode] = useState('crystallization_temperature')
  // 多材料多选过滤
  const [selectedMaterials, setSelectedMaterials] = useState<string[]>([])
  const [heatingRateFilter, setHeatingRateFilter] = useState<string>('')
  const [useAltUnit, setUseAltUnit] = useState(false)
  const [activeTab, setActiveTab] = useState<'scatter' | 'boxplot' | 'table'>('scatter')

  const [data, setData] = useState<PropertyComparisonResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 选中的数据点（激活右侧证据溯源抽屉）
  const [selectedPoint, setSelectedPoint] = useState<RenderPoint | null>(null)
  const [hoveredPoint, setHoveredPoint] = useState<RenderPoint | null>(null)

  const currentPropMeta = useMemo(() => {
    return SUPPORTED_PROPERTIES.find((p) => p.code === selectedPropCode) || {
      code: selectedPropCode,
      name: selectedPropCode,
      defaultUnit: data?.display_unit || 'a.u.',
      altUnit: data?.display_unit || 'a.u.',
    }
  }, [selectedPropCode, data])

  const fetchComparisonData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      params.set('property_code', selectedPropCode)
      // 如果只单选了一个基体材料，可透传给后端提速；若多选或未选，获取全部后由前端秒级多选过滤
      if (selectedMaterials.length === 1) {
        params.set('base_material', selectedMaterials[0])
      }
      if (heatingRateFilter) {
        params.set('heating_rate', heatingRateFilter)
      }

      const res = await fetch(`${API_BASE}/v1/analytics/property-comparison?${params.toString()}`)
      if (!res.ok) {
        throw new Error(`获取对比数据失败: HTTP ${res.status}`)
      }
      const json: PropertyComparisonResponse = await res.json()
      setData(json)
    } catch (err: any) {
      setError(err.message || '加载物性对比数据失败，请检查网络或后端服务连接')
    } finally {
      setLoading(false)
    }
  }, [selectedPropCode, selectedMaterials, heatingRateFilter])

  useEffect(() => {
    void fetchComparisonData()
  }, [fetchComparisonData])

  // 单位统一与换算辅助函数
  const convertValue = useCallback(
    (
      rawVal: number | null | undefined,
      normVal: number | null | undefined,
      rawUnit: string | null | undefined,
      propCode: string,
      alt: boolean
    ): number | null => {
      // 优先取有效数值
      const effectiveVal = normVal ?? rawVal
      if (effectiveVal === null || effectiveVal === undefined || isNaN(effectiveVal)) return null

      // 温度系列：K (规范) vs °C (工程)
      if (
        propCode === 'crystallization_temperature' ||
        propCode === 'melting_temperature' ||
        propCode === 'glass_transition_temperature'
      ) {
        let valInKelvin = effectiveVal
        // 若原始报告单位为 °C 且未做归一化
        if (normVal == null && rawUnit === '°C' && effectiveVal < 1000) {
          valInKelvin = effectiveVal + 273.15
        }
        if (alt) {
          return Number((valInKelvin - 273.15).toFixed(2)) // 换算为 °C
        }
        return Number(valInKelvin.toFixed(2)) // 保持 K
      }

      // 活化能系列：eV (规范) vs kJ/mol (工程)
      if (propCode === 'activation_energy') {
        let valInEV = effectiveVal
        if (normVal == null && rawUnit?.includes('kJ')) {
          valInEV = effectiveVal / 96.4853
        }
        if (alt) {
          return Number((valInEV * 96.4853).toFixed(2)) // 换算为 kJ/mol
        }
        return Number(valInEV.toFixed(3)) // 保持 eV
      }

      // 时间系列：s (规范) vs ns (工程)
      if (propCode === 'crystallization_time' || propCode === 'SET_time' || propCode === 'RESET_time') {
        let valInSeconds = effectiveVal
        if (normVal == null && rawUnit === 'ns') {
          valInSeconds = effectiveVal * 1e-9
        }
        if (alt) {
          return Number((valInSeconds * 1e9).toFixed(2)) // 换算为 ns
        }
        return Number(valInSeconds.toExponential(3)) // 保持 s
      }

      // 电阻率系列：Ω·cm vs Ω·m
      if (propCode === 'electrical_resistivity') {
        if (alt) {
          return Number((effectiveVal * 0.01).toFixed(4)) // Ω·m
        }
        return Number(effectiveVal.toFixed(4))
      }

      // 潜热系列：J/g vs kJ/kg
      if (propCode === 'latent_heat') {
        return Number(effectiveVal.toFixed(2))
      }

      return Number(effectiveVal.toFixed(2))
    },
    []
  )

  const displayUnit = useAltUnit ? currentPropMeta.altUnit : currentPropMeta.defaultUnit

  // 配色方案：按掺杂元素或基体区分
  const getDopantColor = (dopant?: string | null, baseMat?: string) => {
    if (!dopant) {
      if (baseMat?.includes('Sb2Te3')) return '#8b5cf6'
      if (baseMat?.includes('GST') || baseMat?.includes('Ge2Sb2Te5')) return '#10b981'
      return '#0284c7' // 纯 GeTe
    }
    switch (dopant) {
      case 'Bi': return '#ec4899'
      case 'In': return '#f59e0b'
      case 'Sb': return '#7c3aed'
      case 'Ag': return '#10b981'
      case 'N': return '#06b6d4'
      case 'C': return '#64748b'
      case 'Ti': return '#dc2626'
      case 'Sc': return '#0d9488'
      default: return '#3b82f6'
    }
  }

  // 提取可用材料列表与加热速率（带绝对安全的空值防御）
  const availableMaterials = useMemo(() => {
    if (!data) return ['GeTe', 'Sb2Te3']
    const list = data.available_materials || data.available_base_materials || []
    return Array.isArray(list) && list.length > 0 ? list : ['GeTe', 'Sb2Te3']
  }, [data])

  const availableHeatingRates = useMemo(() => {
    if (!data) return []
    const list = data.available_heating_rates || []
    return Array.isArray(list) ? list : []
  }, [data])

  // 计算散点图全部有效数据点
  const allScatterPoints = useMemo(() => {
    if (!data?.data_points || !Array.isArray(data.data_points)) return []
    return data.data_points
      .map((p) => {
        const rawVal = p.value
        const normVal = p.normalized_value
        const rawUnit = p.unit
        const displayVal = convertValue(rawVal, normVal, rawUnit, p.property_code, useAltUnit)
        const conc = p.dopant_at_pct ?? p.dopant_concentration ?? 0
        return {
          ...p,
          displayVal: displayVal ?? 0,
          hasVal: displayVal !== null,
          conc,
          color: getDopantColor(p.dopant_element, p.base_material),
        }
      })
      .filter((p) => p.hasVal) as RenderPoint[]
  }, [data, convertValue, useAltUnit])

  // 按用户多选材料过滤
  const visiblePoints = useMemo(() => {
    if (selectedMaterials.length === 0) return allScatterPoints
    return allScatterPoints.filter((p) => selectedMaterials.includes(p.base_material))
  }, [allScatterPoints, selectedMaterials])

  // 散点图轴刻度与界限
  const scatterMetrics = useMemo(() => {
    if (visiblePoints.length === 0) {
      return { minX: 0, maxX: 15, minY: 0, maxY: 100 }
    }
    const xVals = visiblePoints.map((p) => p.conc)
    const yVals = visiblePoints.map((p) => p.displayVal)

    const minX = 0
    const maxValX = Math.max(...xVals)
    const maxX = maxValX > 0 ? Math.ceil(maxValX * 1.25) : 15

    const minYRaw = Math.min(...yVals)
    const maxYRaw = Math.max(...yVals)
    const padding = (maxYRaw - minYRaw) * 0.15 || 10
    const minY = Number((minYRaw - padding).toFixed(1))
    const maxY = Number((maxYRaw + padding).toFixed(1))

    return { minX, maxX, minY, maxY }
  }, [visiblePoints])

  // 箱线图换算后的统计数据
  const convertedBoxStats = useMemo(() => {
    if (!data?.box_plot_stats || !Array.isArray(data.box_plot_stats)) return []
    return data.box_plot_stats
      .map((st: PropertyBoxPlotStat) => {
        const minVal = st.min_val ?? st.min ?? 0
        const maxVal = st.max_val ?? st.max ?? 0
        const q1Val = st.q1 ?? minVal
        const q3Val = st.q3 ?? maxVal
        const medVal = st.median ?? (minVal + maxVal) / 2

        // 统一换算
        const cMin = convertValue(minVal, null, data.display_unit, selectedPropCode, useAltUnit) ?? minVal
        const cQ1 = convertValue(q1Val, null, data.display_unit, selectedPropCode, useAltUnit) ?? q1Val
        const cMed = convertValue(medVal, null, data.display_unit, selectedPropCode, useAltUnit) ?? medVal
        const cQ3 = convertValue(q3Val, null, data.display_unit, selectedPropCode, useAltUnit) ?? q3Val
        const cMax = convertValue(maxVal, null, data.display_unit, selectedPropCode, useAltUnit) ?? maxVal

        return {
          group_name: st.group_name || '未命名分组',
          count: st.count || 0,
          min: Number(cMin.toFixed(2)),
          q1: Number(cQ1.toFixed(2)),
          median: Number(cMed.toFixed(2)),
          q3: Number(cQ3.toFixed(2)),
          max: Number(cMax.toFixed(2)),
          mean: Number(((cMin + cMax) / 2).toFixed(2)),
        }
      })
      .filter((st) => {
        // 若用户筛选了特定材料，过滤箱线图分组
        if (selectedMaterials.length === 0) return true
        return selectedMaterials.some((mat) => st.group_name.includes(mat))
      })
  }, [data, convertValue, selectedPropCode, useAltUnit, selectedMaterials])

  const boxPlotYMetrics = useMemo(() => {
    if (convertedBoxStats.length === 0) return { minY: 0, maxY: 100 }
    const allMins = convertedBoxStats.map((s) => s.min)
    const allMaxs = convertedBoxStats.map((s) => s.max)
    const minYRaw = Math.min(...allMins)
    const maxYRaw = Math.max(...allMaxs)
    const padding = (maxYRaw - minYRaw) * 0.15 || 10
    return {
      minY: Number((minYRaw - padding).toFixed(1)),
      maxY: Number((maxYRaw + padding).toFixed(1)),
    }
  }, [convertedBoxStats])

  // 尺寸常量
  const svgWidth = 860
  const svgHeight = 440
  const margin = { top: 40, right: 40, bottom: 60, left: 75 }
  const plotWidth = svgWidth - margin.left - margin.right
  const plotHeight = svgHeight - margin.top - margin.bottom

  const toggleMaterialSelection = (mat: string) => {
    setSelectedMaterials((prev) => {
      if (prev.includes(mat)) {
        return prev.filter((m) => m !== mat)
      } else {
        return [...prev, mat]
      }
    })
  }

  return (
    <div className="property-comparison-container">
      {/* 顶部标题与科学语义提示 */}
      <div className="pc-header">
        <div>
          <div className="pc-badge">
            <span className="pulse-indicator" />
            <span>CROSS-PAPER COMPARISON · 跨文献物性横向对齐看板</span>
          </div>
          <h2>相变材料物性横向对比与条件对齐</h2>
          <p className="pc-subtitle">
            对齐实验条件与测量标尺，横向对比多材料物性演变，支持直接溯源文献证据。
          </p>
        </div>
      </div>

      {/* 核心控制栏：物性指标、基质多选、加热速率、单位与视图切换 */}
      <div className="pc-filter-bar">
        {/* 物性指标选择 */}
        <div className="filter-item">
          <label className="filter-label">物性指标：</label>
          <div className="btn-group">
            {SUPPORTED_PROPERTIES.map((prop) => (
              <button
                key={prop.code}
                className={`tab-pill-btn ${selectedPropCode === prop.code ? 'active' : ''}`}
                onClick={() => setSelectedPropCode(prop.code)}
              >
                {prop.name}
              </button>
            ))}
          </div>
        </div>

        {/* 条件过滤区 */}
        <div className="filter-row-secondary">
          {/* 基体材料多选过滤 */}
          <div className="filter-multi-materials">
            <span className="filter-label">基体材料对比：</span>
            <button
              className={`mat-pill-btn ${selectedMaterials.length === 0 ? 'active' : ''}`}
              onClick={() => setSelectedMaterials([])}
              title="显示所有材料体系"
            >
              全部材料 ({availableMaterials.length})
            </button>
            {availableMaterials.map((mat) => {
              const isSelected = selectedMaterials.includes(mat)
              return (
                <button
                  key={mat}
                  className={`mat-pill-btn ${isSelected ? 'active' : ''}`}
                  onClick={() => toggleMaterialSelection(mat)}
                >
                  <span className="checkbox-dot">{isSelected ? '✓' : '+'}</span>
                  {mat} 系列
                </button>
              )
            })}
          </div>

          {/* 升温速率条件对齐过滤 */}
          {availableHeatingRates.length > 0 && (
            <div className="filter-select-group">
              <label>升温速率对齐：</label>
              <select
                value={heatingRateFilter}
                onChange={(e) => setHeatingRateFilter(e.target.value)}
              >
                <option value="">所有速率条件</option>
                {availableHeatingRates.map((rate) => (
                  <option key={rate} value={String(rate)}>
                    {rate} K/min (等温条件对齐)
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* 单位切换开关 */}
          <div className="filter-unit-toggle">
            <label>显示单位：</label>
            <button
              className="unit-toggle-btn"
              onClick={() => setUseAltUnit((prev) => !prev)}
              title="点击在标准 SI 单位与常用工程单位间切换"
            >
              <span>{currentPropMeta.defaultUnit}</span>
              <span className={`toggle-switch ${useAltUnit ? 'on' : ''}`}>
                <span className="toggle-thumb" />
              </span>
              <span>{currentPropMeta.altUnit}</span>
            </button>
          </div>

          {/* 视图切换 (散点 vs 箱线 vs 表格) */}
          <div className="view-mode-selector">
            <button
              className={`mode-btn ${activeTab === 'scatter' ? 'active' : ''}`}
              onClick={() => setActiveTab('scatter')}
            >
              📊 散点对比图 ({visiblePoints.length})
            </button>
            <button
              className={`mode-btn ${activeTab === 'boxplot' ? 'active' : ''}`}
              onClick={() => setActiveTab('boxplot')}
            >
              📦 分组箱线图 ({convertedBoxStats.length})
            </button>
            <button
              className={`mode-btn ${activeTab === 'table' ? 'active' : ''}`}
              onClick={() => setActiveTab('table')}
            >
              📋 数据明细表
            </button>
          </div>
        </div>
      </div>

      {/* 主展示区：图表与右侧证据抽屉 */}
      <div className="pc-main-workspace">
        <div className="pc-chart-panel">
          {loading && (
            <div className="chart-overlay-msg">
              <div className="loading-spinner" />
              <p>正在从 MySQL 加载并对齐跨文献物性数据…</p>
            </div>
          )}

          {error && (
            <div className="chart-overlay-msg error">
              <p>⚠️ {error}</p>
              <button className="primary" onClick={() => void fetchComparisonData()}>
                🔄 重新加载
              </button>
            </div>
          )}

          {!loading && !error && visiblePoints.length === 0 && (
            <div className="chart-overlay-msg empty">
              <div className="empty-icon-large">📊</div>
              <h3>暂无匹配的物性实测数据</h3>
              <p>在当前筛选条件下暂无已审核记录，您可以尝试清除筛选或切换其他物性指标。</p>
              <button
                className="btn-secondary"
                onClick={() => {
                  setSelectedMaterials([])
                  setHeatingRateFilter('')
                }}
              >
                重置所有筛选
              </button>
            </div>
          )}

          {/* 1. 散点对比图 (Scatter Plot) */}
          {!loading && !error && activeTab === 'scatter' && visiblePoints.length > 0 && (
            <div className="svg-chart-wrap">
              <div className="chart-legend-row">
                <span className="legend-title">掺杂体系：</span>
                <span className="legend-item"><span className="dot" style={{ background: '#0284c7' }} />纯 GeTe</span>
                <span className="legend-item"><span className="dot" style={{ background: '#8b5cf6' }} />纯 Sb2Te3</span>
                <span className="legend-item"><span className="dot" style={{ background: '#ec4899' }} />Bi 掺杂</span>
                <span className="legend-item"><span className="dot" style={{ background: '#f59e0b' }} />In 掺杂</span>
                <span className="legend-item"><span className="dot" style={{ background: '#10b981' }} />Ag 掺杂</span>
                <span className="legend-item"><span className="dot" style={{ background: '#06b6d4' }} />N 掺杂</span>
                <span className="legend-item"><span className="dot" style={{ background: '#64748b' }} />C 掺杂</span>
                <span className="legend-item"><span className="dot" style={{ background: '#dc2626' }} />Ti 掺杂</span>
              </div>

              <svg className="pc-svg-plot" viewBox={`0 0 ${svgWidth} ${svgHeight}`}>
                {/* 坐标轴背景网格 */}
                <g transform={`translate(${margin.left}, ${margin.top})`}>
                  {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                    const yPos = plotHeight * ratio
                    const val = scatterMetrics.maxY - (scatterMetrics.maxY - scatterMetrics.minY) * ratio
                    return (
                      <g key={ratio}>
                        <line x1={0} y1={yPos} x2={plotWidth} y2={yPos} stroke="#e2e8f0" strokeDasharray="3 3" />
                        <text x={-10} y={yPos + 4} textAnchor="end" fontSize={11} fill="#64748b">
                          {isNaN(val) ? '—' : val.toFixed(1)}
                        </text>
                      </g>
                    )
                  })}

                  {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                    const xPos = plotWidth * ratio
                    const val = scatterMetrics.minX + (scatterMetrics.maxX - scatterMetrics.minX) * ratio
                    return (
                      <g key={ratio}>
                        <line x1={xPos} y1={0} x2={xPos} y2={plotHeight} stroke="#e2e8f0" strokeDasharray="3 3" />
                        <text x={xPos} y={plotHeight + 20} textAnchor="middle" fontSize={11} fill="#64748b">
                          {isNaN(val) ? '—' : val.toFixed(1)}
                        </text>
                      </g>
                    )
                  })}

                  {/* 坐标轴标签 */}
                  <text
                    x={plotWidth / 2}
                    y={plotHeight + 46}
                    textAnchor="middle"
                    fontSize={13}
                    fontWeight="600"
                    fill="#334155"
                  >
                    掺杂元素浓度 (Dopant Concentration, at.%)
                  </text>
                  <text
                    x={-plotHeight / 2}
                    y={-50}
                    textAnchor="middle"
                    fontSize={13}
                    fontWeight="600"
                    fill="#334155"
                    transform="rotate(-90)"
                  >
                    {currentPropMeta.name} [{displayUnit}]
                  </text>

                  {/* 散点渲染 */}
                  {visiblePoints.map((pt) => {
                    const xSpan = scatterMetrics.maxX - scatterMetrics.minX || 1
                    const ySpan = scatterMetrics.maxY - scatterMetrics.minY || 1
                    const xRatio = (pt.conc - scatterMetrics.minX) / xSpan
                    const yRatio = (scatterMetrics.maxY - pt.displayVal) / ySpan
                    const cx = Math.max(0, Math.min(plotWidth, xRatio * plotWidth))
                    const cy = Math.max(0, Math.min(plotHeight, yRatio * plotHeight))

                    const isSelected = selectedPoint?.observation_id === pt.observation_id
                    const isHovered = hoveredPoint?.observation_id === pt.observation_id

                    return (
                      <g
                        key={pt.observation_id}
                        className="scatter-point-group"
                        style={{ cursor: 'pointer' }}
                        onClick={() => setSelectedPoint(pt)}
                        onMouseEnter={() => setHoveredPoint(pt)}
                        onMouseLeave={() => setHoveredPoint(null)}
                      >
                        {/* 选中/悬停高亮外光圈 */}
                        {(isSelected || isHovered) && (
                          <circle
                            cx={cx}
                            cy={cy}
                            r={12}
                            fill={pt.color}
                            fillOpacity={0.25}
                            stroke={pt.color}
                            strokeWidth={2}
                          />
                        )}
                        {/* 散点实体 */}
                        <circle
                          cx={cx}
                          cy={cy}
                          r={isSelected ? 7 : 5.5}
                          fill={pt.color}
                          stroke="#ffffff"
                          strokeWidth={2}
                        />
                        {/* 悬停微型标签 */}
                        {isHovered && (
                          <g transform={`translate(${cx}, ${cy - 12})`}>
                            <rect
                              x={-55}
                              y={-22}
                              width={110}
                              height={20}
                              rx={4}
                              fill="#1e293b"
                              fillOpacity={0.92}
                            />
                            <text
                              textAnchor="middle"
                              y={-8}
                              fontSize={10}
                              fill="#ffffff"
                              fontWeight="600"
                            >
                              {pt.material_formula}: {pt.displayVal} {displayUnit}
                            </text>
                          </g>
                        )}
                      </g>
                    )
                  })}
                </g>
              </svg>
              <p className="plot-hint">
                💡 提示：点击任意散点可呼出右侧【科学证据溯源抽屉】，查看原实验图表、文献出处及升温速率条件。
              </p>
            </div>
          )}

          {/* 2. 箱线统计图 (Box Plot) */}
          {!loading && !error && activeTab === 'boxplot' && convertedBoxStats.length > 0 && (
            <div className="svg-chart-wrap">
              <svg className="pc-svg-plot" viewBox={`0 0 ${svgWidth} ${svgHeight}`}>
                <g transform={`translate(${margin.left}, ${margin.top})`}>
                  {/* Y 轴网格线 */}
                  {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                    const yPos = plotHeight * ratio
                    const val = boxPlotYMetrics.maxY - (boxPlotYMetrics.maxY - boxPlotYMetrics.minY) * ratio
                    return (
                      <g key={ratio}>
                        <line x1={0} y1={yPos} x2={plotWidth} y2={yPos} stroke="#e2e8f0" strokeDasharray="3 3" />
                        <text x={-10} y={yPos + 4} textAnchor="end" fontSize={11} fill="#64748b">
                          {isNaN(val) ? '—' : val.toFixed(1)}
                        </text>
                      </g>
                    )
                  })}

                  <text
                    x={-plotHeight / 2}
                    y={-50}
                    textAnchor="middle"
                    fontSize={13}
                    fontWeight="600"
                    fill="#334155"
                    transform="rotate(-90)"
                  >
                    {currentPropMeta.name} [{displayUnit}]
                  </text>

                  {/* 箱线图各分组渲染 */}
                  {convertedBoxStats.map((stat, idx) => {
                    const groupCount = convertedBoxStats.length
                    const colWidth = plotWidth / groupCount
                    const boxWidth = Math.min(55, colWidth * 0.55)
                    const centerX = colWidth * idx + colWidth / 2

                    const ySpan = boxPlotYMetrics.maxY - boxPlotYMetrics.minY || 1
                    const getY = (val: number) => {
                      const ratio = (boxPlotYMetrics.maxY - val) / ySpan
                      return Math.max(0, Math.min(plotHeight, ratio * plotHeight))
                    }

                    const yMin = getY(stat.min)
                    const yQ1 = getY(stat.q1)
                    const yMedian = getY(stat.median)
                    const yQ3 = getY(stat.q3)
                    const yMax = getY(stat.max)
                    const yMean = getY(stat.mean)

                    const boxTop = Math.min(yQ1, yQ3)
                    const boxHeight = Math.max(2, Math.abs(yQ3 - yQ1))

                    return (
                      <g key={stat.group_name} className="boxplot-group">
                        {/* 须线 (Whisker) */}
                        <line x1={centerX} y1={yMin} x2={centerX} y2={boxTop + boxHeight} stroke="#475569" strokeWidth={1.5} />
                        <line x1={centerX} y1={boxTop} x2={centerX} y2={yMax} stroke="#475569" strokeWidth={1.5} />
                        {/* 须线端点帽 */}
                        <line x1={centerX - boxWidth / 4} y1={yMin} x2={centerX + boxWidth / 4} y2={yMin} stroke="#475569" strokeWidth={1.5} />
                        <line x1={centerX - boxWidth / 4} y1={yMax} x2={centerX + boxWidth / 4} y2={yMax} stroke="#475569" strokeWidth={1.5} />

                        {/* 箱体 (IQR) */}
                        <rect
                          x={centerX - boxWidth / 2}
                          y={boxTop}
                          width={boxWidth}
                          height={boxHeight}
                          fill="#e0e7ff"
                          stroke="#4338ca"
                          strokeWidth={2}
                          rx={3}
                        />

                        {/* 中位数线 (Median) */}
                        <line
                          x1={centerX - boxWidth / 2}
                          y1={yMedian}
                          x2={centerX + boxWidth / 2}
                          y2={yMedian}
                          stroke="#b91c1c"
                          strokeWidth={2.5}
                        />

                        {/* 均值标记点 (Mean diamond) */}
                        <polygon
                          points={`${centerX},${yMean - 4} ${centerX + 4},${yMean} ${centerX},${yMean + 4} ${centerX - 4},${yMean}`}
                          fill="#059669"
                        />

                        {/* X 轴标签 */}
                        <text
                          x={centerX}
                          y={plotHeight + 20}
                          textAnchor="middle"
                          fontSize={11}
                          fontWeight="600"
                          fill="#1e293b"
                        >
                          {stat.group_name}
                        </text>
                        <text
                          x={centerX}
                          y={plotHeight + 36}
                          textAnchor="middle"
                          fontSize={10}
                          fill="#64748b"
                        >
                          (N={stat.count})
                        </text>
                      </g>
                    )
                  })}
                </g>
              </svg>
              <div className="boxplot-legend">
                <span>🔴 红横线: 中位数 (Median)</span>
                <span>🟩 绿菱形: 平均值 (Mean)</span>
                <span>📦 蓝箱体: 四分位距 [Q1, Q3]</span>
                <span>📏 须线端点: 极值 [Min, Max]</span>
              </div>
            </div>
          )}

          {/* 3. 数据明细表 (Data Table) */}
          {!loading && !error && activeTab === 'table' && visiblePoints.length > 0 && (
            <div className="pc-table-wrap">
              <table className="pc-table">
                <thead>
                  <tr>
                    <th>材料配方</th>
                    <th>基体</th>
                    <th>掺杂体系</th>
                    <th>实测物性值 ({displayUnit})</th>
                    <th>升温速率条件</th>
                    <th>出处文献</th>
                    <th>审核状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {visiblePoints.map((pt) => (
                    <tr
                      key={pt.observation_id}
                      className={selectedPoint?.observation_id === pt.observation_id ? 'selected-row' : ''}
                    >
                      <td className="cell-formula">
                        <strong>{pt.material_formula || pt.sample_formula || '—'}</strong>
                      </td>
                      <td>{pt.base_material || '—'}</td>
                      <td>
                        {pt.dopant_element ? (
                          <span className="dopant-badge" style={{ borderColor: pt.color, color: pt.color }}>
                            {pt.dopant_element} ({pt.conc} at.%)
                          </span>
                        ) : (
                          <span className="pure-badge">纯基体</span>
                        )}
                      </td>
                      <td className="cell-value">
                        <strong>{pt.displayVal}</strong> {displayUnit}
                      </td>
                      <td>
                        {pt.heating_rate_k_per_min || pt.heating_rate_value ? (
                          <span className="condition-tag">
                            🔥 {pt.heating_rate_k_per_min ?? pt.heating_rate_value} K/min
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td className="cell-paper">
                        <span className="paper-title-clip" title={pt.paper_title || ''}>
                          {pt.paper_title || '暂无文献标题'}
                        </span>
                        {pt.paper_doi && (
                          <a
                            href={`https://doi.org/${pt.paper_doi}`}
                            target="_blank"
                            rel="noreferrer"
                            className="doi-badge"
                          >
                            DOI ↗
                          </a>
                        )}
                      </td>
                      <td>
                        <span className={`status-pill ${(pt.verification_status || '').toLowerCase()}`}>
                          {pt.verification_status === 'HUMAN_REVIEWED' ? '✓ 专家已核' : pt.verification_status || '已录入'}
                        </span>
                      </td>
                      <td>
                        <button
                          className="btn-inspect"
                          onClick={() => setSelectedPoint(pt)}
                        >
                          🔍 溯源证据
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* 右侧滑出：科学证据溯源抽屉 (Evidence Trace Drawer) */}
        {selectedPoint && (
          <div className="pc-evidence-drawer">
            <div className="drawer-header">
              <div className="drawer-title-group">
                <span className="drawer-eyebrow">EVIDENCE PROVENANCE · 科学证据追溯</span>
                <h3>{selectedPoint.material_formula || selectedPoint.sample_formula || '样品实测观测'}</h3>
              </div>
              <button
                className="close-drawer-btn"
                onClick={() => setSelectedPoint(null)}
                title="关闭抽屉"
              >
                ✕
              </button>
            </div>

            <div className="drawer-body">
              {/* 核心物性指标卡 */}
              <div className="provenance-card highlight">
                <div className="card-row">
                  <span className="prop-name">{currentPropMeta.name}</span>
                  <span className="status-badge-solid">
                    {selectedPoint.verification_status === 'HUMAN_REVIEWED'
                      ? '✓ 专家已审核'
                      : selectedPoint.verification_status || '已验证'}
                  </span>
                </div>
                <div className="main-metric">
                  <span className="metric-num">{selectedPoint.displayVal}</span>
                  <span className="metric-unit">{displayUnit}</span>
                  {useAltUnit && selectedPoint.normalized_value != null && (
                    <span className="sub-metric">
                      (规范存储值: {selectedPoint.normalized_value} {selectedPoint.normalized_unit || currentPropMeta.defaultUnit})
                    </span>
                  )}
                </div>
                <div className="condition-box">
                  <strong>⚠️ 关键耦合实验条件：</strong>
                  {selectedPoint.heating_rate_k_per_min || selectedPoint.heating_rate_value ? (
                    <span>
                      升温速率 <strong>{selectedPoint.heating_rate_k_per_min ?? selectedPoint.heating_rate_value} K/min</strong>（结晶温度严格随加热速率漂移，跨文献横向对比必须对齐升温速率条件）
                    </span>
                  ) : (
                    <span>未报告升温速率（需由领域专家进一步标定）</span>
                  )}
                </div>
              </div>

              {/* 材料与样品信息 */}
              <div className="provenance-card">
                <h4>🧪 样品与掺杂信息</h4>
                <div className="info-grid">
                  <div className="info-row">
                    <span className="info-lbl">基体系统：</span>
                    <span className="info-val">{selectedPoint.base_material || '—'}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-lbl">掺杂元素：</span>
                    <span className="info-val">{selectedPoint.dopant_element || '无 (纯相)'}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-lbl">掺杂浓度：</span>
                    <span className="info-val">{selectedPoint.conc ? `${selectedPoint.conc} at.%` : '0 at.%'}</span>
                  </div>
                  {(selectedPoint.sample_formula || selectedPoint.sample_label) && (
                    <div className="info-row">
                      <span className="info-lbl">样品编号：</span>
                      <span className="info-val">{selectedPoint.sample_formula || selectedPoint.sample_label}</span>
                    </div>
                  )}
                  {selectedPoint.substrate && (
                    <div className="info-row">
                      <span className="info-lbl">衬底材料：</span>
                      <span className="info-val">{selectedPoint.substrate}</span>
                    </div>
                  )}
                  {selectedPoint.film_thickness_nm && (
                    <div className="info-row">
                      <span className="info-lbl">薄膜厚度：</span>
                      <span className="info-val">{selectedPoint.film_thickness_nm} nm</span>
                    </div>
                  )}
                </div>
                {onSelectMaterial && selectedPoint.material_id && (
                  <button
                    className="btn-link"
                    onClick={() => onSelectMaterial(selectedPoint.material_id!)}
                  >
                    👉 打开该材料详情卡片
                  </button>
                )}
              </div>

              {/* 文献出处溯源 */}
              <div className="provenance-card">
                <h4>📄 出处文献与作者</h4>
                <p className="paper-name">{selectedPoint.paper_title || '文献出处待查'}</p>
                <div className="info-grid">
                  <div className="info-row">
                    <span className="info-lbl">第一作者：</span>
                    <span className="info-val">{selectedPoint.first_author || '—'}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-lbl">收录期刊：</span>
                    <span className="info-val">{selectedPoint.journal || '—'}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-lbl">出版年份：</span>
                    <span className="info-val">
                      {selectedPoint.paper_year ?? selectedPoint.publication_year ? `${selectedPoint.paper_year ?? selectedPoint.publication_year} 年` : '—'}
                    </span>
                  </div>
                </div>

                {selectedPoint.paper_doi && (
                  <div className="doi-action-box">
                    <a
                      href={`https://doi.org/${selectedPoint.paper_doi}`}
                      target="_blank"
                      rel="noreferrer"
                      className="doi-out-btn"
                    >
                      🔗 外部 DOI 链接: {selectedPoint.paper_doi} ↗
                    </a>
                  </div>
                )}
                {onSelectPaper && selectedPoint.paper_id && (
                  <button
                    className="btn-link"
                    onClick={() => onSelectPaper(selectedPoint.paper_id!)}
                  >
                    👉 在数据库中检索该文献全部观测
                  </button>
                )}
              </div>

              {/* 科学证据片段与图表出处 */}
              <div className="provenance-card">
                <h4>🔬 科学证据片段 (Evidence Fragment)</h4>
                {(selectedPoint.figure_or_table || selectedPoint.figure_reference) && (
                  <div className="fig-tag">
                    📌 对应图表：<strong>{selectedPoint.figure_or_table || selectedPoint.figure_reference}</strong>
                    {selectedPoint.page_number && <span> (第 {selectedPoint.page_number} 页)</span>}
                  </div>
                )}
                <blockquote className="evidence-quote">
                  {selectedPoint.evidence_snippet ||
                    '从差示扫描量热法 (DSC) 或变温电阻曲线中精确测量并经过领域专家审核晋升入库。'}
                </blockquote>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
