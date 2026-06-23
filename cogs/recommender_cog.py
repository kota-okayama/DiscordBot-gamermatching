"""RecommenderCog: コサイン類似度によるプレイヤーマッチング・ゲーム推薦"""
import discord
from discord.ext import commands
import sqlite3
import numpy as np

DB_PATH = 'game_history.db'


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
            conn = sqlite3.connect(DB_PATH)
            user_ids, all_games, game_mat, hour_mat = _build_user_vectors(conn.cursor(), days)
            conn.close()

            if str(ctx.author.id) not in user_ids:
                await ctx.send(embed=discord.Embed(
                    title="📭 プレイ記録なし",
                    description=f"過去{days}日間のプレイ記録が見つかりませんでした。",
                    color=discord.Color.orange()))
                return

            me = user_ids.index(str(ctx.author.id))
            results = []
            for i, uid in enumerate(user_ids):
                if uid == str(ctx.author.id):
                    continue
                sg = _cosine_similarity(game_mat[me], game_mat[i])
                sh = _cosine_similarity(hour_mat[me], hour_mat[i])
                score = sg * 0.6 + sh * 0.4
                common = [all_games[j] for j in range(len(all_games))
                          if game_mat[me, j] > 0 and game_mat[i, j] > 0]
                results.append((uid, score, sg, sh, common))

            results.sort(key=lambda x: x[1], reverse=True)

            embed = discord.Embed(
                title="👥 プレイスタイルが似ているプレイヤー",
                description=f"**{ctx.author.display_name}** さんとの類似度（過去{days}日）\nスコア = ゲーム類似度×0.6 ＋ 時間帯類似度×0.4",
                color=discord.Color.blue())

            shown = 0
            for uid, score, sg, sh, common in results[:10]:
                member = ctx.guild.get_member(int(uid))
                if not member:
                    continue
                pct = int(score * 100)
                common_str = ', '.join(common[:5]) + (f' 他{len(common)-5}本' if len(common) > 5 else '')
                embed.add_field(
                    name=f"👤 {member.display_name}",
                    value=f"{_progress_bar(pct)} **{pct}%**\nゲーム:{int(sg*100)}% / 時間帯:{int(sh*100)}%\n共通: {common_str or 'なし'}",
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
            conn = sqlite3.connect(DB_PATH)
            user_ids, all_games, game_mat, hour_mat = _build_user_vectors(conn.cursor(), days)
            conn.close()

            if str(ctx.author.id) not in user_ids:
                await ctx.send(embed=discord.Embed(
                    title="📭 プレイ記録なし",
                    description=f"過去{days}日間のプレイ記録が見つかりませんでした。",
                    color=discord.Color.orange()))
                return

            me = user_ids.index(str(ctx.author.id))
            unplayed = [j for j, v in enumerate(game_mat[me]) if v == 0]
            if not unplayed:
                await ctx.send("このサーバーで記録されているゲームはすべてプレイ済みです！")
                return

            sim_scores = {}
            for i, uid in enumerate(user_ids):
                if uid == str(ctx.author.id):
                    continue
                sg = _cosine_similarity(game_mat[me], game_mat[i])
                sh = _cosine_similarity(hour_mat[me], hour_mat[i])
                sim_scores[i] = sg * 0.6 + sh * 0.4

            rec: dict = {}
            for j in unplayed:
                s = sum(sim * game_mat[i, j] for i, sim in sim_scores.items())
                if s > 0:
                    rec[j] = s

            if not rec:
                await ctx.send("推薦できるゲームが見つかりませんでした。")
                return

            sorted_rec = sorted(rec.items(), key=lambda x: x[1], reverse=True)
            max_s = sorted_rec[0][1]

            embed = discord.Embed(
                title="🎯 おすすめのゲーム",
                description=f"**{ctx.author.display_name}** さんへの協調フィルタリング推薦（過去{days}日）",
                color=discord.Color.green())

            for j, score in sorted_rec[:top_k]:
                pct = int(score / max_s * 100) if max_s > 0 else 0
                players = [ctx.guild.get_member(int(user_ids[i]))
                           for i, s in sim_scores.items() if game_mat[i, j] > 0]
                players = [p for p in players if p]
                names = ', '.join(p.display_name for p in players[:3])
                if len(players) > 3:
                    names += f' 他{len(players)-3}人'
                embed.add_field(
                    name=f"🎮 {all_games[j]}",
                    value=f"{_progress_bar(pct)} {pct}%\nプレイ中: {names or '不明'}",
                    inline=False)

            embed.set_footer(text="協調フィルタリング（コサイン類似度重み付き）")
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Error in !recommend: {e}")
            await ctx.send(f"エラーが発生しました: {e}")
