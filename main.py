import os
import time
import asyncio
import sqlite3
import datetime
import astrbot.api.message_components as Comp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

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


@register("groupkw", "Oct1Nov0", "多群关键词自动回复，支持图文、等价词、多词触发、限速", "2.1.0", "https://github.com/Oct1Nov0/astrbot_plugin_groupkw")
class GroupKeywordPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.plugin_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "groupkw.db")
        self._init_db()
        # 限速相关（内存记录，重启清空）
        self._last_trigger = {}
        self._warned = set()
        self.RATE_WINDOW = 30
        self.SEND_INTERVAL = 1.0
        self.REPLY_DELAY = 1.0
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
        # 升级：加 image_url 列（已存在则忽略）
        try:
            c.execute("ALTER TABLE keywords ADD COLUMN image_url TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        c.execute("""
        CREATE TABLE IF NOT EXISTS enabled_groups (
            group_id TEXT PRIMARY KEY,
            enabled_at TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT,
            alias TEXT,
            main_keyword TEXT,
            created_at TEXT,
            UNIQUE(group_id, alias)
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
                    "INSERT INTO keywords (group_id, keyword, reply, image_url, created_by, created_at) VALUES (?,?,?,?,?,?)",
                    (gid, kw, reply, "", "default", now),
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

    def _check_rate(self, gid: str, uid: str):
        key = f"{gid}:{uid}"
        now = time.time()
        last = self._last_trigger.get(key, 0)
        if now - last >= self.RATE_WINDOW:
            self._last_trigger[key] = now
            self._warned.discard(key)
            return True, False
        if key not in self._warned:
            self._warned.add(key)
            return False, True
        return False, False

    def _pure_text(self, event: AstrMessageEvent) -> str:
        # 只取消息里的文字段（type=text），跳过 at/image 等，避免被@人的昵称误触发关键词
        try:
            raw = event.message_obj.raw_message
            if isinstance(raw, dict):
                segs = raw.get("message", [])
                if isinstance(segs, list):
                    texts = []
                    for seg in segs:
                        if isinstance(seg, dict) and seg.get("type") == "text":
                            texts.append(seg.get("data", {}).get("text", ""))
                    return "".join(texts).strip()
        except Exception as e:
            logger.warning(f"[群关键词] 提取纯文字失败：{e}")
        # 兜底：取不到分段就用 message_str
        return event.message_str.strip()

    def _extract_image_url(self, event: AstrMessageEvent) -> str:
        # 从当前消息里提取第一张图片的url
        try:
            raw = event.message_obj.raw_message
            if isinstance(raw, dict):
                for seg in raw.get("message", []):
                    if isinstance(seg, dict) and seg.get("type") == "image":
                        return seg.get("data", {}).get("url", "")
        except Exception as e:
            logger.warning(f"[群关键词] 提取图片url失败：{e}")
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
        """添加本群文字关键词。格式：/添加 关键词 回复内容"""
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
            "INSERT INTO keywords (group_id, keyword, reply, image_url, created_by, created_at) VALUES (?,?,?,?,?,?)",
            (gid, keyword, reply, "", str(event.get_sender_id()), self._now()),
        )
        conn.commit()
        conn.close()
        yield event.plain_result(f"已添加关键词「{keyword}」。")

    @filter.command("添加图片")
    async def add_image_kw(self, event: AstrMessageEvent):
        """添加本群图片关键词。发送图片同时输入：/添加图片 关键词 文字(可选)"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._is_group_enabled(gid):
            return
        if not self._can_manage(event):
            yield event.plain_result("只有本群群主、管理员才能管理关键词。")
            return
        img_url = self._extract_image_url(event)
        if not img_url:
            yield event.plain_result("没检测到图片。请在发送图片的同时输入指令（图片和指令在同一条消息里）。")
            return
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 2:
            yield event.plain_result("指令有误bot看不懂喵~请检查指令")
            return
        keyword = parts[1].strip()
        has_text = len(parts) >= 3 and parts[2].strip() != ""
        text = parts[2].strip() if has_text else ""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT reply, image_url FROM keywords WHERE group_id=? AND keyword=?", (gid, keyword))
        row = c.fetchone()
        now = self._now()
        uid = str(event.get_sender_id())
        if row is None:
            # 关键词不存在：新建（带或不带文字）
            c.execute(
                "INSERT INTO keywords (group_id, keyword, reply, image_url, created_by, created_at) VALUES (?,?,?,?,?,?)",
                (gid, keyword, text, img_url, uid, now),
            )
            msg = f"已添加图片关键词「{keyword}」。"
        else:
            # 关键词已存在
            if has_text:
                # 带文字：覆盖文字，并加图片
                c.execute(
                    "UPDATE keywords SET reply=?, image_url=?, created_by=?, created_at=? WHERE group_id=? AND keyword=?",
                    (text, img_url, uid, now, gid, keyword),
                )
                msg = f"已更新「{keyword}」的文字并添加图片。"
            else:
                # 不带文字：保留原文字，只加图片
                c.execute(
                    "UPDATE keywords SET image_url=?, created_by=?, created_at=? WHERE group_id=? AND keyword=?",
                    (img_url, uid, now, gid, keyword),
                )
                msg = f"已为「{keyword}」添加图片（原文字回答保留）。"
        conn.commit()
        conn.close()
        yield event.plain_result(msg)

    @filter.command("删除图片")
    async def del_image_kw(self, event: AstrMessageEvent):
        """删除本群图片关键词。格式：/删除图片 关键词"""
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
        if len(parts) < 2:
            yield event.plain_result("指令有误bot看不懂喵~请检查指令")
            return
        keyword = parts[1].strip()
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT reply, image_url FROM keywords WHERE group_id=? AND keyword=?", (gid, keyword))
        row = c.fetchone()
        if row is None:
            conn.close()
            yield event.plain_result(f"本群没有关键词「{keyword}」。")
            return
        if not row["image_url"]:
            conn.close()
            yield event.plain_result("该关键词没有图片")
            return
        if row["reply"]:
            # 有文字：只删图片，保留文字
            c.execute(
                "UPDATE keywords SET image_url=?, created_at=? WHERE group_id=? AND keyword=?",
                ("", self._now(), gid, keyword),
            )
            msg = f"已删除「{keyword}」的图片（文字回答保留）。"
        else:
            # 只有图片：删整条
            c.execute("DELETE FROM keywords WHERE group_id=? AND keyword=?", (gid, keyword))
            msg = f"已删除图片关键词「{keyword}」。"
        conn.commit()
        conn.close()
        yield event.plain_result(msg)

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
        """修改本群关键词的文字回复。格式：/修改 关键词 新回复内容"""
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

    @filter.command("加等价词")
    async def add_alias(self, event: AstrMessageEvent):
        """给主关键词加等价词。格式：/加等价词 主词 等价词"""
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
        main_kw = parts[1].strip()
        alias = parts[2].strip()
        conn = self._conn()
        c = conn.cursor()
        # 主关键词必须已存在
        c.execute("SELECT id FROM keywords WHERE group_id=? AND keyword=?", (gid, main_kw))
        if not c.fetchone():
            conn.close()
            yield event.plain_result(f"本群没有关键词「{main_kw}」，请先用 /添加 创建它。")
            return
        # 等价词不能本身已是某个关键词
        c.execute("SELECT id FROM keywords WHERE group_id=? AND keyword=?", (gid, alias))
        if c.fetchone():
            conn.close()
            yield event.plain_result("该词已是其他关键词，不能设为等价词，请删除或修改关键词")
            return
        # 等价词不能已经挂在别处
        c.execute("SELECT main_keyword FROM aliases WHERE group_id=? AND alias=?", (gid, alias))
        exist = c.fetchone()
        if exist:
            conn.close()
            yield event.plain_result(f"等价词「{alias}」已挂在关键词「{exist['main_keyword']}」下了。")
            return
        c.execute(
            "INSERT INTO aliases (group_id, alias, main_keyword, created_at) VALUES (?,?,?,?)",
            (gid, alias, main_kw, self._now()),
        )
        conn.commit()
        conn.close()
        yield event.plain_result(f"已为「{main_kw}」添加等价词「{alias}」。")

    @filter.command("删等价词")
    async def del_alias(self, event: AstrMessageEvent):
        """删除某个等价词。格式：/删等价词 主词 等价词"""
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
        main_kw = parts[1].strip()
        alias = parts[2].strip()
        conn = self._conn()
        c = conn.cursor()
        c.execute("DELETE FROM aliases WHERE group_id=? AND alias=? AND main_keyword=?", (gid, alias, main_kw))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        if deleted:
            yield event.plain_result(f"已删除「{main_kw}」的等价词「{alias}」。")
        else:
            yield event.plain_result(f"没找到「{main_kw}」下的等价词「{alias}」。")

    @filter.command("等价词清单")
    async def list_alias(self, event: AstrMessageEvent):
        """查看本群所有等价词"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._is_group_enabled(gid):
            return
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT main_keyword, alias FROM aliases WHERE group_id=? ORDER BY main_keyword, id", (gid,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            yield event.plain_result("本群还没有设置等价词。用 /加等价词 主词 等价词 来添加。")
            return
        groups = {}
        for r in rows:
            groups.setdefault(r["main_keyword"], []).append(r["alias"])
        lines = [f"本群等价词（共{len(rows)}个）："]
        for main_kw, aliases in groups.items():
            lines.append(f"· {main_kw} ＝ {'、'.join(aliases)}")
        yield event.plain_result("\n".join(lines))

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
        c.execute("SELECT keyword, reply, image_url FROM keywords WHERE group_id=? ORDER BY id", (gid,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            yield event.plain_result("本群还没有设置关键词。群主或管理员可用 /添加 添加。")
            return
        lines = [f"本群关键词（共{len(rows)}个）："]
        for r in rows:
            tag = "[图]" if r["image_url"] else ""
            preview = r["reply"] if len(r["reply"]) <= 18 else r["reply"][:18] + "…"
            lines.append(f"· {r['keyword']} {tag}→ {preview}")
        yield event.plain_result("\n".join(lines))

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        gid = self._get_group_id(event)
        if not gid:
            return
        if not self._is_group_enabled(gid):
            return
        msg = self._pure_text(event)
        if not msg:
            return
        cmd_words = ("添加", "删除", "修改", "关键词清单", "开启", "关闭", "添加图片", "删除图片", "加等价词", "删等价词", "等价词清单")
        cleaned = msg.lstrip("/／!！#").strip()
        if cleaned.startswith(cmd_words):
            return
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT keyword, reply, image_url FROM keywords WHERE group_id=?", (gid,))
        rows = c.fetchall()
        kw_map = {r["keyword"]: r for r in rows}
        c.execute("SELECT alias, main_keyword FROM aliases WHERE group_id=?", (gid,))
        alias_rows = c.fetchall()
        conn.close()

        # 收集所有命中的主关键词（按在消息中出现位置排序，去重）
        hit_keywords = []
        for kw, r in kw_map.items():
            if kw and kw in msg:
                pos = msg.find(kw)
                hit_keywords.append((pos, kw))
        # 等价词命中，归到主关键词
        for a in alias_rows:
            alias = a["alias"]
            main_kw = a["main_keyword"]
            if alias and alias in msg and main_kw in kw_map:
                pos = msg.find(alias)
                hit_keywords.append((pos, main_kw))
        # 去重（同一主关键词只保留一次，取最靠前的位置）
        seen = {}
        for pos, kw in hit_keywords:
            if kw not in seen or pos < seen[kw]:
                seen[kw] = pos
        ordered = sorted(seen.items(), key=lambda x: x[1])

        if not ordered:
            return

        # 限速：同一人30秒只响应一次
        uid = str(event.get_sender_id())
        allowed, need_warn = self._check_rate(gid, uid)
        if not allowed:
            if need_warn:
                yield event.plain_result("刷屏啦，请30秒后再试~")
            return

        # 回复延迟
        await asyncio.sleep(self.REPLY_DELAY)

        LIMIT = 3
        to_reply = ordered[:LIMIT]
        first = True
        for kw, _pos in to_reply:
            r = kw_map[kw]
            text = r["reply"]
            img = r["image_url"]
            if text:
                if not first:
                    await asyncio.sleep(self.SEND_INTERVAL)
                first = False
                yield event.plain_result("\u200b\n" + text)
            if img:
                if not first:
                    await asyncio.sleep(self.SEND_INTERVAL)
                first = False
                ok = False
                try:
                    client = event.bot
                    await client.api.call_action(
                        "send_group_msg",
                        group_id=int(gid),
                        message=[{"type": "image", "data": {"file": img}}],
                    )
                    ok = True
                except Exception as e:
                    logger.warning(f"[群关键词] 发送图片失败（可能已过期）：{e}")
                if not ok:
                    yield event.plain_result("图片已过期，请重新配置~")
        if len(ordered) > LIMIT:
            await asyncio.sleep(self.SEND_INTERVAL)
            yield event.plain_result("已同时触发多个关键词，bot最多只能处理3个噢，稍后再试吧~")
        return

    async def terminate(self):
        logger.info("[群关键词] 插件已卸载")
