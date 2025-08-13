from datetime import datetime, timezone
from uuid import uuid4

from peewee import *

from src import config


db = SqliteDatabase(f"{config.DATA_DIR}/sqlite.db")


def gen_uuid() -> str:
    return str(uuid4())

class FeedItem(Model):
    id = CharField(default=gen_uuid)
    create_date = DateTimeField(default=datetime.now(tz=timezone.UTC))
    title = CharField(unique=True)
    url = CharField(unique=True)
    source = CharField(unique=True)
    

# "page": {
#         "id": "string (uuid)",
#         "create_date": "timestamp",
#         "title": "string (page title from rss)",
#         "url": "string (url)",
#         "source": "string (rss url)"
#     },

db.create_tables([Node])
