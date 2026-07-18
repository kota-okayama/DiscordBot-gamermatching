"""HistoryCog: ゲームセッション記録・履歴コマンド"""
import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
import pandas as pd

DB_PATH = 'data/game_history.db'


class HistoryCog(commands.Cog, name='History'):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_sessions: dict = {}
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute('''CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, user_name TEXT, game_name TEXT,
            start_time TEXT, end_time TEXT, duration INTEGER, details TEXT
        )''')
        conn.commit()
        conn.close()
        print("✅ HistoryCog: DBテーブル初期化完了")

    @commands.Cog.listener()
    async def on_ready(self):
        now = datetime.now()
        conn = sqlite3.connect(DB_PATH, timeout=10)
        c = conn.cursor()
        
        # 1. DB上の未終了(NULL)セッションを読み込む
        c.execute('''
            SELECT id, user_id, game_name, start_time, details 
            FROM game_sessions 
            WHERE end_time IS NULL
        ''')
        null_sessions = c.fetchall()
        db_active = {}
        for row in null_sessions:
            db_active[(str(row[1]), row[2])] = {
                'id': row[0],
                'start_time': datetime.fromisoformat(row[3]),
                'details': row[4]
            }

        # 2. 現在Discord上でプレイ中のゲームを取得
        current_playing = {}
        for guild in self.bot.guilds:
            for member in guild.members:
                for activity in member.activities:
                    if activity.type == discord.ActivityType.playing:
                        current_playing[(str(member.id), activity.name)] = {
                            'member': member,
                            'activity': activity
                        }

        # 3. 状態の照合
        for key, data in current_playing.items():
            member, activity = data['member'], data['activity']
            if key in db_active:
                # 既にDBにNULLで存在するので継続
                self.active_sessions[(member.id, activity.name)] = db_active[key]
                print(f"🎮 [復元] ゲームプレイ継続中: {member.name} - {activity.name}")
                del db_active[key]
            else:
                # 新規開始
                details = getattr(activity, 'details', None)
                c.execute('''
                    INSERT INTO game_sessions
                    (user_id, user_name, game_name, start_time, end_time, duration, details)
                    VALUES (?, ?, ?, ?, NULL, 0, ?)
                ''', (str(member.id), member.name, activity.name, now.isoformat(), details))
                self.active_sessions[(member.id, activity.name)] = {
                    'start_time': now,
                    'id': c.lastrowid,
                    'details': details
                }
                print(f"🎮 [新規] ゲームプレイ開始: {member.name} - {activity.name}")

        # 4. DBにはNULLで残っているが、現在はもうプレイしていないセッションを閉じる
        for key, session_data in db_active.items():
            duration = int((now - session_data['start_time']).total_seconds())
            c.execute('''
                UPDATE game_sessions
                SET end_time=?, duration=?
                WHERE id=?
            ''', (now.isoformat(), duration, session_data['id']))
            print(f"🧹 [クリーンアップ] オフライン中に終了: {key[0]} - {key[1]} ({duration}秒)")
            
        conn.commit()
        conn.close()
        print("✅ HistoryCog: 起動時セッション処理完了")

    async def cog_unload(self):
        # 以前のように強制的にend_timeを書き込む処理は廃止。
        # DB上はNULLのまま残し、次回on_readyで復元またはクリーンアップする。
        print("🛑 HistoryCog: 終了（セッション状態はDBに保持）")

    # ── プレゼンス監視（ゲームセッション記録） ─────────
    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        # ゲーム開始
        if after.activities:
            for activity in after.activities:
                if activity.type == discord.ActivityType.playing:
                    if (after.id, activity.name) in self.active_sessions:
                        continue
                    
                    if (not before.activities or activity.name not in [a.name for a in before.activities]):
                        now = datetime.now()
                        details = getattr(activity, 'details', None)
                        
                        conn = sqlite3.connect(DB_PATH, timeout=10)
                        c = conn.cursor()
                        c.execute('''
                            INSERT INTO game_sessions
                            (user_id, user_name, game_name, start_time, end_time, duration, details)
                            VALUES (?, ?, ?, ?, NULL, 0, ?)
                        ''', (str(after.id), after.name, activity.name, now.isoformat(), details))
                        conn.commit()
                        
                        self.active_sessions[(after.id, activity.name)] = {
                            'start_time': now,
                            'id': c.lastrowid,
                            'details': details
                        }
                        conn.close()
                        print(f"🎮 ゲーム開始: {after.name} - {activity.name}")

        # ゲーム終了
        if before.activities:
            for activity in before.activities:
                if (activity.type == discord.ActivityType.playing and
                        (not after.activities or activity.name not in [a.name for a in after.activities])):
                    session = self.active_sessions.pop((before.id, activity.name), None)
                    if not session:
                        continue
                    
                    end_time = datetime.now()
                    duration = int((end_time - session['start_time']).total_seconds())
                    
                    conn = sqlite3.connect(DB_PATH, timeout=10)
                    conn.execute('''
                        UPDATE game_sessions
                        SET end_time=?, duration=?
                        WHERE id=?
                    ''', (end_time.isoformat(), duration, session['id']))
                    conn.commit()
                    conn.close()
                    print(f"💾 ゲーム終了: {before.name} - {activity.name} ({duration}秒)")

    # ── コマンド ──────────────────────────────────────
    @commands.command(name='history')
    async def show_history(self, ctx, days: int = 7):
        """サーバー全体のプレイ履歴を表示"""
        conn = sqlite3.connect(DB_PATH, timeout=10)
        df = pd.read_sql_query('''
            SELECT user_name, game_name,
                   COUNT(*) as session_count, SUM(duration) as total_duration
            FROM game_sessions
            WHERE datetime(start_time) > datetime('now', ?)
            GROUP BY user_name, game_name ORDER BY total_duration DESC
        ''', conn, params=(f'-{days} days',))
        conn.close()
        if df.empty:
            await ctx.send(f"過去{days}日間のプレイ記録はありません。")
            return
        lines = [f"過去{days}日間のプレイ記録:\n```"]
        for _, row in df.iterrows():
            hours = row['total_duration'] / 3600
            lines.append(f"{row['user_name']} - {row['game_name']}: {hours:.1f}h ({row['session_count']}回)")
        lines.append("```")
        await ctx.send('\n'.join(lines))

    @commands.command(name='top')
    async def show_top_games(self, ctx, days: int = 7):
        """サーバーで人気のゲームを表示"""
        conn = sqlite3.connect(DB_PATH, timeout=10)
        df = pd.read_sql_query('''
            SELECT game_name, COUNT(DISTINCT user_id) as player_count,
                   COUNT(*) as session_count, SUM(duration) as total_duration
            FROM game_sessions WHERE datetime(start_time) > datetime('now', ?)
            GROUP BY game_name ORDER BY player_count DESC, total_duration DESC LIMIT 10
        ''', conn, params=(f'-{days} days',))
        conn.close()
        if df.empty:
            await ctx.send(f"過去{days}日間のプレイ記録はありません。")
            return
        lines = [f"過去{days}日間の人気ゲーム:\n```"]
        for _, row in df.iterrows():
            hours = row['total_duration'] / 3600
            lines.append(f"{row['game_name']}: {row['player_count']}人 / {hours:.1f}h")
        lines.append("```")
        await ctx.send('\n'.join(lines))

    @commands.command(name='mygames')
    async def show_my_games(self, ctx, days: int = 7):
        """自分のプレイ統計を表示"""
        conn = sqlite3.connect(DB_PATH, timeout=10)
        df = pd.read_sql_query('''
            SELECT game_name, COUNT(*) as session_count,
                   SUM(duration) as total_duration, AVG(duration) as avg_duration
            FROM game_sessions
            WHERE user_id=? AND datetime(start_time) > datetime('now', ?)
            GROUP BY game_name ORDER BY total_duration DESC
        ''', conn, params=(str(ctx.author.id), f'-{days} days'))
        conn.close()
        if df.empty:
            await ctx.send(f"過去{days}日間のプレイ記録はありません。")
            return
        lines = [f"あなたの過去{days}日間:\n```"]
        for _, row in df.iterrows():
            h = row['total_duration'] / 3600
            avg_m = row['avg_duration'] / 60
            lines.append(f"{row['game_name']}: {h:.1f}h / 平均{avg_m:.0f}分 ({row['session_count']}回)")
        lines.append("```")
        await ctx.send('\n'.join(lines))

    @commands.command(name='dummy_history')
    async def dummy_history(self, ctx):
        """[ダミーデータ] プレイ履歴を表示"""
        lines = ["過去7日間のプレイ記録 [ダミーデータ]:\n```",
                 "kurara_ra - Valorant: 24.5h (12回)",
                 "test_gamer - Minecraft: 18.2h (6回)",
                 "pro_player - Apex Legends: 15.0h (8回)",
                 "kurara_ra - Escape from Tarkov: 10.5h (5回)",
                 "user123 - Genshin Impact: 8.0h (4回)",
                 "```"]
        await ctx.send('\n'.join(lines))

    @commands.command(name='dummy_top')
    async def dummy_top(self, ctx):
        """[ダミーデータ] 人気ゲームを表示"""
        lines = ["過去7日間の人気ゲーム [ダミーデータ]:\n```",
                 "Valorant: 15人 / 120.5h",
                 "Apex Legends: 12人 / 95.0h",
                 "Minecraft: 8人 / 45.2h",
                 "Genshin Impact: 5人 / 30.0h",
                 "Escape from Tarkov: 3人 / 25.5h",
                 "```"]
        await ctx.send('\n'.join(lines))

    @commands.command(name='dummy_mygames')
    async def dummy_mygames(self, ctx):
        """[ダミーデータ] 自分のプレイ統計を表示"""
        lines = [f"あなたの過去7日間 [ダミーデータ]:\n```",
                 "Valorant: 12.5h / 平均120分 (6回)",
                 "Apex Legends: 8.0h / 平均90分 (5回)",
                 "Minecraft: 4.5h / 平均135分 (2回)",
                 "```"]
        await ctx.send('\n'.join(lines))
