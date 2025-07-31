import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from collections import defaultdict

class ActivityCalendarBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.add_commands()

    def add_commands(self):
        @self.command(name='week')
        async def show_week_calendar(ctx, offset: int = 0):
            """一週間のアクティビティカレンダーを表示"""
            # 表示開始日を計算（offset週前から）
            start_date = datetime.now() - timedelta(days=datetime.now().weekday(), weeks=offset)
            end_date = start_date + timedelta(days=6)
            
            # データベースからアクティビティを取得
            activities = self.get_week_activities(ctx.author.id, start_date, end_date)
            
            # カレンダーを生成
            calendar = self.generate_calendar(start_date, activities)
            
            await ctx.send(f"{start_date.strftime('%Y年%m月%d日')}週のアクティビティ:\n{calendar}")

        @self.command(name='day')
        async def show_day_detail(ctx, date_str: str = None):
            """指定した日の詳細なアクティビティを表示"""
            try:
                if date_str:
                    target_date = datetime.strptime(date_str, '%Y-%m-%d')
                else:
                    target_date = datetime.now()
            except ValueError:
                await ctx.send("日付の形式が正しくありません。YYYY-MM-DD形式で指定してください。")
                return

            activities = self.get_day_activities(ctx.author.id, target_date)
            if not activities:
                await ctx.send(f"{target_date.strftime('%Y年%m月%d日')}のプレイ記録はありません。")
                return

            response = f"{target_date.strftime('%Y年%m月%d日')}のプレイ記録:\n```"
            for game, durations in activities.items():
                total_duration = sum(d['duration'] for d in durations)
                response += f"\n{game}:"
                for d in durations:
                    start = datetime.fromisoformat(d['start_time']).strftime('%H:%M')
                    end = datetime.fromisoformat(d['end_time']).strftime('%H:%M')
                    response += f"\n  {start}-{end} ({d['duration'] // 60}分)"
                response += f"\n  合計: {total_duration // 60}分\n"
            response += "```"
            await ctx.send(response)

    def get_week_activities(self, user_id: int, start_date: datetime, end_date: datetime):
        """週間のアクティビティを取得"""
        conn = sqlite3.connect('game_history.db')
        df = pd.read_sql_query('''
            SELECT game_name, start_time, end_time, duration
            FROM game_sessions
            WHERE user_id = ? 
            AND date(start_time) >= date(?)
            AND date(start_time) <= date(?)
        ''', conn, params=(str(user_id), start_date.isoformat(), end_date.isoformat()))
        conn.close()

        activities = defaultdict(list)
        for _, row in df.iterrows():
            start = datetime.fromisoformat(row['start_time'])
            activities[start.date()].append({
                'game': row['game_name'],
                'duration': row['duration']
            })
        return activities

    def get_day_activities(self, user_id: int, target_date: datetime):
        """一日のアクティビティ詳細を取得"""
        conn = sqlite3.connect('game_history.db')
        df = pd.read_sql_query('''
            SELECT game_name, start_time, end_time, duration
            FROM game_sessions
            WHERE user_id = ? 
            AND date(start_time) = date(?)
        ''', conn, params=(str(user_id), target_date.isoformat()))
        conn.close()

        activities = defaultdict(list)
        for _, row in df.iterrows():
            activities[row['game_name']].append({
                'start_time': row['start_time'],
                'end_time': row['end_time'],
                'duration': row['duration']
            })
        return activities

    def generate_calendar(self, start_date: datetime, activities: dict):
        """カレンダービューを生成"""
        weekdays = "月火水木金土日"
        calendar = "```\n"
        
        # ヘッダー
        calendar += "     " + " | ".join(f"{weekdays[i]}" for i in range(7)) + "\n"
        calendar += "-----+" + "--+".join("---" for _ in range(6)) + "---\n"
        
        # 時間帯ごとのビュー
        for hour in range(0, 24, 3):  # 3時間ごとに区切る
            calendar += f"{hour:02d}-{hour+3:02d}"
            
            current_date = start_date
            for _ in range(7):
                date_activities = activities.get(current_date.date(), [])
                hour_activities = [
                    a for a in date_activities
                    if any(h in range(hour, hour+3) 
                          for h in range(datetime.fromisoformat(a['start_time']).hour, 
                                     datetime.fromisoformat(a['end_time']).hour + 1))
                ]
                
                if hour_activities:
                    game_initial = hour_activities[0]['game'][0]
                    calendar += f" |{game_initial:^3}"
                else:
                    calendar += f" |   "
                current_date += timedelta(days=1)
            calendar += "\n"
        
        # 凡例
        calendar += "\n凡例:\n"
        all_games = set()
        for activities_list in activities.values():
            for activity in activities_list:
                all_games.add(activity['game'])
        for game in sorted(all_games):
            calendar += f"{game[0]}: {game}\n"
            
        calendar += "```"
        return calendar

    async def on_ready(self):
        print(f'{self.user} としてログインしました!')
        print('使用可能なコマンド:')
        print('!week [offset] - 週間カレンダーを表示')
        print('!day [YYYY-MM-DD] - 指定した日の詳細を表示')