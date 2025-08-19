from collections import OrderedDict

from flask import Blueprint, render_template, request
from peewee import fn

from src.models import Post, Tag

bp = Blueprint("htmx", "htmx", url_prefix="/htmx")


@bp.route("/search")
def search():
    posts = [[]]
    _tags = Tag.select()
    query = request.args.get("query")
    if query:
        _tags = _tags.where(fn.LOWER(Tag.name).contains(query))
    _posts = list(OrderedDict.fromkeys([tag.post for tag in _tags]))
    chunk_size = 3
    for post in _posts:
        if not post.get_summary().exists():
            continue
        if len(posts[-1]) >= chunk_size:
            posts.append([post])
        else:
            posts[-1].append(post)
    return render_template("htmx/list_posts.html", posts=posts)

