import os
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands


def load_token() -> str:
    """Docker Secrets のファイルを優先し、なければ .env から読み込む。"""
    # Docker Secrets: /run/secrets/discord_token にマウントされる
    secret_file = os.getenv('DISCORD_TOKEN_FILE', '/run/secrets/discord_token')
    if os.path.exists(secret_file):
        with open(secret_file, 'r') as f:
            token = f.read().strip()
        if token:
            return token

    # フォールバック: ローカル開発用 .env
    load_dotenv()
    token = os.getenv('DISCORD_TOKEN')
    if token:
        return token

    raise ValueError(
        "Discord トークンが見つかりません。\n"
        "本番環境: `docker secret create discord_token` でシークレットを登録してください。\n"
        "開発環境: .env に DISCORD_TOKEN を設定してください。"
    )

# 各機能モジュールをCogとしてインポート
from cogs.tracker_cog   import TrackerCog    # VC・Party・メンション収集
from cogs.history_cog   import HistoryCog    # ゲームセッション記録・!history etc
from cogs.recommender_cog import RecommenderCog  # !similar / !recommend
from cogs.calendar_cog  import CalendarCog   # !calendar
from cogs.profile_cog   import ProfileCog    # !profile

async def main():
    TOKEN = load_token()

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