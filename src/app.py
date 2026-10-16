import json
from pathlib import Path
from typing import cast
from functools import wraps
from datetime import datetime
from flask import Flask, abort, redirect, render_template, url_for, request

BASE_PATH = Path(__file__).resolve().parent
ARTICLE_PATH = BASE_PATH / "articles"

ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin"

def admin_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if auth is None or auth.username != ADMIN_USER or auth.password != ADMIN_PASSWORD:
            return ("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="Admin"'})
        return view(*args, **kwargs)
    return wrapped

def json_data_parser(file_id=None):
    if file_id is not None:
        article_path = ARTICLE_PATH / f"{file_id}.json"
        if not article_path.exists():
            raise FileNotFoundError
        with article_path.open("r", encoding="utf-8") as f:
            json_data = cast(dict[str, str], json.load(f))
            raw_iso_date = datetime.fromisoformat(json_data.get("timestamp", ""))
            date = f"{raw_iso_date:%B} {raw_iso_date.day} {raw_iso_date:%Y}"
            json_data["timestamp"] = date
            return json_data
    result = []
    for article in ARTICLE_PATH.glob("*.json"):
        with article.open("r", encoding="utf-8") as f:
            data = cast(dict[str, str], json.load(f))
        raw_iso_date = datetime.fromisoformat(data.get("timestamp", ""))
        date = f"{raw_iso_date:%B} {raw_iso_date.day} {raw_iso_date:%Y}"
        result.append(
            {
                "article_title": data.get("title", ""),
                "article_timestamp": date,
                "article_name": article.stem,
            }
        )
    return result


def _renumber_articles() -> None:
    # TODO
    # later fix whatever this is into something normal and actually working
    articles = sorted(ARTICLE_PATH.glob("*.json"), key=lambda path: int(path.stem))
    temporary_paths: list[Path] = []

    for _, article_path in enumerate(articles, start=1):
        temporary_path = article_path.with_suffix(".tmp")
        _ = article_path.rename(temporary_path)
        temporary_paths.append(temporary_path)

    for index, temporary_path in enumerate(temporary_paths, start=1):
        _ = temporary_path.rename(ARTICLE_PATH / f"{index}.json")


def article_creator(title: str, content: str, timestamp: str) -> None:
    _ = _renumber_articles()
    payload = {"title": title, "content": content, "timestamp": timestamp}
    articles_ids = (int(path.stem) for path in ARTICLE_PATH.glob("*.json"))
    new_id = max(articles_ids, default=0) + 1
    new_path = ARTICLE_PATH / f"{new_id}.json"
    with new_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

app = Flask(__name__)


@app.get("/")
def mainpage_get_handler():
    return redirect(url_for("homepage_get_handler"))


@app.get("/home")
def homepage_get_handler() -> str:
    articles_data = json_data_parser()
    return render_template("webpage_head.html", articles_data=articles_data)


@app.get("/article/<int:article_id>")
def articlepage_get_handler(article_id: int):
    try:
        article_data = json_data_parser(article_id)
    except FileNotFoundError:
        abort(404)
    return render_template("webpage_article.html", article=article_data)

@app.get("/admin")
@admin_auth
def adminpage_get_handler():
    articles_data = json_data_parser()
    return render_template("webpage_admin.html", articles_data=articles_data)

@app.get("/new")
@admin_auth
def newpage_get_handler():
    return render_template("webpage_new.html")

@app.post("/new")
@admin_auth
def newpage_post_handler():
    article_title = request.form["title"]
    article_publishing_date = request.form["publishing_date"]
    article_content = request.form["content"]

    create_timestamp = datetime.fromisoformat(article_publishing_date)
    create_timestamp_iso = create_timestamp.isoformat()

    _ = article_creator(article_title, article_content, create_timestamp_iso)

    return redirect(url_for("adminpage_get_handler"))
