import { useEffect, useState } from 'react'
import type { LiteratureAgentConfig } from '../types/batch'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'
const LOCAL_STORAGE_LLM_KEY = 'phasechangedb_llm_custom_config'

export interface CustomLLMConfig {
  provider: 'gemini' | 'openai_compatible'
  baseUrl: string
  modelName: string
  apiKey: string
}

interface LiteratureAgentViewProps {
  onOpenBatchUpload: () => void
}

export function LiteratureAgentView({ onOpenBatchUpload }: LiteratureAgentViewProps) {
  const [config, setConfig] = useState<LiteratureAgentConfig>({
    agent_name: 'PhaseChangeLiteratureAgent',
    version: 'v1.0-alpha',
    enabled: true,
    available_models: ['gemini-2.5-pro'],
    default_model: 'gemini-2.5-pro',
    prompt_version: 'pcm-extract-v2.1',
    ontology_version: '0.3.0',
    auto_staging_enabled: true,
    require_human_review: true,
  })

  // 安全加固：自定义大模型配置仅在当前内存状态中维护，严禁持久化明文至 localStorage
  const [customLLM, setCustomLLM] = useState<CustomLLMConfig | null>(null)

  // 页面加载时主动清理可能存在的历史遗留明文 Key
  useEffect(() => {
    try {
      localStorage.removeItem(LOCAL_STORAGE_LLM_KEY)
    } catch {
      // ignore
    }
  }, [])

  const [selectedModel, setSelectedModel] = useState('gemini-2.5-pro')
  const [isSimulating, setIsSimulating] = useState(false)
  const [isModelModalOpen, setIsModelModalOpen] = useState(false)
  const [explainModal, setExplainModal] = useState<'prompt' | 'ontology' | null>(null)

  // 模态框临时编辑状态
  const [tempProvider, setTempProvider] = useState<'gemini' | 'openai_compatible'>('gemini')
  const [tempBaseUrl, setTempBaseUrl] = useState('https://generativelanguage.googleapis.com')
  const [tempModelName, setTempModelName] = useState('gemini-2.5-pro')
  const [tempApiKey, setTempApiKey] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  const [configSuccessMsg, setConfigSuccessMsg] = useState<string | null>(null)

  const [logs, setLogs] = useState<string[]>([
    '⚙️ [Agent Init] 科学文献智能解析智能体已就绪，当前加载本体契约版本 v0.3.0',
    '🔒 [Security Guard] 遵循科学家工作流规范：提取结果仅写入 ext_* 暂存区，严禁直写权威主表',
    '🛡️ [Vault Active] 凭据安全中继已激活：大模型 API Key 仅保留在内存会话，严禁明文落地',
    '💡 [Ready] 待命中，可通过右上角【批量上传文献】投喂相变存储领域的 PDF 或 XML 格式文献',
  ])

  useEffect(() => {
    fetch(`${API_BASE}/v1/agents/literature-parser/config`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: LiteratureAgentConfig | null) => {
        if (data) {
          setConfig(data)
          if (!customLLM) {
            setSelectedModel(data.default_model)
          }
        }
      })
      .catch(() => {})
  }, [customLLM])

  // 当自定义模型加载时，更新选中模型
  useEffect(() => {
    if (customLLM && customLLM.modelName) {
      setSelectedModel(customLLM.modelName)
    }
  }, [customLLM])

  // 打开配置模态框时同步数据
  const handleOpenModelModal = () => {
    if (customLLM) {
      setTempProvider(customLLM.provider)
      setTempBaseUrl(customLLM.baseUrl)
      setTempModelName(customLLM.modelName)
      setTempApiKey(customLLM.apiKey)
    } else {
      setTempProvider('gemini')
      setTempBaseUrl('https://generativelanguage.googleapis.com')
      setTempModelName('gemini-2.5-pro')
      setTempApiKey('')
    }
    setConfigSuccessMsg(null)
    setIsModelModalOpen(true)
  }

  // 切换预设时提供合理的默认 Base URL 与 Model Name
  const handleProviderPresetChange = (p: 'gemini' | 'openai_compatible') => {
    setTempProvider(p)
    if (p === 'gemini') {
      setTempBaseUrl('https://generativelanguage.googleapis.com')
      setTempModelName('gemini-2.5-pro')
    } else {
      setTempBaseUrl('https://api.deepseek.com/v1')
      setTempModelName('deepseek-chat')
    }
  }

  // 保存自定义模型配置到会话内存中（安全隔离）
  const handleSaveModelConfig = () => {
    const trimmedModel = tempModelName.trim() || 'gemini-2.5-pro'
    const newConfig: CustomLLMConfig = {
      provider: tempProvider,
      baseUrl: tempBaseUrl.trim(),
      modelName: trimmedModel,
      apiKey: tempApiKey.trim(),
    }
    setCustomLLM(newConfig)
    setSelectedModel(trimmedModel)
    setConfigSuccessMsg('大模型配置已安全载入当前会话内存（不持久化明文，刷新即销毁）')
    setTimeout(() => {
      setIsModelModalOpen(false)
      setConfigSuccessMsg(null)
    }, 800)
  }

  // 重置回官方默认
  const handleResetToDefault = () => {
    setCustomLLM(null)
    setSelectedModel(config.default_model)
    setIsModelModalOpen(false)
  }

  // 合并展示的模型列表（保持极简：仅 1 个默认推荐 + 当前自定义配置）
  const allModels = Array.from(
    new Set([
      config.default_model,
      ...(customLLM?.modelName ? [customLLM.modelName] : []),
    ])
  )

  const handleRunDiagnostic = async () => {
    if (isSimulating) return
    setIsSimulating(true)
    setLogs((prev) => [
      ...prev,
      `🚀 [Diagnostic Started] 正在请求后端安全代理网关，检测推理节点连通性: ${selectedModel}...`,
    ])

    try {
      const res = await fetch(`${API_BASE}/v1/agents/literature-parser/diagnostic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: customLLM?.provider ?? 'gemini',
          base_url: customLLM?.baseUrl || null,
          model_name: selectedModel,
          api_key: customLLM?.apiKey || null,
        }),
      })

      if (res.ok) {
        const data = await res.json()
        const returnedLogs: string[] = data.logs || []
        setLogs((prev) => [...prev, ...returnedLogs, `⚡ [Benchmark] 往返通信延时: ${data.latency_ms}ms`])
      } else {
        const err = await res.json().catch(() => ({}))
        setLogs((prev) => [
          ...prev,
          `❌ [Diagnostic Failed] 后端代理通信失败 (HTTP ${res.status}): ${err.detail || '服务异常'}`,
        ])
      }
    } catch (e: any) {
      setLogs((prev) => [
        ...prev,
        `⚠️ [Network Warning] 无法直连后端代理，回退本地保护模式: ${e.message || String(e)}`,
      ])
    } finally {
      setIsSimulating(false)
    }
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
            <h2 className="agent-hero-title">相变文献智能解析智能体</h2>
            <p className="agent-hero-desc">
              自动解析文献并提取相变参数与实验条件，精准锚定证据，经暂存区待专家审核入库。
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
            <span className="sub-badge">受控安全策略</span>
          </div>

          <div className="config-form">
            {/* 推理底座模型选择与配置按钮 */}
            <div className="form-item">
              <div className="form-item-header-row">
                <label htmlFor="agent-model-select">选用推理底座模型 (Foundation Model)</label>
                <button
                  type="button"
                  className="button small secondary btn-open-model-config"
                  onClick={handleOpenModelModal}
                  title="配置大模型 API Key、Base URL 及模型名称"
                >
                  ⚙️ 配置大模型 / API Key
                </button>
              </div>

              <select
                id="agent-model-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="config-select"
              >
                {allModels.map((m) => (
                  <option key={m} value={m}>
                    {m} {m === config.default_model ? '（系统默认推荐）' : '（自定义大模型）'}
                  </option>
                ))}
              </select>
              <span className="form-help">
                {customLLM
                  ? `当前已生效自定义模型: ${customLLM.modelName} (${customLLM.provider === 'gemini' ? 'Google Gemini' : 'OpenAI-Compatible'})`
                  : '针对相变材料物性数据与相变曲线，系统默认推荐选用具备深度多模态科学推断能力的模型。'}
              </span>
            </div>

            {/* 提示词工程版本 */}
            <div className="form-item">
              <div className="version-label-row">
                <label>提示词工程版本 (Prompt Version)</label>
                <button
                  type="button"
                  className="version-info-btn"
                  onClick={() => setExplainModal('prompt')}
                  title="点击了解提示词工程版本的定义、作用与可复现性机制"
                >
                  ❓ 什么是提示词版本
                </button>
              </div>
              <input type="text" value={config.prompt_version} readOnly className="config-input-readonly" />
            </div>

            {/* 本体契约版本 */}
            <div className="form-item">
              <div className="version-label-row">
                <label>本体契约版本 (Ontology Terminology)</label>
                <button
                  type="button"
                  className="version-info-btn"
                  onClick={() => setExplainModal('ontology')}
                  title="点击了解本体契约版本的定义、作用与准入守门机制"
                >
                  ❓ 什么是本体契约
                </button>
              </div>
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

      {/* 大模型配置弹窗 */}
      {isModelModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsModelModalOpen(false)}>
          <div
            className="modal-content model-config-modal card"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="model-config-title"
          >
            <div className="modal-header">
              <h3 id="model-config-title">⚙️ 配置大语言模型推理节点 (LLM Provider Config)</h3>
              <button
                type="button"
                className="close-button"
                onClick={() => setIsModelModalOpen(false)}
                aria-label="关闭"
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              {configSuccessMsg && <div className="success-banner">{configSuccessMsg}</div>}

              <div className="security-notice-box">
                <span className="security-icon">🔒</span>
                <div>
                  <strong>凭证安全隔离说明：</strong>
                  <p>
                    您的 API Key 仅保存在当前浏览器的本地受控存储中（localStorage），在解析请求时直接通过安全头通信，绝不写入公开日志或跨域泄漏。
                  </p>
                </div>
              </div>

              <div className="form-row">
                <label>模型服务商预设 (Provider)</label>
                <div className="provider-presets-row">
                  <button
                    type="button"
                    className={`preset-btn ${tempProvider === 'gemini' ? 'active' : ''}`}
                    onClick={() => handleProviderPresetChange('gemini')}
                  >
                    Google Gemini 官方
                  </button>
                  <button
                    type="button"
                    className={`preset-btn ${tempProvider === 'openai_compatible' ? 'active' : ''}`}
                    onClick={() => handleProviderPresetChange('openai_compatible')}
                  >
                    OpenAI-Compatible (DeepSeek / Ollama / 本地等)
                  </button>
                </div>
              </div>

              <div className="form-row">
                <label htmlFor="llm-base-url">API Base URL (接口基准地址)</label>
                <input
                  id="llm-base-url"
                  type="text"
                  placeholder="https://api.deepseek.com/v1"
                  value={tempBaseUrl}
                  onChange={(e) => setTempBaseUrl(e.target.value)}
                />
              </div>

              <div className="form-row">
                <label htmlFor="llm-model-name">模型标识符 (Model Name)</label>
                <input
                  id="llm-model-name"
                  type="text"
                  placeholder="例如: gemini-2.5-pro 或 deepseek-chat 或 qwen2.5:72b"
                  value={tempModelName}
                  onChange={(e) => setTempModelName(e.target.value)}
                />
                <small className="help-text">
                  请填写该 Provider 对应的准确模型 ID，切换后将作为解析智能体调用的目标底座。
                </small>
              </div>

              <div className="form-row">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label htmlFor="llm-api-key">API Key (认证凭证密钥)</label>
                  <button
                    type="button"
                    className="text-button-mini"
                    onClick={() => setShowApiKey(!showApiKey)}
                  >
                    {showApiKey ? '🙈 隐藏密钥' : '👁️ 显示明文'}
                  </button>
                </div>
                <input
                  id="llm-api-key"
                  type={showApiKey ? 'text' : 'password'}
                  placeholder="sk-..."
                  value={tempApiKey}
                  onChange={(e) => setTempApiKey(e.target.value)}
                  autoComplete="off"
                />
                <small className="help-text">支持输入 OpenAI / DeepSeek / Gemini API Key；若为本地免密模型可留空。</small>
                <div style={{ marginTop: 8, padding: '8px 12px', background: 'rgba(56, 189, 248, 0.08)', borderRadius: 6, fontSize: '0.8rem', color: '#0284c7' }}>
                  🛡️ <strong>安全保密规范</strong>：自定义 API Key 仅在当前会话内存中维护，绝不持久化到 LocalStorage 或硬盘；请求经由后端安全中继代理并实施日志敏感脱敏。
                </div>
              </div>
            </div>

            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <button
                type="button"
                className="button small secondary"
                onClick={handleResetToDefault}
              >
                🔄 恢复官方默认配置
              </button>
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  type="button"
                  className="button small secondary"
                  onClick={() => setIsModelModalOpen(false)}
                >
                  取消
                </button>
                <button
                  type="button"
                  className="button small primary"
                  onClick={handleSaveModelConfig}
                >
                  💾 保存并应用配置
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 版本概念解释弹窗 */}
      {explainModal && (
        <div className="modal-backdrop" onClick={() => setExplainModal(null)}>
          <div
            className="modal-content version-explain-modal card"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="modal-header">
              <h3>
                {explainModal === 'prompt' ? '📑 什么是「提示词工程版本」？' : '🧬 什么是「本体契约版本」？'}
              </h3>
              <button
                type="button"
                className="close-button"
                onClick={() => setExplainModal(null)}
                aria-label="关闭"
              >
                ✕
              </button>
            </div>

            <div className="modal-body version-explain-body">
              {explainModal === 'prompt' ? (
                <div className="explain-content-flow">
                  <div className="explain-section">
                    <h4>1. 核心定义 (What is it?)</h4>
                    <p>
                      <strong>提示词工程版本 (Prompt Version)</strong> 指向系统指导大语言模型抽取相变文献的结构化 Prompt 模板、少样本（Few-shot）标注范例以及 JSON Schema 契约规范的版本标识（如 <code>pcm-extract-v2.1</code>）。
                    </p>
                  </div>

                  <div className="explain-section">
                    <h4>2. 关键作用 (What does it do?)</h4>
                    <p>
                      它是大模型理解专业相变科学文献的“操作指南”。指导模型识别复杂的化学式（如 <code>Ge₂Sb₂Te₅</code>、掺杂 <code>Sc₀.₂Sb₂Te₃</code>）、相变温度、潜热数值与测试条件，并将原文段落与页码切片精准锚定到证据片段中。
                    </p>
                  </div>

                  <div className="explain-section">
                    <h4>3. 如何影响解析结果与科研复现性 (Impact on Reproducibility)</h4>
                    <p>
                      提示词模板的优化迭代直接影响字段提取的召回率与准确度。在 PhaseChangeDB 中，<strong>每次提取流水线运行都会将所用 Prompt 版本永久记录在数据库中</strong>。科研人员未来复查数据时，可 100% 审计、还原并复现当时的提取过程。
                    </p>
                  </div>
                </div>
              ) : (
                <div className="explain-content-flow">
                  <div className="explain-section">
                    <h4>1. 核心定义 (What is it?)</h4>
                    <p>
                      <strong>本体契约版本 (Ontology Terminology Version)</strong> 代表 PhaseChangeDB 数据库当前加载的相变材料领域受控词表（Controlled Vocabulary）、标准单位系统与实体分类体系的版本规范（如 <code>v0.3.0</code>）。
                    </p>
                  </div>

                  <div className="explain-section">
                    <h4>2. 关键作用 (What does it do?)</h4>
                    <p>
                      作为 AI 提取进入暂存区的“准入守门员”。定义了合法的物性代码（如 <code>crystallization_temperature</code>）、实验测量技术（如 <code>dsc</code>、<code>xrd</code>）、样品形态（如 <code>thin_film</code>）以及国际规范量纲（如 <code>K</code>、<code>J/g</code>）。
                    </p>
                  </div>

                  <div className="explain-section">
                    <h4>3. 如何影响解析结果与数据纯洁性 (Impact on Data Quality)</h4>
                    <p>
                      大模型抽取的非结构化属性必须能够映射并通过本体契约的严格校验。如果模型生成了未经验证的臆想属性或非法量纲，契约校验器会将其阻断在正式库外部，确保数据库科学概念的绝对严谨与统一。
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer" style={{ textAlign: 'right' }}>
              <button
                type="button"
                className="button small primary"
                onClick={() => setExplainModal(null)}
              >
                我知道了
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
