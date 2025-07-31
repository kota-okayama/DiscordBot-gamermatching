import os
from dotenv import load_dotenv
from ml_game_matcher import GameTrackerBot

# .envファイルから環境変数を読み込む
load_dotenv()

# ボットのセットアップと実行
bot = GameTrackerBot()

try:
    bot.run(os.getenv('DISCORD_TOKEN'))
except Exception as e:
    print(f"エラーが発生しました: {e}")