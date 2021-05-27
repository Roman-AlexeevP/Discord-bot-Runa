from discord.ext import commands

from playhouse.sqlite_ext import *
import discord
import datetime
import logging
from Utilities import BaseModel, BotEmbed

logging.basicConfig(filename='bots_errors.log', level=logging.ERROR)
logger = logging.getLogger('peewee')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


class Tag(BaseModel.BaseModel):
    """ Класс TagModel используется для описания таблицы Tags в БД

        Основное применение - запись данных из БД в структуру Python

        """
    id = AutoIncrementField(primary_key=True)
    name = TextField(null=False)
    created_date = DateTimeField(null=False, default=datetime.datetime.now())
    content = TextField(null=False)
    author = TextField(null=False)
    category = TextField(default="Общее")
    guild_id = IntegerField(null=False)


class TagIndex(FTSModel):
    rowid = RowIDField()
    name = SearchField()
    content = SearchField()

    class Meta:
        database = BaseModel.database
        options = {'tokenize': 'porter'}


class TagIndexManager:

    @staticmethod
    def insert_index(tag):
        TagIndex.insert({
            TagIndex.rowid: tag.id,
            TagIndex.name: tag.name,
            TagIndex.content: tag.content
        }).execute()


class TagManager:
    """ Класс TagManager используется для запросов в БД

    Основное применение - получение результата запроса в виде модели TagModel или
    индикатора успешно выполненного запроса.

    """

    @staticmethod
    def search(phrase: str, guild_id: int):
        return (Tag
                .select()
                .join(
            TagIndex,
            on=(Tag.id == TagIndex.rowid))
                .where((TagIndex.match(phrase)) &
                       (Tag.guild_id == guild_id)))

    @staticmethod
    def get_names(guild_id: int):
        query = Tag.select().where(Tag.guild_id == guild_id)
        return [tag.name for tag in query]

    @staticmethod
    def get_by_author(author: int, guild_id: int):
        query = Tag.select().where((Tag.author == author) &
                                   (Tag.guild_id == guild_id))
        return [tag.name for tag in query]

    @staticmethod
    def get_by_category(category: str, guild_id: int):
        query = Tag.select().where((Tag.category == category) &
                                   (Tag.guild_id == guild_id))
        return [tag.name for tag in query]

    @staticmethod
    def get_categories(guild_id: int):
        query = Tag.select().where(Tag.guild_id == guild_id)
        return [tag.category for tag in query]

    @staticmethod
    def insert_tag(tag: Tag):
        with BaseModel.database.atomic():
            tag.save()
        TagIndexManager.insert_index(tag)
        return True

    @staticmethod
    def get_by_name(name: str, guild_id: int):
        try:
            tag = Tag.get((Tag.name == name) &
                          (Tag.guild_id == guild_id))
        except DoesNotExist as ex:
            logger.exception(ex)
            logger.exception(f"\nTag with name {name} doesn't exist!\n")
        else:
            return tag

    @staticmethod
    def delete_tag(name: str, guild_id: int):
        try:
            tag = Tag.get((Tag.name == name) & (Tag.guild_id == guild_id))
        except DoesNotExist as ex:
            logger.exception(ex)
            logger.exception(f"\nTag with name {name} doesn't exist!\n")
        else:
            return tag.delete_instance()

    @staticmethod
    def update_content(name: str, content: str, guild_id: int):
        try:
            tag = Tag.get((Tag.name == name) & (Tag.guild_id == guild_id))
        except DoesNotExist as ex:
            logger.exception(ex)
            logger.exception(f"\nTag with name {name} doesn't exist!\n")
        else:
            tag.content = content
            return tag.save()

    @staticmethod
    def init_db():
        BaseModel.database.connect()
        BaseModel.database.create_tables([TagIndex, Tag], safe=True)
        BaseModel.database.close()


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="тег", invoke_without_command=True)
    @commands.guild_only()
    async def tag(self, ctx, *, tag_name: str = None):
        """Работа с записью интересных вам тегов и ссылок и дальнейшего обращения к ним
                Осуществлено: просмотр, создание, редактирование, удаление и поиск тегов
        """
        if tag_name is None:
            await ctx.send("Введите аргументы")
        else:
            tag = TagManager.get_by_name(tag_name.lower(), ctx.guild.id)
            if tag is None:
                await ctx.send(f"Тег с названием \"{tag_name}\" не существует!")
            else:
                await ctx.send(tag.content)

    @tag.command(name="создать")
    async def create_tag(self, ctx, *, tag_name: str = None):
        """Создает тег с заданным названием, категорией и содержимым"""

        def check(msg):
            return ctx.channel == msg.channel and msg.author == ctx.author

        if tag_name is not None:
            if tag_name.lower() in TagManager.get_names(ctx.guild.id):
                await ctx.send("Такое имя уже существует, попробуйте другое")
            elif tag_name.lower() in ["создать", "мои", "удалить", "поиск", "изменить", "все", "категория"]:
                await ctx.send("Это служебное слово, выберите другое название")
            else:
                await ctx.send("Введите содержимое тега и категорию в кавычках при наличии:")
                raw_content = await self.bot.wait_for('message', check=check)
                category = "default"
                content = raw_content.content
                if raw_content.content.count("\'") % 2 == 0 or raw_content.content.count("\"") % 2 == 0:

                    if "\'" in raw_content.content:
                        clear_content = [x for x in raw_content.content.split("\'") if x not in ('', ' ')]
                        content = clear_content[0]
                        category = clear_content[1]

                    elif "\"" in raw_content.content:
                        clear_content = [x for x in raw_content.content.split("\"") if x not in ('', ' ')]
                        content = clear_content[0]
                        category = clear_content[1]

                tag = Tag(
                    name=tag_name.lower(),
                    created_date=datetime.datetime.now(),
                    author=ctx.author.id,
                    content=content,
                    category=category,
                    guild_id=ctx.guild.id
                )
                if TagManager.insert_tag(tag):
                    await ctx.send("Тег создан!")
                else:
                    await ctx.send("Ошибка при создании тега.")
        else:
            await ctx.send("Введите название создаваемого тега")

    @tag.command(name="удалить")
    async def delete_tag(self, ctx, *, tag_name: str = None):
        """Удаляет заданный тег по имени"""
        if tag_name is not None:

            def check_author(msg_id):
                return str(ctx.author.id) == msg_id

            tag = TagManager.get_by_name(tag_name, ctx.guild.id)
            if tag is not None:
                if check_author(tag.author):
                    TagManager.delete_tag(tag.name, ctx.guild.id)
                    await ctx.send("Успешно удалено!")
                else:
                    await ctx.send("Ошибка доступа: вы не являетесь автором тега.")
            else:
                await ctx.send("Ошибка в имени тега, попробуйте другое название.")

        else:
            await ctx.send("Введите название удаляемого тега")

    @tag.command(name="изменить")
    async def update_tag(self, ctx, *, tag_name: str = None):
        """Обновляет содержимое тега по имени"""
        if tag_name is not None:
            def check(msg):
                return ctx.channel == msg.channel and msg.author == ctx.author

            def check_author(msg_id):
                return str(ctx.author.id) == msg_id

            tag = TagManager.get_by_name(tag_name, ctx.guild.id)
            if tag is not None:
                if check_author(tag.author):
                    await ctx.send("Введите новое значение:")
                    message = await self.bot.wait_for('message', check=check)
                    content = message.content
                    TagManager.update_content(tag_name, content, ctx.guild.id)
                    await ctx.send("Успешно обновлено")
                else:
                    await ctx.send("Ошибка доступа: вы не являетесь автором тега.")
            else:
                await ctx.send("Ошибка в имени тега, попробуйте другое название.")
        else:
            await ctx.send("Введите название редактируемого тега")

    @tag.command(name="все")
    async def all_tags(self, ctx):
        """Выводит все теги на сервере"""
        tags = TagManager.get_names(ctx.guild.id)

        embed = BotEmbed.BotEmbed(self.bot.user, title=f"{ctx.guild.name}")
        embed.add_enumerated_field(tags, name="Список тегов")
        await ctx.send(embed=embed)

    @tag.command(name="мои")
    async def my_tags(self, ctx):
        """Выводит теги пользователя, вызвавшего команду"""
        tags = TagManager.get_by_author(ctx.author.id, ctx.guild.id)
        if tags:
            embed = BotEmbed.BotEmbed(self.bot.user, title=f"Теги {ctx.author.nick}")
            embed.add_enumerated_field(tags, name="Список тегов")
            await ctx.send(embed=embed)
        else:
            await ctx.send("У вас нет тегов")

    @tag.command(name="поиск")
    async def search_tag(self, ctx, *, phrase: str = None):
        """Выводит теги, соответствующие указанному слову/фразе"""

        result = [tag.name for tag in TagManager.search(phrase, ctx.guild.id)]
        if result:
            embed = BotEmbed.BotEmbed(self.bot.user, title=f"Поиск по \"{phrase}\"")
            embed.add_enumerated_field(result, name="Вам могут подойти")
            await ctx.send(embed=embed)
        else:
            await ctx.send("Не найдено совпадений!")

    @tag.command(name="категория")
    async def category_tag(self, ctx, *, category: str = None):
        """Выводит названия тегов внутри определенной категории или выводит список категорий по аргументу \"все\""""
        if category is None:
            await ctx.send("Введите нужную вам категорию или 'все' для отображения списка категорий")
        elif category == 'все':
            categories = set(TagManager.get_categories(ctx.guild.id))
            embed = BotEmbed.BotEmbed(self.bot.user, title=f"{ctx.guild.name}")
            embed.add_enumerated_field(categories, name="Список категорий тегов")
            await ctx.send(embed=embed)

        else:
            tags = TagManager.get_by_category(category, ctx.guild.id)
            if tags:
                embed = BotEmbed.BotEmbed(self.bot.user, title=f"{category}")
                embed.add_enumerated_field(tags, name="Список тегов")
                await ctx.send(embed=embed)
            else:
                await ctx.send("Такая категория отсутствует")


def setup(bot):
    bot.add_cog(Tags(bot))
