import {
  ArrowUp,
  CaretDown,
  CheckCircle,
  ChatsCircle,
  ClockCounterClockwise,
  GearSix,
  List,
  LockKey,
  Plus,
  Pulse,
  QrCode,
  Scroll,
  ShieldCheck,
  SidebarSimple,
  SignOut,
  Sparkle,
  SpinnerGap,
  Stop,
  User,
  WechatLogo,
  WifiHigh,
  X,
} from "@phosphor-icons/react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { createRoot } from "react-dom/client";
import QRCode from "qrcode";

import "./styles.css";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:6500";

type Role = "system" | "user" | "assistant" | "tool";
type ToolPanel = "wechat" | "status" | "logs";

interface Message {
  id: number;
  role: Role;
  content: string;
  created_at: string;
}

interface Conversation {
  id: string;
  source: string;
  created_at: string;
  updated_at: string;
}

interface WechatStatus {
  login_status: string;
  polling: boolean;
  qr_url: string;
  last_error: string;
  received_count: number;
  sent_count: number;
  has_token: boolean;
}

interface AppStatus {
  config: {
    channel: string;
    model: { provider: string; model: string; base_url: string };
    web: { host: string; port: number };
    agent: { max_context_turns: number; max_steps: number; tool_allowlist: string[] };
    wechat: { base_url: string; credentials_path: string; text_only: boolean };
    storage: { sqlite_path: string };
  };
  wechat: WechatStatus;
}

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, token: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail || `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

function conversationLabel(conversation: Conversation, index: number): string {
  if (conversation.id === "web:default") return "默认对话";
  return `对话 ${String(index + 1).padStart(2, "0")}`;
}

function shortTime(value: string): string {
  const match = value.match(/\d{2}:\d{2}/);
  return match?.[0] || "刚刚";
}

function LoginScreen({ onLogin }: { onLogin: (password: string) => Promise<void> }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!password.trim() || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      await onLogin(password);
    } catch {
      setError("密码不正确，请重新输入");
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="brand-mark brand-mark-large" aria-hidden="true">
          <Sparkle weight="fill" />
        </div>
        <p className="eyebrow">PRIVATE WECHAT AGENT</p>
        <h1 id="login-title">欢迎回来</h1>
        <p className="login-copy">登录你的本地私人助手控制台</p>
        <form onSubmit={submit}>
          <label htmlFor="password">控制台密码</label>
          <div className="input-with-icon">
            <LockKey aria-hidden="true" />
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="输入 WEB_PASSWORD"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoFocus
            />
          </div>
          {error && <p className="form-error">{error}</p>}
          <button className="primary-button login-button" type="submit" disabled={!password.trim() || submitting}>
            {submitting ? <SpinnerGap className="spin" aria-hidden="true" /> : <ShieldCheck aria-hidden="true" />}
            {submitting ? "正在验证" : "安全登录"}
          </button>
        </form>
        <div className="local-note">
          <WifiHigh aria-hidden="true" />
          <span>仅连接本机 127.0.0.1</span>
        </div>
      </section>
    </main>
  );
}

function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState(localStorage.getItem("conversation") || "web:default");
  const [messages, setMessages] = useState<Message[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(Boolean(token));
  const [sending, setSending] = useState(false);
  const [activePanel, setActivePanel] = useState<ToolPanel | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [qrValue, setQrValue] = useState("");
  const [qrImage, setQrImage] = useState("");
  const [qrPhase, setQrPhase] = useState("");
  const [wechatBusy, setWechatBusy] = useState(false);
  const threadEndRef = useRef<HTMLDivElement>(null);

  const webConversations = useMemo(
    () => conversations.filter((conversation) => conversation.source === "web" || conversation.id.startsWith("web:")),
    [conversations],
  );

  const wechat = status?.wechat;
  const currentConversation = webConversations.find((conversation) => conversation.id === activeConversation);
  const currentConversationIndex = Math.max(
    0,
    webConversations.findIndex((conversation) => conversation.id === activeConversation),
  );
  const currentTitle = currentConversation
    ? conversationLabel(currentConversation, currentConversationIndex)
    : "新对话";

  function logout(messageText = "") {
    localStorage.removeItem("token");
    setToken("");
    setStatus(null);
    setMessages([]);
    setError(messageText);
  }

  async function login(password: string) {
    const response = await fetch(`${API}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!response.ok) throw new Error("invalid password");
    const data = (await response.json()) as { token: string };
    localStorage.setItem("token", data.token);
    setToken(data.token);
    setLoading(true);
  }

  async function refreshAll(showLoading = false) {
    if (!token) return;
    if (showLoading) setLoading(true);
    try {
      const [nextStatus, nextConversations, nextMessages, nextLogs] = await Promise.all([
        request<AppStatus>("/api/status", token),
        request<Conversation[]>("/api/conversations", token),
        request<Message[]>(`/api/messages?conversation_id=${encodeURIComponent(activeConversation)}`, token),
        request<{ lines: string[] }>("/api/logs", token),
      ]);
      setStatus(nextStatus);
      setConversations(nextConversations);
      setMessages(nextMessages);
      setLogs(nextLogs.lines || []);
      setError("");
    } catch (nextError) {
      if (nextError instanceof ApiError && nextError.status === 401) {
        logout("登录状态已过期，请重新登录");
      } else {
        setError(nextError instanceof Error ? nextError.message : "刷新状态失败");
      }
    } finally {
      setLoading(false);
    }
  }

  async function loadConversation(conversationId: string) {
    setActiveConversation(conversationId);
    localStorage.setItem("conversation", conversationId);
    setSidebarOpen(false);
    setLoading(true);
    try {
      const nextMessages = await request<Message[]>(
        `/api/messages?conversation_id=${encodeURIComponent(conversationId)}`,
        token,
      );
      setMessages(nextMessages);
      setError("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "加载对话失败");
    } finally {
      setLoading(false);
    }
  }

  function startNewConversation() {
    const conversationId = `web:${crypto.randomUUID()}`;
    setActiveConversation(conversationId);
    localStorage.setItem("conversation", conversationId);
    setMessages([]);
    setMessage("");
    setActivePanel(null);
    setSidebarOpen(false);
  }

  async function sendChat() {
    const content = message.trim();
    if (!content || sending) return;
    setSending(true);
    setError("");
    setMessage("");
    setMessages((current) => [
      ...current,
      { id: Date.now(), role: "user", content, created_at: new Date().toISOString() },
    ]);
    try {
      await request<{ conversation_id: string; reply: string }>("/api/chat", token, {
        method: "POST",
        body: JSON.stringify({ conversation_id: activeConversation, message: content }),
      });
      await refreshAll();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "消息发送失败");
      setMessage(content);
      await refreshAll();
    } finally {
      setSending(false);
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendChat();
    }
  }

  async function requestWechatQr() {
    setWechatBusy(true);
    setError("");
    try {
      const result = await request<{ status: string; qr_url: string }>("/api/wechat/qr", token, {
        method: "POST",
        body: "{}",
      });
      setQrValue(result.qr_url);
      setQrPhase(result.status);
      setStatus((current) =>
        current ? { ...current, wechat: { ...current.wechat, login_status: result.status, qr_url: result.qr_url } } : current,
      );
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "获取二维码失败");
    } finally {
      setWechatBusy(false);
    }
  }

  async function wechatAction(path: "/api/wechat/start" | "/api/wechat/stop") {
    setWechatBusy(true);
    setError("");
    try {
      const result = await request<WechatStatus>(path, token, { method: "POST", body: "{}" });
      setStatus((current) => (current ? { ...current, wechat: result } : current));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "微信操作失败");
    } finally {
      setWechatBusy(false);
    }
  }

  function openPanel(panel: ToolPanel) {
    setActivePanel((current) => (current === panel ? null : panel));
    setSidebarOpen(false);
  }

  useEffect(() => {
    if (!token) return;
    void refreshAll(true);
    const id = window.setInterval(() => void refreshAll(), 5000);
    return () => window.clearInterval(id);
  }, [token, activeConversation]);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  useEffect(() => {
    if (!qrValue) {
      setQrImage("");
      return;
    }
    let cancelled = false;
    void QRCode.toDataURL(qrValue, {
      width: 280,
      margin: 2,
      errorCorrectionLevel: "M",
      color: { dark: "#16181d", light: "#ffffff" },
    }).then((value) => {
      if (!cancelled) setQrImage(value);
    });
    return () => {
      cancelled = true;
    };
  }, [qrValue]);

  useEffect(() => {
    if (!token || !qrValue || !["waiting_scan", "scanned"].includes(qrPhase)) return;
    let cancelled = false;
    let inFlight = false;
    const poll = async () => {
      if (inFlight || cancelled) return;
      inFlight = true;
      try {
        const result = await request<{ status: string; has_token: boolean }>("/api/wechat/qr/poll", token, {
          method: "POST",
          body: "{}",
        });
        if (cancelled) return;
        setQrPhase(result.status);
        setStatus((current) =>
          current
            ? {
                ...current,
                wechat: { ...current.wechat, login_status: result.status, has_token: result.has_token },
              }
            : current,
        );
        if (result.status === "logged_in") {
          setQrValue("");
          setQrImage("");
          await refreshAll();
        }
      } catch (nextError) {
        if (!cancelled) setError(nextError instanceof Error ? nextError.message : "扫码状态更新失败");
      } finally {
        inFlight = false;
      }
    };
    void poll();
    const id = window.setInterval(() => void poll(), 1800);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [token, qrValue, qrPhase]);

  if (!token) return <LoginScreen onLogin={login} />;

  return (
    <div className="app-shell">
      {sidebarOpen && <button className="mobile-scrim" aria-label="关闭导航" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-mark" aria-hidden="true">
            <Sparkle weight="fill" />
          </div>
          <span>微伴 Agent</span>
          <button className="icon-button sidebar-close" aria-label="收起导航" onClick={() => setSidebarOpen(false)}>
            <SidebarSimple aria-hidden="true" />
          </button>
        </div>

        <button className="new-chat-button" onClick={startNewConversation}>
          <Plus aria-hidden="true" />
          <span>发起新对话</span>
        </button>

        <nav className="primary-nav" aria-label="主要导航">
          <button className={!activePanel ? "nav-item active" : "nav-item"} onClick={() => setActivePanel(null)}>
            <ChatsCircle aria-hidden="true" />
            <span>对话</span>
          </button>
          <button className={activePanel === "wechat" ? "nav-item active" : "nav-item"} onClick={() => openPanel("wechat")}>
            <WechatLogo aria-hidden="true" />
            <span>微信接入</span>
            <span className={`nav-status ${wechat?.polling ? "online" : wechat?.has_token ? "ready" : ""}`} />
          </button>
          <button className={activePanel === "status" ? "nav-item active" : "nav-item"} onClick={() => openPanel("status")}>
            <Pulse aria-hidden="true" />
            <span>运行状态</span>
          </button>
          <button className={activePanel === "logs" ? "nav-item active" : "nav-item"} onClick={() => openPanel("logs")}>
            <Scroll aria-hidden="true" />
            <span>运行日志</span>
          </button>
        </nav>

        <div className="conversation-section">
          <div className="section-label">
            <span>最近对话</span>
            <ClockCounterClockwise aria-hidden="true" />
          </div>
          <div className="conversation-list">
            {webConversations.length === 0 && <p className="empty-list">发送第一条消息后会显示在这里</p>}
            {webConversations.slice(0, 8).map((conversation, index) => (
              <button
                key={conversation.id}
                className={conversation.id === activeConversation ? "conversation-item selected" : "conversation-item"}
                onClick={() => void loadConversation(conversation.id)}
              >
                <span>{conversationLabel(conversation, index)}</span>
                <small>{shortTime(conversation.updated_at)}</small>
              </button>
            ))}
          </div>
        </div>

        <div className="sidebar-footer">
          <div className="local-avatar" aria-hidden="true"><User weight="bold" /></div>
          <div>
            <strong>本机私有运行</strong>
            <span>数据保存在本地</span>
          </div>
          <button className="icon-button" aria-label="打开运行状态" onClick={() => openPanel("status")}>
            <GearSix aria-hidden="true" />
          </button>
        </div>
      </aside>

      <main className="main-column">
        <header className="topbar">
          <div className="topbar-title">
            <button className="icon-button mobile-menu" aria-label="打开导航" onClick={() => setSidebarOpen(true)}>
              <List aria-hidden="true" />
            </button>
            <div>
              <strong>{currentTitle}</strong>
              <span>{sending ? "正在思考" : "DeepSeek 已就绪"}</span>
            </div>
          </div>
          <div className="topbar-actions">
            <button className="status-pill" onClick={() => openPanel("wechat")}>
              <span className={`status-dot ${wechat?.polling ? "online" : wechat?.has_token ? "ready" : ""}`} />
              {wechat?.polling ? "微信在线" : wechat?.has_token ? "微信已登录" : "微信未连接"}
            </button>
            <button className="icon-button" aria-label="退出登录" title="退出登录" onClick={() => logout()}>
              <SignOut aria-hidden="true" />
            </button>
          </div>
        </header>

        <section className={messages.length ? "chat-stage has-messages" : "chat-stage"}>
          {loading && messages.length === 0 ? (
            <div className="center-state">
              <SpinnerGap className="spin loading-mark" aria-hidden="true" />
              <p>正在载入你的私人空间</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="welcome-state">
              <div className="welcome-mark" aria-hidden="true">
                <Sparkle weight="fill" />
              </div>
              <p className="welcome-kicker">你的本地私人助手</p>
              <h1>今天需要我为你做些什么？</h1>
              <div className="prompt-suggestions" aria-label="快捷提示">
                <button onClick={() => setMessage("帮我整理一下今天最重要的三件事")}>整理今日重点</button>
                <button onClick={() => setMessage("帮我把这段想法整理成清晰的行动计划")}>生成行动计划</button>
                <button onClick={() => openPanel("wechat")}>检查微信连接</button>
              </div>
            </div>
          ) : (
            <div className="message-thread" aria-live="polite">
              {messages
                .filter((item) => item.role === "user" || item.role === "assistant")
                .map((item) => (
                  <article key={item.id} className={`message-row ${item.role}`}>
                    <div className="message-avatar" aria-hidden="true">
                      {item.role === "assistant" ? <Sparkle weight="fill" /> : <User weight="bold" />}
                    </div>
                    <div className="message-body">
                      <div className="message-meta">
                        <strong>{item.role === "assistant" ? "微伴 Agent" : "你"}</strong>
                        <time>{shortTime(item.created_at)}</time>
                      </div>
                      <p>{item.content}</p>
                    </div>
                  </article>
                ))}
              {sending && (
                <article className="message-row assistant thinking-row">
                  <div className="message-avatar" aria-hidden="true">
                    <Sparkle weight="fill" />
                  </div>
                  <div className="thinking-indicator" aria-label="助手正在思考">
                    <span />
                    <span />
                    <span />
                  </div>
                </article>
              )}
              <div ref={threadEndRef} />
            </div>
          )}

          <div className="composer-wrap">
            <div className="composer">
              <button className="composer-plus" aria-label="打开微信工具" title="微信工具" onClick={() => openPanel("wechat")}>
                <Plus aria-hidden="true" />
              </button>
              <textarea
                rows={1}
                value={message}
                placeholder="问问你的私人助手"
                aria-label="聊天消息"
                onChange={(event) => setMessage(event.target.value)}
                onKeyDown={handleComposerKeyDown}
              />
              <div className="composer-model" title="当前模型">
                <span>{status?.config.model.model || "DeepSeek"}</span>
                <CaretDown aria-hidden="true" />
              </div>
              <button className="send-button" aria-label="发送消息" onClick={() => void sendChat()} disabled={!message.trim() || sending}>
                {sending ? <SpinnerGap className="spin" aria-hidden="true" /> : <ArrowUp weight="bold" aria-hidden="true" />}
              </button>
            </div>
            <p className="composer-note">AI 可能会犯错，请核对重要信息。本地数据不会提交到仓库。</p>
          </div>
        </section>
      </main>

      {activePanel && (
        <aside className="utility-panel" aria-label="控制台工具">
          <div className="panel-header">
            <div>
              <p className="eyebrow">CONTROL CENTER</p>
              <h2>{activePanel === "wechat" ? "微信接入" : activePanel === "status" ? "运行状态" : "运行日志"}</h2>
            </div>
            <button className="icon-button" aria-label="关闭面板" onClick={() => setActivePanel(null)}>
              <X aria-hidden="true" />
            </button>
          </div>

          {activePanel === "wechat" && (
            <div className="panel-content">
              <div className={`connection-banner ${wechat?.polling ? "connected" : wechat?.has_token ? "ready" : ""}`}>
                <div className="connection-icon" aria-hidden="true">
                  {wechat?.polling ? <CheckCircle weight="fill" /> : <WechatLogo weight="fill" />}
                </div>
                <div>
                  <strong>{wechat?.polling ? "微信消息已接通" : wechat?.has_token ? "微信已登录" : "等待微信连接"}</strong>
                  <span>
                    {wechat?.polling
                      ? "Agent 正在接收并回复文本消息"
                      : wechat?.has_token
                        ? "启动轮询后即可自动回复"
                        : "扫码后凭证只保存在本机"}
                  </span>
                </div>
              </div>

              <div className="metric-grid">
                <div><span>已接收</span><strong>{wechat?.received_count ?? 0}</strong></div>
                <div><span>已回复</span><strong>{wechat?.sent_count ?? 0}</strong></div>
              </div>

              {!wechat?.has_token && (
                <div className="qr-section">
                  {qrImage ? (
                    <>
                      <div className="qr-frame"><img src={qrImage} alt="微信登录二维码" /></div>
                      <div className="scan-status">
                        <span className="scan-pulse" />
                        {qrPhase === "scanned" ? "已扫码，请在手机上确认" : "正在等待微信扫码"}
                      </div>
                    </>
                  ) : (
                    <div className="qr-empty">
                      <QrCode aria-hidden="true" />
                      <strong>连接你的个人微信</strong>
                      <span>二维码约两分钟有效</span>
                    </div>
                  )}
                  <button className="primary-button" onClick={() => void requestWechatQr()} disabled={wechatBusy}>
                    {wechatBusy ? <SpinnerGap className="spin" aria-hidden="true" /> : <QrCode aria-hidden="true" />}
                    {qrImage ? "刷新二维码" : "获取登录二维码"}
                  </button>
                </div>
              )}

              {wechat?.has_token && (
                <div className="wechat-actions">
                  {wechat.polling ? (
                    <button className="secondary-button danger" onClick={() => void wechatAction("/api/wechat/stop")} disabled={wechatBusy}>
                      <Stop weight="fill" aria-hidden="true" />
                      停止微信轮询
                    </button>
                  ) : (
                    <button className="primary-button" onClick={() => void wechatAction("/api/wechat/start")} disabled={wechatBusy}>
                      <WifiHigh aria-hidden="true" />
                      启动微信轮询
                    </button>
                  )}
                </div>
              )}

              {wechat?.last_error && <p className="panel-error">{wechat.last_error}</p>}
              <div className="privacy-note">
                <ShieldCheck aria-hidden="true" />
                <p><strong>隐私保护</strong><span>Token、context token 和消息数据库均保存在 runtime 目录，并由 Git 忽略。</span></p>
              </div>
            </div>
          )}

          {activePanel === "status" && (
            <div className="panel-content">
              <div className="status-overview">
                <div className="status-overview-icon"><Pulse aria-hidden="true" /></div>
                <div><strong>服务运行正常</strong><span>前后端与本地存储均已连接</span></div>
              </div>
              <div className="detail-list">
                <div><span>模型</span><strong>{status?.config.model.model || "—"}</strong></div>
                <div><span>服务地址</span><strong>{status ? `${status.config.web.host}:${status.config.web.port}` : "—"}</strong></div>
                <div><span>消息渠道</span><strong>{status?.config.channel || "—"}</strong></div>
                <div><span>上下文轮次</span><strong>{status?.config.agent.max_context_turns ?? "—"}</strong></div>
                <div><span>外部工具</span><strong>{status?.config.agent.tool_allowlist.length ? "已启用" : "未启用"}</strong></div>
              </div>
              <button className="secondary-button" onClick={() => void refreshAll(true)}>
                <ClockCounterClockwise aria-hidden="true" />
                刷新运行状态
              </button>
            </div>
          )}

          {activePanel === "logs" && (
            <div className="panel-content logs-panel">
              <div className="logs-toolbar">
                <span><span className="status-dot online" /> 实时更新</span>
                <button onClick={() => void refreshAll()}><ClockCounterClockwise aria-hidden="true" />刷新</button>
              </div>
              <pre className="logs-view">{logs.length ? logs.join("\n") : "暂无运行日志"}</pre>
            </div>
          )}
        </aside>
      )}

      {error && (
        <div className="toast" role="alert">
          <X aria-hidden="true" />
          <span>{error}</span>
          <button aria-label="关闭错误提示" onClick={() => setError("")}><X aria-hidden="true" /></button>
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
