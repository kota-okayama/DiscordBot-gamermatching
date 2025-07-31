import tkinter as tk
from tkinter import ttk
import asyncio
import os
from dotenv import load_dotenv
from calendar_bot import CalendarBot
from game_history_bot import GameHistoryBot
from game_recommender_bot import GameRecommenderBot
import threading

class BotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Discord Bot Controller")
        
        # ボットの状態
        self.bots_running = False
        
        # メインフレーム
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # ステータス表示
        self.status_label = ttk.Label(self.main_frame, text="ステータス: 停止中")
        self.status_label.grid(row=0, column=0, columnspan=2, pady=5)
        
        # 起動/停止ボタン
        self.start_button = ttk.Button(self.main_frame, text="ボットを起動", command=self.toggle_bots)
        self.start_button.grid(row=1, column=0, pady=5)
        
        # ログ表示エリア
        self.log_area = tk.Text(self.main_frame, height=10, width=50)
        self.log_area.grid(row=2, column=0, columnspan=2, pady=5)
        
        # スクロールバー
        scrollbar = ttk.Scrollbar(self.main_frame, command=self.log_area.yview)
        scrollbar.grid(row=2, column=2, sticky=(tk.N, tk.S))
        self.log_area.configure(yscrollcommand=scrollbar.set)
        
        # コマンド一覧
        commands_frame = ttk.LabelFrame(self.main_frame, text="使用可能なコマンド", padding="5")
        commands_frame.grid(row=3, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        
        commands = [
            "!calendar - 週間プレイカレンダーを表示",
            "!stats - プレイ統計を表示",
            "!similar - 似たプレイヤーを探す",
            "!recommend - ゲーム推薦を表示"
        ]
        
        for i, cmd in enumerate(commands):
            ttk.Label(commands_frame, text=cmd).grid(row=i, column=0, sticky=tk.W)

    def toggle_bots(self):
        """ボットの起動/停止を切り替え"""
        if not self.bots_running:
            self.start_bots()
        else:
            self.stop_bots()

    def start_bots(self):
        """ボットを起動"""
        self.bots_running = True
        self.start_button.configure(text="ボットを停止")
        self.status_label.configure(text="ステータス: 実行中")
        self.log_message("ボットを起動中...")
        
        # 別スレッドでボットを起動
        threading.Thread(target=self.run_bots, daemon=True).start()

    def stop_bots(self):
        """ボットを停止"""
        self.bots_running = False
        self.start_button.configure(text="ボットを起動")
        self.status_label.configure(text="ステータス: 停止中")
        self.log_message("ボットを停止中...")

    def run_bots(self):
        """ボットを実行"""
        try:
            # 環境変数の読み込み
            load_dotenv()
            TOKEN = os.getenv('DISCORD_TOKEN')
            
            # ボットのインスタンスを作成
            calendar_bot = CalendarBot()
            history_bot = GameHistoryBot()
            recommender_bot = GameRecommenderBot()
            
            # ログ出力をGUIに転送
            def log_handler(message):
                self.log_message(str(message))
            
            # ボットにログハンドラを設定
            calendar_bot.log_callback = log_handler
            history_bot.log_callback = log_handler
            recommender_bot.log_callback = log_handler
            
            # イベントループの取得と実行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # ボットの実行
            loop.run_until_complete(asyncio.gather(
                calendar_bot.start(TOKEN),
                history_bot.start(TOKEN),
                recommender_bot.start(TOKEN)
            ))
            
        except Exception as e:
            self.log_message(f"エラーが発生しました: {str(e)}")
            self.bots_running = False
            self.root.after(0, self.update_status_stopped)

    def update_status_stopped(self):
        """UI更新（メインスレッドで実行）"""
        self.start_button.configure(text="ボットを起動")
        self.status_label.configure(text="ステータス: エラーで停止")

    def log_message(self, message):
        """ログメッセージを表示"""
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)  # 最新のメッセージまでスクロール

if __name__ == "__main__":
    root = tk.Tk()
    app = BotGUI(root)
    root.mainloop()