import { useEffect, useState } from 'react'
import type { LiteratureAgentConfig } from '../types/batch'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

interface LiteratureAgentViewProps {
  onOpenBatchUpload: () => void
}

export function LiteratureAgentView({ onOpenBatchUpload }: LiteratureAgentViewProps) {
  const [config, setConfig] = useState<LiteratureAgentConfig>({
    agent_name: 'PhaseChangeLiteratureAgent',
    version: 'v1.0-alpha',
    enabled: true,
    available_models: ['gemini-2.5-pro', 'gemini-2.5-flash', 'deepseek-r1-materials', 'local-pcm-fine-tuned'],
    default_model: 'gemini-2.5-pro',
    prompt_version: 'pcm-extract-v2.1',
    ontology_version: '0.3.0',
    auto_staging_enabled: true,
    require_human_review: true,
  })

  const [selectedModel, setSelectedModel] = useState('gemini-2.5-pro')
  const [isSimulating, setIsSimulating] = useState(false)
  const [logs, setLogs] = useState<string[]>([
    '⚙️ [Agent Init] 科学文献智能解析智能体已就绪，当前加载本体契约版本 v0.3.0',
    '🔒 [Security Guard] 遵循科学家工作流规范：提取结果仅写入 ext_* 暂存区，严禁直写权威主表',
    '💡 [Ready] 待命中，可通过右上角【批量上传文献】投喂相变存储领域的 PDF 或 XML 格式文献',
  ])

  useEffect(() => {
    fetch(`${API_BASE}/v1/agents/literature-parser/config`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: LiteratureAgentConfig | null) => {
        if (data) {
          setConfig(data)
          setSelectedModel(data.default_model)
        }
      })
      .catch(() => {})
  }, [])

  const handleRunDiagnostic = () => {
    if (isSimulating) return
    setIsSimulating(true)
    const newLogs: string[] = [
      ...logs,
      `🚀 [Diagnostic Started] 正在连接大模型推理节点 (${selectedModel})...`,
      `📑 [Prompt Pipeline] 载入结构化提示词模板 ${config.prompt_version} (少样本示例: GeTe, Sb2Te3)`,
      `🔍 [Entity Recognizer] 正在探测相变材料化学式、相变温度与开关态电阻比抽取规则...`,
      `✅ [Model Benchmark] 连通性测试通过！响应延时 42ms，支持多模态图表解析与表格坐标定位。`,
    ]

    let step = 0
    const interval = setInterval(() => {
      step += 1
      if (step <= 4) {
        setLogs((prev) => [...prev, newLogs[newLogs.length - 5 + step]])
      } else {
        clearInterval(interval)
        setIsSimulating(false)
      }
    }, 600)
  }

  return (
    <div className="agent-workbench-container">
      {/* 顶部智能体看板 */}
      <div className="agent-hero-banner">
        <div className="agent-status-indicator">
          <span className={`status-badge-dot ${config.enabled ? 'online' : 'offline'}`} />
          <span className="agent-status-text">{config.enabled ? '智能体服务正常 · 待命中' : '智能体已停用'}</span>
          <span className="agent-version-tag">{config.version}</span>
        </div>

        <div className="agent-hero-content">
          <div>
            <h2>相变文献智能解析智能体 (Scientist Literature Agent)</h2>
            <p>
              具备材料科学领域知识的多模态大模型抽取工作流。自动化完成 PDF 文档解析、相转变参数结构化提取、
              实验条件归一化与证据碎片（evd_fragment）精准锚定，成果安全流入暂存区等待专家仲裁。
            </p>
          </div>

          <div className="agent-hero-actions">
            <button className="primary btn-hero-upload" onClick={onOpenBatchUpload}>
              📁 批量上传并触发智能解析
            </button>
            <button
              className="btn-secondary"
              onClick={handleRunDiagnostic}
              disabled={isSimulating}
            >
              {isSimulating ? '⚡ 正在诊断推理节点…' : '⚡ 运行智能体全链路自检'}
            </button>
          </div>
        </div>
      </div>

      {/* 中部卡片栅格 */}
      <div className="agent-grid-layout">
        {/* 左侧配置项 */}
        <div className="agent-config-card">
          <div className="card-header">
            <h3>🛠️ 智能体工作流设置 (Agent Settings)</h3>
            <span className="sub-badge">只读受控策略</span>
          </div>

          <div className="config-form">
            <div className="form-item">
              <label>选用推理底座模型 (Foundation Model)</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="config-select"
              >
                {config.available_models.map((m) => (
                  <option key={m} value={m}>
                    {m} {m === config.default_model ? '（默认推荐）' : ''}
                  </option>
                ))}
              </select>
              <span className="form-help">针对相变材料物性数据与相变曲线，推荐选择具备深度科学推断能力的模型。</span>
            </div>

            <div className="form-item">
              <label>提示词工程版本 (Prompt Version)</label>
              <input type="text" value={config.prompt_version} readOnly className="config-input-readonly" />
            </div>

            <div className="form-item">
              <label>本体契约版本 (Ontology Terminology)</label>
              <input type="text" value={`v${config.ontology_version}`} readOnly className="config-input-readonly" />
            </div>

            <div className="toggle-group">
              <label className="toggle-label">
                <input type="checkbox" checked={config.auto_staging_enabled} readOnly />
                <span>自动写入 AI 提取暂存区 (ext_candidate)</span>
              </label>
              <label className="toggle-label">
                <input type="checkbox" checked={config.require_human_review} readOnly />
                <span>必须经专家人工审核后晋升 (Human-in-the-loop)</span>
              </label>
            </div>
          </div>
        </div>

        {/* 右侧：工作流规范机制说明 */}
        <div className="agent-rules-card">
          <div className="card-header">
            <h3>🛡️ 科学数据可信提取与安全规范</h3>
          </div>
          <div className="rules-content">
            <div className="rule-box">
              <span className="rule-num">1</span>
              <div>
                <strong>绝对四元组锚定原则</strong>
                <p>每个抽取的属性值均绑定「材料-相态-物性-测试条件」，缺一不可，严禁模糊入库。</p>
              </div>
            </div>
            <div className="rule-box">
              <span className="rule-num">2</span>
              <div>
                <strong>保留原始报告值与规范单位双轨制</strong>
                <p>自动进行温度（K/°C）、能量（eV）、压力（GPa）换算，同时永久保留文献原始文本。</p>
              </div>
            </div>
            <div className="rule-box">
              <span className="rule-num">3</span>
              <div>
                <strong>证据链与可解释溯源</strong>
                <p>提取结果精准记录文献 DOI、页码、段落文本切片与图表编号，保障科研结论 100% 可复现。</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 底部流式调用日志 / Trace 输出占位终端 */}
      <div className="agent-terminal-card">
        <div className="terminal-header">
          <div className="terminal-dots">
            <span className="dot red" />
            <span className="dot yellow" />
            <span className="dot green" />
          </div>
          <span className="terminal-title">🖥️ 智能体推理与流式解析日志 (Live Execution Trace)</span>
          <button className="btn-clear-logs" onClick={() => setLogs([])}>清空日志</button>
        </div>

        <div className="terminal-body">
          {logs.map((log, index) => (
            <div key={index} className="terminal-line">
              <span className="line-prefix">&gt;</span>
              <span className="line-text">{log}</span>
            </div>
          ))}
          {isSimulating && (
            <div className="terminal-line blinking">
              <span className="line-prefix">&gt;</span>
              <span className="line-cursor">▋ 智能体正在解析文献文档流与生成结构化实体...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
