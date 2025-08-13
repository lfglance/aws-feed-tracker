import re
import sys
import json
import glob
import datetime
from time import mktime, sleep
from pathlib import Path

import boto3
import feedparser
from flask import Blueprint

from src import config
from src.models import Post, PostTag, Tag

bp = Blueprint("cli", "cli", cli_group=None)

model_id = "us.amazon.nova-micro-v1:0"
# model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

def clean_string(input_string):
    return re.sub(r'[^a-zA-Z0-9]+', '_', input_string)

def convert_to_dt(struct_time):
    return datetime.datetime.fromtimestamp(mktime(struct_time))

def query_bedrock(model_id, prompt, query, temperature=0.7, max_tokens=5000):
    bedrock = boto3.client('bedrock-runtime', region_name='us-west-2')
    body = {
        "system": [{"text": prompt}],
        "messages": [{"role": "user", "content": [{"text": query}]}]
    }
    if model_id.startswith("anthropic"):
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "top_p": 0.9,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": query}],
            "system": prompt
        }
    elif model_id.startswith("us.amazon.nova"):
        body = {
            "system": [{"text": prompt}],
            "messages": [{"role": "user", "content": [{"text": query}]}],
            "inferenceConfig": {
                "maxTokens": max_tokens, 
                "topP": 0.9, 
                "topK": 20, 
                "temperature": temperature
            }
        }

    body = json.dumps(body)
    response = bedrock.invoke_model_with_response_stream(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=body
    )
    
    return response

def handle_bedrock_response(model_id, response, print_stdout=True):
    full_response = ""
    results = {}
    if model_id.startswith("anthropic"):
        for event in response['body']:
            if "chunk" in event:
                chunk = json.loads(event["chunk"]["bytes"])
                chunk_type = chunk.get('type')
                if chunk_type == "content_block_delta":
                    text = chunk['delta'].get('text', '')
                    full_response += text
                    if print_stdout:
                        sys.stdout.write(text)
                        sys.stdout.flush()
                elif chunk_type == "message_stop":
                    results = chunk.get("amazon-bedrock-invocationMetrics")
    elif model_id.startswith("us.amazon.nova"):
        for event in response['body']:
            if "chunk" in event:
                chunk = json.loads(event["chunk"]["bytes"])
                if "contentBlockDelta" in chunk:
                    text = chunk["contentBlockDelta"]["delta"].get("text", "")
                    full_response += text
                    if print_stdout:
                        sys.stdout.write(text)
                        sys.stdout.flush()
                elif "amazon-bedrock-invocationMetrics" in chunk:
                    results = chunk.get("amazon-bedrock-invocationMetrics")

    return (full_response, results)

def calculate_cost(model, input_tokens, output_tokens):
    # model id -> input token cost, output token cost
    models = {
        "anthropic.claude-3-5-sonnet-20240620-v1:0": (0.003, 0.015),
        "us.amazon.nova-pro-v1:0": (0.0008, 0.0032),
        "us.amazon.nova-micro-v1:0": (0.000035, 0.00014)
    }
    icp, ocp = models[model]
    input_cost = (input_tokens / 1000) * icp
    output_cost = (output_tokens / 1000) * ocp
    total_cost = input_cost + output_cost
    return total_cost

@bp.cli.command("scrape")
def scrape():
    for feed in config.RSS_FEEDS:
        sys.stdout.write(f"[+] Scraping {feed}...")
        sys.stdout.flush()
        parsed_feed = feedparser.parse(feed)
        sys.stdout.write(f"found {len(parsed_feed.entries)}\n")
        sys.stdout.flush()
        for entry in parsed_feed.entries:
            cleaned_id = clean_string(entry.id)
            file_path = f"data/raw/{cleaned_id}.json"
            dt = convert_to_dt(entry["published_parsed"])
            post_id = Post.select().filter(Post.id == cleaned_id).first()
            if post_id:
                print(f" - Post {post_id} already exists, skipping")
                continue
            post = Post.create(
                id=cleaned_id,
                title=entry["title"],
                url=entry["link"],
                post_date=dt,
                source=feed,
                # location_type
                raw_location=file_path
            )
            print(f" - Post {post.id} ({dt.strftime("%Y%m%d-%H%M%S")}) created and saved at {file_path}")
            with open(file_path, "w") as f:
                json.dump(entry, f)
        sleep(1)


# class Tag(Model):
#     id = CharField(default=gen_uuid)
#     create_date = DateTimeField(default=datetime.now(tz=timezone.UTC))
#     name = CharField(unique=True)

# class PostTag(Model):
#     id = CharField(default=gen_uuid)
#     create_date = DateTimeField(default=datetime.now(tz=timezone.UTC))
#     post = ForeignKeyField(Post, backref="tags")
#     tag = ForeignKeyField(Tag, backref="posts")

@bp.cli.command("summarize")
def summarize():
    for file in glob.glob("data/raw/*.json"):
        summarized = False
        file_name = Path(file).name
        summarized_file = f"data/summarized/{file_name}_summarized.json"
        if Path(summarized_file).exists():
            print(f"Summary {file_name} already exists, skipping/deleting")
            Path(file).unlink()
            continue
        print(f"Summarizing {file_name}")
        with open(file, "r") as f:
            response = query_bedrock(model_id, "You are a helpful assistant that summarizes AWS blog posts and RSS feeds.", f.read())
            full_response, results = handle_bedrock_response(model_id, response, False)
            input_tokens = results.get("inputTokenCount", 0)
            output_tokens = results.get("outputTokenCount", 0)
            cost = calculate_cost(model_id, input_tokens, output_tokens)
            with open(summarized_file, "w") as f:
                f.write(json.dumps({
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "model": model_id,
                    "total_cost": cost,
                    "content": full_response
                }))
            summarized = True            
            print(f"**Input Tokens**: {input_tokens}")
            print(f"**Output Tokens**: {output_tokens}")
            print(f"**Estimated Cost**: ${cost:.6f}")
        
        if summarized:
            Path(file).unlink()
        
        print()
        sleep(5)

@bp.cli.command("costs")
def costs():
    total = 0
    for file in glob.glob("data/summarized/*.json"):
        with open(file, "r") as f:
            data = json.loads(f.read())
            print(f"Cost of {Path(file).name}: ${data.get("total_cost"):.6f}")
            total += data.get("total_cost")
    
    print(f"\nGrand Total: ${total:.6f}")

    