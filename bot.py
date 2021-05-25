import datetime
import sys
import traceback
from cogs import reminder, Study, tags, Utils
from discord.ext import commands
import discord
import json
from playhouse.sqlite_ext import *
from Utilities import BaseModel
description = """
Бот написан для реализации дистанционного обучения в рамках программы 'Discord'.
"""

with open("config.json") as file:
    config = json.load(file)

initial_extensions = (
    'cogs.admin',
    'cogs.tags',
    'cogs.Polls',
    'cogs.reminder',
    'cogs.Study',
    'cogs.Utils'
)


def _prefix_callable(bot, msg):
    """Returns the prefix."""
    prefix = config.get('prefix')
    return prefix


class StudyBot(commands.AutoShardedBot):
    def __init__(self):
        allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)
        intents = discord.Intents(
            guilds=True,
            members=True,
            bans=True,
            emojis=True,
            voice_states=True,
            messages=True,
            reactions=True,
        )
        super().__init__(command_prefix=_prefix_callable, description=description,
                         pm_help=None, allowed_mentions=allowed_mentions, intents=intents)
        self.client_id = config.get('client_id')

        for extension in initial_extensions:
            try:
                self.load_extension(extension)
            except Exception as e:
                print(f'Failed to load extension {extension}.', file=sys.stderr)
                traceback.print_exc()

    async def on_ready(self):
        if not hasattr(self, 'uptime'):
            self.uptime = datetime.datetime.utcnow()

        print(f'Ready: {self.user} (ID: {self.user.id})')

        BaseModel.database.create_tables([tags.Tag, tags.TagIndex, reminder.Reminders,
                                          Study.Student, Study.Exercise, Study.DoneExercises,
                                          Utils.RoleMessages, Study.Groups])

    def run(self):
        super().run(config["token"], reconnect=True)
