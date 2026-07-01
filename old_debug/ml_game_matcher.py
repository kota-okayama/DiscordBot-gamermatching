import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional
import sqlite3

DB_PATH = 'game_history.db'

class GameTrackerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        # VC参加時刻を一時保存: {(user_id, channel_id): {'joined_at': datetime, 'members_at_join': set}}
        self._vc_sessions = {}
        self.add_commands()

    # ──────────────────────────────────────────────
    # DB 初期化
    # ──────────────────────────────────────────────
    def _init_db(self):
        """データ収集用テーブルの初期化"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # ① ボイスチャンネル共同参加ログ（最強の正解ラベル候補）
        c.execute('''
            CREATE TABLE IF NOT EXISTS voice_co_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id_a TEXT NOT NULL,
                user_id_b TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                channel_name TEXT,
                game_name_a TEXT,
                game_name_b TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration INTEGER
            )
        ''')

        # ② パーティ同時プレイログ（「一緒にゲームした」直接証拠）
        c.execute('''
            CREATE TABLE IF NOT EXISTS party_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                party_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                game_name TEXT NOT NULL,
                party_size_current INTEGER,
                party_size_max INTEGER,
                joined_at TEXT NOT NULL,
                left_at TEXT
            )
        ''')

        # ③ メンション共起ログ（弱いシグナル）
        c.execute('''
            CREATE TABLE IF NOT EXISTS mention_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id TEXT NOT NULL,
                to_user_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()
        print("✅ データ収集用DBテーブルを初期化しました")

    # ──────────────────────────────────────────────
    # ヘルパー
    # ──────────────────────────────────────────────
    def _get_game_name(self, member: discord.Member) -> Optional[str]:
        """メンバーの現在プレイ中ゲーム名を返す（Rich Presence）"""
        for activity in member.activities:
            if activity.type == discord.ActivityType.playing:
                return activity.name
        return None

    def _get_party_info(self, activity) -> Optional[dict]:
        """ActivityからParty情報を取得"""
        if not hasattr(activity, 'party') or not activity.party:
            return None
        party = activity.party
        return {
            'party_id': party.get('id'),
            'size': party.get('size', [None, None])
        }

    # ──────────────────────────────────────────────
    # イベント: ボイスチャンネル
    # ──────────────────────────────────────────────
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """VCの参加・退出を検知してvc_co_sessionsに記録する"""
        now = datetime.now()

        # ── チャンネルに参加した場合 ──
        if after.channel and after.channel != before.channel:
            channel = after.channel
            # 既にいるメンバーとの共同セッション開始を記録
            for other in channel.members:
                if other.id == member.id:
                    continue
                key = tuple(sorted([str(member.id), str(other.id)])) + (str(channel.id),)
                if key not in self._vc_sessions:
                    self._vc_sessions[key] = {
                        'start_time': now,
                        'channel_name': channel.name,
                    }
            print(f"🎙️ VCに参加: {member.name} → #{channel.name}")

        # ── チャンネルから退出した場合 ──
        if before.channel and before.channel != after.channel:
            channel = before.channel
            game_a = self._get_game_name(member)

            for other in channel.members:
                if other.id == member.id:
                    continue
                key = tuple(sorted([str(member.id), str(other.id)])) + (str(channel.id),)
                session = self._vc_sessions.pop(key, None)
                if session:
                    duration = int((now - session['start_time']).total_seconds())
                    # user_id_a を常に辞書順の小さい方にする
                    id_a, id_b = sorted([str(member.id), str(other.id)])
                    game_b = self._get_game_name(other)

                    conn = sqlite3.connect(DB_PATH)
                    conn.execute('''
                        INSERT INTO voice_co_sessions
                        (user_id_a, user_id_b, channel_id, channel_name,
                         game_name_a, game_name_b, start_time, end_time, duration)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        id_a, id_b,
                        str(channel.id), session['channel_name'],
                        game_a if id_a == str(member.id) else game_b,
                        game_b if id_a == str(member.id) else game_a,
                        session['start_time'].isoformat(),
                        now.isoformat(),
                        duration
                    ))
                    conn.commit()
                    conn.close()
                    print(f"💾 VC共同セッション記録: {id_a}↔{id_b} ({duration}秒)")

    # ──────────────────────────────────────────────
    # イベント: プレゼンス（Party ID取得）
    # ──────────────────────────────────────────────
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """パーティ参加・離脱を検知してparty_sessionsに記録する"""
        now = datetime.now()

        before_parties = {}
        after_parties = {}

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

        # 新しく参加したパーティ
        for pid, act in after_parties.items():
            if pid not in before_parties:
                info = self._get_party_info(act)
                size = info['size'] if info else [None, None]
                conn = sqlite3.connect(DB_PATH)
                conn.execute('''
                    INSERT INTO party_sessions
                    (party_id, user_id, game_name, party_size_current, party_size_max, joined_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    pid, str(after.id), act.name,
                    size[0] if size else None,
                    size[1] if size else None,
                    now.isoformat()
                ))
                conn.commit()
                conn.close()
                print(f"🎮 パーティ参加記録: {after.name} → party={pid} ({act.name})")

        # 離脱したパーティ
        for pid in before_parties:
            if pid not in after_parties:
                conn = sqlite3.connect(DB_PATH)
                conn.execute('''
                    UPDATE party_sessions SET left_at = ?
                    WHERE party_id = ? AND user_id = ? AND left_at IS NULL
                ''', (now.isoformat(), pid, str(after.id)))
                conn.commit()
                conn.close()
                print(f"🚪 パーティ離脱記録: {after.name} ← party={pid}")

        # コンソールログ（デバッグ）
        print(f"\n=== プレゼンス更新検知 ===")
        print(f"メンバー: {after.name}")
        print(f"前のステータス: {before.status}")
        print(f"新しいステータス: {after.status}")
        await self._log_activity_change(before, after)

    # ──────────────────────────────────────────────
    # イベント: メンション
    # ──────────────────────────────────────────────
    async def on_message(self, message: discord.Message):
        """メンションを検知してmention_logsに記録する"""
        # コマンド処理を先に実行
        await self.process_commands(message)

        if message.author.bot:
            return
        if not message.mentions:
            return

        now = datetime.now().isoformat()
        conn = sqlite3.connect(DB_PATH)
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

    # ──────────────────────────────────────────────
    # ライフサイクル
    # ──────────────────────────────────────────────
    async def setup_hook(self):
        print("\n=== セットアップ開始 ===")
        self._init_db()

    async def on_ready(self):
        print(f'{self.user} としてログインしました!')
        print(f'参加しているサーバー:')
        for guild in self.guilds:
            print(f'  - {guild.name}')
        print("\n📡 収集中のデータ:")
        print("  - VC共同参加ログ (voice_co_sessions)")
        print("  - パーティ同時プレイ (party_sessions)")
        print("  - メンション共起 (mention_logs)")
        print("\n使用可能なコマンド:")
        print("  !status  - 全メンバーのステータスを表示")
        print("  !debug   - ボットの設定を表示")
        print("  !whoami  - 自分の状態を確認")

    # ──────────────────────────────────────────────
    # デバッグコマンド（既存）
    # ──────────────────────────────────────────────
    def add_commands(self):
        """コマンドの明示的な追加"""

        @self.command(name='status')
        async def check_status(ctx):
            """全メンバーのステータスをチェック"""
            response = "サーバーメンバーのステータス:\n```"
            for member in ctx.guild.members:
                response += f"\n{member.name}:"
                response += f"\nステータス: {member.status}"
                if member.activity:
                    response += f"\nアクティビティ: {member.activity.name}"
                    response += f"\nタイプ: {member.activity.type}"
                else:
                    response += f"\nアクティビティ: なし"
                response += "\n"
            response += "```"
            await ctx.send(response)

        @self.command(name='debug')
        async def debug_info(ctx):
            """ボットの設定情報を表示"""
            response = "ボットの設定情報:\n```"
            response += f"Intents:\n"
            response += f"- presences: {self.intents.presences}\n"
            response += f"- members: {self.intents.members}\n"
            response += f"- message_content: {self.intents.message_content}\n"
            response += f"\n権限:\n"
            permissions = ctx.guild.me.guild_permissions
            for perm, value in permissions:
                if value:
                    response += f"- {perm}\n"
            response += "```"
            await ctx.send(response)

        @self.command(name='whoami')
        async def whoami(ctx):
            """自分の現在の状態を確認"""
            member = ctx.author
            response = f"あなたの情報:\n```"
            response += f"名前: {member.name}\n"
            response += f"ID: {member.id}\n"
            response += f"ステータス: {member.status}\n"
            if member.activity:
                response += f"アクティビティ: {member.activity.name}\n"
                response += f"アクティビティタイプ: {member.activity.type}\n"
            else:
                response += f"アクティビティ: なし\n"
            response += "```"
            await ctx.send(response)

    async def _log_activity_change(self, before, after):
        """アクティビティの変更をコンソールに記録"""
        if before.activity:
            print(f"前の活動: {before.activity.name} ({before.activity.type})")
        else:
            print("前の活動: なし")

        if after.activity:
            print(f"新しい活動: {after.activity.name} ({after.activity.type})")
        else:
            print("新しい活動: なし")