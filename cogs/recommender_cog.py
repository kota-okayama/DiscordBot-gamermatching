"""RecommenderCog: コサイン類似度によるプレイヤーマッチング・ゲーム推薦"""
import discord
from discord.ext import commands
import sqlite3
import numpy as np
import os
import pickle

from cogs.ui_constants import ICON_FIELD

DB_PATH = 'data/game_history.db'

# エンベディングのロード
GAME_EMBEDDINGS = {}
if os.path.exists('data/game_embeddings.pkl'):
    try:
        with open('data/game_embeddings.pkl', 'rb') as f:
            GAME_EMBEDDINGS = pickle.load(f)
        if GAME_EMBEDDINGS:
            emb_matrix = np.array(list(GAME_EMBEDDINGS.values()))
            mean_vec = np.mean(emb_matrix, axis=0)
            for gname, vec in GAME_EMBEDDINGS.items():
                centered = vec - mean_vec
                norm = np.linalg.norm(centered)
                GAME_EMBEDDINGS[gname] = centered / norm if norm > 0 else centered
        print(f"Loaded {len(GAME_EMBEDDINGS)} game embeddings (Applied Mean Centering).")
    except Exception as e:
        print(f"Failed to load game embeddings: {e}")


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _build_user_vectors(cursor, days: int):
    cursor.execute(
        "SELECT DISTINCT game_name FROM game_sessions WHERE datetime(start_time) > datetime('now', ?)",
        (f'-{days} days',))
    all_games = sorted([r[0] for r in cursor.fetchall()])
    game_idx = {g: i for i, g in enumerate(all_games)}

    cursor.execute(
        "SELECT DISTINCT user_id FROM game_sessions WHERE datetime(start_time) > datetime('now', ?)",
        (f'-{days} days',))
    user_ids = [r[0] for r in cursor.fetchall()]

    n, m = len(user_ids), len(all_games)
    game_mat = np.zeros((n, m), dtype=np.float64)
    hour_mat = np.zeros((n, 24), dtype=np.float64)

    for ui, uid in enumerate(user_ids):
        cursor.execute('''
            SELECT game_name, SUM(duration) FROM game_sessions
            WHERE user_id=? AND datetime(start_time) > datetime('now', ?)
            GROUP BY game_name
        ''', (uid, f'-{days} days'))
        for gname, total in cursor.fetchall():
            if gname in game_idx:
                game_mat[ui, game_idx[gname]] = total

        cursor.execute('''
            SELECT CAST(strftime('%H', start_time) AS INTEGER) as h, COUNT(*)
            FROM game_sessions
            WHERE user_id=? AND datetime(start_time) > datetime('now', ?)
            GROUP BY h
        ''', (uid, f'-{days} days'))
        for hour, cnt in cursor.fetchall():
            hour_mat[ui, hour] = cnt

    return user_ids, all_games, game_mat, hour_mat


def _build_user_embedding(user_game_vec, all_games):
    """
    プレイ時間を重みとして、ゲームのエンベディングの加重平均（ユーザーベクトル）を計算する
    """
    if not GAME_EMBEDDINGS:
        return np.zeros(384) # ダミー次元
        
    vecs = []
    weights = []
    for j, gname in enumerate(all_games):
        w = user_game_vec[j]
        if w > 0 and gname in GAME_EMBEDDINGS:
            vecs.append(GAME_EMBEDDINGS[gname])
            weights.append(w)
            
    if not vecs:
        return np.zeros(384)
        
    vecs = np.array(vecs)
    weights = np.array(weights)
    
    weights = weights / weights.sum()
    user_emb = np.average(vecs, axis=0, weights=weights)
    return user_emb


def _progress_bar(pct: int, length: int = 10) -> str:
    filled = int(length * pct / 100)
    return '█' * filled + '▒' * (length - filled)


class RecommenderCog(commands.Cog, name='Recommender'):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='similar')
    async def find_similar_players(self, ctx, days: int = 30):
        """コサイン類似度でプレイスタイルが近いサーバーメンバーを表示"""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            user_ids, all_games, game_mat, hour_mat = _build_user_vectors(conn.cursor(), days)
            conn.close()

            if str(ctx.author.id) not in user_ids:
                await ctx.send(embed=discord.Embed(
                    title="プレイ記録なし",
                    description=f"過去{days}日間のプレイ記録が見つかりませんでした。",
                    color=discord.Color.orange()))
                return

            me = user_ids.index(str(ctx.author.id))
            
            # 各ユーザーのコンテンツベクトル（好みの重心）を計算
            user_embs = [_build_user_embedding(game_mat[i], all_games) for i in range(len(user_ids))]
            
            results = []
            for i, uid in enumerate(user_ids):
                if uid == str(ctx.author.id):
                    continue
                sg = _cosine_similarity(game_mat[me], game_mat[i]) # 一致するゲームの類似度
                sh = _cosine_similarity(hour_mat[me], hour_mat[i]) # 時間帯の類似度
                sc = _cosine_similarity(user_embs[me], user_embs[i]) # ゲーム性・好みの類似度（エンベディング）
                
                # スコアをブレンド（例: ゲーム30%, 時間帯20%, 好み50%）
                score = sg * 0.3 + sh * 0.2 + sc * 0.5
                common = [all_games[j] for j in range(len(all_games))
                          if game_mat[me, j] > 0 and game_mat[i, j] > 0]
                results.append((uid, score, sg, sh, sc, common))

            results.sort(key=lambda x: x[1], reverse=True)

            embed = discord.Embed(
                title="プレイスタイルが似ているプレイヤー",
                description=f"**{ctx.author.display_name}** さんとの類似度（過去{days}日）\nスコア = プレイタイトル30% ＋ 時間帯20% ＋ ジャンル・好み50%",
                color=discord.Color.blue())

            shown = 0
            for uid, score, sg, sh, sc, common in results:
                user = self.bot.get_user(int(uid))
                if not user:
                    continue
                pct = int(score * 100)
                common_str = ', '.join(common[:5]) + (f' 他{len(common)-5}本' if len(common) > 5 else '')
                embed.add_field(
                    name=f"{ICON_FIELD}{user.display_name}",
                    value=f"{_progress_bar(pct)} **{pct}%**\nタイトル一致:{int(sg*100)}% / 時間帯:{int(sh*100)}% / ジャンル・好み:{int(sc*100)}%\n共通: {common_str or 'なし'}",
                    inline=False)
                shown += 1
                if shown >= 5:
                    break

            if shown == 0:
                await ctx.send("類似したプレイヤーが見つかりませんでした。")
                return

            embed.set_footer(text="コサイン類似度ベース（numpy実装）")
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Error in !similar: {e}")
            await ctx.send(f"エラーが発生しました: {e}")

    @commands.command(name='recommend')
    async def recommend_games(self, ctx, days: int = 30, top_k: int = 5):
        """協調フィルタリングでゲームを推薦"""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            user_ids, all_games, game_mat, hour_mat = _build_user_vectors(conn.cursor(), days)
            conn.close()

            if str(ctx.author.id) not in user_ids:
                await ctx.send(embed=discord.Embed(
                    title="プレイ記録なし",
                    description=f"過去{days}日間のプレイ記録が見つかりませんでした。",
                    color=discord.Color.orange()))
                return

            me = user_ids.index(str(ctx.author.id))
            unplayed = [j for j, v in enumerate(game_mat[me]) if v == 0]
            if not unplayed:
                await ctx.send("このサーバーで記録されているゲームはすべてプレイ済みです！")
                return

            user_embs = [_build_user_embedding(game_mat[i], all_games) for i in range(len(user_ids))]

            sim_scores = {}
            for i, uid in enumerate(user_ids):
                if uid == str(ctx.author.id):
                    continue
                sg = _cosine_similarity(game_mat[me], game_mat[i])
                sh = _cosine_similarity(hour_mat[me], hour_mat[i])
                sc = _cosine_similarity(user_embs[me], user_embs[i])
                sim_scores[i] = sg * 0.3 + sh * 0.2 + sc * 0.5

            rec_cf = {}
            for j in unplayed:
                # プレイ時間を対数スケールにして、一部の廃人プレイヤーのプレイ時間に引っ張られすぎないようにする
                s = sum(sim * np.log1p(game_mat[i, j]) for i, sim in sim_scores.items() if sim > 0)
                if s > 0:
                    rec_cf[j] = s

            if not rec_cf:
                await ctx.send("推薦できるゲームが見つかりませんでした。")
                return

            # CFスコアを0-1に正規化
            max_cf = max(rec_cf.values()) if rec_cf else 1
            
            final_rec = []
            for j, cf_raw in rec_cf.items():
                cf_score = cf_raw / max_cf
                
                game_name = all_games[j]
                cb_score = 0.0
                if game_name in GAME_EMBEDDINGS:
                    cb_score = _cosine_similarity(user_embs[me], GAME_EMBEDDINGS[game_name])
                    
                # スコアのブレンド（フレンドが遊んでいるか 50% + 自分の好みのジャンルか 50%）
                total_score = cf_score * 0.5 + max(0, cb_score) * 0.5
                final_rec.append((j, total_score, cf_score, cb_score))

            final_rec.sort(key=lambda x: x[1], reverse=True)
            max_total = final_rec[0][1] if final_rec else 1

            embed = discord.Embed(
                title="おすすめのゲーム",
                description=f"**{ctx.author.display_name}** さんへのハイブリッド推薦（過去{days}日）\nスコア = フレンドのプレイ状況50% ＋ ジャンルの一致度50%",
                color=discord.Color.green())

            for j, total, cf, cb in final_rec[:top_k]:
                pct = int(total / max_total * 100) if max_total > 0 else 0
                
                # このゲームを遊んでいるフレンドを抽出（類似度スコアが高い順）
                players = [(self.bot.get_user(int(user_ids[i])), sim_scores[i])
                           for i in sim_scores if game_mat[i, j] > 0]
                players = [p for p in players if p[0]]
                players.sort(key=lambda x: x[1], reverse=True)
                
                names = ', '.join(p[0].display_name for p in players[:3])
                if len(players) > 3:
                    names += f' 他{len(players)-3}人'
                    
                embed.add_field(
                    name=f"{ICON_FIELD}{all_games[j]}",
                    value=f"{_progress_bar(pct)} **{pct}%**\n流行度(CF): {int(cf*100)}% / ジャンル(CB): {int(max(0, cb)*100)}%\nプレイ中: {names or 'なし'}",
                    inline=False)

            embed.set_footer(text="ハイブリッド推薦（協調フィルタリング ＋ コンテンツベース）")
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Error in !recommend: {e}")
            await ctx.send(f"エラーが発生しました: {e}")

    @commands.command(name='dummy_similar')
    async def dummy_similar(self, ctx):
        """[ダミーデータ] 類似ユーザーを検索"""
        embed = discord.Embed(
            title="プレイスタイルが似ているプレイヤー",
            description=f"**{ctx.author.display_name}** さんとの類似度（過去30日）\nスコア = ゲーム類似度×0.6 ＋ 時間帯類似度×0.4",
            color=discord.Color.blue())
        
        embed.add_field(name=f"{ICON_FIELD}kurara_ra", value=f"{_progress_bar(85)} **85%**\nゲーム:80% / 時間帯:92%\n共通: Valorant, Apex Legends", inline=False)
        embed.add_field(name=f"{ICON_FIELD}test_gamer", value=f"{_progress_bar(62)} **62%**\nゲーム:70% / 時間帯:50%\n共通: Minecraft", inline=False)
        embed.add_field(name=f"{ICON_FIELD}pro_player", value=f"{_progress_bar(45)} **45%**\nゲーム:30% / 時間帯:67%\n共通: Genshin Impact", inline=False)
        
        embed.set_footer(text="コサイン類似度ベース（ダミーデータ）")
        await ctx.send(embed=embed)

    @commands.command(name='dummy_recommend')
    async def dummy_recommend(self, ctx):
        """[ダミーデータ] ゲームを推薦"""
        embed = discord.Embed(
            title="おすすめのゲーム",
            description=f"**{ctx.author.display_name}** さんへのハイブリッド推薦（過去30日）\nスコア = フレンドのプレイ状況50% ＋ ジャンルの一致度50%",
            color=discord.Color.green())
            
        embed.add_field(name=f"{ICON_FIELD}Escape from Tarkov", value=f"{_progress_bar(95)} **95%**\n流行度(CF): 80% / ジャンル(CB): 100%\nプレイ中: kurara_ra, test_gamer", inline=False)
        embed.add_field(name=f"{ICON_FIELD}Overwatch 2", value=f"{_progress_bar(78)} **78%**\n流行度(CF): 90% / ジャンル(CB): 66%\nプレイ中: pro_player, user123", inline=False)
        embed.add_field(name=f"{ICON_FIELD}League of Legends", value=f"{_progress_bar(52)} **52%**\n流行度(CF): 100% / ジャンル(CB): 4%\nプレイ中: kurara_ra", inline=False)
        
        embed.set_footer(text="ハイブリッド推薦（ダミーデータ）")
        await ctx.send(embed=embed)
