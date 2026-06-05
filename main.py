import os
import time
import asyncio
import sqlite3
import datetime
import base64
import uuid
import astrbot.api.message_components as Comp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

try:
    import aiohttp
    _HAS_AIOHTTP = True
except ImportError:
    aiohttp = None
    _HAS_AIOHTTP = False
    logger.warning("[群关键词] 未安装 aiohttp，自动上传图片功能不可用，请 pip install aiohttp")

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


@register("groupkw", "Oct1Nov0", "多群关键词自动回复，支持图文链接、自动上传图床、等价词、多词触发、限速、一键清空", "2.5.1", "https://github.com/Oct1Nov0/astrbot_plugin_groupkw")
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
        self._pending_clear = {}
        # GitHub 自动上传相关配置（在插件配置界面填写）
        self.MAX_IMG_SIZE = 10 * 1024 * 1024  # 单图上限 10MB
        self.UPLOAD_TIMEOUT = 15  # 上传/下载超时秒数
        logger.info(f"[群关键词] 插件已加载，数据库：{self.db_path}")

    def _gh_token(self):
        return str(self.config.get("github_token", "")).strip()

    def _gh_repo(self):
        return str(self.config.get("github_repo", "Oct1Nov0/bot-images")).strip()

    def _gh_branch(self):
        return str(self.config.get("github_branch", "main")).strip() or "main"

    def _gh_proxy(self):
        # 可选的 GitHub API 代理地址，留空走直连
        return str(self.config.get("github_proxy", "")).strip().rstrip("/")

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

    def _purge_group(self, gid: str):
        """删除某个群的全部关键词、等价词，并移出启用列表。退群时调用。"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("DELETE FROM keywords WHERE group_id=?", (gid,))
        kw_n = c.rowcount
        c.execute("DELETE FROM aliases WHERE group_id=?", (gid,))
        c.execute("DELETE FROM enabled_groups WHERE group_id=?", (gid,))
        conn.commit()
        conn.close()
        return kw_n

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

    def _guess_ext(self, qq_url: str) -> str:
        # 从 QQ 图片链接里猜扩展名，默认 jpg
        low = qq_url.lower()
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            if ext in low:
                return ext.lstrip(".")
        return "jpg"

    def _gen_filename(self, ext: str) -> str:
        # 时间戳 + 随机串，避免重名覆盖
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rnd = uuid.uuid4().hex[:4]
        return f"{ts}_{rnd}.{ext}"

    def _jsdelivr_url(self, path: str) -> str:
        # 把仓库内文件路径拼成 jsDelivr CDN 链接
        repo = self._gh_repo()
        branch = self._gh_branch()
        return f"https://cdn.jsdelivr.net/gh/{repo}@{branch}/{path}"

    async def _download_qq_image(self, qq_url: str):
        """把 QQ 图片下载到内存。返回 (图片字节, 错误信息)，成功时错误为空。"""
        if not qq_url:
            return None, "没拿到图片链接"
        try:
            timeout = aiohttp.ClientTimeout(total=self.UPLOAD_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.get(qq_url) as resp:
                    if resp.status != 200:
                        return None, f"下载图片失败（HTTP {resp.status}）"
                    # 先看响应头里的大小，超限直接拒绝
                    clen = resp.headers.get("Content-Length")
                    if clen and clen.isdigit() and int(clen) > self.MAX_IMG_SIZE:
                        return None, "图片太大了（超过10MB），请换张小一点的"
                    # 边读边累计，超限即停
                    chunks = []
                    total = 0
                    async for chunk in resp.content.iter_chunked(64 * 1024):
                        total += len(chunk)
                        if total > self.MAX_IMG_SIZE:
                            return None, "图片太大了（超过10MB），请换张小一点的"
                        chunks.append(chunk)
                    return b"".join(chunks), ""
        except asyncio.TimeoutError:
            return None, "下载图片超时，请重试"
        except Exception as e:
            logger.warning(f"[群关键词] 下载QQ图片失败：{e}")
            return None, "下载图片出错，请重试或改用手动配链接"

    async def _upload_to_github(self, img_bytes: bytes, filename: str):
        """把图片字节上传到 GitHub 仓库。返回 (jsDelivr链接, 错误信息)，成功时错误为空。"""
        token = self._gh_token()
        if not token:
            return None, "没配置 GitHub 令牌，请在插件配置里填写 github_token，或改用手动配链接"
        repo = self._gh_repo()
        branch = self._gh_branch()
        path = f"images/{filename}"  # 统一传到仓库的 images 目录下
        # 拼接 GitHub API 地址，支持可选代理
        proxy = self._gh_proxy()
        base = proxy if proxy else "https://api.github.com"
        api_url = f"{base}/repos/{repo}/contents/{path}"
        content_b64 = base64.b64encode(img_bytes).decode("ascii")
        payload = {
            "message": f"bot upload {filename}",
            "content": content_b64,
            "branch": branch,
        }
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "astrbot-groupkw",
        }
        try:
            timeout = aiohttp.ClientTimeout(total=self.UPLOAD_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.put(api_url, json=payload, headers=headers) as resp:
                    if resp.status in (200, 201):
                        return self._jsdelivr_url(path), ""
                    elif resp.status == 401:
                        return None, "GitHub 令牌无效或已过期，请重新生成并填入配置"
                    elif resp.status == 404:
                        return None, "找不到仓库，请检查 github_repo 配置是否正确"
                    elif resp.status == 403:
                        return None, "GitHub 拒绝（权限不足或触发限流），请检查令牌权限"
                    else:
                        body = await resp.text()
                        logger.warning(f"[群关键词] GitHub上传失败 HTTP {resp.status}：{body[:200]}")
                        return None, f"上传失败（HTTP {resp.status}），可改用手动配链接"
        except asyncio.TimeoutError:
            return None, "连接 GitHub 超时（服务器可能连不上），请改用手动配链接或配置代理"
        except Exception as e:
            logger.warning(f"[群关键词] 上传GitHub出错：{e}")
            return None, "上传 GitHub 出错（服务器可能连不上），请改用手动配链接或配置代理"

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

    def _store_image(self, gid: str, keyword: str, img_url: str, text: str, has_text: bool, uid: str) -> str:
        """把一张图链接累加存进关键词。返回给用户的提示文字。"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT reply, image_url FROM keywords WHERE group_id=? AND keyword=?", (gid, keyword))
        row = c.fetchone()
        now = self._now()
        if row is None:
            # 关键词不存在：新建（带或不带文字）
            c.execute(
                "INSERT INTO keywords (group_id, keyword, reply, image_url, created_by, created_at) VALUES (?,?,?,?,?,?)",
                (gid, keyword, text, img_url, uid, now),
            )
            msg = f"已添加图片关键词「{keyword}」（当前 1 张图）。"
        else:
            # 关键词已存在：图片累加（多个链接用换行分隔）
            old_imgs = row["image_url"] or ""
            img_list = [u for u in old_imgs.split("\n") if u.strip()]
            img_list.append(img_url)
            new_imgs = "\n".join(img_list)
            n = len(img_list)
            if has_text:
                c.execute(
                    "UPDATE keywords SET reply=?, image_url=?, created_by=?, created_at=? WHERE group_id=? AND keyword=?",
                    (text, new_imgs, uid, now, gid, keyword),
                )
                msg = f"已更新「{keyword}」的文字并新增一张图（当前 {n} 张图）。"
            else:
                c.execute(
                    "UPDATE keywords SET image_url=?, created_by=?, created_at=? WHERE group_id=? AND keyword=?",
                    (new_imgs, uid, now, gid, keyword),
                )
                msg = f"已为「{keyword}」新增一张图（当前 {n} 张图，原文字保留）。"
        conn.commit()
        conn.close()
        return msg

    @filter.command("添加图片")
    async def add_image_kw(self, event: AstrMessageEvent):
        """添加本群图片关键词。
        发图同时打：/添加图片 关键词 文字(可选)  → 自动上传
        不带图：/添加图片 关键词 图床链接 文字(可选)  → 手动配链接"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._is_group_enabled(gid):
            return
        if not self._can_manage(event):
            yield event.plain_result("只有本群群主、管理员才能管理关键词。")
            return
        uid = str(event.get_sender_id())
        qq_img = self._extract_image_url(event)

        if qq_img:
            # —— 模式一：消息带图，自动上传 ——
            parts = event.message_str.strip().split(maxsplit=2)
            if len(parts) < 2:
                yield event.plain_result("指令有误bot看不懂喵~请检查指令\n发图同时打：/添加图片 关键词 文字(可选)")
                return
            keyword = parts[1].strip()
            has_text = len(parts) >= 3 and parts[2].strip() != ""
            text = parts[2].strip() if has_text else ""
            if not _HAS_AIOHTTP:
                yield event.plain_result("自动上传不可用（服务器缺少 aiohttp）。请改用手动配链接：/添加图片 关键词 图床链接")
                return
            if not self._gh_token():
                yield event.plain_result("还没配置 GitHub 令牌，无法自动上传。请在插件配置里填 github_token，或改用手动配链接：/添加图片 关键词 图床链接")
                return
            yield event.plain_result("正在上传图片到图床，请稍候~")
            # 下载到内存
            img_bytes, err = await self._download_qq_image(qq_img)
            if err:
                yield event.plain_result(err)
                return
            # 上传 GitHub
            ext = self._guess_ext(qq_img)
            filename = self._gen_filename(ext)
            cdn_url, err = await self._upload_to_github(img_bytes, filename)
            if err:
                yield event.plain_result(err)
                return
            msg = self._store_image(gid, keyword, cdn_url, text, has_text, uid)
            yield event.plain_result(msg)
            return

        # —— 模式二：不带图，手动配链接 ——
        parts = event.message_str.strip().split(maxsplit=3)
        if len(parts) < 3:
            yield event.plain_result("指令有误bot看不懂喵~请检查指令\n发图自动上传：/添加图片 关键词 文字(可选)\n手动配链接：/添加图片 关键词 图床链接 文字(可选)")
            return
        keyword = parts[1].strip()
        img_url = parts[2].strip()
        if not (img_url.startswith("http://") or img_url.startswith("https://")):
            yield event.plain_result("没检测到图片，按手动配链接处理时，链接必须以 http 开头哦~\n发图自动上传：/添加图片 关键词 文字(可选)\n手动配链接：/添加图片 关键词 图床链接 文字(可选)")
            return
        has_text = len(parts) >= 4 and parts[3].strip() != ""
        text = parts[3].strip() if has_text else ""
        msg = self._store_image(gid, keyword, img_url, text, has_text, uid)
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

    @filter.command("清空关键词")
    async def clear_keywords(self, event: AstrMessageEvent):
        """清空本群所有关键词（需二次确认）。格式：/清空关键词"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._is_group_enabled(gid):
            return
        if not self._can_manage(event):
            yield event.plain_result("只有本群群主、管理员才能管理关键词。")
            return
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM keywords WHERE group_id=?", (gid,))
        n = c.fetchone()[0]
        conn.close()
        if n == 0:
            yield event.plain_result("本群还没有关键词，无需清空。")
            return
        self._pending_clear[f"{gid}:{event.get_sender_id()}"] = time.time()
        yield event.plain_result(f"确定要清空本群全部 {n} 个关键词吗？等价词也会一起删除，此操作不可恢复。\n请在30秒内发送 /确认清空 来执行。")

    @filter.command("确认清空")
    async def confirm_clear(self, event: AstrMessageEvent):
        """确认清空本群所有关键词。格式：/确认清空"""
        gid = self._get_group_id(event)
        if not gid:
            yield event.plain_result("请在群里使用本指令。")
            return
        if not self._is_group_enabled(gid):
            return
        if not self._can_manage(event):
            yield event.plain_result("只有本群群主、管理员才能管理关键词。")
            return
        key = f"{gid}:{event.get_sender_id()}"
        ts = self._pending_clear.get(key, 0)
        if not ts or time.time() - ts > 30:
            self._pending_clear.pop(key, None)
            yield event.plain_result("没有待确认的清空操作，或已超过30秒。请重新发送 /清空关键词。")
            return
        self._pending_clear.pop(key, None)
        conn = self._conn()
        c = conn.cursor()
        c.execute("DELETE FROM keywords WHERE group_id=?", (gid,))
        kw_deleted = c.rowcount
        c.execute("DELETE FROM aliases WHERE group_id=?", (gid,))
        conn.commit()
        conn.close()
        yield event.plain_result(f"已清空本群全部关键词（共 {kw_deleted} 个）及其等价词。")

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

    @filter.command("删除群关键词")
    async def purge_group_cmd(self, event: AstrMessageEvent):
        """超级管理员清除指定群的全部关键词数据并恢复未开启状态。格式：/删除群关键词 群号"""
        if not self._is_super(event):
            yield event.plain_result("只有超级管理员才能使用本指令。")
            return
        parts = event.message_str.strip().split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            yield event.plain_result("格式：/删除群关键词 群号\n例如：/删除群关键词 1234567")
            return
        gid = parts[1].strip()
        kw_n = self._purge_group(gid)
        yield event.plain_result(f"已清除群 {gid} 的全部关键词（共 {kw_n} 条）及等价词，并恢复为未开启状态。")

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
        cmd_words = ("添加", "删除", "修改", "关键词清单", "开启", "关闭", "添加图片", "删除图片", "加等价词", "删等价词", "等价词清单", "清空关键词", "确认清空", "删除群关键词")
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
                # 多张图用换行分隔，逐张发送
                img_list = [u for u in img.split("\n") if u.strip()]
                for one_img in img_list:
                    if not first:
                        await asyncio.sleep(self.SEND_INTERVAL)
                    first = False
                    ok = False
                    try:
                        client = event.bot
                        await client.api.call_action(
                            "send_group_msg",
                            group_id=int(gid),
                            message=[{"type": "image", "data": {"file": one_img}}],
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
