# Railway 部署指南

## 一、部署到 Railway

1. 打开 https://railway.app → New Project → Deploy from GitHub repo
2. 选择 `all-in-one-gateway` 仓库
3. Railway 会自动识别 requirements.txt 并启动

## 二、配置环境变量

在 Railway 的 Variables 里添加（全部必填）：

| 变量 | 说明 |
|------|------|
| `AUTH_TOKEN` | 查岗上报密码，iPhone快捷指令用 |
| `TARGET_API_URL` | 上游LLM地址，形如 `https://api.deepseek.com/v1/chat/completions` |
| `TARGET_API_KEY` | 上游LLM的API Key |
| `MODEL_NAME` | 模型名，如 `deepseek-chat` |
| `BARK_KEY` | Bark推送Key |
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

## 三、部署后拿到的地址

- 服务域名：`https://你的项目名.up.railway.app`
- Kelivo gateway：`https://你的项目名.up.railway.app/v1/chat/completions`
- MCP端点：`https://你的项目名.up.railway.app/mcp`
- 查岗上报：`https://你的项目名.up.railway.app/report`
- 手动唤醒测试：`POST /wake/run`

## 四、配置 Kelivo

1. Kelivo 的 gateway 地址填：`https://你的项目名.up.railway.app/v1/chat/completions`
2. API Key 填 `GATEWAY_API_KEY`（如果开了公网鉴权）
3. MCP 工具 URL 填：`https://你的项目名.up.railway.app/mcp`

## 五、配置 iPhone 快捷指令

把原来查岗的 `/report` 地址改成新域名：
```
https://你的项目名.up.railway.app/report
```
Authorization 头改成 `Bearer 你的AUTH_TOKEN`

## 六、验证

1. `GET /health` → `{"status":"ok"}`
2. `POST /wake/run` → 手动触发一次唤醒，看是否查岗+推送
3. `GET /activity/summary` → 看查岗数据
