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
- 无 Key 的本地点别名与高德 URI 导航链接；
- 无 Key 的 Open-Meteo 实时天气和短期预报；
- 日志脱敏；
- 单元测试。

暂未启用：

- 高德 Web 服务查询（天气、POI、地理编码与路线详情需要 Key）；
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

## 地点别名与导航

复制 `profile.local.example.json` 为 `profile.local.json`，再填入你自己的地点名称和经纬度。该文件已被 Git 忽略，不能提交。

在登录后的控制台会话中，可调用受鉴权保护的 `POST /api/maps/navigation`：`destination` 和可选的 `origin` 必须是已保存的地点别名。接口只生成确定性的高德导航 URL，不查询外部服务，也不需要 Key。省略 `origin` 时，移动端高德可使用设备当前位置。

`GET /api/maps/status` 可查看本地地点配置和地图能力状态。未填写 `AMAP_MAPS_API_KEY` 时，POI、地址解析和路线详情保持禁用，系统不会猜测地点或请求第三方服务。

拿到高德 Web 服务 Key 后，只在本机 `.env` 中填写 `AMAP_MAPS_API_KEY`；不要提交该值。

## 天气查询（无需高德 Key）

发送明确城市的天气问题，例如“上海明天天气怎么样”，Agent 会调用 Open-Meteo 的公开地理编码和预报服务，回复数据时间和来源。也可在登录后调用 `GET /api/weather?location=上海&day_offset=0`。

天气服务开关位于 `config.json` 的 `agent.weather_enabled`，默认启用。天气查询需要网络连接；地点不明确、无法找到地点或服务临时失败时，Agent 会说明原因而不会猜测结果。

## macOS 常驻运行

项目提供当前 macOS 用户范围的 LaunchAgent 模板。它只启动后端并绑定 `127.0.0.1:6500`；已有微信凭证时，后端启动后会自动恢复微信轮询。前端如需由后端提供，请先执行一次 `cd frontend && npm run build`。

确认 `.env`、`.venv` 和 `config.json` 都已准备完成后，显式执行：

```bash
scripts/launchd-agent.sh install
```

查看状态或移除常驻服务：

```bash
scripts/launchd-agent.sh status
scripts/launchd-agent.sh uninstall
```

生成的 plist 位于 `~/Library/LaunchAgents/`，运行日志位于 `runtime/logs/launchd.stdout.log` 与 `runtime/logs/launchd.stderr.log`。安装脚本不会把环境变量或密钥写入 plist，凭证和运行时数据也不会在卸载时删除。

## Docker 与云端部署

Docker 镜像固定使用 Python 3.12.13、Node 22.23.1 和 `requirements.lock` 中锁定的运行依赖；前端在构建阶段编译，最终镜像以非 root 用户运行。`.dockerignore` 会排除 `.env`、`config.json`、本机 `runtime/` 和 `profile.local.json`，因此它们不会进入镜像层。

本机容器运行前，先准备本地 `.env` 和 `config.json`：

```bash
docker compose build
docker compose up -d
docker compose ps
```

Compose 只发布 `127.0.0.1:6500`，并将容器的运行数据保存到命名卷 `wechat-assistant-runtime`。不要以端口映射、反向代理或防火墙规则把该服务直接公开到互联网。

云端应使用全新仓库副本和一个空的 `wechat-assistant-runtime` 卷，然后在云端控制台重新扫码登录。绝不能复制、上传或挂载本机 `runtime/wechat_credentials.json`。需要从本机访问云端实例时，使用 SSH 隧道：

```bash
ssh -L 6500:127.0.0.1:6500 your-user@your-server
```

Docker 可用时，运行以下命令完成 Compose 配置、镜像构建和基础启动校验：

```bash
make docker-verify
```

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
