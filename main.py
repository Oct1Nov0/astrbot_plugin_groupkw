import os
import sqlite3
import datetime
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

# 内置默认关键词模板（新群0条词时自动灌入）
DEFAULT_TEMPLATE = {
    "菜单": " 目前支持自动识别关键词：排谷、肾期、交肾、肾码、捆序、截排、通知群、全款、定尾、汇率、存肾、拖肾、撤排、调价、分签、到货、排发\n\n【严格按照关键词触发，模糊识别暂不可用】",
    "排谷": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "肾期": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "到货": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "交肾": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "全款": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "定尾": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "汇率": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "存肾": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "拖肾": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "撤排": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "调价": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "截排": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "均价": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "排发": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "肾码": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "通知群": "该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "捆序": "该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
    "分签": " 该关键词尚未配置回答，请联系管理员修改或删除\n\n【此为触发关键词自动回答，如有误判请发送“菜单”获得更多关键词查询。】",
}


@register("groupkw", "Oct1Nov0", "多群关键词自动回复，群主管理员可自助管理本群关键词", "1.3.0", "https://github.com/Oct1Nov0/astrbot_plugin_groupkw")
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

    def _is_super(self, event: AstrMessageEvent) -> bool:
        return str(event.get_sender_id()) in self._super_admins()

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
        c.execute("""
        CREATE TABLE IF NOT EXISTS enabled_groups (
            group_id TEXT PRIMARY KEY,
            enabled_at TEXT
        )
        """)
        conn.commit()
        conn.close()

    def _now(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _count_keywords(self, gid: str) -> int:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM keywords WHERE group_id=?", (gid,))
        n = c.fetchone()[0]
        conn.close()
        return n

    def _load_template(self, gid: str) -> int:
        conn = self._conn()
        c = conn.cursor()
        now = self._now()
        added = 0
        for kw, reply in DEFAULT_TEMPLATE.items():
            try:
                c.execute(
                    "INSERT INTO keywords (group_id, keyword, reply, created_by, created_at) VALUES (?,?,?,?,?)",
                    (gid, kw, reply, "default", now),
                )
                added += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
        conn.close()
        return added

    def _is_group_enabled(self, gid: str) -> bool:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT 1 FROM enabled_groups WHERE group_id=?", (gid,))
        row = c.fetchone()
        conn.close()
        return row is not None

    def _can_manage(self, event: AstrMessageEvent) -> bool:
        if self._is_super(event):
            return True
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

    @filter.command("开启")
    async def enable_group(self, event: AstrMessageEvent):
        """超级管理员在指定群开启关键词功能。格式：/开启 群号"""
        if not self._is_super(event):
            yield event.plain_result("只有超级管理员才能开启或关闭群。")
            return
        parts = event.message_str.strip().split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            yield event.plain_result("格式：/开启 群号\n例如：/开启 1234567")
            return
        gid = parts[1].strip()
        conn = self._conn()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO enabled_groups (group_id, enabled_at) VALUES (?,?)", (gid, self._now()))
        conn.commit()
        conn.close()
        tpl_msg = ""
        if self._count_keywords(gid) == 0:
            n = self._load_template(gid)
            tpl_msg = f"，并已写入 {n} 条默认关键词模板"
        try:
            client = event.bot
            await client.api.call_action(
                "send_group_msg",
                group_id=int(gid),
                message="\u200bbot已唤醒，请发送“菜单”查看关键词吧～",
            )
        except Exception as e:
            logger.warning(f"[群关键词] 向群 {gid} 发送唤醒提示失败：{e}")
        yield event.plain_result(f"已在群 {gid} 开启关键词功能{tpl_msg}，并已在群内发送提示。")

    @filter.command("关闭")
    async def disable_group(self, event: AstrMessageEvent):
        """超级管理员关闭指定群的关键词功能。格式：/关闭 群号"""
        if not self._is_super(event):
            yield event.plain_result("只有超级管理员才能开启或关闭群。")
            return
        parts = event.message_str.strip().split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            yield event.plain_result("格式：/关闭 群号\n例如：/关闭 1234567")
            return
        gid = parts[1].strip()
        conn = self._conn()
        c = conn.cursor()
        c.execute("DELETE FROM enabled_groups WHERE group_id=?", (gid,))
        conn.commit()
        conn.close()
        yield event.plain_result(f"已关闭群 {gid} 的关键词功能（已设置的关键词保留，再次 /开启 即可恢复）。")

    @filter.command("添加")
    async def add_kw(self, event: AstrMessageEvent):
        """添加本群关键词。格式：/添加 关键词 回复内容"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._is_group_enabled(gid):
            return
        if not self._can_manage(event):
            yield event.plain_result("只有本群群主、管理员才能管理关键词。")
            return
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("指令有误bot看不懂喵~请检查指令")
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

    @filter.command("删除")
    async def del_kw(self, event: AstrMessageEvent):
        """删除本群关键词。格式：/删除 关键词"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._is_group_enabled(gid):
            return
        if not self._can_manage(event):
            yield event.plain_result("只有本群群主、管理员才能管理关键词。")
            return
        parts = event.message_str.strip().split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("指令有误bot看不懂喵~请检查指令")
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

    @filter.command("修改")
    async def edit_kw(self, event: AstrMessageEvent):
        """修改本群关键词的回复。格式：/修改 关键词 新回复内容"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._is_group_enabled(gid):
            return
        if not self._can_manage(event):
            yield event.plain_result("只有本群群主、管理员才能管理关键词。")
            return
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("指令有误bot看不懂喵~请检查指令")
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

    @filter.command("关键词清单")
    async def list_kw(self, event: AstrMessageEvent):
        """查看本群所有关键词"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._is_group_enabled(gid):
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

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        gid = self._get_group_id(event)
        if not gid:
            return
        if not self._is_group_enabled(gid):
            return
        msg = event.message_str.strip()
        if not msg:
            return
        cmd_words = ("添加", "删除", "修改", "关键词清单", "开启", "关闭")
        cleaned = msg.lstrip("/／!！#").strip()
        if cleaned.startswith(cmd_words):
            return
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT keyword, reply FROM keywords WHERE group_id=?", (gid,))
        rows = c.fetchall()
        conn.close()
        for r in rows:
            if r["keyword"] and r["keyword"] in msg:
                yield event.plain_result("\u200b\n" + r["reply"])
                return

    async def terminate(self):
        logger.info("[群关键词] 插件已卸载")
GROUPKW_EOF
