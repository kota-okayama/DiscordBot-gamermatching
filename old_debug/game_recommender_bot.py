import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
import numpy as np

DB_PATH = 'game_history.db'

# ──────────────────────────────────────────────────────────────
# ユーティリティ関数
# ──────────────────────────────────────────────────────────────

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """コサイン類似度を計算（ゼロベクトル対策あり）"""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _build_user_vectors(
    cursor, days: int
) -> tuple[list[str], list[str], np.ndarray, np.ndarray]:
    """
    全ユーザーのゲームベクトルと時間帯ベクトルを構築する。

    Returns:
        user_ids:    ユーザーIDのリスト
        all_games:   全ゲーム名のリスト（ベクトルの次元に対応）
        game_matrix: shape (n_users, n_games)  各ユーザーのゲーム別プレイ時間
        hour_matrix: shape (n_users, 24)       各ユーザーの時間帯別セッション数
    """
    # 全ゲームを収集
    cursor.execute('''
        SELECT DISTINCT game_name FROM game_sessions
        WHERE datetime(start_time) > datetime('now', ?)
    ''', (f'-{days} days',))
    all_games = sorted([row[0] for row in cursor.fetchall()])
    game_idx = {g: i for i, g in enumerate(all_games)}

    # 全ユーザーを収集
    cursor.execute('''
        SELECT DISTINCT user_id FROM game_sessions
        WHERE datetime(start_time) > datetime('now', ?)
    ''', (f'-{days} days',))
    user_ids = [row[0] for row in cursor.fetchall()]

    n_users = len(user_ids)
    n_games = len(all_games)

    game_matrix = np.zeros((n_users, n_games), dtype=np.float64)
    hour_matrix = np.zeros((n_users, 24),      dtype=np.float64)

    for ui, uid in enumerate(user_ids):
        # ゲームベクトル（プレイ時間）
        cursor.execute('''
            SELECT game_name, SUM(duration) as total
            FROM game_sessions
            WHERE user_id = ? AND datetime(start_time) > datetime('now', ?)
            GROUP BY game_name
        ''', (uid, f'-{days} days'))
        for game_name, total in cursor.fetchall():
            if game_name in game_idx:
                game_matrix[ui, game_idx[game_name]] = total

        # 時間帯ベクトル（セッション数）
        cursor.execute('''
            SELECT CAST(strftime('%H', start_time) AS INTEGER) as hour, COUNT(*) as cnt
            FROM game_sessions
            WHERE user_id = ? AND datetime(start_time) > datetime('now', ?)
            GROUP BY hour
        ''', (uid, f'-{days} days'))
        for hour, cnt in cursor.fetchall():
            hour_matrix[ui, hour] = cnt

    return user_ids, all_games, game_matrix, hour_matrix


def _progress_bar(pct: int, length: int = 10) -> str:
    filled = int(length * pct / 100)
    return '█' * filled + '▒' * (length - filled)


# ──────────────────────────────────────────────────────────────
# Bot クラス
# ──────────────────────────────────────────────────────────────

class GameRecommenderBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self._add_commands()

    def _add_commands(self):

        # ──────────────────────────────────────────
        # !similar [days]
        #   コサイン類似度でプレイスタイルが近いユーザーを表示
        # ──────────────────────────────────────────
        @self.command(name='similar')
        async def find_similar_players(ctx, days: int = 30):
            """
            コサイン類似度でプレイスタイルが近いサーバーメンバーを表示します。

            スコア計算:
              ゲームベクトル類似度 × 0.6 + 時間帯類似度 × 0.4
            """
            try:
                conn   = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()

                user_ids, all_games, game_mat, hour_mat = _build_user_vectors(cursor, days)
                conn.close()

                if str(ctx.author.id) not in user_ids:
                    embed = discord.Embed(
                        title="📭 プレイ記録なし",
                        description=f"過去 {days} 日間のプレイ記録が見つかりませんでした。",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=embed)
                    return

                me_idx    = user_ids.index(str(ctx.author.id))
                me_game   = game_mat[me_idx]
                me_hour   = hour_mat[me_idx]

                results = []
                for i, uid in enumerate(user_ids):
                    if uid == str(ctx.author.id):
                        continue

                    sim_game = _cosine_similarity(me_game, game_mat[i])
                    sim_hour = _cosine_similarity(me_hour, hour_mat[i])
                    score    = sim_game * 0.6 + sim_hour * 0.4

                    # 共通ゲームを列挙
                    common = [
                        all_games[j]
                        for j in range(len(all_games))
                        if me_game[j] > 0 and game_mat[i, j] > 0
                    ]
                    results.append((uid, score, sim_game, sim_hour, common))

                if not results:
                    embed = discord.Embed(
                        title="🔍 類似ユーザーなし",
                        description="比較できるプレイヤーが見つかりませんでした。",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=embed)
                    return

                results.sort(key=lambda x: x[1], reverse=True)

                embed = discord.Embed(
                    title="👥 プレイスタイルが似ているプレイヤー",
                    description=(
                        f"**{ctx.author.display_name}** さんとの類似度 "
                        f"（過去 {days} 日間）\n"
                        f"スコア = ゲームベクトル類似度×0.6 ＋ 時間帯類似度×0.4"
                    ),
                    color=discord.Color.blue()
                )

                for uid, score, sim_g, sim_h, common in results[:5]:
                    member = ctx.guild.get_member(int(uid))
                    if not member:
                        continue
                    pct  = int(score * 100)
                    bar  = _progress_bar(pct)
                    common_str = ', '.join(common[:5]) if common else 'なし'
                    if len(common) > 5:
                        common_str += f' 他{len(common)-5}本'
                    embed.add_field(
                        name=f"👤 {member.display_name}",
                        value=(
                            f"総合スコア: {bar} **{pct}%**\n"
                            f"ゲーム類似度: {int(sim_g*100)}% ／ "
                            f"時間帯類似度: {int(sim_h*100)}%\n"
                            f"共通ゲーム: {common_str}"
                        ),
                        inline=False
                    )

                embed.set_footer(text="コサイン類似度ベース（scikit-learnなし・numpy実装）")
                await ctx.send(embed=embed)

            except Exception as e:
                print(f"Error in !similar: {e}")
                await ctx.send(f"エラーが発生しました: {e}")

        # ──────────────────────────────────────────
        # !recommend [days] [top_k]
        #   協調フィルタリング（コサイン類似度ベース）
        # ──────────────────────────────────────────
        @self.command(name='recommend')
        async def recommend_games(ctx, days: int = 30, top_k: int = 5):
            """
            協調フィルタリングでゲームを推薦します。

            アルゴリズム:
              1. コサイン類似度で類似ユーザーを選択
              2. 類似ユーザーがプレイしているが自分は未プレイのゲームを抽出
              3. 類似度で重み付けしたスコアでランキング
            """
            try:
                conn   = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()

                user_ids, all_games, game_mat, hour_mat = _build_user_vectors(cursor, days)
                conn.close()

                if str(ctx.author.id) not in user_ids:
                    embed = discord.Embed(
                        title="📭 プレイ記録なし",
                        description=f"過去 {days} 日間のプレイ記録が見つかりませんでした。",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=embed)
                    return

                me_idx  = user_ids.index(str(ctx.author.id))
                me_game = game_mat[me_idx]
                me_hour = hour_mat[me_idx]

                # ── 自分が未プレイのゲームのインデックス ──
                unplayed_idx = [j for j, v in enumerate(me_game) if v == 0]
                if not unplayed_idx:
                    embed = discord.Embed(
                        title="🎮 推薦なし",
                        description="このサーバーで記録されているゲームはすべてプレイ済みです！",
                        color=discord.Color.green()
                    )
                    await ctx.send(embed=embed)
                    return

                # ── 類似ユーザーのスコアを計算 ──
                sim_scores = {}
                for i, uid in enumerate(user_ids):
                    if uid == str(ctx.author.id):
                        continue
                    sim_g = _cosine_similarity(me_game, game_mat[i])
                    sim_h = _cosine_similarity(me_hour, hour_mat[i])
                    sim_scores[i] = sim_g * 0.6 + sim_h * 0.4

                if not sim_scores:
                    await ctx.send("比較できるプレイヤーが見つかりませんでした。")
                    return

                # ── 協調フィルタリングスコア計算 ──
                # score[game] = Σ (類似度 × そのユーザーのプレイ時間)
                rec_scores: dict[int, float] = {}
                for j in unplayed_idx:
                    total_sim_weighted = 0.0
                    for i, sim in sim_scores.items():
                        total_sim_weighted += sim * game_mat[i, j]
                    if total_sim_weighted > 0:
                        rec_scores[j] = total_sim_weighted

                if not rec_scores:
                    embed = discord.Embed(
                        title="😅 推薦なし",
                        description="類似したプレイヤーが未プレイのゲームをプレイしていません。",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=embed)
                    return

                sorted_recs = sorted(rec_scores.items(), key=lambda x: x[1], reverse=True)

                embed = discord.Embed(
                    title="🎯 おすすめのゲーム",
                    description=(
                        f"**{ctx.author.display_name}** さんへの協調フィルタリング推薦\n"
                        f"（過去 {days} 日間 / 類似ユーザーのプレイ傾向から算出）"
                    ),
                    color=discord.Color.green()
                )

                max_score = sorted_recs[0][1]
                for j, score in sorted_recs[:top_k]:
                    game_name  = all_games[j]
                    pct        = int(score / max_score * 100) if max_score > 0 else 0
                    bar        = _progress_bar(pct)

                    # そのゲームをプレイしている類似ユーザーを列挙
                    players_who_play = [
                        ctx.guild.get_member(int(user_ids[i]))
                        for i, sim in sim_scores.items()
                        if game_mat[i, j] > 0 and ctx.guild.get_member(int(user_ids[i]))
                    ]
                    player_names = ', '.join(
                        m.display_name for m in players_who_play[:3] if m
                    )
                    if len(players_who_play) > 3:
                        player_names += f' 他{len(players_who_play)-3}人'

                    embed.add_field(
                        name=f"🎮 {game_name}",
                        value=(
                            f"推薦スコア: {bar} {pct}%\n"
                            f"プレイ中のメンバー: {player_names or '不明'}"
                        ),
                        inline=False
                    )

                embed.set_footer(text="協調フィルタリング（コサイン類似度ベース重み付き）")
                await ctx.send(embed=embed)

            except Exception as e:
                print(f"Error in !recommend: {e}")
                await ctx.send(f"エラーが発生しました: {e}")

    async def on_ready(self):
        print(f'{self.user} としてログインしました!')
        print('使用可能なコマンド:')
        print('  !similar [日数]          - コサイン類似度でプレイスタイルが近いメンバーを表示')
        print('  !recommend [日数] [top_k] - 協調フィルタリングでゲームを推薦')