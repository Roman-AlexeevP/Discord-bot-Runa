import datetime
from datetime import datetime, timedelta

from discord import Embed
from discord.ext import commands, tasks
from playhouse.sqlite_ext import *

from Utilities import BaseModel


class Reminders(BaseModel.BaseModel):
    id = IntegerField(primary_key=True, unique=True)
    created_at = DateTimeField(null=False, default=datetime.now())
    ended_at = DateTimeField(null=False)
    reason = TextField(null=False)
    author_id = IntegerField(null=False)
    channel_id = IntegerField(null=False)


class ReminderManager:

    @staticmethod
    def get_all_reminders() -> list:
        query = Reminders.select()
        return list(query)

    @staticmethod
    def get_by_author(author: int) -> dict:
        query = Reminders.select().where(Reminders.author_id == author)
        reasons = [rem.reason for rem in query]
        end_time = [rem.ended_at for rem in query]
        return dict(zip(reasons, end_time))

    @staticmethod
    def insert_reminder(reminder: Reminders):
        with BaseModel.database.atomic():
            return reminder.save()

    @staticmethod
    def delete_reminder(reminder: Reminders):
        return reminder.delete_instance()

    @staticmethod
    def init_db():
        BaseModel.database.connect()
        BaseModel.database.create_tables(Reminders)
        BaseModel.database.close()


def string_to_date(string_to_parse: str) -> datetime:
    regex_delta_absolute = r"\b(?:в|на) (\d\d:\d\d|\d?(?: вечера| утра| ночи)?)\b"
    regex_delta_relative = r"\bчерез (\d{1,3}) (минут\w?|час\w?\w?|секунд\w?)\b"
    match = re.fullmatch(regex_delta_relative, string_to_parse)
    if not match:
        return False
    elif re.fullmatch(regex_delta_relative, string_to_parse):
        return get_relative_delta(count=match[1], unit=match[2])
    elif re.fullmatch(regex_delta_absolute, string_to_parse):
        match = re.fullmatch(regex_delta_absolute, string_to_parse)
        return get_absolute_delta(string_to_parse)


def get_relative_delta(unit, count):
    reminder_date = datetime.now()

    if re.fullmatch(r"\bминут\w?\b", unit):

        delta = timedelta(days=0, hours=0, minutes=float(count))
        return reminder_date + delta
    elif re.fullmatch(r"\bчас\w?\w?\b", unit):

        delta = timedelta(days=0, hours=float(count), minutes=0)
        return reminder_date + delta
    elif re.fullmatch(r"\bсекунд\w?\b", unit):

        delta = timedelta(days=0, hours=0, minutes=0, seconds=float(count))
        return reminder_date + delta
    else:
        return reminder_date


def get_absolute_delta(date_string):
    regex_delta_absolute = r"\b(?:в|на) (\d\d:\d\d|(\d)?( вечера| утра| ночи)?)\b"
    match = re.fullmatch(regex_delta_absolute, date_string)
    if re.fullmatch(r"\bв (\d\d:\d\d)\b", date_string):
        pass
    elif re.fullmatch(r"\b(?:в|на) (\d)?( вечера| утра| ночи)?\b", date_string):
        pass

    print(f"match 0 -- {match[1]}\nmatch 1 -- {match[2]}\nmatch 3 -- {match[3]}")


class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = ReminderManager.get_all_reminders()
        self.check_reminders.start()


    @commands.command(name="напомни")
    @commands.guild_only()
    async def remind(self, ctx, *args):
        """Создает напоминание на указаное время в формате "через n минут/часов/секунд"
        """
        def check(msg):
            return ctx.channel == msg.channel and msg.author == ctx.author

        try:
            ended_date = string_to_date(' '.join(args))
        except Exception as e:
            print(e)
        else:
            await ctx.send("Введите что именно вам напомнить: ")
            raw_content = await self.bot.wait_for('message', check=check)

            reminder = Reminders(
                ended_at=ended_date,
                reason=raw_content.content,
                author_id=ctx.author.id,
                channel_id=ctx.channel.id
            )
            ReminderManager.insert_reminder(reminder)
            self.reminders.append(reminder)
            await ctx.send("Напоминание записано!")

    @commands.command(name="напоминания")
    @commands.guild_only()
    async def my_reminders(self, ctx):
        """
        Выводит все ваши актуальные напоминания
        """
        dict_rem = ReminderManager.get_by_author(ctx.author.id)
        embed = Embed(title=f"{ctx.author.nick} напоминания",
                      color=0x8080ff)
        for reason, time in dict_rem.items():
            embed.add_field(name=reason,
                            value=f"время - {time:%Y-%m-%d %H:%M:%S}",
                            inline=False)
        await ctx.send(embed=embed)

    @tasks.loop(seconds=10.0)
    async def check_reminders(self):
        delta = timedelta(seconds=10)
        if self.reminders:
            now = datetime.now()

            for reminder in self.reminders:
                is_ready = reminder.ended_at - now < delta and (reminder.ended_at - now).days >= 0
                if is_ready:
                    channel = self.bot.get_channel(reminder.channel_id)
                    user = self.bot.get_user(reminder.author_id)
                    await channel.send(user.mention + ", напоминаю вам: " + reminder.reason)
                    ReminderManager.delete_reminder(reminder)

    @check_reminders.before_loop
    async def before_checking(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Reminder(bot))
