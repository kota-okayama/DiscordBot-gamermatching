"""CalendarCog: ゲームプレイカレンダー画像生成"""
import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import io
import colorsys
import math

DB_PATH = 'game_history.db'


class CalendarCog(commands.Cog, name='Calendar'):

    THEME = {
        'bg':          (15,  17,  26),
        'panel':       (22,  25,  37),
        'grid':        (40,  44,  60),
        'text':        (220, 225, 240),
        'subtext':     (120, 130, 160),
        'weekend_sat': (80,  160, 240),
        'weekend_sun': (240, 90,  130),
        'accent':      (100, 180, 255),
    }
    LAYOUT = {
        'width': 1280, 'header_h': 70, 'day_header_h': 50,
        'time_col_w': 65, 'right_pad': 20, 'cell_h_per_min': 1.0,
        'legend_item_w': 220, 'legend_pad_top': 50, 'legend_pad_bot': 30,
        'legend_item_h': 36, 'legend_row_gap': 10, 'color_box': 20,
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='calendar')
    async def show_calendar(self, ctx, offset: int = 0):
        """
        ゲームプレイカレンダーを画像として表示

        !calendar      → 今週（月〜日）
        !calendar -1   → 先週（月〜日）
        """
        try:
            week_start, week_end = self._get_week_range(offset)
            sessions = self._get_sessions(ctx.author.id, week_start, week_end)

            period = (f"{week_start.strftime('%Y/%m/%d')} 〜 "
                      f"{week_end.strftime('%Y/%m/%d')}")

            if not sessions:
                await ctx.send(embed=discord.Embed(
                    title="📅 プレイ記録なし",
                    description=f"{period} のプレイ記録が見つかりませんでした。",
                    color=discord.Color.orange()))
                return

            img = self._generate_image(sessions, week_start, week_end)
            with io.BytesIO() as buf:
                img.save(buf, 'PNG')
                buf.seek(0)
                await ctx.send(
                    f"🎮 **{ctx.author.display_name}** のカレンダー ({period})",
                    file=discord.File(fp=buf, filename='calendar.png'))
        except Exception as e:
            await ctx.send(f"エラーが発生しました: {e}")
            raise

    def _get_week_range(self, offset: int = 0):
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        start = monday + timedelta(weeks=offset)
        end   = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return start, end

    def _get_sessions(self, user_id, week_start: datetime, week_end: datetime):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT game_name, start_time, end_time, duration
            FROM game_sessions
            WHERE user_id=? AND datetime(start_time)>=datetime(?) AND datetime(start_time)<=datetime(?)
            ORDER BY start_time
        ''', (str(user_id), week_start.isoformat(), week_end.isoformat()))
        rows = c.fetchall()
        conn.close()
        return rows

    def _generate_colors(self, game_names):
        colors = {}
        n = len(game_names)
        for i, g in enumerate(sorted(game_names)):
            r, g2, b = colorsys.hsv_to_rgb(i / max(n, 1), 0.72, 0.88)
            colors[g] = (int(r*255), int(g2*255), int(b*255))
        return colors

    def _draw_rounded_rect(self, draw, xy, radius, fill):
        x1, y1, x2, y2 = xy
        h = y2 - y1
        if h < radius * 2:
            draw.rectangle([x1, y1, x2, y2], fill=fill)
            return
        d = radius * 2
        draw.ellipse([x1, y1, x1+d, y1+d], fill=fill)
        draw.ellipse([x2-d, y1, x2, y1+d], fill=fill)
        draw.ellipse([x1, y2-d, x1+d, y2], fill=fill)
        draw.ellipse([x2-d, y2-d, x2, y2], fill=fill)
        draw.rectangle([x1+radius, y1, x2-radius, y2], fill=fill)
        draw.rectangle([x1, y1+radius, x2, y2-radius], fill=fill)

    def _load_fonts(self):
        candidates = [
            "/usr/share/fonts/google-noto-cjk/NotoSansJP-Regular.otf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        ]
        for path in candidates:
            try:
                return (ImageFont.truetype(path, 26), ImageFont.truetype(path, 16),
                        ImageFont.truetype(path, 13), ImageFont.truetype(path, 11))
            except Exception:
                continue
        d = ImageFont.load_default()
        return d, d, d, d

    def _generate_image(self, sessions, week_start: datetime, week_end: datetime):
        L, T = self.LAYOUT, self.THEME
        cal_h = int(24 * 60 * L['cell_h_per_min'])
        content_w = L['width'] - L['time_col_w'] - L['right_pad']
        day_w = content_w // 7

        unique_games = {s[0] for s in sessions}
        colors = self._generate_colors(unique_games)
        n_games = len(colors)
        items_per_row = max(1, content_w // L['legend_item_w'])
        rows = math.ceil(n_games / items_per_row)
        legend_h = L['legend_pad_top'] + rows * (L['legend_item_h'] + L['legend_row_gap']) + L['legend_pad_bot']

        total_h = L['header_h'] + L['day_header_h'] + cal_h + legend_h
        img = Image.new('RGB', (L['width'], total_h), T['bg'])
        draw = ImageDraw.Draw(img)
        title_f, norm_f, small_f, tiny_f = self._load_fonts()

        # ヘッダー
        period = (f"{week_start.strftime('%Y/%m/%d')}（月）〜 "
                  f"{week_end.strftime('%Y/%m/%d')}（日）")
        draw.text((L['time_col_w'], 20), "🎮 Gaming Activity", T['accent'], font=title_f)
        draw.text((L['time_col_w'], 50), period, T['subtext'], font=small_f)

        # 曜日ヘッダー
        day_y = L['header_h']
        for i, label in enumerate(['月','火','水','木','金','土','日']):
            x = L['time_col_w'] + i * day_w
            color = T['weekend_sat'] if i == 5 else T['weekend_sun'] if i == 6 else T['text']
            date_str = (week_start + timedelta(days=i)).strftime('%-m/%-d')
            draw.text((x + day_w//2 - 15, day_y + 8), f"{label} {date_str}", color, font=norm_f)

        # カレンダーグリッド
        cal_y = L['header_h'] + L['day_header_h']
        self._draw_rounded_rect(draw,
            [L['time_col_w']-5, cal_y, L['width']-L['right_pad'], cal_y+cal_h],
            radius=8, fill=T['panel'])

        for hour in range(0, 24, 2):
            y = cal_y + int(hour * 60 * L['cell_h_per_min'])
            h = int(60 * L['cell_h_per_min'])
            draw.rectangle([L['time_col_w'], y, L['width']-L['right_pad'], y+h], fill=(20, 23, 35))

        for hour in range(25):
            y = cal_y + int(hour * 60 * L['cell_h_per_min'])
            draw.line([(L['time_col_w'], y), (L['width']-L['right_pad'], y)],
                      fill=T['grid'], width=2 if hour % 6 == 0 else 1)
            draw.text((2, y-8), f"{hour:02d}:00", T['subtext'], font=tiny_f)

        for i in range(8):
            x = L['time_col_w'] + i * day_w
            draw.line([(x, cal_y), (x, cal_y+cal_h)], fill=T['grid'], width=1)

        # セッション描画
        def draw_block(s, e, day_idx):
            if not (0 <= day_idx < 7):
                return
            sm = s.hour * 60 + s.minute
            em = e.hour * 60 + e.minute
            if em <= sm:
                em = sm + 1
            sy = cal_y + int(sm * L['cell_h_per_min'])
            ey = cal_y + int(em * L['cell_h_per_min'])
            x  = L['time_col_w'] + day_idx * day_w
            color = colors.get(game_name, (150, 150, 150))
            self._draw_rounded_rect(draw, [x+3, sy+1, x+day_w-3, ey-1], radius=4, fill=color)
            if ey - sy >= 16:
                label = game_name[:14] + '…' if len(game_name) > 14 else game_name
                draw.text((x+6, sy+3), label, (20, 20, 30), font=tiny_f)
            if ey - sy >= 30:
                dur_m = (e - s).seconds // 60
                draw.text((x+6, sy+16), f"{dur_m}min", (40, 40, 55), font=tiny_f)

        for game_name, start_str, end_str, _ in sessions:
            try:
                s = datetime.fromisoformat(start_str)
                e = datetime.fromisoformat(end_str)
                if s.date() != e.date():
                    midnight = datetime.combine(e.date(), datetime.min.time())
                    draw_block(s, midnight, (s.date() - week_start.date()).days)
                    draw_block(midnight, e, (e.date() - week_start.date()).days)
                else:
                    draw_block(s, e, (s.date() - week_start.date()).days)
            except Exception as err:
                print(f"描画エラー: {err}")

        # 凡例
        legend_y = cal_y + cal_h + 20
        draw.text((L['time_col_w'], legend_y), "Game List", T['accent'], font=norm_f)
        for i, (gname, color) in enumerate(sorted(colors.items())):
            row = i // items_per_row
            col = i % items_per_row
            x = L['time_col_w'] + col * L['legend_item_w']
            y = legend_y + L['legend_pad_top'] + row * (L['legend_item_h'] + L['legend_row_gap'])
            self._draw_rounded_rect(draw, [x, y, x+L['color_box'], y+L['color_box']], radius=3, fill=color)
            label = gname[:24] + '…' if len(gname) > 24 else gname
            draw.text((x+L['color_box']+8, y+3), label, T['text'], font=small_f)

        return img
