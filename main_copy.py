import os
from dotenv import load_dotenv
from game_history_bot import GameHistoryBot

# .envファイルから環境変数を読み込む
load_dotenv()

# ボットを実行
bot = GameHistoryBot()
bot.run(os.getenv('DISCORD_TOKEN'))