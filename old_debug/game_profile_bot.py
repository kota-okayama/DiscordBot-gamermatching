import os
import asyncio
from dotenv import load_dotenv
from discord.ext import commands
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import io
import discord

class GameProfileBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='!', intents=intents)
        self.add_commands()

    def add_commands(self):
        @self.command(name='profile')
        async def show_profile(ctx, member: discord.Member = None):
            """ゲームプロフィールを表示"""
            target = member or ctx.author
            profile = self.get_user_profile(target.id)
            if not profile:
                embed = discord.Embed(
                    title="😅 プロフィルなし",
                    description="プレイ記録が見つかりませんでした。",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                return

            embed = discord.Embed(
                title=f"📊 {target.name}のゲームプロフィール",
                color=discord.Color.purple()
            )

            favorites_text = ""
            for game, duration in profile['favorites']:
                hours = duration / 3600
                favorites_text += f"🎮 {game}: {hours:.1f}時間\n"
            embed.add_field(
                name="🏆 お気に入りのゲーム",
                value=favorites_text or "データなし",
                inline=False
            )

            if profile['hours']:
                plt.figure(figsize=(10, 4))
                hours = [int(h[0]) for h in profile['hours']]
                counts = [h[1] for h in profile['hours']]
                plt.bar(hours, counts, color='purple', alpha=0.6)
                plt.title('Distribution of Playing Time')
                plt.xlabel('Playing Time')
                plt.ylabel('Play Count')
                plt.xticks(range(0, 24, 2))  # 2時間ごとに目盛りを表示
                plt.xlim(-0.5, 23.5)  # x軸の範囲を0-23に調整
                plt.grid(True, alpha=0.3)

                buf = io.BytesIO()
                plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
                buf.seek(0)
                plt.close()

                file = discord.File(buf, filename='playtime_distribution.png')
                embed.set_image(url='attachment://playtime_distribution.png')
                
                await ctx.send(file=file, embed=embed)
            else:
                await ctx.send(embed=embed)

    def get_user_profile(self, user_id: int):
        """ユーザーのゲームプロフィールを取得"""
        conn = sqlite3.connect('game_history.db')

        # お気に入りのゲーム
        favorites = pd.read_sql_query('''
            SELECT game_name, SUM(duration) as total_duration
            FROM game_sessions
            WHERE user_id = ?
            GROUP BY game_name
            ORDER BY total_duration DESC
            LIMIT 5
        ''', conn, params=(str(user_id),))

        # プレイ時間帯
        hours = pd.read_sql_query('''
            SELECT strftime('%H', start_time) as hour, COUNT(*) as count
            FROM game_sessions
            WHERE user_id = ?
            GROUP BY hour
            ORDER BY count DESC
        ''', conn, params=(str(user_id),))

        conn.close()

        if favorites.empty:
            return None

        return {
            'favorites': favorites[['game_name', 'total_duration']].values.tolist(),
            'hours': hours[['hour', 'count']].values.tolist(),
            'genres': []  # ゲームのジャンル情報がある場合はここに追加
        }

    async def on_ready(self):
        print(f'{self.user} としてログインしました!')
        print('使用可能なコマンド:')
        print('!profile [メンバー] - ゲームプロフィールを表示')