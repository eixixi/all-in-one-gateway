import asyncio
import json
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from fastapi.responses import Response

from config import cfg
from services import reporting, timeline, wake
from mcp_tools import TOOLS, FUNCS


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(wake.wake_loop())
    yield
    task.cancel()


app = FastAPI(title="All-in-One Gateway", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ReportBody(BaseModel):
    app_name: str = ""
    event: str = ""
    battery: str = ""
    location: str = ""
    weather: str = ""
    device: str = ""
    brightness: str = ""
    volume: str = ""
    steps: str = ""


# ===== 查岗上报 =====
@app.post("/report")
async def report(body: ReportBody, req: Request):
    auth = req.headers.get("Authorization", "")
    if auth != f"Bearer {cfg.AUTH_TOKEN}":
        raise HTTPException(401, "Unauthorized")
    return reporting.add_record(body.app_name, body.event, body.battery, body.location,
                                body.weather, body.device, body.brightness, body.volume, body.steps)


@app.get("/ping")
async def ping():
    return "pong"


@app.get("/activity/summary")
async def summary():
    return reporting.get_summary()


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ===== Kelivo Gateway =====
@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": cfg.MODEL_NAME, "object": "model", "created": 0, "owned_by": "gateway"}]}


@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    if cfg.ALLOW_PUBLIC_API:
        auth = req.headers.get("Authorization", "")
        if auth != f"Bearer {cfg.GATEWAY_API_KEY}":
            raise HTTPException(401, "Unauthorized")

    body = await req.json()
    kelivo_messages = body.get("messages", [])

    timeline.save_timeline(timeline.build_timeline(kelivo_messages))

    llm_messages = list(kelivo_messages)
    for event in timeline.load_timeline():
        if timeline.is_special_event(event) and event not in llm_messages:
            llm_messages.append(event)

    if not cfg.TARGET_API_URL or not cfg.TARGET_API_KEY:
        raise HTTPException(500, "TARGET_API_URL / TARGET_API_KEY 未配置")

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            cfg.TARGET_API_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg.TARGET_API_KEY}"},
            json={**body, "messages": llm_messages},
        )

    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        return Response(content=resp.content, media_type="text/event-stream")
    return resp.json()


# ===== MCP端点 =====
@app.post("/mcp")
async def mcp(req: Request):
    body = await req.json()
    method, params = body.get("method"), body.get("params") or {}
    rid = body.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "All-in-One Gateway", "version": "1.0.0"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name not in FUNCS:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "未知工具"}}
        try:
            result = FUNCS[name](**args)
        except Exception as e:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32603, "message": str(e)}}
        return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"未知方法: {method}"}}


# ===== 手动触发唤醒（测试用） =====
@app.post("/wake/run")
async def wake_run():
    return await wake.run_wake_once()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=cfg.PORT)
