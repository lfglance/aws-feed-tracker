import sys
import json
import glob
from time import sleep
from pathlib import Path

import click
import feedparser
from flask import Blueprint

from src import config
from src.models import Post, Tag, BedrockCall
from src.helpers import clean_string, convert_to_dt, query_bedrock, handle_bedrock_response

bp = Blueprint("cli", "cli", cli_group=None)


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
            with open(file_path, "w") as f:
                json.dump(entry, f)
            if not post_id:
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

        sleep(1)

@bp.cli.command("summarize")
def summarize():
    # summarize_model_id = "us.amazon.nova-micro-v1:0"
    summarize_model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    prompt = " ".join([
        "You are a helpful assistant that summarizes AWS blog posts and RSS feeds.",
        "Try to condense the post as much as you can, capturing the most important themes and topics.",
        "If there are links mentioned, please include a glossary of links at the end of the summarization.",
        "Be advised, some blog posts might be a summary in their own, try not to be too repetitive.",
        "Strive to summarize in five sentences or less.",
        "If the post is an instruction or workshop just summarize the contents, do not include steps.",
        "Ensure that the response is valid markdown format and that links, newlines, and lists are formatted properly."
    ])
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
            response = query_bedrock(summarize_model_id, prompt, f.read())
            full_response, _ = handle_bedrock_response(summarize_model_id, response, True)

            with open(summarized_file, "w") as f:
                f.write(full_response)

            summarized = True            
        
        if summarized:
            Path(file).unlink()
        
        print()
        sleep(5)

@bp.cli.command("tag")
def tag():
    # tag_model_id = "us.amazon.nova-pro-v1:0"
    tag_model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    posts = Post.select().order_by(Post.post_date.desc())
    prompt = " ".join([
        "You are a helpful assistant that retrieves metadata from AWS blog posts and RSS feeds.",
        "Your job is to summarize text to the most overall topics in a comma delimited list.", 
        "You must be extremely precise and only grab the most relevant terms and not excessively capture minor components.",
        "Just the highest level themes. The text should be cleaned up, no whitespaces or hanging dashes.",
        "Avoid the basic tag of 'aws' because that is a given."
    ])
    for post in posts:
        if not post.get_tags() and post.get_summary().exists():
            print(f"Tagging post {post.id} {post.uuid}")
            with open(post.get_summary(), "r") as f:
                summary_content = f.read()
                response = query_bedrock(tag_model_id, prompt, "Summarize the following text as a comma-delimited list of 3-8 metadata tags capturing the most relevant key topics, entities, and themes of the following text: " + summary_content)
                full_response, _ = handle_bedrock_response(tag_model_id, response, True)

                tags = full_response.split(",")
                for tag in tags:
                    if tag.strip().lower() == "aws":
                        print("Skipping tag 'AWS'")
                        continue
                    Tag.create(
                        name=tag.strip(),
                        post_id=post.id
                    )
                    print(f"Added tag '{tag.strip()}' to post {post.uuid}")
                sleep(2)


@bp.cli.command("costs")
def costs():
    total = 0
    for cost in BedrockCall.select():
        total += cost.calculate_cost()    
    print(f"Total: ${total:.6f}")

@bp.cli.command("debug")
@click.argument("uuid")
def debug(uuid):
    post = Post.select().filter(Post.uuid == uuid).first()
    if post:
        print(f"{post.title} - {post.uuid} ({post.id}) - {post.post_date}")

def delete_post(uuid):
    post = Post.select().filter(Post.uuid == uuid).first()
    if not post:
        print("That post does not exist!")
        return
    tags = post.get_tags()
    summary = post.get_summary()
    if summary.exists():
        summary.unlink()
    print(f"Deleted summary at {summary}")
    for tag in tags:
        tag.delete_instance()
        print(f"Deleted tag {tag.id} ({tag.name})")
    post.delete_instance()
    print(f"Delete post {post.uuid}")

@bp.cli.command("delete")
@click.argument("uuid")
def delete(uuid):
    delete_post(uuid)

@bp.cli.command("wipe_all")
def wipe():
    for post in Post.select().order_by(Post.post_date.desc()):
        delete_post(post.uuid)
