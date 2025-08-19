from pathlib import Path
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

    def get_summary(self):
        fp = f"data/summarized/{self.id}.json_summarized.json"
        return Path(fp)

    def get_tags(self, amount=0):
        tags = Tag.select().filter(Tag.post == self)
        if amount:
            tags = tags.limit(amount)
        return tags

class Tag(Base):
    id = CharField(default=gen_uuid)
    create_date = DateTimeField(default=datetime.now(tz=timezone.utc))
    name = CharField(unique=False)
    post = ForeignKeyField(Post, backref="tags", unique=False, on_delete="CASCADE")

class BedrockCall(Base):
    id = CharField(default=gen_uuid)
    create_date = DateTimeField(default=datetime.now(tz=timezone.utc))
    input_tokens = IntegerField()
    output_tokens = IntegerField()
    model_id = CharField()

    def calculate_cost(self):
        # model id -> input token cost, output token cost
        models = {
            "anthropic.claude-3-5-sonnet-20240620-v1:0": (0.003, 0.015),
            "us.amazon.nova-pro-v1:0": (0.0008, 0.0032),
            "us.amazon.nova-micro-v1:0": (0.000035, 0.00014)
        }
        icp, ocp = models[self.model_id]
        input_cost = (self.input_tokens / 1000) * icp
        output_cost = (self.output_tokens / 1000) * ocp
        total_cost = input_cost + output_cost
        return total_cost


db.create_tables([Post, Tag, BedrockCall])
