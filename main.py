import os
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands

# 各機能モジュールをCogとしてインポート
from cogs.tracker_cog   import TrackerCog    # VC・Party・メンション収集
from cogs.history_cog   import HistoryCog    # ゲームセッション記録・!history etc
from cogs.recommender_cog import RecommenderCog  # !similar / !recommend
from cogs.calendar_cog  import CalendarCog   # !calendar
from cogs.profile_cog   import ProfileCog    # !profile

async def main():
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN が .env に設定されていません")

    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix='!', intents=intents)

    # 全機能を1つのBotにCogとして追加
    await bot.add_cog(TrackerCog(bot))
    await bot.add_cog(HistoryCog(bot))
    await bot.add_cog(RecommenderCog(bot))
    await bot.add_cog(CalendarCog(bot))
    await bot.add_cog(ProfileCog(bot))

    @bot.event
    async def on_ready():
        print(f'✅ {bot.user} としてログインしました!')
        print(f'参加サーバー数: {len(bot.guilds)}')
        for g in bot.guilds:
            print(f'  - {g.name}')
        print('\n📡 収集中: VC共同参加 / パーティプレイ / メンション')
        print('💬 コマンド: !calendar / !similar / !recommend / !mygames / !profile')

    await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nボットを停止しました")
    except Exception as e:
        print(f"エラー: {e}")