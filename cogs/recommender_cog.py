"""RecommenderCog: cosine-similarity matching and game recommendation."""
import discord
from discord.ext import commands
import sqlite3
import numpy as np
import os
import pickle

from cogs.ui_constants import ICON_FIELD

DB_PATH = 'data/game_history.db'

# Fallback avatar for dummy_similar (Discord default embed avatar)
_DEFAULT_AVATAR_URL = 'https://cdn.discordapp.com/embed/avatars/0.png'

# Embedding load
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
    """Weighted average of game embeddings by playtime (user preference vector)."""
    if not GAME_EMBEDDINGS:
        return np.zeros(384)

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
    """Geometric meter bar (▰ filled / ▱ empty).

    Wrapped in inline code so Discord renders it with a monospace font;
    otherwise ▰/▱ have uneven advance widths in proportional text.
    """
    filled = max(0, min(length, int(length * pct / 100)))
    bar = '▰' * filled + '▱' * (length - filled)
    return f'{bar}'


def build_similar_entries(results, bot, limit: int = 5) -> list[dict]:
    """Build display entries from scored results.

    Each entry: user_id, display_name, pct, sg, sh, sc, common, avatar_url
    """
    entries = []
    for uid, score, sg, sh, sc, common in results:
        user = bot.get_user(int(uid))
        if not user:
            continue
        common_str = ', '.join(common[:5]) + (
            f' 他{len(common) - 5}本' if len(common) > 5 else '')
        entries.append({
            'user_id': int(uid),
            'display_name': user.display_name,
            'pct': int(score * 100),
            'sg': int(sg * 100),
            'sh': int(sh * 100),
            'sc': int(sc * 100),
            'common': common_str or 'なし',
            'avatar_url': user.display_avatar.url,
        })
        if len(entries) >= limit:
            break
    return entries


EXPIRED_MSG = "操作可能時間を過ぎました"


class SimilarProfileSelect(discord.ui.Select):
    """Select menu to open Bot game profile (ProfileCog) as ephemeral.

    Each selection replaces the previous detail message instead of stacking.
    """

    def __init__(self, options_data: list[tuple[int, str]]):
        options = [
            discord.SelectOption(label=name, value=str(uid))
            for uid, name in options_data
        ]
        super().__init__(
            placeholder="詳細を見る",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, SimilarPlayersLayout) or view.is_finished():
            await interaction.response.send_message(EXPIRED_MSG, ephemeral=True)
            return

        user_id = int(self.values[0])
        display_name = next(
            (opt.label for opt in self.options if opt.value == self.values[0]),
            str(user_id),
        )
        profile_cog = interaction.client.get_cog('Profile')
        if profile_cog is None:
            embed = discord.Embed(
                title="プロフィールなし",
                description="プロフィール機能が利用できません。",
                color=discord.Color.orange())
            await view.show_detail(interaction, embed, None)
            return

        embed, file = await profile_cog.build_profile_message(user_id, display_name)
        if embed is None:
            embed = discord.Embed(
                title="プロフィールなし",
                description="プレイ記録が見つかりませんでした。",
                color=discord.Color.orange())
            await view.show_detail(interaction, embed, None)
            return

        await view.show_detail(interaction, embed, file)


class SimilarPlayersLayout(discord.ui.LayoutView):
    """Components V2 layout: avatar Thumbnail + mention + profile Select.

    Notes from discord.py Components V2 docs:
    - LayoutView messages cannot include content/embeds
    - Mentions inside TextDisplay ping by default; callers must pass
      AllowedMentions.none() when sending
    """

    def __init__(
        self,
        author_name: str,
        days: int,
        entries: list[dict],
        footer: str = "コサイン類似度ベース（numpy実装）",
        enable_profile_select: bool = True,
    ):
        super().__init__(timeout=180)
        self.message: discord.Message | None = None
        self.detail_message: discord.Message | None = None

        children: list = [
            discord.ui.TextDisplay(
                f"## Similar Players\n"
                f"**{author_name}** さんとの類似度（過去{days}日）\n"
                f"スコア = プレイタイトル30% ＋ 時間帯20% ＋ ジャンル・好み50%"
            ),
            discord.ui.Separator(
                visible=True,
                spacing=discord.SeparatorSpacing.large,
            ),
        ]

        select_options: list[tuple[int, str]] = []
        for i, entry in enumerate(entries):
            uid = entry['user_id']
            name = entry['display_name']
            pct = entry['pct']
            # Layout D: name + mention
            #           monospace geometric bar + match%
            #           score breakdown
            #           common games
            body = (
                f"**{name}** <@{uid}>\n"
                f"{_progress_bar(pct)}  **{pct}%**\n"
                f"タイトル {entry['sg']}% / 時間帯 {entry['sh']}% / ジャンル {entry['sc']}%\n"
                f"共通: {entry['common']}"
            )
            if i > 0:
                children.append(discord.ui.Separator(
                    visible=True,
                    spacing=discord.SeparatorSpacing.large,
                ))
            children.append(discord.ui.Section(
                body,
                accessory=discord.ui.Thumbnail(entry['avatar_url']),
            ))
            select_options.append((uid, name))

        children.append(discord.ui.Separator(
            visible=True,
            spacing=discord.SeparatorSpacing.small,
        ))
        children.append(discord.ui.TextDisplay(f"-# {footer}"))
        self.add_item(discord.ui.Container(
            *children,
            accent_color=discord.Color.blue(),
        ))

        if enable_profile_select and select_options:
            row = discord.ui.ActionRow()
            row.add_item(SimilarProfileSelect(select_options))
            self.add_item(row)

    async def show_detail(
        self,
        interaction: discord.Interaction,
        embed: discord.Embed,
        file: discord.File | None,
    ) -> None:
        """Send or replace the ephemeral Bot profile detail message."""
        if self.detail_message is None:
            if file:
                await interaction.response.send_message(
                    embed=embed, file=file, ephemeral=True)
            else:
                await interaction.response.send_message(
                    embed=embed, ephemeral=True)
            self.detail_message = await interaction.original_response()
            return

        await interaction.response.defer(ephemeral=True)
        try:
            # discord.py Message.edit takes new uploads via attachments=[File, ...]
            await self.detail_message.edit(
                embed=embed,
                attachments=[file] if file else [],
            )
        except discord.HTTPException:
            # Previous detail was deleted or expired; open a new one
            if file:
                self.detail_message = await interaction.followup.send(
                    embed=embed, file=file, ephemeral=True, wait=True)
            else:
                self.detail_message = await interaction.followup.send(
                    embed=embed, ephemeral=True, wait=True)

    def _disable_selects(self) -> None:
        for item in self.walk_children():
            if isinstance(item, discord.ui.Select):
                item.disabled = True
                item.placeholder = EXPIRED_MSG

    async def on_timeout(self) -> None:
        self._disable_selects()
        if self.message is None:
            return
        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass


class RecommenderCog(commands.Cog, name='Recommender'):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='similar')
    async def find_similar_players(self, ctx, days: int = 30):
        """Show server members with similar play style (cosine similarity)."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            user_ids, all_games, game_mat, hour_mat = _build_user_vectors(
                conn.cursor(), days)
            conn.close()

            if str(ctx.author.id) not in user_ids:
                await ctx.send(embed=discord.Embed(
                    title="プレイ記録なし",
                    description=f"過去{days}日間のプレイ記録が見つかりませんでした。",
                    color=discord.Color.orange()))
                return

            me = user_ids.index(str(ctx.author.id))

            user_embs = [
                _build_user_embedding(game_mat[i], all_games)
                for i in range(len(user_ids))
            ]

            results = []
            for i, uid in enumerate(user_ids):
                if uid == str(ctx.author.id):
                    continue
                sg = _cosine_similarity(game_mat[me], game_mat[i])
                sh = _cosine_similarity(hour_mat[me], hour_mat[i])
                sc = _cosine_similarity(user_embs[me], user_embs[i])
                score = sg * 0.3 + sh * 0.2 + sc * 0.5
                common = [
                    all_games[j] for j in range(len(all_games))
                    if game_mat[me, j] > 0 and game_mat[i, j] > 0
                ]
                results.append((uid, score, sg, sh, sc, common))

            results.sort(key=lambda x: x[1], reverse=True)
            entries = build_similar_entries(results, self.bot)

            if not entries:
                await ctx.send("類似したプレイヤーが見つかりませんでした。")
                return

            view = SimilarPlayersLayout(
                ctx.author.display_name, days, entries)
            view.message = await ctx.send(
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        except Exception as e:
            print(f"Error in !similar: {e}")
            await ctx.send(f"エラーが発生しました: {e}")

    @commands.command(name='recommend')
    async def recommend_games(self, ctx, days: int = 30, top_k: int = 5):
        """Recommend games via hybrid collaborative + content filtering."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            user_ids, all_games, game_mat, hour_mat = _build_user_vectors(
                conn.cursor(), days)
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

            user_embs = [
                _build_user_embedding(game_mat[i], all_games)
                for i in range(len(user_ids))
            ]

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
                # log1p playtime so heavy users do not dominate CF
                s = sum(
                    sim * np.log1p(game_mat[i, j])
                    for i, sim in sim_scores.items() if sim > 0
                )
                if s > 0:
                    rec_cf[j] = s

            if not rec_cf:
                await ctx.send("推薦できるゲームが見つかりませんでした。")
                return

            max_cf = max(rec_cf.values()) if rec_cf else 1

            final_rec = []
            for j, cf_raw in rec_cf.items():
                cf_score = cf_raw / max_cf

                game_name = all_games[j]
                cb_score = 0.0
                if game_name in GAME_EMBEDDINGS:
                    cb_score = _cosine_similarity(
                        user_embs[me], GAME_EMBEDDINGS[game_name])

                total_score = cf_score * 0.5 + max(0, cb_score) * 0.5
                final_rec.append((j, total_score, cf_score, cb_score))

            final_rec.sort(key=lambda x: x[1], reverse=True)
            max_total = final_rec[0][1] if final_rec else 1

            embed = discord.Embed(
                title="おすすめのゲーム",
                description=(
                    f"**{ctx.author.display_name}** さんへのハイブリッド推薦（過去{days}日）\n"
                    "スコア = フレンドのプレイ状況50% ＋ ジャンルの一致度50%"
                ),
                color=discord.Color.green())

            for j, total, cf, cb in final_rec[:top_k]:
                pct = int(total / max_total * 100) if max_total > 0 else 0

                players = [
                    (self.bot.get_user(int(user_ids[i])), sim_scores[i])
                    for i in sim_scores if game_mat[i, j] > 0
                ]
                players = [p for p in players if p[0]]
                players.sort(key=lambda x: x[1], reverse=True)

                names = ', '.join(p[0].display_name for p in players[:3])
                if len(players) > 3:
                    names += f' 他{len(players)-3}人'

                embed.add_field(
                    name=f"{ICON_FIELD}{all_games[j]}",
                    value=(
                        f"{_progress_bar(pct)} **{pct}%**\n"
                        f"流行度(CF): {int(cf*100)}% / ジャンル(CB): {int(max(0, cb)*100)}%\n"
                        f"プレイ中: {names or 'なし'}"
                    ),
                    inline=False)

            embed.set_footer(text="ハイブリッド推薦（協調フィルタリング ＋ コンテンツベース）")
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Error in !recommend: {e}")
            await ctx.send(f"エラーが発生しました: {e}")

    @commands.command(name='dummy_similar')
    async def dummy_similar(self, ctx):
        """[Dummy] similar UI via Components V2 (no DB / no profile Select)."""
        dummy_entries = [
            {
                'user_id': 1,
                'display_name': 'kurara_ra',
                'pct': 85, 'sg': 80, 'sh': 92, 'sc': 50,
                'common': 'Valorant, Apex Legends',
                'avatar_url': _DEFAULT_AVATAR_URL,
            },
            {
                'user_id': 2,
                'display_name': 'test_gamer',
                'pct': 62, 'sg': 70, 'sh': 50, 'sc': 30,
                'common': 'Minecraft',
                'avatar_url': 'https://cdn.discordapp.com/embed/avatars/1.png',
            },
            {
                'user_id': 3,
                'display_name': 'pro_player',
                'pct': 45, 'sg': 30, 'sh': 67, 'sc': 20,
                'common': 'Genshin Impact',
                'avatar_url': 'https://cdn.discordapp.com/embed/avatars/2.png',
            },
        ]
        view = SimilarPlayersLayout(
            ctx.author.display_name,
            30,
            dummy_entries,
            footer="コサイン類似度ベース（ダミーデータ）",
            enable_profile_select=False,
        )
        await ctx.send(
            view=view,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @commands.command(name='dummy_recommend')
    async def dummy_recommend(self, ctx):
        """[Dummy] recommend games."""
        embed = discord.Embed(
            title="おすすめのゲーム",
            description=(
                f"**{ctx.author.display_name}** さんへのハイブリッド推薦（過去30日）\n"
                "スコア = フレンドのプレイ状況50% ＋ ジャンルの一致度50%"
            ),
            color=discord.Color.green())

        embed.add_field(
            name=f"{ICON_FIELD}Escape from Tarkov",
            value=(
                f"{_progress_bar(95)} **95%**\n"
                "流行度(CF): 80% / ジャンル(CB): 100%\n"
                "プレイ中: kurara_ra, test_gamer"
            ),
            inline=False)
        embed.add_field(
            name=f"{ICON_FIELD}Overwatch 2",
            value=(
                f"{_progress_bar(78)} **78%**\n"
                "流行度(CF): 90% / ジャンル(CB): 66%\n"
                "プレイ中: pro_player, user123"
            ),
            inline=False)
        embed.add_field(
            name=f"{ICON_FIELD}League of Legends",
            value=(
                f"{_progress_bar(52)} **52%**\n"
                "流行度(CF): 100% / ジャンル(CB): 4%\n"
                "プレイ中: kurara_ra"
            ),
            inline=False)

        embed.set_footer(text="ハイブリッド推薦（ダミーデータ）")
        await ctx.send(embed=embed)
