# 画像ファイルについて

このフォルダには、READMEファイルで使用する画像ファイルを保存します。

## 画像の追加方法

1. **画像ファイルをこのフォルダに追加**
   - Botのスクリーンショット、コマンド実行例、機能説明図などを配置
   - 推奨フォーマット: PNG, JPG, SVG
   - ファイル名は英数字とハイフンを使用（例：`bot-commands.png`）

2. **README.mdで画像を参照**
   ```markdown
   ![説明文](images/画像ファイル名.png)
   ```

## 画像の最適化

- **ファイルサイズ**: 1MB以下を推奨
- **解像度**: 幅1200px以下が適切
- **形式**:
  - Discord画面: PNG
  - フローチャート: SVG
  - 機能説明図: PNG

## 使用例

```markdown
# Botコマンド実行例
![Botコマンド](images/bot-commands.png)

# 類似ユーザー検索結果
![類似ユーザー](images/similar-users.png)

# ゲーム推薦機能
![ゲーム推薦](images/game-recommendations.png)
```

## 推奨する画像

- **bot-commands.png**: Botコマンドの実行例
- **similar-users.png**: 類似ユーザー検索結果
- **game-recommendations.png**: ゲーム推薦の表示例
- **user-stats.png**: ユーザー統計の表示
- **calendar-view.png**: カレンダー機能の表示
- **setup-guide.png**: セットアップ手順の図解
- **architecture-diagram.png**: Botアーキテクチャ図

## Discordスクリーンショットのコツ

1. **Discord開発者モード**を有効にしてテスト
2. **プライバシー保護**: ユーザー名やサーバー名をモザイクまたは架空の名前に変更
3. **テーマ**: ダークテーマとライトテーマ両方での表示確認
4. **解像度**: 高解像度での撮影を推奨