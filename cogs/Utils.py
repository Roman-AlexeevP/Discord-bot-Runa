from discord.ext import commands
import discord
from Utilities import BaseModel
from playhouse.sqlite_ext import *


class MemberRoles(commands.MemberConverter):
    async def convert(self, ctx, argument):
        member = await super().convert(ctx, argument)
        return [role.name for role in member.roles[1:]]  # without "everyone"


class RoleMessages(BaseModel.BaseModel):
    id = AutoIncrementField(primary_key=True)
    message_id = IntegerField(null=False)
    role = TextField(null=False)
    guild_id = IntegerField(null=False)


class RoleMessagesManager:

    @staticmethod
    def insert(message: RoleMessages):
        with BaseModel.database.atomic():
            try:
                return message.save()
            except Exception as e:
                print(e)

    @staticmethod
    def get_by_id(message_id: int, guild_id: int):
        try:
            message = RoleMessages.get((RoleMessages.message_id == message_id) &
                                       (RoleMessages.guild_id == guild_id))
        except DoesNotExist as ex:
            print(ex)
        else:
            return message

    @staticmethod
    def get_all():
        return RoleMessages.select()

    @staticmethod
    def init_db():
        BaseModel.database.connect()
        BaseModel.database.create_tables(RoleMessages, safe=True)
        BaseModel.database.close()


class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.messages = []

    @commands.command(name="роли")
    @commands.guild_only()
    async def member_roles(self, ctx, *, member: MemberRoles):
        await ctx.send("Роли пользователя: **" + ', '.join(member) + "**")

    @commands.command(name="роль")
    @commands.has_permissions(manage_roles=True)
    async def give_role(self, ctx, *, role: str):
        def check(msg):
            return ctx.channel == msg.channel and msg.author == ctx.author

        converter = commands.RoleConverter()
        try:
            await converter.convert(ctx=ctx, argument=role)
        except commands.RoleNotFound:
            await ctx.send(f"Роли {role} нет на данном сервере, хотите создать такую?(+/-)")
            answer = await self.bot.wait_for("message", check=check)
            if answer.content == "+":
                perms = discord.Permissions().all_channel()

                perms.update(manage_channels=False,
                             manage_roles=False,
                             manage_webhooks=False,
                             manage_messages=False,
                             read_message_history=False,
                             mute_members=False,
                             move_members=False,
                             deafen_members=False
                             )

                await ctx.guild.create_role(name=role, permissions=perms)
                await ctx.send("Роль создана!")
            elif answer.content == "-":
                pass
            else:
                await ctx.send("Ошибка ввода, повторите команду")

        else:
            message = await ctx.send(f"**Сообщение отмечено для получение роли \"{role}\"\n" +
                                     f"Отреагируйте любым эмодзи**")
            message = RoleMessages(
                message_id=message.id,
                role=role,
                guild_id=ctx.guild.id
            )
            RoleMessagesManager.insert(message)
            self.messages.append(message)

    @commands.Cog.listener(name="on_ready")
    async def on_ready(self):
        for message in RoleMessagesManager.get_all():
            self.messages.append(message)

    @commands.Cog.listener(name="on_raw_reaction_add")
    async def on_raw_reaction_add(self, reaction_data: discord.RawReactionActionEvent):
        # message = RoleMessagesManager.get_by_id(reaction_data.message_id,
        #                                         reaction_data.guild_id)
        def check_message(user_message):
            return reaction_data.message_id == user_message.message_id and \
                   reaction_data.guild_id == user_message.guild_id

        message = list(filter(check_message, self.messages))
        if message:
            role = discord.utils.get(reaction_data.member.guild.roles, name=message[0].role)
            await reaction_data.member.add_roles(role)


def setup(bot):
    bot.add_cog(Utils(bot))
