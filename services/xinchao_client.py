import httpx
from config import cfg


class XinchaoClient:
    """通过HTTP调用心潮动态状态引擎（xinchao-dynamic-mind，Node.js独立运行）。"""

    def __init__(self):
        self.base_url = cfg.XINCHAO_URL.rstrip("/")
        self.token = cfg.XINCHAO_TOKEN
        self.timeout = cfg.XINCHAO_TIMEOUT

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _get(self, path, params=None):
        if not self.base_url or not self.token:
            return None
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.base_url}{path}", headers=self._headers(), params=params)
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:200]}
        except Exception as e:
            return {"error": "connection_failed", "detail": str(e)}

    def _post(self, path, body=None):
        if not self.base_url or not self.token:
            return None
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}{path}", headers=self._headers(), json=body or {})
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:200]}
        except Exception as e:
            return {"error": "connection_failed", "detail": str(e)}

    def get_intent(self):
        """拿当前意图 + topDrives + 念头池 + 疲惫。唤醒时用这个。"""
        return self._get("/v1/intent")

    def get_state(self):
        """拿完整动态状态。"""
        return self._get("/v1/state")

    def get_context(self, session_id="wake", max_tokens=2200):
        """拿Context Envelope（动态状态+梦境余韵+交接便签）。"""
        return self._get("/v1/context", params={"session_id": session_id, "max_tokens": max_tokens})

    def record_interaction(self, interaction_type, session_id="wake"):
        """记一次互动，让心潮结算驱动力。发完推送后调用。"""
        import uuid
        return self._post("/v1/conversation-event", {
            "eventId": str(uuid.uuid4()),
            "sessionId": session_id,
            "interactionType": interaction_type,
        })

    def drive_feedback(self, deltas):
        """直接调整驱动力（管理端受控）。"""
        return self._post("/v1/drive-feedback", {"driveDeltas": deltas})


client = XinchaoClient()

# 驱动力英文key -> 中文
DRIVE_CN = {
    "possess": "占有",
    "monitor": "惦记",
    "crave": "渴望",
    "share": "分享",
    "libido": "欲念",
    "curiosity": "好奇",
    "boredom": "无聊",
    "social": "社交",
    "duty": "责任",
    "reflection": "反思",
    "grieve": "悲伤",
    "anger": "愤怒",
}

# 意识状态英文 -> 中文
STATE_CN = {
    "sleeping": "沉睡",
    "awake": "清醒",
    "drowsy": "昏沉",
    "dreaming": "梦中",
    "emerging": "苏醒",
}


def _num(v, digits=2):
    try:
        return round(float(v), digits)
    except Exception:
        return v


def format_mood_cn(data):
    """把心潮原始状态格式化成中文可读文本。"""
    if not data or "error" in data:
        return "（心潮状态引擎未连接或不可用）"

    lines = []

    # 意识状态
    state = data.get("consciousness")
    if state:
        lines.append(f"意识状态：{STATE_CN.get(state, state)}")

    # 驱动力
    drives = data.get("drives", {})
    if drives:
        parts = []
        for k, v in drives.items():
            name = DRIVE_CN.get(k, k)
            parts.append(f"{name}={_num(v)}")
        lines.append("驱动力：" + "，".join(parts))

    # 念头池
    pool = data.get("thoughtPool", {})
    flash = pool.get("flash", [])
    obs = pool.get("obsessions", [])
    if flash:
        lines.append("闪念：" + "，".join(str(f) for f in flash[:3]))
    if obs:
        lines.append("持续念头：" + "，".join(str(o) for o in obs[:3]))

    # 疲惫
    if "fatigue" in data:
        lines.append(f"疲惫：{_num(data['fatigue'])}")

    # 上次互动
    if "lastConversationAt" in data:
        lines.append(f"上次互动：{data['lastConversationAt']}")

    return "\n".join(lines) if lines else "（心潮暂无动态状态）"


def get_mood_text():
    """把心潮状态格式化成可注入prompt的文本。"""
    data = client.get_intent()
    if not data or "error" in data:
        return "（心潮状态引擎未连接或不可用）"
    lines = []
    intent = data.get("intent")
    if intent:
        lines.append(f"当前意图：{intent.get('label', intent.get('key', ''))}")
    top = data.get("topDrives", [])
    if top:
        drives = "；".join(f"{DRIVE_CN.get(d.get('key'), d.get('label', d.get('key')))}={d.get('value', 0):.3f}" for d in top[:5])
        lines.append(f"当前驱动力：{drives}")
    if "fatigue" in data:
        lines.append(f"疲惫：{data['fatigue']:.3f}")
    pool = data.get("thoughtPool", {})
    obs = pool.get("obsessions", [])
    if obs:
        obs_text = "，".join(f"{o.get('key')}:{o.get('intensity', 0):.3f}" for o in obs[:3])
        lines.append(f"持续念头：{obs_text}")
    flash = pool.get("flash", [])
    if flash:
        flash_text = "，".join(f"{f.get('key')}:{f.get('intensity', 0):.3f}" for f in flash[:3])
        lines.append(f"闪念：{flash_text}")
    return "\n".join(lines) if lines else "（心潮暂无动态状态）"


def record_contact(interaction_type="companionship"):
    """发完推送后告诉心潮，降驱动力。"""
    result = client.record_interaction(interaction_type)
    return result if result else {"error": "心潮未连接"}
