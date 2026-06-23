"""ProfileCog: ゲームプロフィール表示"""
import discord
from discord.ext import commands
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # GUIなし環境向け
import matplotlib.pyplot as plt
import io

DB_PATH = 'game_history.db'


class ProfileCog(commands.Cog, name='Profile'):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='profile')
    async def show_profile(self, ctx, member: discord.Member = None):
        """ゲームプロフィールを表示"""
        target = member or ctx.author
        profile = self._get_profile(target.id)

        if not profile:
            await ctx.send(embed=discord.Embed(
                title="😅 プロフィールなし",
                description="プレイ記録が見つかりませんでした。",
                color=discord.Color.orange()))
            return

        embed = discord.Embed(
            title=f"📊 {target.display_name} のゲームプロフィール",
            color=discord.Color.purple())

        favs = '\n'.join(
            f"🎮 {game}: {dur/3600:.1f}時間"
            for game, dur in profile['favorites']
        ) or 'データなし'
        embed.add_field(name="🏆 お気に入りゲーム", value=favs, inline=False)

        if profile['hours']:
            fig, ax = plt.subplots(figsize=(10, 4))
            hours  = [int(h[0]) for h in profile['hours']]
            counts = [h[1] for h in profile['hours']]
            ax.bar(hours, counts, color='#6464e8', alpha=0.8)
            ax.set_title('Distribution of Playing Time')
            ax.set_xlabel('Hour of Day')
            ax.set_ylabel('Session Count')
            ax.set_xticks(range(0, 24, 2))
            ax.set_xlim(-0.5, 23.5)
            ax.grid(True, alpha=0.3)
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            plt.close(fig)

            file = discord.File(buf, filename='profile.png')
            embed.set_image(url='attachment://profile.png')
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

    def _get_profile(self, user_id: int):
        conn = sqlite3.connect(DB_PATH)
        favs = pd.read_sql_query('''
            SELECT game_name, SUM(duration) as total
            FROM game_sessions WHERE user_id=?
            GROUP BY game_name ORDER BY total DESC LIMIT 5
        ''', conn, params=(str(user_id),))
        hours = pd.read_sql_query('''
            SELECT strftime('%H', start_time) as hour, COUNT(*) as count
            FROM game_sessions WHERE user_id=?
            GROUP BY hour ORDER BY count DESC
        ''', conn, params=(str(user_id),))
        conn.close()
        if favs.empty:
            return None
        return {
            'favorites': favs[['game_name', 'total']].values.tolist(),
            'hours': hours[['hour', 'count']].values.tolist(),
        }
