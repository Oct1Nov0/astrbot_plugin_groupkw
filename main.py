import os
import sqlite3
import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig


@register("groupkw", "Oct1Nov0", "多群关键词自动回复，群主管理员可自助管理本群关键词", "1.0.0", "https://github.com/Oct1Nov0/astrbot_plugin_groupkw")
class GroupKeywordPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.plugin_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "groupkw.db")
        self._init_db()
        logger.info(f"[群关键词] 插件已加载，数据库：{self.db_path}")

    def _super_admins(self):
        raw = self.config.get("super_admin_qq", "")
        if not raw:
            return []
        return [q.strip() for q in str(raw).split(",") if q.strip()]

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT,
            keyword TEXT,
            reply TEXT,
            created_by TEXT,
            created_at TEXT,
            UNIQUE(group_id, keyword)
        )
        """)
        conn.commit()
        conn.close()

    def _now(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _can_manage(self, event: AstrMessageEvent) -> bool:
        # 超级管理员永远可以管
        if str(event.get_sender_id()) in self._super_admins():
            return True
        # 尝试读取群角色（owner / admin）
        try:
            raw = event.message_obj.raw_message
            role = None
            if isinstance(raw, dict):
                sender = raw.get("sender", {})
                role = sender.get("role")
            else:
                sender = getattr(raw, "sender", None)
                if sender is not None:
                    role = getattr(sender, "role", None)
            if role in ("owner", "admin"):
                return True
        except Exception as e:
            logger.warning(f"[群关键词] 读取群角色失败：{e}")
        return False

    def _get_group_id(self, event: AstrMessageEvent):
        try:
            gid = event.get_group_id()
            return str(gid) if gid else ""
        except Exception:
            return ""

    # ---------- 添加关键词 ----------
    @filter.command("添加")
    async def add_kw(self, event: AstrMessageEvent):
        """添加本群关键词。格式：/添加 关键词 回复内容"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._can_manage(event):
            yield event.plain_result("只有本群群主、管理员才能管理关键词。")
            return
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("格式：/添加 关键词 回复内容\n例如：/添加 发货 每周三统一发货哦")
            return
        keyword = parts[1].strip()
        reply = parts[2].strip()
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT id FROM keywords WHERE group_id=? AND keyword=?", (gid, keyword))
        if c.fetchone():
            conn.close()
            yield event.plain_result(f"关键词「{keyword}」本群已存在，用 /修改 {keyword} 新回复。")
            return
        c.execute(
            "INSERT INTO keywords (group_id, keyword, reply, created_by, created_at) VALUES (?,?,?,?,?)",
            (gid, keyword, reply, str(event.get_sender_id()), self._now()),
        )
        conn.commit()
        conn.close()
        yield event.plain_result(f"已添加关键词「{keyword}」。")

    # ---------- 删除关键词 ----------
    @filter.command("删除")
    async def del_kw(self, event: AstrMessageEvent):
        """删除本群关键词。格式：/删除 关键词"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._can_manage(event):
            yield event.plain_result("只有本群群主、管理员才能管理关键词。")
            return
        parts = event.message_str.strip().split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("格式：/删除 关键词")
            return
        keyword = parts[1].strip()
        conn = self._conn()
        c = conn.cursor()
        c.execute("DELETE FROM keywords WHERE group_id=? AND keyword=?", (gid, keyword))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        if deleted:
            yield event.plain_result(f"已删除关键词「{keyword}」。")
        else:
            yield event.plain_result(f"本群没有关键词「{keyword}」。")

    # ---------- 修改关键词 ----------
    @filter.command("修改")
    async def edit_kw(self, event: AstrMessageEvent):
        """修改本群关键词的回复。格式：/修改 关键词 新回复内容"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._can_manage(event):
            yield event.plain_result("只有本群群主、管理员才能管理关键词。")
            return
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("格式：/修改 关键词 新回复内容")
            return
        keyword = parts[1].strip()
        reply = parts[2].strip()
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT id FROM keywords WHERE group_id=? AND keyword=?", (gid, keyword))
        if not c.fetchone():
            conn.close()
            yield event.plain_result(f"本群没有关键词「{keyword}」，想新增用 /添加。")
            return
        c.execute(
            "UPDATE keywords SET reply=?, created_by=?, created_at=? WHERE group_id=? AND keyword=?",
            (reply, str(event.get_sender_id()), self._now(), gid, keyword),
        )
        conn.commit()
        conn.close()
        yield event.plain_result(f"已修改关键词「{keyword}」的回复。")

    # ---------- 查看本群关键词 ----------
    @filter.command("关键词清单")
    async def list_kw(self, event: AstrMessageEvent):
        """查看本群所有关键词"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT keyword, reply FROM keywords WHERE group_id=? ORDER BY id", (gid,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            yield event.plain_result("本群还没有设置关键词。群主或管理员可用 /添加 添加。")
            return
        lines = [f"本群关键词（共{len(rows)}个）："]
        for r in rows:
            reply_preview = r["reply"] if len(r["reply"]) <= 20 else r["reply"][:20] + "…"
            lines.append(f"· {r['keyword']} → {reply_preview}")
        yield event.plain_result("\n".join(lines))

    # ---------- 关键词匹配自动回复 ----------
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        gid = self._get_group_id(event)
        if not gid:
            return
        msg = event.message_str.strip()
        if not msg:
            return
        # 指令消息不触发关键词（避免管理指令被当成关键词）
        if msg.startswith("/"):
            return
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT keyword, reply FROM keywords WHERE group_id=?", (gid,))
        rows = c.fetchall()
        conn.close()
        for r in rows:
            if r["keyword"] and r["keyword"] in msg:
                yield event.plain_result(r["reply"])
                return

    async def terminate(self):
        logger.info("[群关键词] 插件已卸载")
