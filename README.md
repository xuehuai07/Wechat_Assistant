# 自研微信私人 Agent

这是一个从零实现的私人微信 Agent 项目。当前 CowAgent 只作为协议和产品边界参考，本仓库不继续 Fork CowAgent。

核心链路：

```text
个人微信 iLink → FastAPI 后端 → LangGraph Agent → DeepSeek → 微信/控制台回复
```

## 当前实现范围

已落地 Phase 0–3 的工程骨架：

- Python 3.12 + FastAPI 后端；
- React + TypeScript + Vite 控制台；
- JSON + `.env` 配置；
- SQLite 会话、消息、运行记录表；
- DeepSeek OpenAI-compatible Chat Completions 客户端；
- LangGraph 最小聊天状态机，缺少依赖时有顺序执行 fallback；
- iLink 微信二维码、扫码轮询、长轮询、文本回复适配层；
- Web 控制台密码登录；
- 工具 allowlist 注册层与执行层；
- 日志脱敏；
- 单元测试。

暂未启用：

- 高德地图工具；
- macOS `launchd` 常驻；
- Docker/云端部署；
- 语音、图片、文件、群聊、多用户、支付、下单、终端、浏览器、插件。

## 本机启动

```bash
scripts/bootstrap-local.sh
```

然后编辑：

```bash
.env
config.json
```

`.env` 至少填写：

```text
DEEPSEEK_API_KEY=你的 DeepSeek Key
WEB_PASSWORD=控制台密码
```

启动后端：

```bash
scripts/run-backend.sh
```

启动前端开发服务：

```bash
make frontend-dev
```

控制台默认：

```text
http://127.0.0.1:5500
```

后端默认：

```text
http://127.0.0.1:6500
```

## 微信使用流程

1. 登录控制台。
2. 点击“获取二维码”。
3. 用微信扫码。
4. 点击“轮询扫码状态”，直到状态变为 `logged_in`。
5. 点击“启动微信轮询”。
6. 给微信 Agent 发送文本消息。

微信凭证保存在：

```text
runtime/wechat_credentials.json
```

该目录被 `.gitignore` 忽略，不应提交。

## 测试

```bash
make test
make lint
```

## 安全边界

- Web 默认只监听 `127.0.0.1`。
- 首版工具白名单为空，因此模型不能调用任何外部工具。
- 工具执行层会再次校验 allowlist，防止伪造调用。
- 日志会脱敏 key、token、password、secret、context_token。
- 不支持终端、文件、浏览器、插件安装、支付、下单、打车或后台定位。
