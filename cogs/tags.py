from discord.ext import commands
from peewee import *
import json
from playhouse.sqlite_ext import *
import discord
import datetime
import logging
from Utilities import BaseModel

logging.basicConfig(filename='bots_errors.log', level=logging.ERROR)
logger = logging.getLogger('peewee')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.ERROR)


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

    @commands.command(name="тег")
    @commands.guild_only()
    async def tag(self, ctx, *args):
        """Работа с записью интересных вам тегов и ссылок и дальнейшего обращения к ним
        Осуществлено: просмотр, создание, редактирование и удаление тегов
           """

        def check(msg):
            return ctx.channel == msg.channel and msg.author == ctx.author

        def check_author(msg_id):
            return str(ctx.author.id) == msg_id
        if args:
            if args[0] == "создать":
                await ctx.send("Введите название тега:")
                name = await self.bot.wait_for('message', check=check)

                if name.content.lower() in ["создать", "мои", "удалить", "поиск", "изменить", "все", "категория"]:
                    await ctx.send("Это служебное слово, выберите другое название")
                elif name.content.lower() in TagManager.get_names(ctx.guild.id):
                    await ctx.send("Такое имя уже существует, попробуйте другое")
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
                        name=name.content.lower(),
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

            elif args[0] == "удалить":
                await ctx.send("Введите название тега:")
                message = await self.bot.wait_for('message', check=check)
                name = message.content
                tag = TagManager.get_by_name(name, ctx.guild.id)
                if tag is not None:
                    if check_author(tag.author):
                        TagManager.delete_tag(tag.name, ctx.guild.id)
                        await ctx.send("Успешно удалено!")
                    else:
                        await ctx.send("Ошибка доступа: вы не являетесь автором тега.")
                else:
                    await ctx.send("Ошибка в имени тега, попробуйте другое название.")

            elif args[0] == "изменить":
                await ctx.send("Введите название тега:")
                message = await self.bot.wait_for('message', check=check)
                name = message.content
                tag = TagManager.get_by_name(name, ctx.guild.id)
                if tag is not None:
                    if check_author(tag.author):
                        await ctx.send("Введите новое значение:")
                        message = await self.bot.wait_for('message', check=check)
                        content = message.content
                        TagManager.update_content(name, content, ctx.guild.id)
                        await ctx.send("Успешно обновлено")
                    else:
                        await ctx.send("Ошибка доступа: вы не являетесь автором тега.")
                else:
                    await ctx.send("Ошибка в имени тега, попробуйте другое название.")

            elif args[0] == "все":
                tags = TagManager.get_names(ctx.guild.id)
                tags_emb = [f"**{i[0] + 1}**. {i[1]}\n" for i in enumerate(tags)]
                embed = discord.Embed(title="", color=0x8080ff)
                embed.add_field(name="Список тегов", value=''.join(tags_emb), inline=True)
                await ctx.send(embed=embed)

            elif args[0] == "мои":
                tags = TagManager.get_by_author(ctx.author.id, ctx.guild.id)
                if tags:

                    tags_emb = [f"**{i[0] + 1}**. {i[1]}\n" for i in enumerate(tags)]
                    embed = discord.Embed(title=f"Теги {ctx.author.nick}", color=0x8080ff)
                    embed.add_field(name="Список тегов", value=''.join(tags_emb), inline=True)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("У вас нет тегов")

            elif args[0] == "поиск":
                # await ctx.send("Введите строку или слово, которую хотите найти:")
                # message = await self.bot.wait_for('message', check=check)
                # phrase = message.content
                phrase = args[1:]
                result = TagManager.search(phrase, ctx.guild.id)

                if result:
                    tags_emb = [f"**{i[0] + 1}**. {i[1].name}\n" for i in enumerate(result)]
                    embed = discord.Embed(title=f"Вам могут подойти", color=0x8080ff)
                    embed.add_field(name="Список тегов", value=''.join(tags_emb), inline=True)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("Не найдено совпадений!")
            elif args[0] == "категория":
                if len(args) < 2:
                    await ctx.send("Введите нужную вам категорию или 'все' для отображения списка категорий")
                elif args[1] == 'все':
                    categories = TagManager.get_categories(ctx.guild.id)
                    tags_emb = [f"**{i[0] + 1}**. {i[1]}\n" for i in enumerate(categories)]
                    embed = discord.Embed(title=f"Категории", color=0x8080ff)
                    embed.add_field(name="Список категорий", value=''.join(tags_emb), inline=True)
                    await ctx.send(embed=embed)
                else:
                    tags = TagManager.get_by_category(" ".join(args[1:]), ctx.guild.id)
                    tags_emb = [f"**{i[0] + 1}**. {i[1]}\n" for i in enumerate(tags)]
                    embed = discord.Embed(title=f"{args[1]}", color=0x8080ff)
                    embed.add_field(name="Список тегов", value=''.join(tags_emb), inline=True)
                    await ctx.send(embed=embed)
            else:
                tag_name = " ".join(args)
                tag = TagManager.get_by_name(tag_name.lower(), ctx.guild.id)
                if tag is None:
                    await ctx.send(f"Тег с названием \"{tag_name}\" не существует!")
                else:
                    # await ctx.send(f"tag name: {tag.name}\ntag value: {tag.content} \ntag author: {tag.author}\n"
                    #                f"tag date: {tag.created_date}\ntag category: {tag.category}")
                    await ctx.send(tag.content)
        else:
            await ctx.send("Введите аргументы для команды, может тут будет справка")

def setup(bot):
    bot.add_cog(Tags(bot))
