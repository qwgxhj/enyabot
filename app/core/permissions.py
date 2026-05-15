from app.config.config_manager import ConfigManager

ROLE_LEVEL = {
    "blacklist": -1,
    "member": 1,
    "admin": 2,
    "owner": 3,
    "master2": 50,
    "master": 99,
}


def _get_master_config() -> dict:
    config = ConfigManager().get()
    return config.get("bot", {})


def is_master(user_id: str, level: int = 0) -> bool:
    """判断是否为机器人主人。level=0 任意主人，level=1 一级主人，level=2 二级主人。"""
    bot_cfg = _get_master_config()
    uid = str(user_id)
    if level == 0:
        return uid in _get_all_masters(bot_cfg)
    elif level == 1:
        return uid == str(bot_cfg.get("master_qq", "")).strip()
    elif level == 2:
        return uid in _get_master2_list(bot_cfg)
    return False


def _get_all_masters(bot_cfg: dict) -> set:
    """获取所有主人QQ号集合。"""
    masters = set()
    m1 = str(bot_cfg.get("master_qq", "")).strip()
    if m1:
        masters.add(m1)
    masters.update(_get_master2_list(bot_cfg))
    return masters


def _get_master2_list(bot_cfg: dict) -> set:
    """获取二级主人列表。"""
    raw = bot_cfg.get("master2_qq", [])
    if isinstance(raw, str):
        return {x.strip() for x in raw.split("|") if x.strip()}
    if isinstance(raw, list):
        return {str(x).strip() for x in raw if str(x).strip()}
    return set()


def get_sender_role(sender_role: str, user_id: str) -> str:
    """获取发送者有效角色（主人优先）。"""
    bot_cfg = _get_master_config()
    uid = str(user_id)
    if uid == str(bot_cfg.get("master_qq", "")).strip():
        return "master"
    if uid in _get_master2_list(bot_cfg):
        return "master2"
    return sender_role


def has_permission(sender_role: str, required: str) -> bool:
    return ROLE_LEVEL.get(sender_role, 0) >= ROLE_LEVEL.get(required, 999)
