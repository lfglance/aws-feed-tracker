from flask import Flask

from src import cli
from src import config 

app = Flask(__name__)
# app.config.from_envvar("FLASK_SECRETS")
# app.secret_key = app.config["SECRET_KEY"]
app.register_blueprint(cli.bp)


if __name__ == "__main__":
    app.run()