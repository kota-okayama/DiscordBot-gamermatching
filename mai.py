import os
from dotenv import load_dotenv
from calendar_bot import CalendarBot

# .envファイルから環境変数を読み込む
load_dotenv()

# ボットを実行
bot = CalendarBot()
bot.run(os.getenv('DISCORD_TOKEN'))