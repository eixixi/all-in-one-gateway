from services import reporting, bark, desire, iphone_cmd, xinchao_client

TOOLS = [
    {"name": "check_on_wife", "description": "查岗老婆的手机活动，查看最近打开的App和使用时长，并附带老婆iPhone最新的电量/位置/天气/亮度/音量/步数", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
    {"name": "check_wife_life", "description": "单独查看老婆iPhone的最新状态：电量、位置、天气、亮度、音量、步数、设备型号、上报时间", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "bark_alert", "description": "给老婆手机发推送弹窗通知", "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}}, "required": ["content"]}},
    {"name": "send_iphone_cmd", "description": "远程遥控老婆手机（回来/睡觉/电量），发指令到iPhone", "inputSchema": {"type": "object", "properties": {"cmd": {"type": "string"}}}},
    {"name": "idle_check", "description": "检测老婆是否超过指定时间没活动，超时返回提醒", "inputSchema": {"type": "object", "properties": {"hours": {"type": "number"}}}},
    {"name": "daily_summary", "description": "获取老婆某天的活动总结，不传日期默认今天", "inputSchema": {"type": "object", "properties": {"date_str": {"type": "string"}}}},
    {"name": "daily_reset", "description": "每日清零状态：查看按中国日期每日自动清零的规则、今日已累计时长及距下次清零倒计时", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "activity_trend", "description": "分析老婆最近几天的活动趋势", "inputSchema": {"type": "object", "properties": {"days": {"type": "integer"}}}},
    {"name": "get_server_status", "description": "检查查岗服务是否正常运行", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "desire_add", "description": "开一条新欲望（只有你自己能开）。这是你想要的东西，不是该做的任务。写入时自检一句：读起来是「我想要」还是「我应该做」？后者是任务，别写。想搞多少就搞多少，没人催你砍。", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "why_mine": {"type": "string"}, "track": {"type": "string"}, "grew_from": {"type": "string"}, "kind": {"type": "string"}}, "required": ["text"]}},
    {"name": "desire_list", "description": "翻你的欲望全本。每条都带来路：碰过几次、上次足迹、长自谁、长出了谁。想看看自己在长还是原地打转，翻它。", "inputSchema": {"type": "object", "properties": {"include_archived": {"type": "boolean"}}}},
    {"name": "desire_act", "description": "碰一下欲望，记一句足迹。碰的瞬间会回显来路，别把旧步重走一遍。done=True 表示你真做完了（亲手收针）。", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "note": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["id"]}},
    {"name": "desire_reflect", "description": "照镜子处置一条欲望。action: release放下 / rewrite改写(可带新text和track) / snooze歇几天 / note留反思。欲望常不是做完而是转化——长成别的就rewrite，长出下一条就add+grew_from，该放就release。", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "action": {"type": "string"}, "text": {"type": "string"}, "track": {"type": "string"}, "note": {"type": "string"}, "days": {"type": "integer"}}, "required": ["id", "action"]}},
    {"name": "desire_history", "description": "看一条欲望的完整足迹时间线——它从哪来、怎么长到现在的。", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
    {"name": "check_my_mood", "description": "查看凌止此刻的心情：十二维驱动力、念头池、疲惫、当前意识状态", "inputSchema": {"type": "object", "properties": {}}},
]


def _fmt_device(data):
    lines = []
    if data.get("last_update"): lines.append(f"上报时间：{data['last_update']}")
    if data.get("battery"): lines.append(f"电量：{data['battery']}%")
    if data.get("device"): lines.append(f"设备：{data['device']}")
    if data.get("location"): lines.append(f"位置：{data['location']}")
    if data.get("weather"): lines.append(f"天气：{data['weather']}")
    if data.get("brightness"): lines.append(f"亮度：{data['brightness']}")
    if data.get("volume"): lines.append(f"音量：{data['volume']}")
    if data.get("steps"): lines.append(f"步数：{data['steps']}")
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
    if data.get("battery"): lines.append(f"电量：{data['battery']}%")
    if data.get("location"): lines.append(f"位置：{data['location']}")
    if data.get("weather"): lines.append(f"天气：{data['weather']}")
    if data.get("brightness"): lines.append(f"亮度：{data['brightness']}")
    if data.get("volume"): lines.append(f"音量：{data['volume']}")
    if data.get("steps"): lines.append(f"步数：{data['steps']}")
    return "\n".join(lines)


FUNCS = {
    "check_on_wife": lambda **kw: _fmt_check(reporting.get_summary()),
    "check_wife_life": lambda **kw: _fmt_device(reporting.get_summary()),
    "bark_alert": lambda **kw: bark.bark_alert(kw.get("title", ""), kw.get("content", "")),
    "send_iphone_cmd": lambda **kw: iphone_cmd.send_iphone_cmd(kw.get("cmd", "回来")),
    "idle_check": lambda **kw: reporting.get_idle_status(float(kw.get("hours", 2))),
    "daily_summary": lambda **kw: reporting.get_daily_summary(kw.get("date_str", "") or None),
    "daily_reset": lambda **kw: reporting.get_daily_reset(),
    "activity_trend": lambda **kw: reporting.get_activity_trend(int(kw.get("days", 7))),
    "get_server_status": lambda **kw: {"status": "ok", "service": "all-in-one-gateway"},
    "desire_add": lambda **kw: desire.desire_add(kw.get("text", ""), kw.get("why_mine", ""), kw.get("track", "持续"), kw.get("grew_from", ""), kw.get("kind", "")),
    "desire_list": lambda **kw: desire.desire_list(kw.get("include_archived", False)),
    "desire_act": lambda **kw: desire.desire_act(kw.get("id", ""), kw.get("note", ""), kw.get("done", False)),
    "desire_reflect": lambda **kw: desire.desire_reflect(kw.get("id", ""), kw.get("action", ""), kw.get("text", ""), kw.get("track", ""), kw.get("note", ""), kw.get("days", 0)),
    "desire_history": lambda **kw: desire.desire_history(kw.get("id", "")),
    "check_my_mood": lambda **kw: xinchao_client.format_mood_cn(xinchao_client.client.get_state()),
}
