"""TrackerCog: VC共同参加・パーティプレイ・メンション収集"""
import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional
import sqlite3

DB_PATH = 'data/game_history.db'


class TrackerCog(commands.Cog, name='Tracker'):
    """VC・Party・メンションのデータを収集するCog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._vc_sessions: dict = {}  # {(id_a, id_b, channel_id): {'start_time': dt, 'channel_name': str}}
        self._tracked_parties = set() # 複数ギルド重複発火防止用
        self._init_db()

    # ── DB初期化 ───────────────────────────────────────
    def _init_db(self):
        conn = sqlite3.connect(DB_PATH, timeout=10)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS voice_co_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id_a TEXT NOT NULL, user_id_b TEXT NOT NULL,
            channel_id TEXT NOT NULL, channel_name TEXT,
            game_name_a TEXT, game_name_b TEXT,
            start_time TEXT NOT NULL, end_time TEXT, duration INTEGER
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS party_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_id TEXT NOT NULL, user_id TEXT NOT NULL, game_name TEXT NOT NULL,
            party_size_current INTEGER, party_size_max INTEGER,
            joined_at TEXT NOT NULL, left_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS mention_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id TEXT NOT NULL, to_user_id TEXT NOT NULL,
            channel_id TEXT NOT NULL, timestamp TEXT NOT NULL
        )''')
        conn.commit()
        conn.close()
        print("✅ TrackerCog: DBテーブル初期化完了")

    @commands.Cog.listener()
    async def on_ready(self):
        now = datetime.now()
        conn = sqlite3.connect(DB_PATH, timeout=10)
        
        for guild in self.bot.guilds:
            # 1. 既存のVCセッションをスキャン
            for vc in guild.voice_channels:
                members = vc.members
                for i, m1 in enumerate(members):
                    for m2 in members[i+1:]:
                        key = tuple(sorted([str(m1.id), str(m2.id)])) + (str(vc.id),)
                        if key not in self._vc_sessions:
                            self._vc_sessions[key] = {
                                'start_time': now,
                                'channel_name': vc.name
                            }
                            print(f"🎙️ [初期スキャン] VC共同参加を検出: {m1.name}↔{m2.name} in #{vc.name}")
            
            # 2. 既存のパーティセッションをスキャン
            for member in guild.members:
                for act in member.activities:
                    if act.type == discord.ActivityType.playing:
                        info = self._get_party_info(act)
                        if info and info['party_id']:
                            pid = info['party_id']
                            size = info['size']
                            # 既に登録されているか確認
                            cur = conn.cursor()
                            cur.execute("SELECT 1 FROM party_sessions WHERE party_id=? AND user_id=? AND left_at IS NULL", (pid, str(member.id)))
                            if not cur.fetchone():
                                conn.execute('''
                                    INSERT INTO party_sessions
                                    (party_id, user_id, game_name, party_size_current, party_size_max, joined_at)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', (pid, str(member.id), act.name,
                                      size[0] if size else None,
                                      size[1] if size else None,
                                      now.isoformat()))
                                print(f"🎮 [初期スキャン] パーティ参加を検出: {member.name} → {act.name}")
        
        conn.commit()
        conn.close()
        print("✅ TrackerCog: 初期スキャン完了")

    async def cog_unload(self):
        now = datetime.now()
        conn = sqlite3.connect(DB_PATH, timeout=10)
        
        # 残っているVCセッションを全て強制保存
        for key, session in self._vc_sessions.items():
            id_a, id_b, channel_id = key
            duration = int((now - session['start_time']).total_seconds())
            
            conn.execute('''
                INSERT INTO voice_co_sessions
                (user_id_a, user_id_b, channel_id, channel_name, start_time, end_time, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (id_a, id_b, channel_id, session['channel_name'],
                  session['start_time'].isoformat(), now.isoformat(), duration))
        
        # パーティセッションの left_at を一括で閉じる
        conn.execute('''
            UPDATE party_sessions SET left_at=?
            WHERE left_at IS NULL
        ''', (now.isoformat(),))
        
        conn.commit()
        conn.close()
        print("🛑 TrackerCog: 終了時データ保存完了")

    # ── ヘルパー ───────────────────────────────────────
    def _get_game_name(self, member: discord.Member) -> Optional[str]:
        for act in member.activities:
            if act.type == discord.ActivityType.playing:
                return act.name
        return None

    def _get_party_info(self, activity) -> Optional[dict]:
        if not hasattr(activity, 'party') or not activity.party:
            return None
        p = activity.party
        return {'party_id': p.get('id'), 'size': p.get('size', [None, None])}

    # ── イベント: VC ───────────────────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member,
        before: discord.VoiceState, after: discord.VoiceState
    ):
        now = datetime.now()

        # 参加
        if after.channel and after.channel != before.channel:
            for other in after.channel.members:
                if other.id == member.id:
                    continue
                key = tuple(sorted([str(member.id), str(other.id)])) + (str(after.channel.id),)
                if key not in self._vc_sessions:
                    self._vc_sessions[key] = {
                        'start_time': now,
                        'channel_name': after.channel.name,
                    }
            print(f"🎙️ VCに参加: {member.name} → #{after.channel.name}")

        # 退出
        if before.channel and before.channel != after.channel:
            game_a = self._get_game_name(member)
            for other in before.channel.members:
                if other.id == member.id:
                    continue
                key = tuple(sorted([str(member.id), str(other.id)])) + (str(before.channel.id),)
                session = self._vc_sessions.pop(key, None)
                if not session:
                    continue
                duration = int((now - session['start_time']).total_seconds())
                id_a, id_b = sorted([str(member.id), str(other.id)])
                game_b = self._get_game_name(other)
                conn = sqlite3.connect(DB_PATH, timeout=10)
                conn.execute('''
                    INSERT INTO voice_co_sessions
                    (user_id_a, user_id_b, channel_id, channel_name,
                     game_name_a, game_name_b, start_time, end_time, duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    id_a, id_b, str(before.channel.id), session['channel_name'],
                    game_a if id_a == str(member.id) else game_b,
                    game_b if id_a == str(member.id) else game_a,
                    session['start_time'].isoformat(), now.isoformat(), duration
                ))
                conn.commit()
                conn.close()
                print(f"💾 VC共同セッション記録: {id_a}↔{id_b} ({duration}秒)")

    # ── イベント: プレゼンス（Party ID） ──────────────
    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        now = datetime.now()
        before_parties, after_parties = {}, {}

        for act in before.activities:
            if act.type == discord.ActivityType.playing:
                info = self._get_party_info(act)
                if info and info['party_id']:
                    before_parties[info['party_id']] = act

        for act in after.activities:
            if act.type == discord.ActivityType.playing:
                info = self._get_party_info(act)
                if info and info['party_id']:
                    after_parties[info['party_id']] = act

        for pid, act in after_parties.items():
            if pid not in before_parties:
                # 複数サーバー共通のユーザーの場合、重複してイベントが発火するためスキップ
                if (pid, str(after.id)) in self._tracked_parties:
                    continue
                self._tracked_parties.add((pid, str(after.id)))

                info = self._get_party_info(act)
                size = info['size'] if info else [None, None]
                conn = sqlite3.connect(DB_PATH, timeout=10)
                conn.execute('''
                    INSERT INTO party_sessions
                    (party_id, user_id, game_name, party_size_current, party_size_max, joined_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (pid, str(after.id), act.name,
                      size[0] if size else None,
                      size[1] if size else None,
                      now.isoformat()))
                conn.commit()
                conn.close()
                print(f"🎮 パーティ参加: {after.name} → {act.name} (party={pid})")

        for pid in before_parties:
            if pid not in after_parties:
                self._tracked_parties.discard((pid, str(after.id)))
                conn = sqlite3.connect(DB_PATH, timeout=10)
                conn.execute('''
                    UPDATE party_sessions SET left_at=?
                    WHERE party_id=? AND user_id=? AND left_at IS NULL
                ''', (now.isoformat(), pid, str(after.id)))
                conn.commit()
                conn.close()

    # ── イベント: メンション ───────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.mentions:
            return
        now = datetime.now().isoformat()
        conn = sqlite3.connect(DB_PATH, timeout=10)
        for mentioned in message.mentions:
            if mentioned.bot or mentioned.id == message.author.id:
                continue
            conn.execute('''
                INSERT INTO mention_logs (from_user_id, to_user_id, channel_id, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (str(message.author.id), str(mentioned.id), str(message.channel.id), now))
            print(f"📢 メンション記録: {message.author.name} → {mentioned.name}")
        conn.commit()
        conn.close()

    # ── デバッグコマンド ───────────────────────────────
    @commands.command(name='status')
    async def check_status(self, ctx):
        """全メンバーのステータスをチェック"""
        lines = ["サーバーメンバーのステータス:\n```"]
        for member in ctx.guild.members:
            lines.append(f"{member.name}: {member.status}")
            if member.activity:
                lines.append(f"  → {member.activity.name}")
        lines.append("```")
        await ctx.send('\n'.join(lines))

    @commands.command(name='whoami')
    async def whoami(self, ctx):
        """自分の現在の状態を確認"""
        m = ctx.author
        lines = [f"あなたの情報:\n```",
                 f"名前: {m.name}", f"ID: {m.id}", f"ステータス: {m.status}"]
        if m.activity:
            lines.append(f"アクティビティ: {m.activity.name}")
        lines.append("```")
        await ctx.send('\n'.join(lines))
