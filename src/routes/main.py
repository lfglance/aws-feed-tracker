from markdown import Markdown
from flask import Blueprint, render_template, redirect

from src.models import Post, Tag, BedrockCall
from src.helpers import BlankTargetExtension

bp = Blueprint("main", "main")


@bp.route("/")
def main():
    # a list of four lists
    posts = [[]]
    chunk_size = 3
    for post in Post.select().order_by(Post.post_date.desc()):
        if not post.get_summary().exists():
            continue
        if len(posts[-1]) >= chunk_size:
            posts.append([post])
        else:
            posts[-1].append(post)
    return render_template("main/home.html", posts=posts)

@bp.route("/post/<uuid>")
def view_post(uuid):
    post = Post.select().filter(Post.uuid == uuid).first()
    if not post:
        return redirect("/")
    file_name = post.get_summary()
    summary = ""
    with open(file_name, "r") as f:
        summary = f.read()
    md = Markdown(extensions=[BlankTargetExtension()])
    return render_template("main/post.html", post=post, content=md.convert(summary))

@bp.route("/stats")
def stats():
    bedrock_calls = BedrockCall.select()
    return {
        "posts": len(Post.select()),
        "tags": len(Tag.select()),
        "bedrock_calls": len(bedrock_calls),
        "total_costs": sum([c.calculate_cost() for c in bedrock_calls])
    }
