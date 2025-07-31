import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timedelta

class GameRecommenderBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.add_commands()

    def add_commands(self):
        @self.command(name='similar')
        async def find_similar_players(ctx, days: int = 30):
            try:
                conn = sqlite3.connect('game_history.db')
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT game_name, SUM(duration) as total_time
                    FROM game_sessions
                    WHERE user_id = ? AND datetime(start_time) > datetime('now', ?)
                    GROUP BY game_name
                ''', (str(ctx.author.id), f'-{days} days'))

                user_games = {row[0]: row[1] for row in cursor.fetchall()}

                if not user_games:
                    embed = discord.Embed(
                        title="プレイ記録なし",
                        description=f"過去{days}日間のプレイ記録が見つかりませんでした。",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=embed)
                    return

                similar_users = []
                cursor.execute('SELECT DISTINCT user_id FROM game_sessions WHERE datetime(start_time) > datetime("now", ?)', (f'-{days} days',))

                for (other_id,) in cursor.fetchall():
                    if other_id == str(ctx.author.id):
                        continue

                    cursor.execute('''
                        SELECT game_name, SUM(duration) as total_time
                        FROM game_sessions
                        WHERE user_id = ? AND datetime(start_time) > datetime('now', ?)
                        GROUP BY game_name
                    ''', (other_id, f'-{days} days'))

                    other_games = {row[0]: row[1] for row in cursor.fetchall()}
                    common_games = set(user_games.keys()) & set(other_games.keys())

                    if common_games:
                        game_ratio = len(common_games) / len(user_games)

                        time_similarities = []
                        for game in common_games:
                            user_time = user_games[game]
                            other_time = other_games[game]
                            time_ratio = min(user_time, other_time) / max(user_time, other_time)
                            time_similarities.append(time_ratio)

                        time_similarity = sum(time_similarities) / len(time_similarities) if time_similarities else 0

                        cursor.execute('''
                            SELECT strftime('%H', start_time) as hour, COUNT(*) as count
                            FROM game_sessions
                            WHERE user_id = ? AND datetime(start_time) > datetime('now', ?)
                            GROUP BY hour
                        ''', (str(ctx.author.id), f'-{days} days'))
                        user_schedule = {row[0]: row[1] for row in cursor.fetchall()}

                        cursor.execute('''
                            SELECT strftime('%H', start_time) as hour, COUNT(*) as count
                            FROM game_sessions
                            WHERE user_id = ? AND datetime(start_time) > datetime('now', ?)
                            GROUP BY hour
                        ''', (other_id, f'-{days} days'))
                        other_schedule = {row[0]: row[1] for row in cursor.fetchall()}

                        total_hours = set(user_schedule.keys()) | set(other_schedule.keys())
                        schedule_similarity = 0
                        if total_hours:
                            matches = 0
                            for hour in total_hours:
                                user_count = user_schedule.get(hour, 0)
                                other_count = other_schedule.get(hour, 0)
                                if user_count > 0 and other_count > 0:
                                    matches += 1
                            schedule_similarity = matches / len(total_hours)

                        similarity = (
                            game_ratio * 0.25 +
                            time_similarity * 0.25 +
                            schedule_similarity * 0.25 +
                            (1 - abs(len(other_games) - len(user_games)) / max(len(other_games), len(user_games))) * 0.25
                        )
                        
                        similar_users.append((other_id, similarity, list(common_games)))

                if not similar_users:
                    embed = discord.Embed(
                        title="類似ユーザーなし",
                        description="類似したプレイヤーが見つかりませんでした。",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=embed)
                    return

                similar_users.sort(key=lambda x: x[1], reverse=True)

                embed = discord.Embed(
                    title="似たようなプレイヤー",
                    description=f"{ctx.author.name}さんと遊び方が似ているプレイヤーを見つけました！",
                    color=discord.Color.blue()
                )

                for user_id, similarity, common_games in similar_users[:5]:
                    member = ctx.guild.get_member(int(user_id))
                    if member:
                        match_percentage = int(similarity * 100)
                        progress_bar = self.create_progress_bar(match_percentage)

                        field_value = f"マッチ度: {progress_bar} {match_percentage}%\n"
                        field_value += f"共通のゲーム: {', '.join(common_games)}"

                        embed.add_field(
                            name=f"👤 {member.name}",
                            value=field_value,
                            inline=False
                        )

                await ctx.send(embed=embed)

            except Exception as e:
                print(f"Error in similar command: {e}")
                await ctx.send("エラーが発生しました。")
            finally:
                conn.close()

        @self.command(name='recommend')
        async def recommend_games(ctx, days: int = 30):
            """ゲームを推薦する"""
            try:
                conn = sqlite3.connect('game_history.db')
                cursor = conn.cursor()

                # 自分のプレイしたゲームを取得
                cursor.execute('''
                    SELECT DISTINCT game_name
                    FROM game_sessions
                    WHERE user_id = ? AND datetime(start_time) > datetime('now', ?)
                ''', (str(ctx.author.id), f'-{days} days'))
                
                user_games = [row[0] for row in cursor.fetchall()]

                if not user_games:
                    embed = discord.Embed(
                        title="😅 プレイ記録なし",
                        description=f"過去{days}日間のプレイ記録が不足しているため、推薦できません。",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=embed)
                    return

                # 他のユーザーがプレイしているゲームを集計
                cursor.execute('''
                    SELECT 
                        game_name, 
                        COUNT(DISTINCT user_id) as player_count,
                        SUM(duration) as total_playtime
                    FROM game_sessions
                    WHERE datetime(start_time) > datetime('now', ?)
                    AND game_name NOT IN (
                        SELECT DISTINCT game_name
                        FROM game_sessions
                        WHERE user_id = ? AND datetime(start_time) > datetime('now', ?)
                    )
                    GROUP BY game_name
                    ORDER BY player_count DESC, total_playtime DESC
                ''', (f'-{days} days', str(ctx.author.id), f'-{days} days'))

                recommendations = cursor.fetchall()

                if not recommendations:
                    embed = discord.Embed(
                        title="😅 推薦なし",
                        description="新しく推薦できるゲームが見つかりませんでした。",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=embed)
                    return

                embed = discord.Embed(
                    title="🎯 おすすめのゲーム",
                    description=f"{ctx.author.name}さんにおすすめのゲームをご紹介します！",
                    color=discord.Color.green()
                )

                total_players = sum(count for _, count, _ in recommendations)
                
                for game, count, playtime in recommendations[:5]:
                    popularity = (count / total_players) * 100
                    progress_bar = self.create_progress_bar(int(popularity))
                    avg_playtime = playtime / (count * 3600)  # Convert to hours
                    
                    field_value = f"人気度: {progress_bar} {count}人がプレイ中\n"
                    field_value += f"平均プレイ時間: {avg_playtime:.1f}時間"
                    
                    embed.add_field(
                        name=f"🎮 {game}",
                        value=field_value,
                        inline=False
                    )

                embed.set_footer(text="※ スコアは他のプレイヤーの人数とプレイ時間から計算しています")
                await ctx.send(embed=embed)

            except Exception as e:
                print(f"Error in recommend command: {e}")
                await ctx.send("エラーが発生しました。")
            finally:
                conn.close()

    def create_progress_bar(self, percentage, length=10):
        filled = int(length * percentage / 100)
        empty = length - filled
        return '█' * filled + '▒' * empty

    async def on_ready(self):
        print(f'{self.user} としてログインしました!')
        print('使用可能なコマンド:')
        print('!similar [日数] - 似たようなプレイヤーを探す')
        print('!recommend [日数] - ゲームを推薦する')