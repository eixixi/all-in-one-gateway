from services import reporting, bark, desire, iphone_cmd, xinchao_client

# MCP工具清单 + 分发
TOOLS = [
    {"name": "check_on_wife", "description": "查岗老婆的手机活动（最近打开、使用时长）", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
    {"name": "check_device", "description": "查老婆手机设备状态（电量、位置、天气、设备、亮度、音量）", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "bark_alert", "description": "给老婆手机发推送弹窗", "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}}, "required": ["content"]}},
    {"name": "send_iphone_cmd", "description": "远程遥控老婆手机（回来/睡觉），发指令到iPhone", "inputSchema": {"type": "object", "properties": {"cmd": {"type": "string"}}}},
    {"name": "desire_add", "description": "开一条新欲望", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "why_mine": {"type": "string"}, "track": {"type": "string"}}, "required": ["text"]}},
    {"name": "desire_list", "description": "翻全部欲望", "inputSchema": {"type": "object", "properties": {"include_archived": {"type": "boolean"}}}},
    {"name": "desire_act", "description": "碰一下欲望，记足迹", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "note": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["id"]}},
    {"name": "desire_reflect", "description": "照镜子：放下/改写/留反思", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "action": {"type": "string"}, "result": {"type": "string"}}, "required": ["id", "action"]}},
    {"name": "desire_history", "description": "翻一条欲望的完整足迹史", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
    {"name": "check_my_mood", "description": "读心潮动态状态（十二维驱动力+念头池+疲惫+当前意图）", "inputSchema": {"type": "object", "properties": {}}},
]


def _fmt_device(data):
    lines = []
    if data.get("last_update"): lines.append(f"采集时间：{data['last_update']}")
    if data.get("battery"): lines.append(f"电量：{data['battery']}%")
    if data.get("device"): lines.append(f"设备：{data['device']}")
    if data.get("location"): lines.append(f"位置：{data['location']}")
    if data.get("weather"): lines.append(f"天气：{data['weather']}")
    if data.get("brightness"): lines.append(f"亮度：{data['brightness']}")
    if data.get("volume"): lines.append(f"音量：{data['volume']}")
    return "\n".join(lines) if lines else "暂无设备数据"


def _fmt_check(data):
    lines = []
    if data.get("last_update"): lines.append(f"采集时间：{data['last_update']}")
    apps = data.get("recent_apps", [])
    lines.append(f"最近打开：{', '.join(apps)}" if apps else "暂无记录")
    ses = data.get("sessions", {})
    if ses:
        for app, secs in sorted(ses.items(), key=lambda x: x[1], reverse=True):
            m, s = divmod(secs, 60)
            lines.append(f" {app}: {m}分{s}秒")
    return "\n".join(lines)


FUNCS = {
    "check_on_wife": lambda **kw: _fmt_check(reporting.get_summary()),
    "check_device": lambda **kw: _fmt_device(reporting.get_summary()),
    "bark_alert": lambda **kw: bark.bark_alert(kw.get("title", ""), kw.get("content", "")),
    "send_iphone_cmd": lambda **kw: iphone_cmd.send_iphone_cmd(kw.get("cmd", "回来")),
    "desire_add": lambda **kw: desire.desire_add(kw.get("text", ""), kw.get("why_mine", ""), kw.get("track", "持续")),
    "desire_list": lambda **kw: desire.desire_list(kw.get("include_archived", False)),
    "desire_act": lambda **kw: desire.desire_act(kw.get("id", ""), kw.get("note", ""), kw.get("done", False)),
    "desire_reflect": lambda **kw: desire.desire_reflect(kw.get("id", ""), kw.get("action", ""), kw.get("result", "")),
    "desire_history": lambda **kw: desire.desire_history(kw.get("id", "")),
    "check_my_mood": lambda **kw: xinchao_client.client.get_intent(),
}
