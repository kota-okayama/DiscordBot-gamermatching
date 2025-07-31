import discord
from discord.ext import commands
from datetime import datetime

class GameTrackerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.add_commands()  # コマンドを明示的に追加

    def add_commands(self):
        """コマンドの明示的な追加"""
        
        @self.command(name='status')
        async def check_status(ctx):
            """全メンバーのステータスをチェック"""
            response = "サーバーメンバーのステータス:\n```"
            for member in ctx.guild.members:
                response += f"\n{member.name}:"
                response += f"\nステータス: {member.status}"
                if member.activity:
                    response += f"\nアクティビティ: {member.activity.name}"
                    response += f"\nタイプ: {member.activity.type}"
                else:
                    response += f"\nアクティビティ: なし"
                response += "\n"
            response += "```"
            await ctx.send(response)

        @self.command(name='debug')
        async def debug_info(ctx):
            """ボットの設定情報を表示"""
            response = "ボットの設定情報:\n```"
            response += f"Intents:\n"
            response += f"- presences: {self.intents.presences}\n"
            response += f"- members: {self.intents.members}\n"
            response += f"- message_content: {self.intents.message_content}\n"
            response += f"\n権限:\n"
            permissions = ctx.guild.me.guild_permissions
            for perm, value in permissions:
                if value:
                    response += f"- {perm}\n"
            response += "```"
            await ctx.send(response)

        @self.command(name='whoami')
        async def whoami(ctx):
            """自分の現在の状態を確認"""
            member = ctx.author
            response = f"あなたの情報:\n```"
            response += f"名前: {member.name}\n"
            response += f"ID: {member.id}\n"
            response += f"ステータス: {member.status}\n"
            if member.activity:
                response += f"アクティビティ: {member.activity.name}\n"
                response += f"アクティビティタイプ: {member.activity.type}\n"
            else:
                response += f"アクティビティ: なし\n"
            response += "```"
            await ctx.send(response)

    async def setup_hook(self):
        print("\n=== セットアップ開始 ===")

    async def on_ready(self):
        print(f'{self.user} としてログインしました!')
        print(f'参加しているサーバー:')
        for guild in self.guilds:
            print(f'- {guild.name}')
        print("\n使用可能なコマンド:")
        print("!status - 全メンバーのステータスを表示")
        print("!debug - ボットの設定を表示")
        print("!whoami - 自分の状態を確認")

    async def on_member_update(self, before, after):
        """メンバーの更新を検知（ステータス、ニックネーム、ロールなど）"""
        print(f"\n=== メンバー更新検知 ===")
        print(f"メンバー: {after.name}")
        print(f"前のステータス: {before.status}")
        print(f"新しいステータス: {after.status}")
        await self.log_activity_change(before, after)

    async def on_presence_update(self, before, after):
        """プレゼンス更新を検知"""
        print(f"\n=== プレゼンス更新検知 ===")
        print(f"メンバー: {after.name}")
        print(f"前のステータス: {before.status}")
        print(f"新しいステータス: {after.status}")
        await self.log_activity_change(before, after)

    async def log_activity_change(self, before, after):
        """アクティビティの変更をログに記録"""
        print(f"\n活動状態の変更:")
        
        # before の状態
        if before.activity:
            print(f"前の活動:")
            print(f"- 名前: {before.activity.name}")
            print(f"- タイプ: {before.activity.type}")
            if hasattr(before.activity, 'details'):
                print(f"- 詳細: {before.activity.details}")
        else:
            print("前の活動: なし")
            
        # after の状態
        if after.activity:
            print(f"新しい活動:")
            print(f"- 名前: {after.activity.name}")
            print(f"- タイプ: {after.activity.type}")
            if hasattr(after.activity, 'details'):
                print(f"- 詳細: {after.activity.details}")
        else:
            print("新しい活動: なし")