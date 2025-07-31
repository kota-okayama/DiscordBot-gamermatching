import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import io
import colorsys
import math

class CalendarBot(commands.Bot):
    def add_commands(self):
        @self.command(name='calendar')
        async def show_calendar(ctx):
            """ゲームプレイカレンダーを画像として表示"""
            try:
                sessions = self.get_game_sessions(ctx.author.id)
                
                if not sessions:
                    await ctx.send("プレイ記録が見つかりませんでした。")
                    return
                
                image = self.generate_calendar_image(sessions)
                
                with io.BytesIO() as image_binary:
                    image.save(image_binary, 'PNG')
                    image_binary.seek(0)
                    
                    await ctx.send(
                        f"{ctx.author.name}の週間ゲームプレイカレンダー",
                        file=discord.File(fp=image_binary, filename='calendar.png')
                    )
                    
            except Exception as e:
                await ctx.send(f"カレンダーの生成中にエラーが発生しました: {str(e)}")
                raise e

    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        
        # モダンなカラーパレット
        self.base_colors = {
            'background': (248, 250, 252),  # より明るい背景色
            'grid': (203, 213, 225),        # よりソフトなグリッド線
            'text': (51, 65, 85),           # より柔らかいテキスト色
            'accent': (59, 130, 246)        # アクセントカラー
        }
        
        # 影のエフェクト用の設定
        self.shadow_color = (0, 0, 0, 30)   
        self.shadow_offset = 3

        # レイアウトの基本パラメータ
        self.legend_params = {
            'item_width': 200,        # 各ゲームアイテムの幅
            'padding_top': 60,        # 凡例上部のパディング（タイトル用）
            'padding_bottom': 30,     # 凡例下部のパディング
            'item_height': 35,        # 各アイテムの高さ
            'row_spacing': 15,        # 行間のスペース
            'color_box_size': 25,     # カラーボックスのサイズ
            'text_offset_x': 35,      # テキストの横方向オフセット
            'text_offset_y': 4,       # テキストの縦方向オフセット
        }

        self.add_commands()

    def calculate_legend_dimensions(self, game_count, width, margin):
        """凡例の寸法を計算"""
        # 利用可能な幅を計算
        available_width = width - margin * 2 - 40
        # 1行に表示できるアイテム数を計算
        items_per_row = max(1, available_width // self.legend_params['item_width'])
        # 必要な行数を計算
        rows = math.ceil(game_count / items_per_row)
        
        # 1行の実際の高さ（アイテムの高さ + 行間）
        row_height = self.legend_params['item_height'] + self.legend_params['row_spacing']
        
        # 凡例の高さを計算
        legend_height = (
            self.legend_params['padding_top'] +           # 上部パディング
            (row_height * rows) -                         # 全行の高さ
            self.legend_params['row_spacing'] +           # 最後の行間を引く
            self.legend_params['padding_bottom']          # 下部パディング
        )
        
        return legend_height, items_per_row, row_height

    def generate_colors_for_games(self, game_names):
        """ゲーム名に基づいてパステルカラーを生成"""
        colors = {}
        hue_step = 1.0 / (len(game_names) + 1)
        
        for i, game in enumerate(sorted(game_names)):
            hue = i * hue_step
            rgb = colorsys.hsv_to_rgb(hue, 0.4, 0.95)
            colors[game] = tuple(int(x * 255) for x in rgb)
        
        return colors

    def draw_rounded_rectangle(self, draw, xy, radius, fill, outline=None):
        """角丸の四角形を描画"""
        x1, y1, x2, y2 = xy
        height = y2 - y1
        
        if height < radius * 2:
            min_height = 4
            center_y = (y1 + y2) / 2
            y1 = center_y - min_height/2
            y2 = center_y + min_height/2
            draw.rectangle([x1, y1, x2, y2], fill=fill, outline=outline)
            return
        
        diameter = radius * 2
        draw.ellipse([x1, y1, x1 + diameter, y1 + diameter], fill=fill, outline=outline)
        draw.ellipse([x2 - diameter, y1, x2, y1 + diameter], fill=fill, outline=outline)
        draw.ellipse([x1, y2 - diameter, x1 + diameter, y2], fill=fill, outline=outline)
        draw.ellipse([x2 - diameter, y2 - diameter, x2, y2], fill=fill, outline=outline)
        
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)

    def get_game_sessions(self, user_id):
        """データベースからゲームセッションを取得"""
        conn = sqlite3.connect('game_history.db')
        c = conn.cursor()
        
        one_week_ago = datetime.now() - timedelta(days=7)
        
        c.execute('''
            SELECT 
                game_name,
                start_time,
                end_time,
                duration
            FROM game_sessions
            WHERE user_id = ? AND datetime(start_time) >= datetime(?)
            ORDER BY start_time
        ''', (str(user_id), one_week_ago.isoformat()))
        
        sessions = c.fetchall()
        conn.close()
        return sessions

    def generate_calendar_image(self, sessions):
        """改善されたカレンダー画像を生成"""
        width = 1200
        calendar_height = 830  
        padding = 50          
        margin = 60
        minutes_per_pixel = 2
        day_width = (width - margin * 2) // 7
        
        # ゲーム数に基づいて凡例のサイズを計算
        unique_games = {session[0] for session in sessions}
        game_colors = self.generate_colors_for_games(unique_games)
        legend_box_height, items_per_row, row_height = self.calculate_legend_dimensions(
            len(game_colors), width, margin
        )
        
        total_height = calendar_height + padding + legend_box_height
        
        image = Image.new('RGB', (width + self.shadow_offset, total_height + self.shadow_offset), 'white')
        main_image = Image.new('RGB', (width, total_height), self.base_colors['background'])
        draw = ImageDraw.Draw(main_image)
        
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/google-noto-cjk/NotoSansJP-Regular.otf", 24)
            font = ImageFont.truetype("/usr/share/fonts/google-noto-cjk/NotoSansJP-Regular.otf", 16)
            small_font = ImageFont.truetype("/usr/share/fonts/google-noto-cjk/NotoSansJP-Regular.otf", 14)
            print("フォントの読み込みに成功しました")
        except Exception as e:
            print(f"フォント読み込みエラー: {str(e)}")
            title_font = font = small_font = ImageFont.load_default()

        # カレンダー部分の描画
        current_week = datetime.now().strftime('%Y/%m Week %U')
        draw.text((margin, 20), f"Gaming Activity - {current_week}", 
                self.base_colors['text'], font=title_font)

        # 曜日の描画
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for i, day in enumerate(days):
            x = margin + i * day_width
            day_color = self.base_colors['text']
            if i >= 5:  # 土日の色を変える
                day_color = (66, 153, 225) if i == 5 else (236, 72, 153)
            draw.text((x + 10, margin + 10), day, day_color, font=font)

        # 時間軸の描画
        for hour in range(25):
            y = margin + 50 + (hour * 60) // minutes_per_pixel
            # 偶数時間の背景をわずかに暗く
            if hour < 24:
                if hour % 2 == 0:
                    draw.rectangle(
                        [(margin, y), (width - margin, y + 60 // minutes_per_pixel)],
                        fill=(245, 247, 250)
                    )
            
            # グリッド線
            draw.line(
                [(margin, y), (width - margin, y)],
                fill=self.base_colors['grid'],
                width=2
            )
            
            # 時間表示
            time_text = f'{hour:02d}:00'
            text_width = draw.textlength(time_text, font=small_font)
            draw.text(
                (margin - text_width - 15, y - 8),
                time_text,
                self.base_colors['text'],
                font=small_font
            )

        # 垂直グリッド線
        for i in range(8):
            x = margin + i * day_width
            draw.line(
                [(x, margin + 50), (x, calendar_height)],
                fill=self.base_colors['grid'],
                width=2
            )

        # ゲームセッションの描画
        for game_name, start_time, end_time, duration in sessions:
            try:
                start = datetime.fromisoformat(start_time)
                end = datetime.fromisoformat(end_time)
                
                day_index = start.weekday()
                
                # 日付またぎの場合の処理
                if start.date() != end.date():
                    # 日付が変わる時点で分割
                    midnight = datetime.combine(end.date(), datetime.min.time())
                    
                    # 開始日のセッション
                    start_minutes = start.hour * 60 + start.minute
                    end_minutes = 24 * 60  # 23:59
                    
                    start_y = margin + 50 + start_minutes // minutes_per_pixel
                    end_y = margin + 50 + end_minutes // minutes_per_pixel
                    
                    x = margin + day_index * day_width
                    color = game_colors[game_name]
                    
                    self.draw_rounded_rectangle(
                        draw,
                        [x + 5, start_y, x + day_width - 5, end_y],
                        radius=5,
                        fill=color
                    )
                    
                    # 翌日のセッション
                    start_minutes = 0
                    end_minutes = end.hour * 60 + end.minute
                    
                    start_y = margin + 50
                    end_y = margin + 50 + end_minutes // minutes_per_pixel
                    
                    x = margin + ((day_index + 1) % 7) * day_width
                    
                    self.draw_rounded_rectangle(
                        draw,
                        [x + 5, start_y, x + day_width - 5, end_y],
                        radius=5,
                        fill=color
                    )
                    
                else:
                    # 通常の同日セッション
                    start_minutes = start.hour * 60 + start.minute
                    end_minutes = end.hour * 60 + end.minute
                    
                    # 時間が逆転している場合は調整
                    if end_minutes <= start_minutes:
                        end_minutes = start_minutes + 1
                    
                    start_y = margin + 50 + start_minutes // minutes_per_pixel
                    end_y = margin + 50 + end_minutes // minutes_per_pixel
                    
                    x = margin + day_index * day_width
                    color = game_colors[game_name]
                    
                    self.draw_rounded_rectangle(
                        draw,
                        [x + 5, start_y, x + day_width - 5, end_y],
                        radius=5,
                        fill=color
                    )
                    
                    # セッションが一定の高さある場合のみゲーム名を表示
                    if end_y - start_y > 30:
                        text_y = start_y + (end_y - start_y) // 2 - 8
                        game_name_short = game_name[:15] + '...' if len(game_name) > 15 else game_name
                        draw.text((x + 10, text_y), game_name_short, self.base_colors['text'], font=small_font)
            
            except Exception as e:
                print(f"エラー発生: ゲーム {game_name} の処理中 - {str(e)}")
                continue

        # 凡例の描画
        legend_y = calendar_height + padding
        self.draw_rounded_rectangle(
            draw,
            [margin, legend_y, width - margin, legend_y + legend_box_height],
            radius=10,
            fill=(255, 255, 255)
        )

        draw.text(
            (margin + 20, legend_y + 20),
            "Game List",
            self.base_colors['text'],
            font=font
        )

        # 凡例アイテムを横に並べて描画
        games = sorted(game_colors.items())
        for i, (game, color) in enumerate(games):
            row = i // items_per_row
            col = i % items_per_row
            
            # 基準位置の計算
            x = margin + 30 + col * self.legend_params['item_width']
            y = (legend_y + 
                 self.legend_params['padding_top'] + 
                 row * row_height)
            
            # カラーボックスの描画
            self.draw_rounded_rectangle(
                draw,
                [x, y, 
                 x + self.legend_params['color_box_size'], 
                 y + self.legend_params['color_box_size']],
                radius=3,
                fill=color
            )
            
            # ゲーム名の描画
            draw.text(
                (x + self.legend_params['text_offset_x'], 
                 y + self.legend_params['text_offset_y']),
                game,
                self.base_colors['text'],
                font=small_font
            )

        image.paste(main_image, (0, 0))
        return image

    async def setup_hook(self):
        print("Bot is setting up...")
    async def on_ready(self):
        print(f'{self.user} としてログインしました!')
        print('使用可能なコマンド:')
        print('!calendar - ゲームプレイカレンダーを表示')
