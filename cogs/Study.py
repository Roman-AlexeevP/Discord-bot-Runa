from discord.ext import commands

import datetime
import logging
from datetime import datetime
from discord import Embed, Role, Member, PermissionOverwrite

from Utilities import BaseModel
from playhouse.sqlite_ext import *

logging.basicConfig(filename='bots_errors.log', level=logging.ERROR)
logger = logging.getLogger('peewee')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.ERROR)


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
    member_id = IntegerField(null=False)
    group_id = ForeignKeyField(model=Groups, on_delete='SET NULL')
    guild_id = IntegerField(null=False)


class DoneExercises(BaseModel.BaseModel):
    id = AutoIncrementField(primary_key=True)
    student = ForeignKeyField(model=Student)
    exercise = ForeignKeyField(model=Exercise)
    done_at = DateTimeField(default=datetime.now())
    student_result = TextField(null=False)


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
            logger.exception(ex)
            logger.exception(f"\nExercise with title {title} doesn't exist!\n")

        else:
            return exercise

    @staticmethod
    def get_by_student(member_id: int, guild_id: int):
        try:
            student = StudentManager.get_by_id(member_id, guild_id)

            exercise = Exercise.select().where((Exercise.group_id == student.group_id) &
                                               (Exercise.guild_id == guild_id))
        except DoesNotExist as ex:
            logger.exception(ex)
            logger.exception(f"\nExercise with title {member_id} doesn't exist!\n")

        else:
            return exercise

    @staticmethod
    def update(title: str, guild_id: int, content: str):
        try:
            exercise = Exercise.get((Exercise.title == title) &
                                    (Exercise.guild_id == guild_id))
        except DoesNotExist as ex:
            logger.exception(ex)
            logger.exception(f"\nExercise with title {title} doesn't exist!\n")
        else:
            Exercise.content = content
            return exercise.save()

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
        with BaseModel.database.atomic():
            return student.save()

    @staticmethod
    def get_by_group(group_id: str, guild_id: int):
        group = GroupManager.get_by_name(group_id, guild_id)
        students = Student.select().where((Student.guild_id == guild_id) &
                                          (Student.group_id == group))
        return [student.member_id for student in students]

    @staticmethod
    def get_by_id(member_id: int, guild_id: int):
        try:
            student = Student.get((Student.member_id == member_id) &
                                  (Student.guild_id == guild_id))
        except DoesNotExist as ex:
            logger.exception(ex)
            logger.exception(f"\nExercise with title {member_id} doesn't exist!\n")
        else:
            return student


class DoneExerciseManager:

    @staticmethod
    def insert(done_exercise: DoneExercises):
        with BaseModel.database.atomic():
            return done_exercise.save()

    @staticmethod
    def get_by_student(member_id: int, guild_id: int):
        student = StudentManager.get_by_id(member_id, guild_id)
        try:
            exercises = DoneExercises.select().where(DoneExercises.student == student)
        except Exception as ex:
            logger.exception(ex)
        else:
            return exercises

    @staticmethod
    def get_by_exercise():
        pass


class Study(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="канал")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def role_channel(self, ctx):
        """Взамодействует с ролями/группами для создания персональных каналов"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Аргументы введите")

    @role_channel.command(name="создать")
    async def create_group_channel(self, ctx, *, role: Role = None):
        if role is not None:
            if list(filter(lambda x: role.name == x.name, ctx.guild.text_channels)) or \
                    list(filter(lambda x: role.name == x.name, ctx.guild.voice_channels)):
                await ctx.send("Канал с именем этой роли уже существует")
            else:
                overwrites = {
                    ctx.guild.default_role: PermissionOverwrite(read_messages=False, connect=False),
                    role: PermissionOverwrite(read_messages=True)
                }

                category = next(filter(lambda x: role.name == x.name, ctx.guild.categories), None)

                if not category:
                    category = await ctx.guild.create_category(name=role.name, overwrites=overwrites)

                text_channel = await ctx.guild.create_text_channel(name=role.name,
                                                                   overwrites=overwrites,
                                                                   category=category)
                voice_channel = await ctx.guild.create_voice_channel(name=role.name,
                                                                     overwrites=overwrites,
                                                                     category=category)
                await ctx.send("Каналы и категория созданы!")

    @role_channel.command(name="удалить")
    async def create_group_channel(self, ctx, *, channel_name: str = None):
        if channel_name is not None:
            text_channel = next(filter(lambda x: x.name == channel_name, ctx.guild.text_channels), None)
            voice_channel = next(filter(lambda x: x.name == channel_name, ctx.guild.voice_channels), None)

            if text_channel and voice_channel:
                def to_emoji(c):
                    base = 0x1f1e6
                    return chr(base + c)
                emojis = [to_emoji(x) for x in range(3)]
                message = await ctx.send("Удалить:\n1.Текстовый канал.\n2.Голосовой канал.\n3.Оба.")
                await message.add_reaction(*emojis)

    @commands.group(name="группа")
    @commands.guild_only()
    async def groups(self, ctx):
        """Вносит/удаляет или отображает группы студентов в БД, позволяет увидеть количество студентов данной группы"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Введите аргументы для команды \"добавить\","
                           "\"удалить\",\"обновить\",\"список\""
                           " или название группы для отображения студентов")

    @groups.command(name="студенты")
    async def show_group(self, ctx, *, group_name: str = None):
        """Отображает список студентов данной группы"""
        if group_name is not None:
            try:
                GroupManager.get_by_name(group_name, ctx.guild.id)
            except DoesNotExist:
                await ctx.send("В таблице отсутствуют записи о такой группе")
            else:
                students = StudentManager.get_by_group(group_name, ctx.guild.id)
                if students:
                    student_names = list(map(lambda x: ctx.guild.get_member(x), students))
                    group_emb = [f"**{student[0] + 1}**.{student[1].nick}\n" for student in enumerate(student_names)]
                    embed = Embed(title=" ", color=0x8080ff)
                    embed.add_field(name=f"Список студентов группы \"{group_name}\"",
                                    value=''.join(group_emb), inline=True)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("В таблице отсутствуют записи о студентах этой группы")
        else:
            await ctx.send("Введите название группы!")

    @groups.command(name="добавить")
    @commands.has_permissions(manage_roles=True)
    async def create_group(self, ctx, *, group_name: str):
        """Добавляет группу в БД для дальнейшей работы"""
        try:
            GroupManager.insert(group_name, ctx.guild.id)
        except IntegrityError:
            await ctx.send("Ошибка записи в бд, попробуйте другое имя!")
        else:
            await ctx.send("Группа записана!")

    @groups.command(name="удалить")
    @commands.has_permissions(manage_roles=True)
    async def delete_group(self, ctx, *, group_name: str):
        """Удаляет группу из БД"""
        try:
            GroupManager.delete(group_name, ctx.guild.id)
        except DoesNotExist:
            await ctx.send("Ошибка удаления в бд, попробуйте другое имя!")
        else:
            await ctx.send("Группа удалена!")

    @groups.command(name="обновить")
    @commands.has_permissions(manage_roles=True)
    async def update_groups(self, ctx, *, group: Role = None):
        """Обновляет списки студентов, заполняя их данными пользователей с ролью, соответствующей названию группы"""

        def check(msg):
            return ctx.channel == msg.channel and msg.author == ctx.author

        if group is not None:
            students = list(filter(lambda x: group in x.roles, ctx.guild.members))
            students_data = ((member.id,
                              group.name,
                              ctx.guild.id
                              ) for member in students)
            StudentManager.insert_list(students_data)
            await ctx.send("Таблица студентов обновлена!")

    @groups.command(name="список")
    async def list_groups(self, ctx):
        """Отображает список групп, занесенных в БД"""
        groups_list = GroupManager.get_with_count(ctx.guild.id)
        if groups_list:
            group_emb = [f"**{group[0]}**, количество студентов: **{group[1]}**\n" for group in groups_list]
            embed = Embed(title=" ", color=0x8080ff)
            embed.add_field(name="Список групп", value=''.join(group_emb), inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Группы на этом сервере отсутствуют")

    @commands.group(name="работы")
    @commands.guild_only()
    async def tasks(self, ctx):
        """Работа с просмотром/добавлением практических работ студента"""

        if ctx.invoked_subcommand is None:
            await ctx.send("Введите аргументы команды: \"сдать\" или \"мои\"")

    @tasks.command(name="мои")
    async def my_tasks(self, ctx):
        """Вывод списка всех выданных и отправленных студентом работ"""
        exercises = ExerciseManager.get_by_student(ctx.author.id, ctx.guild.id)
        done_exercises = DoneExerciseManager.get_by_student(ctx.author.id, ctx.guild.id)
        embed = Embed(title=f"Студент {ctx.author.nick}", color=0x8080ff)
        if exercises:
            exercises_emb = [f"**{i[0] + 1}**. {i[1].title}\n" for i in enumerate(exercises)]
            embed.add_field(name=f"Список всех заданий ",
                            value=''.join(exercises_emb), inline=True)
        if done_exercises:
            done_emb = [f"**{i[0] + 1}**. {i[1].exercise.title} -- отправлено\n" for i in
                        enumerate(done_exercises)]
            embed.add_field(name=f"Список сданных заданий",
                            value=''.join(done_emb), inline=True)

        if not exercises and not done_exercises:
            await ctx.send(f"Заданий для вас нет")
        else:
            await ctx.send(embed=embed)

    @tasks.command(name="сдать")
    async def insert_tasks(self, ctx):
        """Занесение работы в БД для рассмотрения учителем и статистики"""

        def check(msg):
            return ctx.channel == msg.channel and msg.author == ctx.author

        student = StudentManager.get_by_id(ctx.author.id, ctx.guild.id)
        if student:
            await ctx.send("Введите название задания, которое собираетесь сдать:")
            exercise_name = await self.bot.wait_for('message', check=check)
            exercise = ExerciseManager.get_by_name(exercise_name.content, ctx.guild.id)
            if exercise:
                await ctx.send("Введите результат работы:")
                student_result = await self.bot.wait_for('message', check=check)
                done_exercise = DoneExercises(
                    student=student,
                    exercise=exercise,
                    done_at=datetime.now(),
                    student_result=student_result.content
                )
                DoneExerciseManager.insert(done_exercise)
                await ctx.send("Результат внесен")
            else:
                await ctx.send("Ошибка в имени задания, попробуйте другое")
        else:
            await ctx.send("Вы отсутствуете в БД, попросите модератора внести вас в таблицу")

    @commands.group(name="задание")
    async def exercise(self, ctx):
        """Создает задание в базе данных для определенной группы или отображает данные о заданиях для преподвателя"""

        if ctx.invoked_subcommand is None:
            await ctx.send("Введите аргументы для команды: \"создать\","
                           " название группы или ник/упоминание студента")

    @commands.has_permissions(manage_messages=True)
    @exercise.command(name="создать")
    async def create_exercise(self, ctx):

        def check(msg):
            return ctx.channel == msg.channel and msg.author == ctx.author

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

    @commands.has_permissions(manage_messages=True)
    @exercise.command(name="группа")
    async def group_exercises(self, ctx, *, group_name: str):
        exercises = ExerciseManager.get_all_by_group(group_name, ctx.guild.id)
        if exercises:
            tags_emb = [f"**{i[0] + 1}**. {i[1]}\n" for i in enumerate(exercises)]
            embed = Embed(title="", color=0x8080ff)
            embed.add_field(name=f"Список заданий группы {group_name}", value=''.join(tags_emb), inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Заданий для группы {group_name} нет")

    @commands.has_permissions(manage_messages=True)
    @exercise.command(name="студент")
    async def group_exercises(self, ctx, *, student: Member = None):

        if student is not None:
            done_exercises = DoneExerciseManager.get_by_student(student.id, ctx.guild.id)
            if done_exercises:
                embed = Embed(title=f"Студент {student.nick}", color=0x8080ff)

                done_emb = [f"**{i[0] + 1}**. {i[1].exercise.title} -- отправлено\n" for i in
                            enumerate(done_exercises)]
                embed.add_field(name=f"Список сданных заданий",
                                value=''.join(done_emb), inline=True)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"У студента {student.nick} нет сданных работ")


def setup(bot):
    bot.add_cog(Study(bot))
