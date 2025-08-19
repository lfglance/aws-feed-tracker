from flask import Flask

from src import cli
from src.routes import main, htmx
from src import filters


app = Flask(__name__, template_folder="src/templates", static_folder="src/static")

# app.config.from_envvar("FLASK_SECRETS")
# app.secret_key = app.config["SECRET_KEY"]
app.register_blueprint(cli.bp)
app.register_blueprint(main.bp)
app.register_blueprint(htmx.bp)
app.register_blueprint(filters.bp)


if __name__ == "__main__":
    app.run()