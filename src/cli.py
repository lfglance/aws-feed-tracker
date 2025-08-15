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
from src.models import Post, Tag, BedrockCall

bp = Blueprint("cli", "cli", cli_group=None)


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

@bp.cli.command("summarize")
def summarize():
    summarize_model_id = "us.amazon.nova-micro-v1:0"
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
            response = query_bedrock(summarize_model_id, "You are a helpful assistant that summarizes AWS blog posts and RSS feeds.", f.read())
            full_response, results = handle_bedrock_response(summarize_model_id, response, False)
            input_tokens = results.get("inputTokenCount", 0)
            output_tokens = results.get("outputTokenCount", 0)
            br_call = BedrockCall.create(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_id=summarize_model_id
            )

            with open(summarized_file, "w") as f:
                f.write(full_response)

            summarized = True            
            print(f"**Input Tokens**: {input_tokens}")
            print(f"**Output Tokens**: {output_tokens}")
            print(f"**Estimated Cost**: ${br_call.calculate_cost():.6f}")
        
        if summarized:
            Path(file).unlink()
        
        print()
        sleep(5)

@bp.cli.command("tag")
def tag():
    tag_model_id = "us.amazon.nova-pro-v1:0"
    posts = Post.select()
    for post in posts:
        if not post.tags:
            file_name = Path(f"data/summarized/{post.id}.json_summarized.json")
            summary_content = None
            with open(file_name, "r") as f:
                summary_content = f.read()
            response = query_bedrock(tag_model_id, "You are a helpful assistant that retrieves metadata from AWS blog posts and RSS feeds.", "Summarize the following text as a comma-delimited list of 3-6 metadata tags capturing key topics, entities, and themes: " + summary_content)
            full_response, results = handle_bedrock_response(tag_model_id, response, False)
            input_tokens = results.get("inputTokenCount", 0)
            output_tokens = results.get("outputTokenCount", 0)
            br_call = BedrockCall.create(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_id=tag_model_id
            )
            tags = full_response.split(",")[0:4]
            for tag in tags:
                if tag.strip().lower() == "aws":
                    print("Skipping tag 'AWS'")
                    continue
                Tag.create(
                    name=tag.strip(),
                    post=post
                )
                print(f"Added tag '{tag.strip()}' to post {post.uuid}")

            print(f"**Input Tokens**: {input_tokens}")
            print(f"**Output Tokens**: {output_tokens}")
            print(f"**Estimated Cost**: ${br_call.calculate_cost():.6f}")
            sleep(2)


@bp.cli.command("costs")
def costs():
    total = 0
    for cost in BedrockCall.select():
        total += cost.calculate_cost()    
    print(f"\nTotal: ${total:.6f}")

@bp.cli.command("debug")
def debug():
    posts = Post.select()
    for post in posts:
        if not post.tags:
            print("no tags")
        else:
            for tag in post.tags:
                print(tag)