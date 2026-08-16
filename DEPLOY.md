# Railway 部署指南

## 架构

两个服务：
1. **all-in-one-gateway**（本仓库，Python FastAPI，Railway）— 查岗 + Kelivo gateway + 自动唤醒 + 欲望账本 + 念头池入口 + 远程遥控 + MCP
2. **xinchao-dynamic-mind**（Node.js，独立运行）— 心潮动态状态引擎，十二维驱动力 + 念头池 + 疲惫 + 梦境

心潮通过 HTTP 对接，只当状态引擎，**不发推送**（方案B：推送统一由 all-in-one-gateway 发）。

## 一、部署 all-in-one-gateway 到 Railway

1. 打开 https://railway.app → New Project → Deploy from GitHub repo
2. 选择 `all-in-one-gateway` 仓库
3. Railway 自动识别 requirements.txt 并启动

## 二、配置环境变量（all-in-one-gateway）

必填：
| 变量 | 说明 |
|------|------|
| `AUTH_TOKEN` | 查岗上报密码，iPhone快捷指令用 |
| `TARGET_API_URL` | 上游LLM地址，形如 `https://api.deepseek.com/v1/chat/completions` |
| `TARGET_API_KEY` | 上游LLM的API Key |
| `MODEL_NAME` | 模型名，如 `deepseek-chat` |
| `BARK_KEY` | Bark推送Key |
| `XINCHAO_URL` | 心潮服务地址，形如 `https://你的心潮域名` |
| `XINCHAO_TOKEN` | 心潮的 SERVICE_TOKEN |
| `GATEWAY_API_KEY` | 公网访问/v1的鉴权key（可选） |
| `GH_TOKEN` | GitHub token（欲望账本远端用，可后配） |
| `GH_REPO` | 形如 `eixixi/desires`（欲望账本远端仓库） |
| `TIME_ZONE` | 时区，默认 `Asia/Shanghai` |

可选：
| 变量 | 说明 |
|------|------|
| `CUSTOM_ICON_URL` | Bark推送图标 |
| `MAIL_USER` | 163邮箱账号（远程遥控用） |
| `MAIL_AUTH_CODE` | 163邮箱SMTP授权码 |
| `MAIL_TO` | 收件邮箱（通常是自己的iPhone邮箱） |

## 三、部署心潮（xinchao-dynamic-mind）

心潮是 Node.js 服务，也放 Railway（或你自己的VPS）。

心潮 `.env` 关键配置（方案B）：
```env
PORT=18110
SERVICE_TOKEN=至少32位的随机密钥
SHADOW_MODE=true          # 纯状态机，不调模型
BARK_ENABLED=false        # 关键：关掉心潮自己的推送，统一走all-in-one-gateway
MODEL_ENABLED=false       # 不需要心潮生成梦境/思念
MCP_ENABLED=false         # 不需要心潮的MCP
CONTEXT_ENVELOPE_ENABLED=true
```

心潮部署后，把它的公网地址填到 all-in-one-gateway 的 `XINCHAO_URL`，`XINCHAO_TOKEN` 填心潮的 `SERVICE_TOKEN`。

## 四、部署后拿到的地址

- all-in-one-gateway 域名：`https://你的项目名.up.railway.app`
- Kelivo gateway：`https://你的项目名.up.railway.app/v1/chat/completions`
- MCP端点：`https://你的项目名.up.railway.app/mcp`
- 查岗上报：`https://你的项目名.up.railway.app/report`
- 手动唤醒测试：`POST /wake/run`

## 五、配置 Kelivo

1. Kelivo 的 gateway 地址填：`https://你的项目名.up.railway.app/v1/chat/completions`
2. API Key 填 `GATEWAY_API_KEY`（如果开了公网鉴权）
3. MCP 工具 URL 填：`https://你的项目名.up.railway.app/mcp`

## 六、配置 iPhone 快捷指令

把原来查岗的 `/report` 地址改成新域名：
```
https://你的项目名.up.railway.app/report
```
Authorization 头改成 `Bearer 你的AUTH_TOKEN`

## 七、验证

1. `GET /health` → `{"status":"ok"}`
2. 确认心潮通：调 `GET {心潮域名}/health`，看 all-in-one-gateway 日志无 XINCHAO 连接错误
3. `POST /wake/run` → 手动触发一次唤醒，看是否查岗+心潮状态+推送
4. `GET /activity/summary` → 看查岗数据

## 八、唤醒闭环

```
定时唤醒 → 查岗(SQLite) + 调心潮/v1/intent拿十二维状态 → 注入prompt → 调LLM决定 → Bark推送 → 写回时间线(Kelivo记得) + 调心潮记互动(降驱动力)
```
