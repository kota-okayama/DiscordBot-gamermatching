# Discord Bot - Gamer Matching System

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Discord.py](https://img.shields.io/badge/Discord.py-2.3+-5865F2?style=flat-square&logo=discord&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Bot](https://img.shields.io/badge/Discord-Bot-7289DA?style=flat-square&logo=discord&logoColor=white)

## 📖 概要

Discord Bot - Gamer Matching Systemは、Discordサーバー内でゲーマー同士のマッチングを支援するBotです。ゲームプレイ履歴を自動追跡し、類似のゲーム嗜好を持つユーザーを見つけて推薦します。

## ✨ 主な機能

- **自動ゲーム履歴追跡** - Discordのアクティビティから自動でゲームプレイを記録
- **類似ユーザー検索** - プレイ履歴に基づいた類似ユーザーの発見
- **ゲーム推薦システム** - 他のユーザーがプレイしているゲームの推薦
- **統計機能** - プレイ時間、人気ゲームなどの統計表示
- **カレンダー機能** - ゲームイベントのスケジュール管理
- **機械学習マッチング** - AIによる高精度なユーザーマッチング

## 🛠️ 技術スタック

- **言語**: Python 3.10+
- **フレームワーク**: Discord.py 2.3+
- **データベース**: SQLite3
- **機械学習**: scikit-learn（類似度計算）
- **GUI**: tkinter（管理画面）

## 📁 プロジェクト構造

```
discord-bot-matching/
├── game_recommender_bot.py         # メインのBot機能
├── activity_calendar_bot.py        # カレンダー・イベント機能
├── calendar_bot.py                 # 詳細カレンダー機能
├── game_history_bot.py             # ゲーム履歴追跡
├── game_profile_bot.py             # ユーザープロフィール管理
├── ml_game_matcher.py              # 機械学習マッチング
├── bot_gui.py                      # GUI管理ツール
├── main.py                         # Bot起動スクリプト
├── test.py                         # テスト・デバッグ用
├── requirements.txt                # Python依存関係
└── game_activity_calendar.jsx       # React カレンダーコンポーネント
```

## 🚀 セットアップ方法

### 前提条件

- Python 3.10以上
- Discord Bot Token
- Discordサーバーの管理者権限

### インストール手順

1. **リポジトリのクローン**
   ```bash
   git clone git@github.com:kota-okayama/DiscordBot-gamermatching.git
   cd DiscordBot-gamermatching
   ```

2. **仮想環境の作成**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # または
   venv\Scripts\activate     # Windows
   ```

3. **依存パッケージのインストール**
   ```bash
   pip install -r requirements.txt
   ```

4. **Discord Bot Tokenの設定**
   ```bash
   # .envファイルを作成
   echo "DISCORD_TOKEN=your_bot_token_here" > .env
   ```

   Discord Bot Tokenは[Discord Developer Portal](https://discord.com/developers/applications)から取得してください。

5. **Bot権限の設定**
   
   必要な権限：
   - `Read Messages`
   - `Send Messages`
   - `Embed Links`
   - `Read Message History`
   - `Use Slash Commands`

## 📱 使用方法

### Botの起動

```bash
python main.py
```

### 基本コマンド

| コマンド | 説明 | 例 |
|---------|-----|---|
| `!similar [日数]` | 類似ユーザーを検索 | `!similar 30` |
| `!recommend` | ゲーム推薦を取得 | `!recommend` |
| `!stats` | プレイ統計を表示 | `!stats` |
| `!profile` | プロフィールを表示 | `!profile @username` |
| `!calendar` | ゲームイベント表示 | `!calendar` |

### 機能の詳細

#### 1. 類似ユーザー検索
```
!similar 30
```
- 過去30日間のプレイ履歴を比較
- Jaccard係数による類似度計算
- 共通ゲーム数とプレイ時間を考慮

#### 2. ゲーム推薦
```
!recommend
```
- 類似ユーザーのプレイ履歴から推薦
- まだプレイしていないゲームを優先表示
- 人気度とマッチング度でランキング

#### 3. 統計表示
```
!stats
```
- 総プレイ時間
- 最もプレイしたゲーム
- 週間/月間統計

## 🤖 Bot機能の詳細

### 自動履歴追跡

Botは以下を自動で追跡します：
- ゲーム開始・終了時刻
- プレイ時間の計算
- ゲームタイトルの正規化
- アクティビティステータスの変更

### 機械学習マッチング

```python
# ml_game_matcher.py の使用例
from ml_game_matcher import GameMatcher

matcher = GameMatcher()
similar_users = matcher.find_similar_users(user_id, threshold=0.7)
```

特徴：
- コサイン類似度とJaccard係数の組み合わせ
- ゲームジャンルの重み付け
- 時間減衰（最近のプレイを重視）

## 🖼️ スクリーンショット・使用例

<!-- 画像を追加する場合は以下のような形式で -->
<!-- ![Bot Commands](images/bot-commands.png) -->
<!-- ![Similar Users](images/similar-users.png) -->
<!-- ![Game Recommendations](images/recommendations.png) -->

## ⚙️ 設定オプション

### config.json (作成する場合)

```json
{
  "prefix": "!",
  "similarity_threshold": 0.6,
  "max_recommendations": 10,
  "tracking_interval": 300,
  "database_backup": true
}
```

### 環境変数

| 変数名 | 説明 | 必須 |
|-------|------|-----|
| `DISCORD_TOKEN` | Bot Token | ✅ |
| `PREFIX` | コマンドプレフィックス | ❌ |
| `DEBUG` | デバッグモード | ❌ |

## 🔒 プライバシー・セキュリティ

- **ローカルデータベース**: すべてのデータはローカルSQLiteに保存
- **最小限の情報収集**: ゲーム名とプレイ時間のみ追跡
- **ユーザー制御**: `!optout`コマンドで追跡を無効化可能
- **データ削除**: `!deletedata`で個人データを完全削除

## 🛠️ 開発・カスタマイズ

### 新しいコマンドの追加

```python
@bot.command(name='newcommand')
async def new_command(ctx):
    # コマンドの処理
    await ctx.send("新しいコマンドです！")
```

### データベーススキーマ

```sql
-- game_sessions テーブル
CREATE TABLE game_sessions (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    game_name TEXT,
    start_time DATETIME,
    end_time DATETIME,
    duration INTEGER
);
```

## 🤝 コントリビュート方法

1. このリポジトリをFork
2. 新しいブランチを作成 (`git checkout -b feature/awesome-feature`)
3. 変更をコミット (`git commit -m 'Add awesome feature'`)
4. ブランチにプッシュ (`git push origin feature/awesome-feature`)
5. Pull Requestを作成

### 開発環境

```bash
# 開発用依存関係
pip install -r requirements-dev.txt

# テスト実行
python -m pytest tests/

# フォーマット
black *.py
flake8 *.py
```

## 📝 ライセンス

このプロジェクトはMITライセンスのもとで公開されています。

## 👨‍💻 作成者

**Kota Okayama**
- GitHub: [@kota-okayama](https://github.com/kota-okayama)

## 🔮 今後の予定

- [ ] スラッシュコマンド対応
- [ ] Webダッシュボード開発
- [ ] 複数サーバー対応
- [ ] ゲームAPI統合（Steam, Xbox等）
- [ ] 音声チャンネル参加機能
- [ ] ゲーム大会・トーナメント機能

## 🆘 トラブルシューティング

### よくある問題

**Bot がオンラインにならない**
```
discord.errors.LoginFailure: Improper token has been passed.
```
- `.env`ファイルのTOKENを確認
- Bot Tokenが正しく設定されているか確認

**データベースエラー**
```
sqlite3.OperationalError: no such table: game_sessions
```
- Botの初回起動時に自動でテーブルが作成されます
- `game_history.db`ファイルの権限を確認

**メモリ使用量が多い**
- 定期的にデータベースをクリーンアップ
- 古いセッションデータの削除設定

### ログの確認

```bash
# デバッグモードでの起動
DEBUG=true python main.py

# ログファイルの確認
tail -f bot.log
```

## 🔗 関連リンク

- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers/docs/)
- [SQLite Documentation](https://sqlite.org/docs.html)
- [Discord Bot Best Practices](https://github.com/discord/discord-api-docs/blob/main/docs/topics/Gateway.md)