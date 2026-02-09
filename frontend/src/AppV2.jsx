import { useEffect, useMemo, useState } from "react";

const API_BASE = "http://127.0.0.1:8008";
const REQUEST_TIMEOUT_MS = 60000;

async function request(path, options = {}) {
  const { timeoutMs = REQUEST_TIMEOUT_MS, ...fetchOptions } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...fetchOptions, signal: controller.signal });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Request timeout");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }

  const text = await response.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { raw: text };
    }
  }
  if (!response.ok) {
    throw new Error(data.detail || data.raw || text || `Request failed: ${response.status}`);
  }
  return data;
}

async function post(path, payload) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

async function get(path) {
  return request(path, { method: "GET" });
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function normalizeError(error) {
  const message = String(error?.message || error || "Unknown error");
  if (message.includes("Failed to fetch")) {
    return "无法连接后端服务（127.0.0.1:8008）。请确认桌面端已启动，或先手动启动后端。";
  }
  if (message.includes("Request timeout")) {
    return "请求超时。请稍后重试，或降低上下文文件数量后再试。";
  }
  if (message.includes("Missing API key")) {
    return "缺少 API Key。请在环境变量中设置对应密钥后重试。";
  }
  if (message.includes("Workspace root not found")) {
    return "工作目录不存在。请重新选择一个有效目录。";
  }
  return message;
}

async function pickDirectoryWithTauri() {
  const invoke = window.__TAURI_INTERNALS__?.invoke;
  if (typeof invoke !== "function") {
    return "";
  }
  try {
    const selected = await invoke("pick_folder");
    return selected || "";
  } catch (error) {
    console.warn("Directory picker unavailable:", error);
    return "";
  }
}

function TabButton({ active, onClick, children }) {
  return (
    <button className={`tab-btn ${active ? "active" : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}

function toLlmState(raw = {}) {
  return {
    provider: raw.provider || "echo",
    endpoint: raw.endpoint || "https://api.openai.com/v1",
    model: raw.model || "gpt-4o-mini",
    api_key_env: raw.api_key_env || "OPENAI_API_KEY",
    timeout_seconds: raw.timeout_seconds || 30,
    max_context_tokens: raw.max_context_tokens || 12000
  };
}

export default function AppV2() {
  const [tab, setTab] = useState("scan");
  const [rootDir, setRootDir] = useState(".");
  const [documents, setDocuments] = useState([]);
  const [selectedPaths, setSelectedPaths] = useState([]);
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState("");
  const [quizTraceId, setQuizTraceId] = useState("");
  const [quizItems, setQuizItems] = useState([]);
  const [quizAnswers, setQuizAnswers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState([]);
  const [configLoading, setConfigLoading] = useState(false);
  const [modelConfig, setModelConfig] = useState(toLlmState());

  const title = useMemo(() => {
    if (tab === "scan") return "扫描工作区";
    if (tab === "review") return "复盘模式";
    return "问答 / 测验";
  }, [tab]);

  useEffect(() => {
    void (async () => {
      try {
        const data = await get("/config");
        if (data.workspace_root_dir) {
          setRootDir(data.workspace_root_dir);
        }
        setModelConfig(toLlmState(data.llm));
      } catch (err) {
        console.warn("Load config failed:", err);
        setError(normalizeError(err));
      }
    })();
  }, []);

  async function runScan() {
    setLoading(true);
    setError("");
    setWarnings([]);
    try {
      const data = await post("/scan", { root_dir: rootDir });
      const docs = data.documents || [];
      setDocuments(docs);
      setSelectedPaths(docs.map((item) => item.path));
      setResult(data);
      setWarnings(data.warnings || []);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  }

  async function runReview() {
    setLoading(true);
    setError("");
    setWarnings([]);
    try {
      const data = await post("/review/run", {
        root_dir: rootDir,
        topic: "",
        selected_paths: selectedPaths
      });
      setResult(data);
      setWarnings(data.warnings || []);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  }

  async function sendChat() {
    setLoading(true);
    setError("");
    setWarnings([]);
    try {
      const data = await post("/chat/session", {
        root_dir: rootDir,
        message,
        selected_paths: selectedPaths
      });
      setResult(data);
      setWarnings(data.warnings || []);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  }

  async function genQuiz() {
    setLoading(true);
    setError("");
    setWarnings([]);
    try {
      const data = await post("/quiz/generate", {
        root_dir: rootDir,
        count: 3,
        selected_paths: selectedPaths
      });
      setQuizTraceId(data.trace_id);
      setQuizItems(data.items || []);
      setQuizAnswers(new Array((data.items || []).length).fill(""));
      setResult(data);
      setWarnings(data.warnings || []);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  }

  async function evalQuiz() {
    setLoading(true);
    setError("");
    try {
      const data = await post("/quiz/evaluate", { trace_id: quizTraceId, answers: quizAnswers });
      setResult(data);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  }

  async function saveConfig() {
    setConfigLoading(true);
    setError("");
    try {
      const data = await post("/config", {
        workspace_root_dir: rootDir,
        llm: {
          provider: modelConfig.provider,
          endpoint: modelConfig.endpoint,
          model: modelConfig.model,
          api_key_env: modelConfig.api_key_env,
          timeout_seconds: Number(modelConfig.timeout_seconds),
          max_context_tokens: Number(modelConfig.max_context_tokens)
        }
      });
      setResult(data);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setConfigLoading(false);
    }
  }

  async function pickDirectory() {
    const selected = await pickDirectoryWithTauri();
    if (selected) {
      setRootDir(selected);
    }
  }

  function togglePath(path) {
    setSelectedPaths((prev) => {
      if (prev.includes(path)) {
        return prev.filter((item) => item !== path);
      }
      return [...prev, path];
    });
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Local Review Copilot</h1>
        <p>轻量 · 本地优先 · 可追溯</p>
        <div className="tabs">
          <TabButton active={tab === "scan"} onClick={() => setTab("scan")}>Scan</TabButton>
          <TabButton active={tab === "review"} onClick={() => setTab("review")}>Review</TabButton>
          <TabButton active={tab === "quiz"} onClick={() => setTab("quiz")}>Quiz/Chat</TabButton>
        </div>
      </aside>

      <main className="content">
        <header className="header">
          <h2>{title}</h2>
          <div className="row-actions">
            <input
              value={rootDir}
              onChange={(event) => setRootDir(event.target.value)}
              placeholder="Workspace root directory"
            />
            <button onClick={pickDirectory}>选择目录</button>
            <button onClick={saveConfig} disabled={configLoading}>
              {configLoading ? "保存中..." : "保存设置"}
            </button>
          </div>
        </header>

        <section className="card">
          <h3>模型设置</h3>
          <div className="settings-grid">
            <label>
              Provider
              <select
                value={modelConfig.provider}
                onChange={(event) => setModelConfig((prev) => ({ ...prev, provider: event.target.value }))}
              >
                <option value="echo">echo</option>
                <option value="openai_compat">openai_compat</option>
              </select>
            </label>
            <label>
              Model
              <input
                value={modelConfig.model}
                onChange={(event) => setModelConfig((prev) => ({ ...prev, model: event.target.value }))}
              />
            </label>
            <label>
              Endpoint
              <input
                value={modelConfig.endpoint}
                onChange={(event) => setModelConfig((prev) => ({ ...prev, endpoint: event.target.value }))}
              />
            </label>
            <label>
              API Key Env
              <input
                value={modelConfig.api_key_env}
                onChange={(event) => setModelConfig((prev) => ({ ...prev, api_key_env: event.target.value }))}
              />
            </label>
            <label>
              Timeout(s)
              <input
                type="number"
                min="1"
                value={modelConfig.timeout_seconds}
                onChange={(event) => setModelConfig((prev) => ({ ...prev, timeout_seconds: event.target.value }))}
              />
            </label>
            <label>
              Max Context Tokens
              <input
                type="number"
                min="500"
                value={modelConfig.max_context_tokens}
                onChange={(event) => setModelConfig((prev) => ({ ...prev, max_context_tokens: event.target.value }))}
              />
            </label>
          </div>
        </section>

        {tab === "scan" && (
          <section className="card">
            <div className="row-actions">
              <button onClick={runScan} disabled={loading}>{loading ? "扫描中..." : "运行扫描"}</button>
              <button onClick={() => setSelectedPaths(documents.map((item) => item.path))} disabled={documents.length === 0}>
                全选
              </button>
              <button onClick={() => setSelectedPaths([])} disabled={documents.length === 0}>
                清空
              </button>
              <span className="selected-meta">已选择 {selectedPaths.length} 个文件（共 {documents.length} 个）</span>
            </div>
            <div className="doc-list">
              {documents.map((item) => (
                <label className="doc-item" key={item.doc_id}>
                  <input
                    type="checkbox"
                    checked={selectedPaths.includes(item.path)}
                    onChange={() => togglePath(item.path)}
                  />
                  <span className="doc-main">
                    <span className="doc-path">{item.path}</span>
                    <span className="doc-extra">{(item.file_type || "other").toUpperCase()} · {formatBytes(item.size)}</span>
                  </span>
                </label>
              ))}
              {documents.length === 0 && <p className="muted">暂无扫描结果。</p>}
            </div>
          </section>
        )}

        {tab === "review" && (
          <section className="card">
            <p className="muted">当前使用已勾选文件进行复盘。</p>
            <button onClick={runReview} disabled={loading}>{loading ? "运行中..." : "运行 Review"}</button>
          </section>
        )}

        {tab === "quiz" && (
          <>
            <section className="card">
              <h3>Chat</h3>
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Ask a question..."
              />
              <button onClick={sendChat} disabled={loading || !message.trim()}>
                {loading ? "发送中..." : "发送"}
              </button>
            </section>
            <section className="card">
              <h3>Quiz</h3>
              <button onClick={genQuiz} disabled={loading}>{loading ? "生成中..." : "生成测验"}</button>
              {quizItems.map((item, index) => (
                <div className="quiz-item" key={`${index}-${item.question}`}>
                  <p>{item.question}</p>
                  <textarea
                    value={quizAnswers[index] || ""}
                    onChange={(event) => {
                      const next = [...quizAnswers];
                      next[index] = event.target.value;
                      setQuizAnswers(next);
                    }}
                    placeholder="你的答案"
                  />
                </div>
              ))}
              {quizItems.length > 0 && (
                <button onClick={evalQuiz} disabled={loading || !quizTraceId}>提交点评</button>
              )}
            </section>
          </>
        )}

        {error && <section className="card error">{error}</section>}
        {warnings.length > 0 && (
          <section className="card warning">
            <h3>解析提示</h3>
            <ul className="warning-list">
              {warnings.map((item, index) => (
                <li key={`${index}-${item}`}>{item}</li>
              ))}
            </ul>
          </section>
        )}
        <section className="card">
          <h3>Result</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </section>
      </main>
    </div>
  );
}
