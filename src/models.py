from datetime import datetime, timezone
from uuid import uuid4

from peewee import *

from src import config


db = SqliteDatabase(f"{config.DATA_DIR}/sqlite.db")


def gen_uuid() -> str:
    return str(uuid4())

class Base(Model):
    class Meta:
        database = db

class Post(Base):
    id = CharField()
    uuid = CharField(default=gen_uuid)
    create_date = DateTimeField(default=datetime.now(tz=timezone.utc))
    post_date = DateTimeField()
    title = CharField(unique=False)
    url = CharField(unique=False)
    source = CharField(unique=False)
    location_type = CharField(null=True)
    raw_location = CharField()
    summary_location = CharField(null=True)

class Tag(Base):
    id = CharField(default=gen_uuid)
    create_date = DateTimeField(default=datetime.now(tz=timezone.utc))
    name = CharField(unique=True)

class PostTag(Base):
    id = CharField(default=gen_uuid)
    create_date = DateTimeField(default=datetime.now(tz=timezone.utc))
    post = ForeignKeyField(Post, backref="tags")
    tag = ForeignKeyField(Tag, backref="posts")


db.create_tables([Post, Tag, PostTag])
