from flask import Flask, render_template, redirect, url_for
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent
ARTICLE_PATH = BASE_PATH / "articles"

app = Flask(__name__)


@app.get("/")
def main_page_get_handler():
    return redirect(url_for("home_page_get_handler"))

@app.get("/home")
def home_page_get_handler() -> str:
    article_path_list = ARTICLE_PATH.glob("*json")
    return render_template("webpage_main.html", pathlist = article_path_list)

