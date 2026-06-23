"""HistoryCog: ゲームセッション記録・履歴コマンド"""
import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
import pandas as pd

DB_PATH = 'game_history.db'


class HistoryCog(commands.Cog, name='History'):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_sessions: dict = {}
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, user_name TEXT, game_name TEXT,
            start_time TEXT, end_time TEXT, duration INTEGER, details TEXT
        )''')
        conn.commit()
        conn.close()
        print("✅ HistoryCog: DBテーブル初期化完了")

    # ── プレゼンス監視（ゲームセッション記録） ─────────
    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        # ゲーム開始
        if after.activities:
            for activity in after.activities:
                if (activity.type == discord.ActivityType.playing and
                        (not before.activities or
                         activity.name not in [a.name for a in before.activities])):
                    self.active_sessions[(after.id, activity.name)] = {
                        'start_time': datetime.now(),
                        'details': getattr(activity, 'details', None)
                    }
                    print(f"🎮 ゲーム開始: {after.name} - {activity.name}")

        # ゲーム終了
        if before.activities:
            for activity in before.activities:
                if (activity.type == discord.ActivityType.playing and
                        (not after.activities or
                         activity.name not in [a.name for a in after.activities])):
                    session = self.active_sessions.pop((before.id, activity.name), None)
                    if not session:
                        continue
                    end_time = datetime.now()
                    duration = int((end_time - session['start_time']).total_seconds())
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute('''
                        INSERT INTO game_sessions
                        (user_id, user_name, game_name, start_time, end_time, duration, details)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (str(before.id), before.name, activity.name,
                          session['start_time'].isoformat(), end_time.isoformat(),
                          duration, session['details']))
                    conn.commit()
                    conn.close()
                    print(f"💾 ゲーム終了: {before.name} - {activity.name} ({duration}秒)")

    # ── コマンド ──────────────────────────────────────
    @commands.command(name='history')
    async def show_history(self, ctx, days: int = 7):
        """サーバー全体のプレイ履歴を表示"""
        conn = sqlite3.connect(DB_PATH)
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
        conn = sqlite3.connect(DB_PATH)
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
        conn = sqlite3.connect(DB_PATH)
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
