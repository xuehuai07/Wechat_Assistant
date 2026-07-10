import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = "http://127.0.0.1:6500";

async function request(path: string, token: string, options: RequestInit = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState("");

  async function login() {
    setError("");
    const response = await fetch(`${API}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      setError("登录失败");
      return;
    }
    const data = await response.json();
    localStorage.setItem("token", data.token);
    setToken(data.token);
  }

  async function refresh() {
    if (!token) return;
    try {
      setStatus(await request("/api/status", token));
      const logData = await request("/api/logs", token);
      setLogs(logData.lines || []);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function sendChat() {
    setError("");
    const data = await request("/api/chat", token, {
      method: "POST",
      body: JSON.stringify({ conversation_id: "web:default", message }),
    });
    setReply(data.reply);
    setMessage("");
    await refresh();
  }

  async function post(path: string) {
    setError("");
    const data = await request(path, token, { method: "POST", body: "{}" });
    setStatus({ ...(status || {}), wechat: data });
  }

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 5000);
    return () => window.clearInterval(id);
  }, [token]);

  if (!token) {
    return (
      <main className="shell narrow">
        <h1>私人微信 Agent 控制台</h1>
        <input type="password" placeholder="WEB_PASSWORD" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button onClick={login}>登录</button>
        {error && <p className="error">{error}</p>}
      </main>
    );
  }

  return (
    <main className="shell">
      <header>
        <h1>私人微信 Agent 控制台</h1>
        <button onClick={() => { localStorage.removeItem("token"); setToken(""); }}>退出</button>
      </header>
      {error && <p className="error">{error}</p>}
      <section className="grid">
        <div className="card">
          <h2>运行状态</h2>
          <pre>{JSON.stringify(status?.wechat || {}, null, 2)}</pre>
          <button onClick={() => post("/api/wechat/qr")}>获取二维码</button>
          <button onClick={() => post("/api/wechat/qr/poll")}>轮询扫码状态</button>
          <button onClick={() => post("/api/wechat/start")}>启动微信轮询</button>
          <button onClick={() => post("/api/wechat/stop")}>停止微信轮询</button>
          {status?.wechat?.qr_url && <p className="mono">{status.wechat.qr_url}</p>}
        </div>
        <div className="card">
          <h2>聊天测试</h2>
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="输入一条测试消息" />
          <button onClick={sendChat} disabled={!message.trim()}>发送</button>
          {reply && <p className="reply">{reply}</p>}
        </div>
      </section>
      <section className="card">
        <h2>最近消息</h2>
        <pre>{JSON.stringify(status?.messages || [], null, 2)}</pre>
      </section>
      <section className="card">
        <h2>日志</h2>
        <pre>{logs.join("\n")}</pre>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
