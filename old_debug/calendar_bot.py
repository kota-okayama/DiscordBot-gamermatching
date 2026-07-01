import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import io
import colorsys
import math

DB_PATH = 'game_history.db'

class CalendarBot(commands.Bot):

    # ──────────────────────────────────────────────
    # 定数・設定
    # ──────────────────────────────────────────────
    THEME = {
        'bg':          (15,  17,  26),   # #0F111A ダーク背景
        'panel':       (22,  25,  37),   # #161925 カード背景
        'grid':        (40,  44,  60),   # グリッド線
        'text':        (220, 225, 240),  # メインテキスト
        'subtext':     (120, 130, 160),  # サブテキスト（時間軸）
        'weekend_sat': (80,  160, 240),  # 土曜：ブルー
        'weekend_sun': (240, 90,  130),  # 日曜：ピンク
        'accent':      (100, 180, 255),  # アクセント
        'shadow':      (0,   0,   0,  60),
    }

    LAYOUT = {
        'width':          1280,
        'header_h':       70,    # タイトルエリア高さ
        'day_header_h':   50,    # 曜日ヘッダー高さ
        'time_col_w':     65,    # 時間軸の幅
        'right_pad':      20,
        'cell_h_per_min': 1.0,   # 1分=1px（24h = 1440px）
        'legend_item_w':  220,
        'legend_pad_top': 50,
        'legend_pad_bot': 30,
        'legend_item_h':  36,
        'legend_row_gap': 10,
        'color_box':      20,
    }

    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self._add_commands()

    # ──────────────────────────────────────────────
    # コマンド登録
    # ──────────────────────────────────────────────
    def _add_commands(self):

        @self.command(name='calendar')
        async def show_calendar(ctx, offset: int = 0):
            """
            ゲームプレイカレンダーを画像として表示

            使い方:
              !calendar      → 今週 (月〜日)
              !calendar -1   → 先週 (月〜日)
            """
            try:
                week_start, week_end = self._get_week_range(offset)
                sessions = self._get_game_sessions(ctx.author.id, week_start, week_end)

                if not sessions:
                    period = (
                        f"{week_start.strftime('%Y/%m/%d')} 〜 "
                        f"{week_end.strftime('%Y/%m/%d')}"
                    )
                    embed = discord.Embed(
                        title="📅 プレイ記録なし",
                        description=f"{period} のプレイ記録が見つかりませんでした。",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=embed)
                    return

                image = self._generate_calendar_image(sessions, week_start, week_end)

                with io.BytesIO() as buf:
                    image.save(buf, 'PNG')
                    buf.seek(0)
                    period = (
                        f"{week_start.strftime('%Y/%m/%d')} 〜 "
                        f"{week_end.strftime('%Y/%m/%d')}"
                    )
                    await ctx.send(
                        f"🎮 **{ctx.author.display_name}** のゲームプレイカレンダー ({period})",
                        file=discord.File(fp=buf, filename='calendar.png')
                    )

            except Exception as e:
                await ctx.send(f"カレンダーの生成中にエラーが発生しました: {str(e)}")
                raise e

    # ──────────────────────────────────────────────
    # データ取得
    # ──────────────────────────────────────────────
    def _get_week_range(self, offset: int = 0) -> tuple[datetime, datetime]:
        """今週(offset=0)または先週(offset=-1)の月〜日を返す"""
        today = datetime.now()
        # 今週の月曜日
        monday = today - timedelta(days=today.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        # offsetで週をずらす
        week_start = monday + timedelta(weeks=offset)
        week_end   = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return week_start, week_end

    def _get_game_sessions(
        self, user_id, week_start: datetime, week_end: datetime
    ) -> list[tuple]:
        """DBから指定週のゲームセッションを取得"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT game_name, start_time, end_time, duration
            FROM game_sessions
            WHERE user_id = ?
              AND datetime(start_time) >= datetime(?)
              AND datetime(start_time) <= datetime(?)
            ORDER BY start_time
        ''', (str(user_id), week_start.isoformat(), week_end.isoformat()))
        sessions = c.fetchall()
        conn.close()
        return sessions

    # ──────────────────────────────────────────────
    # 描画ユーティリティ
    # ──────────────────────────────────────────────
    def _generate_colors(self, game_names: set) -> dict[str, tuple]:
        """ゲームごとに鮮やかなHSL色を割り当て（ダークモード映え）"""
        colors = {}
        n = len(game_names)
        for i, game in enumerate(sorted(game_names)):
            hue = i / max(n, 1)
            # 彩度0.75、明度0.85 → 鮮やかで視認性が高い
            r, g, b = colorsys.hsv_to_rgb(hue, 0.72, 0.88)
            colors[game] = (int(r * 255), int(g * 255), int(b * 255))
        return colors

    def _draw_rounded_rect(
        self, draw: ImageDraw.ImageDraw,
        xy: tuple, radius: int,
        fill: tuple, outline: tuple = None, outline_width: int = 1
    ):
        """角丸矩形を描画"""
        x1, y1, x2, y2 = xy
        h = y2 - y1
        if h < radius * 2:
            # 高さが小さすぎる場合は普通の矩形
            draw.rectangle([x1, y1, x2, y2], fill=fill, outline=outline, width=outline_width)
            return
        d = radius * 2
        draw.ellipse([x1,        y1,        x1 + d, y1 + d], fill=fill)
        draw.ellipse([x2 - d,    y1,        x2,     y1 + d], fill=fill)
        draw.ellipse([x1,        y2 - d,    x1 + d, y2    ], fill=fill)
        draw.ellipse([x2 - d,    y2 - d,    x2,     y2    ], fill=fill)
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)

    def _load_fonts(self) -> tuple:
        """日本語フォントを読み込む（失敗時はデフォルト）"""
        font_candidates = [
            "/usr/share/fonts/google-noto-cjk/NotoSansJP-Regular.otf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
        for path in font_candidates:
            try:
                title  = ImageFont.truetype(path, 26)
                normal = ImageFont.truetype(path, 16)
                small  = ImageFont.truetype(path, 13)
                tiny   = ImageFont.truetype(path, 11)
                print(f"✅ フォント読み込み成功: {path}")
                return title, normal, small, tiny
            except Exception:
                continue
        print("⚠️ フォント読み込み失敗: デフォルトフォントを使用")
        default = ImageFont.load_default()
        return default, default, default, default

    # ──────────────────────────────────────────────
    # カレンダー画像生成
    # ──────────────────────────────────────────────
    def _generate_calendar_image(
        self, sessions: list, week_start: datetime, week_end: datetime
    ) -> Image.Image:
        L = self.LAYOUT
        T = self.THEME

        # ── サイズ計算 ──
        calendar_h  = int(24 * 60 * L['cell_h_per_min'])  # 1440px
        content_w   = L['width'] - L['time_col_w'] - L['right_pad']
        day_w       = content_w // 7

        unique_games = {s[0] for s in sessions}
        game_colors  = self._generate_colors(unique_games)
        legend_h     = self._calc_legend_height(len(game_colors), content_w)

        total_h = L['header_h'] + L['day_header_h'] + calendar_h + legend_h
        img  = Image.new('RGB', (L['width'], total_h), T['bg'])
        draw = ImageDraw.Draw(img)

        title_font, normal_font, small_font, tiny_font = self._load_fonts()

        # ── ヘッダー（タイトル＋期間） ──
        period_str = (
            f"{week_start.strftime('%Y/%m/%d')}（月）〜 "
            f"{week_end.strftime('%Y/%m/%d')}（日）"
        )
        draw.text((L['time_col_w'], 20), "🎮 Gaming Activity", T['accent'], font=title_font)
        draw.text((L['time_col_w'], 50), period_str, T['subtext'], font=small_font)

        # ── 曜日ヘッダー ──
        days_ja = ['月', '火', '水', '木', '金', '土', '日']
        day_y = L['header_h']
        for i, label in enumerate(days_ja):
            x = L['time_col_w'] + i * day_w
            if i == 5:
                color = T['weekend_sat']
            elif i == 6:
                color = T['weekend_sun']
            else:
                color = T['text']
            # 日付を取得
            day_date = week_start + timedelta(days=i)
            date_str = day_date.strftime('%-m/%-d')
            draw.text(
                (x + day_w // 2 - 15, day_y + 6),
                f"{label}  {date_str}", color, font=normal_font
            )

        # ── カレンダーグリッド ──
        cal_y = L['header_h'] + L['day_header_h']

        # 背景パネル（カレンダーエリア）
        self._draw_rounded_rect(
            draw,
            [L['time_col_w'] - 5, cal_y, L['width'] - L['right_pad'], cal_y + calendar_h],
            radius=8, fill=T['panel']
        )

        # 偶数時間の薄い帯
        for hour in range(0, 24, 2):
            y = cal_y + int(hour * 60 * L['cell_h_per_min'])
            h = int(60 * L['cell_h_per_min'])
            draw.rectangle(
                [L['time_col_w'], y, L['width'] - L['right_pad'], y + h],
                fill=(20, 23, 35)
            )

        # 水平グリッド線（1時間ごと）
        for hour in range(25):
            y = cal_y + int(hour * 60 * L['cell_h_per_min'])
            lw = 2 if hour % 6 == 0 else 1
            draw.line(
                [(L['time_col_w'], y), (L['width'] - L['right_pad'], y)],
                fill=T['grid'], width=lw
            )
            # 時間ラベル
            time_str = f"{hour:02d}:00"
            draw.text(
                (2, y - 8),
                time_str, T['subtext'], font=tiny_font
            )

        # 垂直グリッド線（曜日ごと）
        for i in range(8):
            x = L['time_col_w'] + i * day_w
            draw.line(
                [(x, cal_y), (x, cal_y + calendar_h)],
                fill=T['grid'], width=1
            )

        # ── セッションの描画 ──
        for game_name, start_str, end_str, duration in sessions:
            try:
                start = datetime.fromisoformat(start_str)
                end   = datetime.fromisoformat(end_str)
                color = game_colors.get(game_name, (150, 150, 150))

                def draw_session_block(s: datetime, e: datetime, day_idx: int):
                    s_min = s.hour * 60 + s.minute
                    e_min = e.hour * 60 + e.minute
                    if e_min <= s_min:
                        e_min = s_min + 1  # 最小1分
                    sy = cal_y + int(s_min * L['cell_h_per_min'])
                    ey = cal_y + int(e_min * L['cell_h_per_min'])
                    x  = L['time_col_w'] + day_idx * day_w

                    # メインブロック
                    self._draw_rounded_rect(
                        draw,
                        [x + 3, sy + 1, x + day_w - 3, ey - 1],
                        radius=4, fill=color
                    )
                    # ラベル（高さ十分なら表示）
                    block_h = ey - sy
                    if block_h >= 16:
                        short_name = game_name[:14] + '…' if len(game_name) > 14 else game_name
                        draw.text(
                            (x + 6, sy + 3),
                            short_name,
                            (20, 20, 30),
                            font=tiny_font
                        )
                    if block_h >= 30:
                        dur_min = (e - s).seconds // 60
                        draw.text(
                            (x + 6, sy + 16),
                            f"{dur_min}min",
                            (40, 40, 55),
                            font=tiny_font
                        )

                # 日付またぎ処理
                if start.date() != end.date():
                    day_idx = (start.date() - week_start.date()).days
                    midnight = datetime.combine(end.date(), datetime.min.time())
                    if 0 <= day_idx < 7:
                        draw_session_block(start, midnight, day_idx)
                    next_idx = day_idx + 1
                    if 0 <= next_idx < 7:
                        draw_session_block(midnight, end, next_idx)
                else:
                    day_idx = (start.date() - week_start.date()).days
                    if 0 <= day_idx < 7:
                        draw_session_block(start, end, day_idx)

            except Exception as e:
                print(f"⚠️ セッション描画エラー ({game_name}): {e}")
                continue

        # ── 凡例の描画 ──
        self._draw_legend(draw, game_colors, cal_y + calendar_h, content_w, normal_font, small_font)

        return img

    def _calc_legend_height(self, game_count: int, content_w: int) -> int:
        L = self.LAYOUT
        items_per_row = max(1, content_w // L['legend_item_w'])
        rows = math.ceil(game_count / items_per_row)
        row_h = L['legend_item_h'] + L['legend_row_gap']
        return L['legend_pad_top'] + row_h * rows + L['legend_pad_bot']

    def _draw_legend(
        self, draw, game_colors: dict,
        top_y: int, content_w: int,
        normal_font, small_font
    ):
        L = self.LAYOUT
        T = self.THEME
        items_per_row = max(1, content_w // L['legend_item_w'])
        legend_y = top_y + 20

        draw.text(
            (L['time_col_w'], legend_y),
            "Game List", T['accent'], font=normal_font
        )

        for i, (game, color) in enumerate(sorted(game_colors.items())):
            row = i // items_per_row
            col = i % items_per_row
            x = L['time_col_w'] + col * L['legend_item_w']
            y = legend_y + L['legend_pad_top'] + row * (L['legend_item_h'] + L['legend_row_gap'])

            # カラーボックス
            self._draw_rounded_rect(
                draw,
                [x, y, x + L['color_box'], y + L['color_box']],
                radius=3, fill=color
            )
            # ゲーム名
            label = game[:24] + '…' if len(game) > 24 else game
            draw.text((x + L['color_box'] + 8, y + 3), label, T['text'], font=small_font)

    # ──────────────────────────────────────────────
    # ライフサイクル
    # ──────────────────────────────────────────────
    async def setup_hook(self):
        print("CalendarBot: セットアップ開始")

    async def on_ready(self):
        print(f'{self.user} としてログインしました!')
        print('使用可能なコマンド:')
        print('  !calendar      - 今週のカレンダーを表示')
        print('  !calendar -1   - 先週のカレンダーを表示')
