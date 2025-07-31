import os
from dotenv import load_dotenv
from game_recommender_bot import GameRecommenderBot

# .envファイルから環境変数を読み込む
load_dotenv()

# ボットを実行
bot = GameRecommenderBot()
bot.run(os.getenv('DISCORD_TOKEN'))