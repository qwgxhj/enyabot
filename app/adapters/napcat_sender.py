from loguru import logger
from app.services import msg_logger


class NapCatSender:
    def __init__(self, ws_client):
        self.ws_client = ws_client

    async def call_action(self, action: str, params: dict):
        payload = await self.ws_client.call_api(action, params)
        status = payload.get("status")
        retcode = payload.get("retcode")
        data = payload.get("data")
        if status != "ok" or retcode not in (0, None):
            logger.warning(f"NapCat action failed: action={action}, status={status}, retcode={retcode}, payload={payload}")
        else:
            logger.info(f"NapCat action success: action={action}, retcode={retcode}")
        return {"status": status, "retcode": retcode, "data": data, "raw": payload}

    # ── 消息发送 ──────────────────────────────────────────────

    async def send_group_text(self, group_id: str, text: str):
        result = await self.call_action("send_group_msg", {"group_id": int(group_id), "message": [{"type": "text", "data": {"text": text}}]})
        msg_logger.log_outgoing("send_group_msg", group_id, "", text, success=(result.get("status") == "ok"))
        return result

    async def send_private_text(self, user_id: str, text: str):
        result = await self.call_action("send_private_msg", {"user_id": int(user_id), "message": [{"type": "text", "data": {"text": text}}]})
        msg_logger.log_outgoing("send_private_msg", "", user_id, text, success=(result.get("status") == "ok"))
        return result

    async def send_group_record(self, group_id: str, file_url: str, title: str = ""):
        """发送语音/音频消息到群。"""
        msg = {"type": "record", "data": {"file": file_url}}
        if title:
            msg["data"]["title"] = title
        return await self.call_action("send_group_msg", {"group_id": int(group_id), "message": [msg]})

    async def send_group_image(self, group_id: str, file_url: str):
        """发送图片消息到群。"""
        return await self.call_action("send_group_msg", {"group_id": int(group_id), "message": [{"type": "image", "data": {"file": file_url}}]})

    # ── 群管 · 禁言/踢人 ─────────────────────────────────────

    async def mute_member(self, group_id: str, user_id: str, duration: int):
        """禁言群成员。duration=0 解禁，单位秒。"""
        return await self.call_action("set_group_ban", {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "duration": duration,
        })

    async def kick_member(self, group_id: str, user_id: str, reject: bool = False):
        """踢出群成员。reject=True 拒绝再次加群。"""
        return await self.call_action("set_group_kick", {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "reject_add_request": reject,
        })

    async def kick_members(self, group_id: str, user_ids: list[str]):
        """批量踢出群成员。"""
        return await self.call_action("set_group_kick_members", {
            "group_id": int(group_id),
            "user_id_list": [int(uid) for uid in user_ids],
        })

    async def whole_ban(self, group_id: str, enable: bool = True):
        """全员禁言/解除。"""
        return await self.call_action("set_group_whole_ban", {
            "group_id": int(group_id),
            "enable": enable,
        })

    # ── 群管 · 管理员/头衔 ───────────────────────────────────

    async def set_admin(self, group_id: str, user_id: str, enable: bool = True):
        """设置/取消管理员。"""
        return await self.call_action("set_group_admin", {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "enable": enable,
        })

    async def set_special_title(self, group_id: str, user_id: str, title: str):
        """设置专属头衔。"""
        return await self.call_action("set_group_special_title", {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "special_title": title,
        })

    async def set_card(self, group_id: str, user_id: str, card: str):
        """设置群名片（备注）。"""
        return await self.call_action("set_group_card", {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "card": card,
        })

    # ── 群管 · 群设置 ────────────────────────────────────────

    async def set_group_name(self, group_id: str, group_name: str):
        """修改群名。"""
        return await self.call_action("set_group_name", {
            "group_id": int(group_id),
            "group_name": group_name,
        })

    async def set_group_leave(self, group_id: str, is_dismiss: bool = False):
        """退出/解散群。"""
        return await self.call_action("set_group_leave", {
            "group_id": int(group_id),
            "is_dismiss": is_dismiss,
        })

    async def set_group_add_request(self, flag: str, approve: bool = True, reason: str = ""):
        """处理加群请求。"""
        params = {"flag": flag, "sub_type": "add", "approve": approve}
        if reason:
            params["reason"] = reason
        return await self.call_action("set_group_add_request", params)

    async def set_group_portrait(self, group_id: str, file: str):
        """设置群头像。file 为图片路径或 URL。"""
        return await self.call_action("set_group_portrait", {
            "group_id": int(group_id),
            "file": file,
        })

    # ── 群管 · 查询 ──────────────────────────────────────────

    async def get_group_info(self, group_id: str):
        """获取群信息。"""
        return await self.call_action("get_group_info", {"group_id": int(group_id)})

    async def get_group_list(self):
        """获取 bot 所在的群列表。"""
        return await self.call_action("get_group_list", {})

    async def get_group_member_info(self, group_id: str, user_id: str, no_cache: bool = False):
        """获取群成员信息。"""
        return await self.call_action("get_group_member_info", {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "no_cache": no_cache,
        })

    async def get_group_member_list(self, group_id: str):
        """获取群成员列表。"""
        return await self.call_action("get_group_member_list", {"group_id": int(group_id)})

    async def get_group_honor_info(self, group_id: str, honor_type: str = "talkative"):
        """获取群荣耀信息。type: talkative/perform/legend/strong_newbie/emotion"""
        return await self.call_action("get_group_honor_info", {
            "group_id": int(group_id),
            "type": honor_type,
        })

    async def get_group_msg_history(self, group_id: str, message_seq: int = 0):
        """获取群消息历史。message_seq=0 获取最新。"""
        params = {"group_id": int(group_id)}
        if message_seq:
            params["message_seq"] = message_seq
        return await self.call_action("get_group_msg_history", params)

    async def get_group_shut_list(self, group_id: str):
        """获取群禁言列表。"""
        return await self.call_action("get_group_shut_list", {"group_id": int(group_id)})

    async def get_group_at_all_remain(self, group_id: str):
        """获取 @all 剩余次数。"""
        return await self.call_action("get_group_at_all_remain", {"group_id": int(group_id)})
