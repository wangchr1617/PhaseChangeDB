import { useState } from 'react'

export function KnowledgeGraphPlaceholder() {
  const [activeNode, setActiveNode] = useState<string>('Ge2Sb2Te5')

  const nodes = [
    { id: 'Ge2Sb2Te5', label: 'Ge₂Sb₂Te₅', type: '材料实体', desc: '经典赝二元相变存储材料，非晶-岩盐矿相快速可逆转变。', color: '#3b82f6' },
    { id: 'PhaseTransition', label: '非晶态 ↔ 面心立方 (FCC)', type: '相转变过程', desc: '纳秒级激光/电脉冲诱导的高速相转变网络。', color: '#8b5cf6' },
    { id: 'PropertyTc', label: '结晶温度 (Tc ~ 433 K)', type: '物理属性', desc: '相变稳定性核心指标，伴随 3 个数量级的电导率跳变。', color: '#10b981' },
    { id: 'PCRAM', label: '神经形态存算器件 (PCRAM)', type: '器件应用', desc: '非易失性多值电导突触器件与存内计算阵列。', color: '#f59e0b' },
    { id: 'PaperWuttig2007', label: 'Wuttig & Yamada (2007)', type: '支撑文献', desc: 'Nature Materials 奠基性相变存储综述，提供权威科学证据。', color: '#ec4899' },
  ]

  const currentNode = nodes.find((n) => n.id === activeNode) ?? nodes[0]

  return (
    <div className="knowledge-graph-container">
      <div className="kg-header-card">
        <div className="kg-badge">
          <span className="pulsing-dot" />
          <span>下一代功能规划 · Neo4j 图数据库拓扑投影</span>
        </div>
        <h2>相变材料科学知识图谱 (Knowledge Graph)</h2>
        <p className="kg-subtitle">
          基于证据链与本体语义网络的材料-相态-物性-器件多维图谱。当前模块处于受控建设中，已完成模式设计与 Cypher 投影契约。
        </p>
      </div>

      <div className="kg-main-layout">
        {/* 图谱模拟拓扑网络视窗 */}
        <div className="kg-graph-canvas">
          <div className="kg-canvas-hint">
            <span>🕸️ 交互式图谱拓扑预览（点击节点查看知识关系定义）</span>
          </div>

          <svg className="kg-svg" viewBox="0 0 700 420">
            <defs>
              <linearGradient id="linkGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.6" />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.6" />
              </linearGradient>
              <linearGradient id="linkGrad2" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.6" />
                <stop offset="100%" stopColor="#10b981" stopOpacity="0.6" />
              </linearGradient>
              <linearGradient id="linkGrad3" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.6" />
                <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.6" />
              </linearGradient>
              <linearGradient id="linkGrad4" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.6" />
                <stop offset="100%" stopColor="#ec4899" stopOpacity="0.6" />
              </linearGradient>
            </defs>

            {/* 连线 */}
            <line x1="350" y1="210" x2="160" y2="120" stroke="url(#linkGrad1)" strokeWidth="3" strokeDasharray="5,5" className="flowing-edge" />
            <line x1="350" y1="210" x2="540" y2="120" stroke="url(#linkGrad2)" strokeWidth="3" strokeDasharray="5,5" className="flowing-edge" />
            <line x1="160" y1="120" x2="200" y2="330" stroke="url(#linkGrad3)" strokeWidth="2.5" />
            <line x1="350" y1="210" x2="490" y2="330" stroke="url(#linkGrad4)" strokeWidth="2.5" />

            {/* 关系标签 */}
            <text x="240" y="150" fill="#94a3b8" fontSize="12" textAnchor="middle">HAS_PHASE</text>
            <text x="460" y="150" fill="#94a3b8" fontSize="12" textAnchor="middle">EXHIBITS_PROPERTY</text>
            <text x="160" y="240" fill="#94a3b8" fontSize="12" textAnchor="middle">APPLIED_IN</text>
            <text x="440" y="280" fill="#94a3b8" fontSize="12" textAnchor="middle">EVIDENCE_FROM</text>

            {/* 节点 1: 中心材料 */}
            <g
              className={`kg-node ${activeNode === 'Ge2Sb2Te5' ? 'active-node' : ''}`}
              onClick={() => setActiveNode('Ge2Sb2Te5')}
              transform="translate(350, 210)"
            >
              <circle r="44" fill="#1e293b" stroke="#3b82f6" strokeWidth="4" />
              <text y="-5" fill="#f8fafc" fontSize="14" fontWeight="bold" textAnchor="middle">Ge₂Sb₂Te₅</text>
              <text y="15" fill="#93c5fd" fontSize="11" textAnchor="middle">核心材料</text>
            </g>

            {/* 节点 2: 相态转变 */}
            <g
              className={`kg-node ${activeNode === 'PhaseTransition' ? 'active-node' : ''}`}
              onClick={() => setActiveNode('PhaseTransition')}
              transform="translate(160, 120)"
            >
              <circle r="36" fill="#1e293b" stroke="#8b5cf6" strokeWidth="3" />
              <text y="-3" fill="#f8fafc" fontSize="12" fontWeight="bold" textAnchor="middle">相态网络</text>
              <text y="14" fill="#c4b5fd" fontSize="10" textAnchor="middle">FCC ↔ Amorph</text>
            </g>

            {/* 节点 3: 物理属性 */}
            <g
              className={`kg-node ${activeNode === 'PropertyTc' ? 'active-node' : ''}`}
              onClick={() => setActiveNode('PropertyTc')}
              transform="translate(540, 120)"
            >
              <circle r="36" fill="#1e293b" stroke="#10b981" strokeWidth="3" />
              <text y="-3" fill="#f8fafc" fontSize="12" fontWeight="bold" textAnchor="middle">Tc 结晶温度</text>
              <text y="14" fill="#6ee7b7" fontSize="10" textAnchor="middle">433 K 观测点</text>
            </g>

            {/* 节点 4: 器件应用 */}
            <g
              className={`kg-node ${activeNode === 'PCRAM' ? 'active-node' : ''}`}
              onClick={() => setActiveNode('PCRAM')}
              transform="translate(200, 330)"
            >
              <circle r="34" fill="#1e293b" stroke="#f59e0b" strokeWidth="3" />
              <text y="-3" fill="#f8fafc" fontSize="12" fontWeight="bold" textAnchor="middle">PCRAM 单元</text>
              <text y="14" fill="#fcd34d" fontSize="10" textAnchor="middle">存算应用</text>
            </g>

            {/* 节点 5: 支撑文献 */}
            <g
              className={`kg-node ${activeNode === 'PaperWuttig2007' ? 'active-node' : ''}`}
              onClick={() => setActiveNode('PaperWuttig2007')}
              transform="translate(490, 330)"
            >
              <circle r="34" fill="#1e293b" stroke="#ec4899" strokeWidth="3" />
              <text y="-3" fill="#f8fafc" fontSize="12" fontWeight="bold" textAnchor="middle">科学文献</text>
              <text y="14" fill="#f472b6" fontSize="10" textAnchor="middle">Nat. Mater.</text>
            </g>
          </svg>
        </div>

        {/* 右侧：节点详细与建设进展说明卡片 */}
        <div className="kg-info-panel">
          <div className="kg-selected-card" style={{ borderColor: currentNode.color }}>
            <span className="kg-type-tag" style={{ backgroundColor: `${currentNode.color}22`, color: currentNode.color }}>
              {currentNode.type}
            </span>
            <h3>{currentNode.label}</h3>
            <p>{currentNode.desc}</p>
          </div>

          <div className="kg-roadmap-card">
            <h4>🚀 知识图谱功能建设规划 (Roadmap)</h4>
            <ul className="kg-roadmap-list">
              <li className="done">
                <span className="step-icon">✓</span>
                <div>
                  <strong>模式与本体模型定义 (v0.1)</strong>
                  <p>完成 MySQL 权威关系建模、UUIDv7 规范以及 Neo4j 节点/边标签规约。</p>
                </div>
              </li>
              <li className="in-progress">
                <span className="step-icon">⟳</span>
                <div>
                  <strong>Outbox 事件驱动异步投影 (v0.2)</strong>
                  <p>通过 Outbox 队列异步流式将材料与证据链增量投影至图存储，确保 MySQL 主库零性能开销与故障隔离。</p>
                </div>
              </li>
              <li className="planned">
                <span className="step-icon">⏱</span>
                <div>
                  <strong>Cypher 图遍历与多跳推断 (v0.3 规划中)</strong>
                  <p>上线前端可视化图谱探索器，支持成分-相变势垒-器件寿命的全链条多跳因果推断与逆向材料设计。</p>
                </div>
              </li>
            </ul>

            <div className="kg-action-box">
              <span className="kg-hint">您可以通过文献解析智能体或批量上传功能，为知识图谱持续注入经过证据核验的高质量数据源。</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
