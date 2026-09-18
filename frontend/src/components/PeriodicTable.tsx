import React, { useState } from 'react'
import { PERIODIC_ELEMENTS } from './periodicElements'

interface PeriodicTableProps {
  availableElements: string[]
  selectedElements: string[]
  onToggleElement: (symbol: string) => void
  onClearSelection: () => void
}

export const PeriodicTable: React.FC<PeriodicTableProps> = ({
  availableElements,
  selectedElements,
  onToggleElement,
  onClearSelection,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const availableSet = new Set(availableElements)
  const selectedSet = new Set(selectedElements)

  return (
    <div className="periodic-table-card">
      <div className="periodic-table-header">
        <div className="header-left">
          <h3>元素周期表筛选</h3>
          <span className="element-stats-badge">
            有效元素: <strong>{availableElements.length}</strong> / 118 种
          </span>
          {selectedElements.length > 0 && (
            <div className="selected-tags">
              <span className="selected-label">已选元素:</span>
              {selectedElements.map((el) => (
                <span
                  key={el}
                  className="selected-tag"
                  onClick={() => onToggleElement(el)}
                  title="点击移除此元素筛选"
                >
                  {el} ×
                </span>
              ))}
              <button
                type="button"
                className="btn-clear-elements"
                onClick={onClearSelection}
              >
                清空筛选
              </button>
            </div>
          )}
        </div>
        <button
          type="button"
          className="btn-toggle-collapse"
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          {isCollapsed ? '展开周期表 ▼' : '收起周期表 ▲'}
        </button>
      </div>

      {!isCollapsed && (
        <>
          <div className="periodic-grid-container">
            <div className="periodic-grid">
              {PERIODIC_ELEMENTS.map((elem) => {
                const isAvailable = availableSet.has(elem.symbol)
                const isSelected = selectedSet.has(elem.symbol)

                return (
                  <button
                    key={elem.symbol}
                    type="button"
                    disabled={!isAvailable}
                    className={`element-cell cat-${elem.category} ${
                      isAvailable ? 'available' : 'disabled'
                    } ${isSelected ? 'selected' : ''}`}
                    style={{
                      gridRow: elem.row,
                      gridColumn: elem.col,
                    }}
                    onClick={() => {
                      if (isAvailable) onToggleElement(elem.symbol)
                    }}
                    title={
                      isAvailable
                        ? `${elem.number}. ${elem.name} (${elem.zh}) - 点击${isSelected ? '取消' : ''}筛选`
                        : `${elem.number}. ${elem.name} (${elem.zh}) - 数据库中暂无此元素材料`
                    }
                  >
                    <span className="elem-number">{elem.number}</span>
                    <span className="elem-symbol">{elem.symbol}</span>
                    <span className="elem-zh">{elem.zh}</span>
                  </button>
                )
              })}

              {/* 镧系占位标示 */}
              <div
                className="element-cell placeholder"
                style={{ gridRow: 6, gridColumn: 3 }}
                title="镧系元素 57-71"
              >
                <span className="elem-number">57-71</span>
                <span className="elem-symbol font-small">La-Lu</span>
              </div>

              {/* 锕系占位标示 */}
              <div
                className="element-cell placeholder"
                style={{ gridRow: 7, gridColumn: 3 }}
                title="锕系元素 89-103"
              >
                <span className="elem-number">89-103</span>
                <span className="elem-symbol font-small">Ac-Lr</span>
              </div>
            </div>
          </div>

          <div className="periodic-legend">
            <span className="legend-item"><i className="legend-dot available-dot" />数据库现有元素（高亮可选）</span>
            <span className="legend-item"><i className="legend-dot disabled-dot" />无收录元素（置灰不可点）</span>
            <span className="legend-item"><i className="legend-dot selected-dot" />当前选中筛选</span>
          </div>
        </>
      )}
    </div>
  )
}
