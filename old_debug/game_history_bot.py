import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
import pandas as pd

class GameHistoryBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.active_sessions = {}  # 現在のゲームセッションを追跡
        self.add_commands()
        
    async def setup_hook(self):
        self.init_db()

    def init_db(self):
        """データベースの初期化"""
        conn = sqlite3.connect('game_history.db')
        c = conn.cursor()
        
        # ゲームセッション記録用のテーブル
        c.execute('''
            CREATE TABLE IF NOT EXISTS game_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                user_name TEXT,
                game_name TEXT,
                start_time TEXT,
                end_time TEXT,
                duration INTEGER,
                details TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_commands(self):
        @self.command(name='history')
        async def show_history(ctx, days: int = 7):
            """指定した日数分のプレイ履歴を表示"""
            conn = sqlite3.connect('game_history.db')
            df = pd.read_sql_query('''
                SELECT user_name, game_name, 
                       COUNT(*) as session_count,
                       SUM(duration) as total_duration
                FROM game_sessions
                WHERE datetime(start_time) > datetime('now', ?)
                GROUP BY user_name, game_name
                ORDER BY total_duration DESC
            ''', conn, params=(f'-{days} days',))
            conn.close()

            if df.empty:
                await ctx.send(f"過去{days}日間のプレイ記録はありません。")
                return

            response = f"過去{days}日間のプレイ記録:\n```"
            for _, row in df.iterrows():
                hours = row['total_duration'] / 3600
                response += f"\n{row['user_name']} - {row['game_name']}:\n"
                response += f"  セッション数: {row['session_count']}\n"
                response += f"  総プレイ時間: {hours:.1f}時間\n"
            response += "```"
            await ctx.send(response)

        @self.command(name='top')
        async def show_top_games(ctx, days: int = 7):
            """サーバーで人気のゲームを表示"""
            conn = sqlite3.connect('game_history.db')
            df = pd.read_sql_query('''
                SELECT game_name, 
                       COUNT(DISTINCT user_id) as player_count,
                       COUNT(*) as session_count,
                       SUM(duration) as total_duration
                FROM game_sessions
                WHERE datetime(start_time) > datetime('now', ?)
                GROUP BY game_name
                ORDER BY player_count DESC, total_duration DESC
                LIMIT 10
            ''', conn, params=(f'-{days} days',))
            conn.close()

            if df.empty:
                await ctx.send(f"過去{days}日間のプレイ記録はありません。")
                return

            response = f"過去{days}日間の人気ゲーム:\n```"
            for _, row in df.iterrows():
                hours = row['total_duration'] / 3600
                response += f"\n{row['game_name']}:\n"
                response += f"  プレイヤー数: {row['player_count']}人\n"
                response += f"  総セッション数: {row['session_count']}\n"
                response += f"  総プレイ時間: {hours:.1f}時間\n"
            response += "```"
            await ctx.send(response)

        @self.command(name='mygames')
        async def show_my_games(ctx, days: int = 7):
            """自分のプレイ統計を表示"""
            conn = sqlite3.connect('game_history.db')
            df = pd.read_sql_query('''
                SELECT game_name, 
                       COUNT(*) as session_count,
                       SUM(duration) as total_duration,
                       AVG(duration) as avg_duration
                FROM game_sessions
                WHERE user_id = ? AND datetime(start_time) > datetime('now', ?)
                GROUP BY game_name
                ORDER BY total_duration DESC
            ''', conn, params=(str(ctx.author.id), f'-{days} days'))
            conn.close()

            if df.empty:
                await ctx.send(f"過去{days}日間のプレイ記録はありません。")
                return

            response = f"あなたの過去{days}日間のプレイ記録:\n```"
            for _, row in df.iterrows():
                hours = row['total_duration'] / 3600
                avg_mins = row['avg_duration'] / 60
                response += f"\n{row['game_name']}:\n"
                response += f"  セッション数: {row['session_count']}\n"
                response += f"  総プレイ時間: {hours:.1f}時間\n"
                response += f"  平均セッション: {avg_mins:.1f}分\n"
            response += "```"
            await ctx.send(response)

    async def on_presence_update(self, before, after):
        """プレゼンス更新の検知とゲームセッションの記録"""
        # ゲーム開始の検知
        if after.activities:
            for activity in after.activities:
                if (activity.type == discord.ActivityType.playing and
                    (not before.activities or 
                     activity.name not in [a.name for a in before.activities])):
                    # 新しいゲームセッションを記録
                    self.active_sessions[(after.id, activity.name)] = {
                        'start_time': datetime.now(),
                        'details': activity.details if hasattr(activity, 'details') else None
                    }
                    print(f"ゲームセッション開始: {after.name} - {activity.name}")

        # ゲーム終了の検知
        if before.activities:
            for activity in before.activities:
                if (activity.type == discord.ActivityType.playing and
                    (not after.activities or 
                     activity.name not in [a.name for a in after.activities])):
                    # セッション情報を取得
                    session_info = self.active_sessions.get((before.id, activity.name))
                    if session_info:
                        end_time = datetime.now()
                        duration = (end_time - session_info['start_time']).seconds
                        
                        # データベースに記録
                        conn = sqlite3.connect('game_history.db')
                        c = conn.cursor()
                        c.execute('''
                            INSERT INTO game_sessions 
                            (user_id, user_name, game_name, start_time, end_time, duration, details)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            str(before.id),
                            before.name,
                            activity.name,
                            session_info['start_time'].isoformat(),
                            end_time.isoformat(),
                            duration,
                            session_info['details']
                        ))
                        conn.commit()
                        conn.close()
                        
                        # アクティブセッションから削除
                        del self.active_sessions[(before.id, activity.name)]
                        print(f"ゲームセッション終了: {before.name} - {activity.name} ({duration}秒)")

    async def on_ready(self):
        print(f'{self.user} としてログインしました!')
        print('使用可能なコマンド:')
        print('!history [日数] - サーバー全体のプレイ履歴を表示')
        print('!top [日数] - 人気のゲームを表示')
        print('!mygames [日数] - 自分のプレイ統計を表示')