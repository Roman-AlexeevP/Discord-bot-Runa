from discord import Embed, User
from discord.ext.commands import AutoShardedBot


class BotEmbed(Embed):
    def __init__(self, bot_user: User, title: str = ""):
        super(BotEmbed, self).__init__(title=title, color=0xcfd242)
        self.set_author(name=bot_user.name, icon_url=bot_user.avatar_url)

    def add_enumerated_field(self, iter_content: list, name: str = "Список"):
        field_content = ''.join([f"**{i[0] + 1}**. {i[1]}\n" for i in enumerate(iter_content)])
        self.add_field(name=name, value=field_content, inline=True)


