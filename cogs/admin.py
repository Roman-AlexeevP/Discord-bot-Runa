from discord.ext import commands
import discord


class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command(hidden=True)
    async def load(self, ctx, *, module):
        """Loads a module."""
        try:
            self.bot.load_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command(hidden=True)
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        try:
            self.bot.unload_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.group(name='reload', hidden=True, invoke_without_command=True)
    async def _reload(self, ctx, *, module):
        """Reloads a module."""
        try:
            self.bot.reload_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command(name="очистить")
    @commands.is_owner()
    async def clear_messages(self, ctx, mgs_count: int):
        """Удаляет n сообщений в текущем канале"""
        deleted_messages = await ctx.message.channel.purge(limit=mgs_count + 1)
        await ctx.message.channel.send(f'Удалено {len(deleted_messages)} сообщений', delete_after=3)

    @commands.command(name="mute")
    @commands.is_owner()
    async def mute(self, ctx, member: discord.Member):
        """Устанавливает запрет на отправку сообщений данному пользователю"""
        await ctx.message.channel.set_permissions(member, send_messages=False)
        await ctx.send(member.mention + ", Вы не можете отправлять сообщения на сервере!")

    @commands.command(name="unmute")
    @commands.is_owner()
    async def unmute(self, ctx, member: discord.Member):
        """Снимает запрет на отправку сообщений данному пользователю"""
        await ctx.message.channel.set_permissions(member, send_messages=True)
        await ctx.send(member.mention + ", Вы можете отправлять сообщения на сервере c текущего момента.")

    @commands.command(name="отключить", hidden=True)
    @commands.is_owner()
    async def logout(self, ctx):
        """Выключение бота аппаратно"""
        await ctx.send(f"Завершаю работу!")
        self.bot.logout()
        raise SystemExit(0)

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """Удаление данного пользователя с сервера"""
        if reason is None:
            reason = f'Action done by {ctx.author} (ID: {ctx.author.id})'

        await ctx.guild.kick(member, reason=reason)
        await ctx.send('\N{OK HAND SIGN}')


def setup(bot):
    bot.add_cog(Admin(bot))
