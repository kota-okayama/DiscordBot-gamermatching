import os
import asyncio
from dotenv import load_dotenv
from calendar_bot import CalendarBot
from game_history_bot import GameHistoryBot
from game_recommender_bot import GameRecommenderBot
from game_profile_bot import GameProfileBot

async def main():
    # 環境変数の読み込み
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    # ボットのインスタンスを作成
    calendar_bot = CalendarBot()
    history_bot = GameHistoryBot()
    recommender_bot = GameRecommenderBot()
    profile_bot = GameProfileBot()

    # 非同期でボットを実行
    await asyncio.gather(
        calendar_bot.start(TOKEN),
        history_bot.start(TOKEN),
        recommender_bot.start(TOKEN),
        profile_bot.start(TOKEN)
    )

# スクリプトを実行
if __name__ == "__main__":
    asyncio.run(main())