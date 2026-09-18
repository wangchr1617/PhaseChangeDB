import { useEffect, useState } from 'react'
import type { LiteratureStatsResponse } from '../types/batch'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

interface LiteratureStatsViewProps {
  onFilterByYear?: (year: number) => void
  onFilterByJournal?: (journal: string) => void
  onFilterBySystem?: (system: string) => void
  onSwitchToList?: () => void
  currentYearFilter?: number | null
  currentJournalFilter?: string | null
  currentSystemFilter?: string | null
  onClearFilters?: () => void
}

export function LiteratureStatsView({
  onFilterByYear,
  onFilterByJournal,
  onFilterBySystem,
  onSwitchToList,
  currentYearFilter,
  currentJournalFilter,
  currentSystemFilter,
  onClearFilters,
}: LiteratureStatsViewProps) {
  const [stats, setStats] = useState<LiteratureStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStats = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/v1/literature/stats`)
      if (!res.ok) {
        throw new Error(`获取文献统计失败: HTTP ${res.status}`)
      }
      const data: LiteratureStatsResponse = await res.json()
      setStats(data)
    } catch (err: any) {
      setError(err.message || '无法加载文献统计数据')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchStats()
  }, [])

  if (loading) {
    return (
      <div className="stats-container loading-state">
        <div className="skeleton-line" style={{ width: '40%', height: 28, marginBottom: 20 }} />
        <div className="stats-grid">
          <div className="skeleton-card" style={{ height: 320 }} />
          <div className="skeleton-card" style={{ height: 320 }} />
        </div>
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="stats-container error-state">
        <p className="error-text">⚠️ {error || '暂无文献统计数据'}</p>
        <button className="button secondary" onClick={() => void fetchStats()}>重试加载</button>
      </div>
    )
  }

  const maxYearCount = Math.max(...stats.year_distribution.map(y => y.count), 1)
  const maxJournalCount = Math.max(...stats.journal_distribution.map(j => j.count), 1)
  const maxSystemCount = Math.max(...(stats.system_distribution || []).map(s => s.count), 1)

  // SVG 柱状图参数
  const chartHeight = 220
  const chartWidth = 560
  const paddingLeft = 40
  const paddingRight = 20
  const paddingTop = 20
  const paddingBottom = 35
  const plotWidth = chartWidth - paddingLeft - paddingRight
  const plotHeight = chartHeight - paddingTop - paddingBottom
  const barCount = stats.year_distribution.length
  const barWidth = barCount > 0 ? Math.min(36, Math.max(16, (plotWidth / barCount) * 0.55)) : 24
  const step = barCount > 1 ? plotWidth / (barCount - 1) : plotWidth / 2

  return (
    <div className="stats-container">
      {/* 顶部概览与筛选标签 */}
      <div className="stats-header">
        <div>
          <h2 className="stats-title">相变存储材料文献计量与知识分布</h2>
          <p className="stats-subtitle">
            共收录 <strong>{stats.total_papers}</strong> 篇已核验学术文献，点击图表柱子、期刊或体系条目可即时下钻筛选
          </p>
        </div>
        <div className="stats-actions">
          {(currentYearFilter || currentJournalFilter || currentSystemFilter) && (
            <div className="active-filters">
              <span className="filter-hint">当前下钻：</span>
              {currentYearFilter && (
                <span className="filter-tag">
                  年份: {currentYearFilter}
                </span>
              )}
              {currentJournalFilter && (
                <span className="filter-tag">
                  期刊: {currentJournalFilter}
                </span>
              )}
              {currentSystemFilter && (
                <span className="filter-tag highlight-system">
                  体系: {currentSystemFilter}
                </span>
              )}
              <button className="button small text-button" onClick={onClearFilters}>
                清空下钻
              </button>
            </div>
          )}
          {onSwitchToList && (
            <button className="button secondary" onClick={onSwitchToList}>
              📄 返回文献列表
            </button>
          )}
        </div>
      </div>

      <div className="stats-grid">
        {/* 年份分布图 */}
        <div className="stats-card">
          <div className="card-head">
            <h3>📅 发表年份分布 (Publication Years)</h3>
            <span className="unit-badge">单位: 篇</span>
          </div>

          {stats.year_distribution.length === 0 ? (
            <div className="empty-chart">暂无年份分布数据</div>
          ) : (
            <div className="chart-wrapper">
              <svg
                viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                className="year-chart-svg"
              >
                {/* 背景刻度线 */}
                {[0, 0.5, 1].map(ratio => {
                  const yVal = paddingTop + plotHeight * (1 - ratio)
                  const labelVal = Math.round(maxYearCount * ratio)
                  return (
                    <g key={ratio} className="grid-line">
                      <line x1={paddingLeft} y1={yVal} x2={chartWidth - paddingRight} y2={yVal} stroke="#e2e8f0" strokeDasharray="3 3" />
                      <text x={paddingLeft - 8} y={yVal + 4} textAnchor="end" fontSize={11} fill="#94a3b8">
                        {labelVal}
                      </text>
                    </g>
                  )
                })}

                {/* 柱子 */}
                {stats.year_distribution.map((item, idx) => {
                  const cx = barCount === 1 ? chartWidth / 2 : paddingLeft + idx * step
                  const barH = (item.count / maxYearCount) * plotHeight
                  const barY = paddingTop + plotHeight - barH
                  const isSelected = currentYearFilter === item.year

                  return (
                    <g
                      key={item.year}
                      className={`bar-group ${isSelected ? 'selected' : ''}`}
                      onClick={() => onFilterByYear && onFilterByYear(item.year)}
                      style={{ cursor: 'pointer' }}
                    >
                      {/* 柱状主体 */}
                      <rect
                        x={cx - barWidth / 2}
                        y={barY}
                        width={barWidth}
                        height={barH}
                        rx={4}
                        className="bar-rect"
                        fill={isSelected ? '#2563eb' : 'url(#yearGrad)'}
                      />
                      {/* 顶部数值 */}
                      <text
                        x={cx}
                        y={barY - 6}
                        textAnchor="middle"
                        fontSize={12}
                        fontWeight="bold"
                        fill={isSelected ? '#1e40af' : '#475569'}
                      >
                        {item.count}
                      </text>
                      {/* X 轴年份文本 */}
                      <text
                        x={cx}
                        y={chartHeight - 10}
                        textAnchor="middle"
                        fontSize={11}
                        fill={isSelected ? '#1e40af' : '#64748b'}
                        fontWeight={isSelected ? 'bold' : 'normal'}
                      >
                        {item.year}
                      </text>
                    </g>
                  )
                })}

                {/* 渐变定义 */}
                <defs>
                  <linearGradient id="yearGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#38bdf8" />
                    <stop offset="100%" stopColor="#0284c7" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="chart-tip-hint">💡 点击年份柱子可下钻筛选该年份的所有学术成果</div>
            </div>
          )}
        </div>

        {/* 期刊分布横向条形图 */}
        <div className="stats-card">
          <div className="card-head">
            <h3>📖 来源期刊与会议分布 (Journals & Sources)</h3>
            <span className="unit-badge">已规范合并同名源</span>
          </div>

          {stats.journal_distribution.length === 0 ? (
            <div className="empty-chart">暂无期刊分布数据</div>
          ) : (
            <div className="journal-list">
              {stats.journal_distribution.map((item) => {
                const percent = ((item.count / stats.total_papers) * 100).toFixed(0)
                const isSelected = currentJournalFilter === item.journal

                return (
                  <div
                    key={item.journal}
                    className={`journal-row ${isSelected ? 'selected' : ''}`}
                    onClick={() => onFilterByJournal && onFilterByJournal(item.journal)}
                    style={{ cursor: 'pointer' }}
                    title={`点击下钻查看 ${item.journal} 的 ${item.count} 篇文献`}
                  >
                    <div className="journal-meta">
                      <span className="journal-name">
                        {isSelected && '✓ '}{item.journal}
                      </span>
                      <span className="journal-count">
                        <strong>{item.count}</strong> 篇 ({percent}%)
                      </span>
                    </div>
                    <div className="progress-bg">
                      <div
                        className="progress-bar"
                        style={{
                          width: `${Math.max(8, (item.count / maxJournalCount) * 100)}%`,
                          backgroundColor: isSelected ? '#0d9488' : '#14b8a6',
                        }}
                      />
                    </div>
                  </div>
                )
              })}
              <div className="chart-tip-hint">💡 点击期刊条目可精准下钻筛选对应期刊发表文献</div>
            </div>
          )}
        </div>

        {/* 化学体系分布横向条形图 */}
        <div className="stats-card">
          <div className="card-head">
            <h3>🧪 材料化学体系分布 (Chemical Systems)</h3>
            <span className="unit-badge">按关联文献数排序</span>
          </div>

          {(stats.system_distribution || []).length === 0 ? (
            <div className="empty-chart">暂无化学体系分布数据</div>
          ) : (
            <div className="journal-list">
              {stats.system_distribution.map((item) => {
                const percent = ((item.count / stats.total_papers) * 100).toFixed(0)
                const isSelected = currentSystemFilter === item.chemical_system

                return (
                  <div
                    key={item.chemical_system}
                    className={`journal-row ${isSelected ? 'selected' : ''}`}
                    onClick={() => onFilterBySystem && onFilterBySystem(item.chemical_system)}
                    style={{ cursor: 'pointer' }}
                    title={`点击下钻查看 ${item.chemical_system} 体系的 ${item.count} 篇文献`}
                  >
                    <div className="journal-meta">
                      <span className="journal-name font-mono">
                        {isSelected && '✓ '}{item.chemical_system}
                      </span>
                      <span className="journal-count">
                        <strong>{item.count}</strong> 篇 ({percent}%)
                      </span>
                    </div>
                    <div className="progress-bg">
                      <div
                        className="progress-bar"
                        style={{
                          width: `${Math.max(8, (item.count / maxSystemCount) * 100)}%`,
                          backgroundColor: isSelected ? '#7c3aed' : '#8b5cf6',
                        }}
                      />
                    </div>
                  </div>
                )
              })}
              <div className="chart-tip-hint">💡 点击化学体系条目可精准下钻筛选该体系发表成果</div>
            </div>
          )}
        </div>

        {/* 作者活跃贡献榜 */}
        <div className="stats-card full-width">
          <div className="card-head">
            <h3>👥 核心作者与科研团队 (Key Authors)</h3>
            <span className="unit-badge">Top 15 署名作者</span>
          </div>

          {stats.author_distribution.length === 0 ? (
            <div className="empty-chart">暂无作者分布数据</div>
          ) : (
            <div className="authors-badge-grid">
              {stats.author_distribution.map((a, idx) => (
                <div key={a.author} className="author-stat-badge">
                  <span className={`author-rank ${idx < 3 ? 'top' : ''}`}>#{idx + 1}</span>
                  <span className="author-name">{a.author}</span>
                  <span className="author-count">{a.count} 篇</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
