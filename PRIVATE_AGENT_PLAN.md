# 自研微信私人 Agent 分阶段计划

## Phase 0：新仓库初始化

- 建立 Python 后端、React 前端、测试目录。
- 使用 `config.example.json` 和 `.env.example` 提供配置模板。
- `.gitignore` 禁止提交 `.env`、`config.json`、`runtime/`、SQLite、微信凭证和日志。
- 提供 `make backend-dev`、`make frontend-dev`、`make test`、`make lint`。

## Phase 1：DeepSeek 聊天内核

- `config.json` 读非密配置，`.env` 读密钥。
- DeepSeek 使用 OpenAI-compatible `/chat/completions`。
- LangGraph 实现最小聊天状态机。
- SQLite 保存 conversations、messages、agent_runs。
- 控制台提供 Web 聊天测试。

## Phase 2：微信 iLink 接入

- 实现二维码获取、扫码状态轮询、token 保存。
- 实现 getUpdates 长轮询。
- 实现 sendMessage 文本回复。
- 保存 context_token，重启后可恢复。
- 媒体消息首版不处理。

## Phase 3：安全边界和控制台

- 控制台密码登录。
- Web 绑定 `127.0.0.1`。
- 工具注册层和执行层双重 allowlist。
- 日志脱敏。
- 状态页显示微信、Agent、最近消息和日志。

## Phase 4：高德地图工具

- 天气、地点搜索、地址解析、路线规划。
- 增加 `profile.local.json` 管理“家”“公司”等别名。
- 导航链接由确定性代码生成。
- 地点不明确必须追问。

## Phase 5：macOS 常驻

- [x] 增加 `launchd` plist 模板和显式安装/卸载脚本。
- [x] 日志进入 `runtime/logs/`。
- [x] 凭证恢复后自动启动微信轮询；轮询断网后继续重试。

## Phase 6：Docker 与云端

- [x] 构建固定版本 Docker 镜像。
- [x] `runtime/` 使用独立命名卷持久化。
- [x] Compose 默认只绑定 `127.0.0.1`，不直接暴露公网。
- [x] 云端部署文档要求重新扫码，不复制本机微信凭证。
