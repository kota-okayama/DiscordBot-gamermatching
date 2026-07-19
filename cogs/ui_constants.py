"""表示用記号・ログタグ定数。

Botの返信・embedで使う記号と、printログ用ブラケットタグをここに集約する。
将来アプリ所有絵文字へ差し替える場合も、このモジュールだけを変更すればよい。
"""

# ユーザー向け表示（コマンド返信・embed）
# embedタイトルには記号を付けない（カラーで区別する）
ICON_FIELD = "▸ "        # 旧: 👤 / 🎮 / 🏆 等（add_field の name 先頭）
ICON_BULLET = "• "       # 旧: 🎮 等（フィールド内リスト項目）

# ログ出力用（grepしやすいブラケットタグ）
LOG_OK = "[OK]"          # 旧: ✅
LOG_GAME = "[GAME]"      # 旧: 🎮
LOG_VC = "[VC]"          # 旧: 🎙️
LOG_SAVE = "[SAVE]"      # 旧: 💾
LOG_CLEAN = "[CLEAN]"    # 旧: 🧹
LOG_STOP = "[STOP]"      # 旧: 🛑
LOG_MENTION = "[MENTION]"  # 旧: 📢
