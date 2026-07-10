# Codex 会话迁移交接

## 新工作区

```text
/Users/uniubi/Desktop/Work/Code/Wechat_Assistant
```

这是一个新的干净项目，用来从零实现自研微信私人 Agent。不要继续在旧的 CowAgent 改造仓库 `/Users/uniubi/Desktop/Work/Code/Assistant` 上堆代码。

## 用户目标

用户希望打造自己的微信私人 Agent，而不是继续 Fork/改 CowAgent。

已锁定技术路线：

- 后端：Python 3.12 + FastAPI
- Agent：LangGraph 为主，LangChain 只做必要适配
- 模型：DeepSeek OpenAI-compatible Chat Completions
- 微信：个人微信 iLink 扫码、长轮询、context_token 机制；参考 CowAgent 行为但代码重写
- 前端：React + TypeScript + Vite
- 存储：SQLite
- 配置：`config.json` + `.env`
- 首阶段运行：macOS 本机
- 后续阶段：高德地图、launchd 常驻、Docker、云端

## 当前已完成

已在新仓库落地 Phase 0–3 的骨架：

- 初始化 Git 仓库。
- 创建后端目录：
  - `backend/app/config.py`
  - `backend/app/db.py`
  - `backend/app/main.py`
  - `backend/app/agent/chat_agent.py`
  - `backend/app/services/deepseek.py`
  - `backend/app/wechat/ilink_client.py`
  - `backend/app/wechat/service.py`
  - `backend/app/tools/policy.py`
  - `backend/app/api/routes.py`
- 创建前端目录：
  - `frontend/src/main.tsx`
  - `frontend/src/styles.css`
  - `frontend/package.json`
  - `frontend/tsconfig.json`
- 创建配置和脚本：
  - `config.example.json`
  - `.env.example`
  - `Makefile`
  - `scripts/bootstrap-local.sh`
  - `scripts/run-backend.sh`
- 创建文档：
  - `README.md`
  - `PRIVATE_AGENT_PLAN.md`
  - `THIRD_PARTY_NOTICES.md`
- 创建测试：
  - 配置加载
  - SQLite 消息持久化
  - 敏感信息脱敏
  - 工具 allowlist
  - 微信消息解析
  - API 鉴权

## 本机依赖状态

已安装：

- Python 3.12.13
- Homebrew
- Node.js 22 via Homebrew `node@22`

已执行：

```bash
scripts/bootstrap-local.sh
```

该命令已创建：

- `.venv/`
- `frontend/node_modules/`
- `.env`
- `config.json`
- `runtime/`

这些运行时文件已被 `.gitignore` 忽略。

## 验证结果

后端测试已通过：

```bash
.venv/bin/python -m pytest -q
```

结果：

```text
9 passed, 1 warning
```

Ruff 当前未通过，都是未使用 import：

```text
backend/app/main.py: pathlib.Path imported but unused
backend/app/tools/policy.py: typing.Callable imported but unused
backend/tests/test_api.py: app.config.load_settings imported but unused
backend/tests/test_api.py: app.db.Database imported but unused
```

前端 `npm audit` 当前有 2 个 Vite/esbuild 相关漏洞：

```text
1 moderate, 1 high
```

原因是当前 `frontend/package.json` 使用 Vite 5。`npm audit` 建议升级到 Vite 8。下一步应优先评估并升级 Vite，而不是直接忽略。

## 已知问题 / 下一步必须先做

1. 修复 Ruff 未使用 import。

2. 检查并删除残留 Git lock：

```bash
rm -f .git/index.lock
```

前提是确认没有其他 git 命令正在运行。

3. 升级前端依赖以修复 audit：

```bash
cd frontend
npm install vite@latest @vitejs/plugin-react@latest typescript@latest
npm audit
npm run typecheck
```

4. 重新跑全量验证：

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check backend
cd frontend && npm run typecheck
```

5. 如果全部通过，再做第一次提交：

```bash
git add .
git commit -m "Initialize self-hosted WeChat private agent"
```

注意 `.env`、`config.json`、`runtime/`、`.venv/`、`node_modules/` 不应进入 Git。

## 继续开发建议顺序

### Step 1：收敛当前骨架质量

- 修 Ruff。
- 修 npm audit。
- 跑测试。
- 跑前端 typecheck。
- 检查 `git status --short`，确认只有源代码和文档待提交。

### Step 2：让后端真正跑起来

用户需要在 `.env` 填：

```text
DEEPSEEK_API_KEY=...
WEB_PASSWORD=...
```

然后运行：

```bash
scripts/run-backend.sh
```

打开：

```text
http://127.0.0.1:9899/healthz
```

如果只跑前端开发服务：

```bash
make frontend-dev
```

控制台：

```text
http://127.0.0.1:5173
```

### Step 3：验证 Web 聊天

- 登录控制台。
- 用“聊天测试”调用 `/api/chat`。
- 确认 DeepSeek 返回中文回复。
- 确认 SQLite 中有消息记录。
- 确认日志没有泄露 key。

### Step 4：验证微信 iLink

控制台操作顺序：

1. 获取二维码。
2. 微信扫码。
3. 轮询扫码状态直到 `logged_in`。
4. 启动微信轮询。
5. 给 Agent 发文本消息。

需要特别关注：

- `request_qr()` 中解析二维码字段是否与真实 iLink 返回一致。
- `poll_qr_once()` 中解析 token 字段是否与真实返回一致。
- `extract_text_messages()` 中消息字段是否与真实 getUpdates 返回一致。

这些字段当前是根据 CowAgent 行为做的兼容性重写，第一次真实扫码时很可能需要微调。

### Step 5：完善控制台体验

当前控制台能登录、查看状态、测试聊天、操作微信、看日志，但还是工程骨架。

建议下一步补：

- 二维码真正渲染为 QR 图片，而不是只显示 URL。
- 自动轮询扫码状态。
- 消息列表 UI。
- 配置摘要 UI。
- 错误提示分级。

### Step 6：再进入 Phase 4 高德地图

高德地图暂时不要急着做。等微信文本聊天稳定后，再加：

- `profile.local.json`
- 高德天气
- POI 搜索
- 路线规划
- 确定性导航链接生成
- 地点歧义追问规则

## 对下一个 Codex 的启动指令建议

可以直接对新工作区 Codex 说：

```text
请先阅读 SESSION_HANDOFF.md，然后继续完成当前骨架的收敛工作：
1. 修复 Ruff 未使用 import；
2. 删除无效 .git/index.lock；
3. 升级前端 Vite 依赖并修复 npm audit；
4. 运行 pytest、ruff、npm typecheck；
5. 确认 git status 中没有运行时/密钥文件；
6. 如果通过，帮我做第一次 git commit。
```
