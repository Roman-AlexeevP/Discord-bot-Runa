from peewee import Model, SqliteDatabase
import json
with open("config.json") as file:
    config = json.load(file)

database = SqliteDatabase(config.get('database'), pragmas=dict(journal_mode='wal',
                                                               cache_size=-1 * 64000,
                                                               foreign_keys=1,

                                                               ignore_check_constraints=0,
                                                               synchronous=0))


class BaseModel(Model):
    class Meta:
        database = database