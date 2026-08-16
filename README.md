# All-in-One Gateway

整合查岗 + 自动唤醒 + DM动态状态 + 欲望账本 + 念头池 + 远程遥控 的 Python FastAPI 单体服务，兼容 Kelivo Gateway。

## 模块
- 查岗：iPhone快捷指令上报 / 使用时长统计
- Kelivo Gateway：/v1/chat/completions 代理 + 时间线管理
- 自动唤醒：定时自唤醒，注入查岗+DM状态
- DM动态状态：四维状态引擎
- 欲望账本：GitHub远端真源 + SQLite缓存
- 念头池：闪念→执念
- 远程遥控：163邮箱SMTP（可选）
- MCP：/mcp 端点全暴露工具

## 快速开始
```bash
cp .env.example .env
# 填配置
uvicorn main:app --host 0.0.0.0 --port 8000
```
