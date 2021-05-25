from discord.ext import commands, tasks
from discord.utils import get
import datetime
import logging
from datetime import datetime, timedelta
from discord import Embed, Role, Message
from peewee import *
from Utilities import BaseModel
from playhouse.sqlite_ext import *


class Groups(BaseModel.BaseModel):
    id = AutoIncrementField(primary_key=True)
    group_name = TextField(null=False, unique=True)
    guild_id = IntegerField(null=False)


class Exercise(BaseModel.BaseModel):
    id = AutoIncrementField(primary_key=True)
    title = TextField(null=False)
    content = TextField(null=False)
    created_at = DateTimeField(null=True, default=datetime.now())
    ended_at = DateTimeField(null=True)
    group_id = ForeignKeyField(model=Groups, on_delete='SET NULL')
    guild_id = IntegerField(null=False)


class Student(BaseModel.BaseModel):
    id = AutoIncrementField(primary_key=True)
    member_id = IntegerField(null=False )
    group_id = ForeignKeyField(model=Groups, on_delete='SET NULL')
    guild_id = IntegerField(null=False)


class DoneExercises(BaseModel.BaseModel):
    id = AutoIncrementField(primary_key=True)
    student = ForeignKeyField(model=Student)
    exercise = ForeignKeyField(model=Exercise)
    done_at = DateTimeField(default=datetime.now())


class GroupManager:

    @staticmethod
    def insert(group_name: str, guild_id: int):
        group = Groups(group_name=group_name,
                       guild_id=guild_id)
        return group.save()

    @staticmethod
    def delete(group_name: str, guild_id: int):
        group = Groups.get((Groups.group_name == group_name) & (Groups.guild_id == guild_id))
        return group.delete_instance()

    @staticmethod
    def get_with_count(guild_id: int):
        query = (Groups
                 .select(Groups.group_name, fn.COUNT(Student.id).alias("count"))
                 .join_from(Groups, Student, JOIN.LEFT_OUTER)
                 .where(Groups.guild_id == guild_id)
                 .group_by(Groups.group_name))
        return [(group.group_name, group.count) for group in query]

    @staticmethod
    def get_by_name(group_name: str, guild_id: int):
        group = Groups.get((Groups.group_name == group_name) &
                           (Groups.guild_id == guild_id))
        return group


class ExerciseManager:

    @staticmethod
    def insert(exercise: Exercise):
        with BaseModel.database.atomic():
            return exercise.save()

    @staticmethod
    def get_by_name(title: str, guild_id: int):
        try:
            exercise = Exercise.select().where((Exercise.title == title) &
                                               (Exercise.guild_id == guild_id))
        except DoesNotExist as ex:
            # logger.exception(ex)
            # logger.exception(f"\nExercise with title {title} doesn't exist!\n")
            print(f"\nExercise with title {title} doesn't exist!\n")
        else:
            return exercise

    @staticmethod
    def update(title: str, guild_id: int, content: str):
        try:
            exercise = Exercise.get((Exercise.title == title) &
                                    (Exercise.guild_id == guild_id))
        except DoesNotExist as ex:
            print(f"\nExercise with title {title} doesn't exist!\n")
        else:
            Exercise.content = content
            return Exercise.save()

    @staticmethod
    def get_all_by_group(group_name: str, guild_id: int):
        group = GroupManager.get_by_name(group_name, guild_id)
        query = Exercise.select() \
            .where((Exercise.group_id == group) &
                   (Exercise.guild_id == guild_id))

        return [exercise.title for exercise in query]

    @staticmethod
    def get_all(guild_id: int):
        query = Exercise.select().where(Exercise.guild_id == guild_id)
        return [exercise.title for exercise in query]


class StudentManager:

    @staticmethod
    def insert_list(students: list[tuple]):

        for student in students:
            Student.get_or_create(
                member_id=student[0],
                group_id=GroupManager.get_by_name(student[1], student[2]),
                guild_id=student[2]
            )

    @staticmethod
    def insert(student: Student):
        return student.save()

    @staticmethod
    def get_by_group(group_id: str, guild_id: int):
        group = GroupManager.get_by_name(group_id, guild_id)
        students = Student.select().where((Student.guild_id == guild_id) &
                                          (Student.group_id == group))
        return [student.member_id for student in students]


class Study(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="группа")
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def groups(self, ctx, *args):
        """Вносит/удаляет или отображает группы студентов в БД, позволяет увидеть количество студентов данной группы"""
        def check(msg):
            return ctx.channel == msg.channel and msg.author == ctx.author

        if args:

            if args[0] == "добавить":
                await ctx.send("Введите название группы")
                group_name = await self.bot.wait_for("message", check=check)

                try:
                    GroupManager.insert(group_name.content, ctx.guild.id)
                except IntegrityError:
                    await ctx.send("Ошибка записи в бд, попробуйте другое имя!")
                else:
                    await ctx.send("Группа записана!")

            elif args[0] == "удалить":
                await ctx.send("Введите название группы")
                group_name = await self.bot.wait_for("message", check=check)

                try:
                    GroupManager.delete(group_name.content, ctx.guild.id)
                except DoesNotExist:
                    await ctx.send("Ошибка удаления в бд, попробуйте другое имя!")
                else:
                    await ctx.send("Группа удалена!")

            elif args[0] == "список":
                groups_list = GroupManager.get_with_count(ctx.guild.id)
                if groups_list:
                    group_emb = [f"**{group[0]}**, количество студентов: **{group[1]}**\n" for group in groups_list]
                    embed = Embed(title=" ", color=0x8080ff)
                    embed.add_field(name="Список групп", value=''.join(group_emb), inline=True)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("Группы на этом сервере отсутствуют")

            elif args[0] == "обновить":
                converter = commands.RoleConverter()

                await ctx.send("Введите название группы")
                group_name = await self.bot.wait_for("message", check=check)
                group_role = await converter.convert(ctx=ctx, argument=group_name.content)
                students = list(filter(lambda x: group_role in x.roles, ctx.guild.members))
                students_data = ((member.id,
                                  group_name.content,
                                  ctx.guild.id
                                  ) for member in students)
                StudentManager.insert_list(students_data)
                await ctx.send("Таблица студентов обновлена!")

            else:

                students = StudentManager.get_by_group(args[0], ctx.guild.id)
                if students:
                    student_names = list(map(lambda x: ctx.guild.get_member(x), students))
                    group_emb = [f"**{student[0]+1}**.{student[1].nick}\n" for student in enumerate(student_names)]
                    embed = Embed(title=" ", color=0x8080ff)
                    embed.add_field(name=f"Список студентов группы \"{args[0]}\"", value=''.join(group_emb), inline=True)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("В таблице отсутствуют записи о студентах этой группы")
        else:
            await ctx.send("Введите аргументы для команды")

    @commands.command(name="работы")
    @commands.guild_only()
    async def tasks(self, ctx, *args):
        """Отображает работы студента/группы"""
        if args:
            pass
        else:
            await ctx.send("Работы такие-то")

    @commands.command(name="задание")
    @commands.has_permissions(manage_messages=True)
    async def exercise(self, ctx, *args):
        """Создает задание в базе данных для определенной группы"""

        def check(msg):
            return ctx.channel == msg.channel and msg.author == ctx.author

        if args:
            if args[0] == "создать":
                await ctx.send("Введите для какой группы задание:")
                group_id = await self.bot.wait_for('message', check=check)
                await ctx.send("Введите название задания:")
                title = await self.bot.wait_for('message', check=check)
                await ctx.send("Введите содержимое задания:")
                raw_content = await self.bot.wait_for('message', check=check)
                if ExerciseManager.insert(Exercise(
                        title=title.content,
                        content=raw_content.content,
                        created_at=datetime.now(),
                        group_id=GroupManager.get_by_name(group_id.content, ctx.guild.id),
                        guild_id=ctx.guild.id
                )):
                    await ctx.send("Задание записано!")
                else:
                    await ctx.send("Ошибка записи")

            elif len(args) > 0:
                group_id = args[0]
                exercises = ExerciseManager.get_all_by_group(group_id, ctx.guild.id)
                if exercises:
                    tags_emb = [f"**{i[0] + 1}**. {i[1]}\n" for i in enumerate(exercises)]
                    embed = Embed(title="", color=0x8080ff)
                    embed.add_field(name=f"Список заданий {group_id}", value=''.join(tags_emb), inline=True)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send(f"Заданий для группы {group_id} нет")
        else:
            await ctx.send("Введите агрументы для команды!")


def setup(bot):
    bot.add_cog(Study(bot))
