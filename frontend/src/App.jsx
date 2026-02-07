import { useMemo, useState } from "react";

const API_BASE = "http://127.0.0.1:8008";

async function post(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

function TabButton({ active, onClick, children }) {
  return (
    <button className={`tab-btn ${active ? "active" : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}

export default function App() {
  const [tab, setTab] = useState("scan");
  const [rootDir, setRootDir] = useState(".");
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState("");
  const [quizTraceId, setQuizTraceId] = useState("");
  const [quizItems, setQuizItems] = useState([]);
  const [quizAnswers, setQuizAnswers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const title = useMemo(() => {
    if (tab === "scan") return "扫描工作区";
    if (tab === "review") return "复盘模式";
    return "问答 / 测验";
  }, [tab]);

  async function runScan() {
    setLoading(true);
    setError("");
    try {
      const data = await post("/scan", { root_dir: rootDir });
      setResult(data);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  }

  async function runReview() {
    setLoading(true);
    setError("");
    try {
      const data = await post("/review/run", { root_dir: rootDir, topic: "" });
      setResult(data);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  }

  async function sendChat() {
    setLoading(true);
    setError("");
    try {
      const data = await post("/chat/session", { root_dir: rootDir, message });
      setResult(data);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  }

  async function genQuiz() {
    setLoading(true);
    setError("");
    try {
      const data = await post("/quiz/generate", { root_dir: rootDir, count: 3 });
      setQuizTraceId(data.trace_id);
      setQuizItems(data.items || []);
      setQuizAnswers(new Array((data.items || []).length).fill(""));
      setResult(data);
    } catch (err) {
      setError(String(err.message || err));
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
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
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
          <input value={rootDir} onChange={(event) => setRootDir(event.target.value)} placeholder="Workspace root directory" />
        </header>

        {tab === "scan" && (
          <section className="card">
            <button onClick={runScan} disabled={loading}>{loading ? "Running..." : "Run Scan"}</button>
          </section>
        )}

        {tab === "review" && (
          <section className="card">
            <button onClick={runReview} disabled={loading}>{loading ? "Running..." : "Run Review"}</button>
          </section>
        )}

        {tab === "quiz" && (
          <>
            <section className="card">
              <h3>Chat</h3>
              <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ask a question..." />
              <button onClick={sendChat} disabled={loading || !message.trim()}>
                {loading ? "Sending..." : "Send"}
              </button>
            </section>
            <section className="card">
              <h3>Quiz</h3>
              <button onClick={genQuiz} disabled={loading}>{loading ? "Generating..." : "Generate Quiz"}</button>
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
                <button onClick={evalQuiz} disabled={loading || !quizTraceId}>Evaluate</button>
              )}
            </section>
          </>
        )}

        {error && <section className="card error">{error}</section>}
        <section className="card">
          <h3>Result</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </section>
      </main>
    </div>
  );
}

