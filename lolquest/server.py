from pathlib import Path
import time

import click
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from lolquest.configuration import QuestConfig
from lolquest.controller import Controller
from lolquest.filters import register_filters
from lolquest.utils import synchronized
from lolquest.views import HintView
from lolquest.views import StandingsTableView
from omegaconf import OmegaConf
import yaml


app = Flask(__name__)
controller = Controller()


@app.route("/", methods=["GET", "POST"])
def start_page():
    if "team_id" in session:
        return redirect(url_for("quest_page"))
    if "admin_id" in session:
        return redirect(url_for("admin_page"))
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        team_id = request.form["team_id"]
        password = request.form["password"]

        if controller.team_login(
            team_id=team_id,
            password=password,
        ):
            session["team_id"] = team_id
            return redirect(url_for("quest_page"))

        if controller.admin_login(
            admin_id=team_id,
            password=password,
        ):
            session["admin_id"] = team_id
            return redirect(url_for("admin_page"))

    return render_template("start.html")


@app.route("/quest", methods=["GET", "POST"])
@synchronized(controller.lock)
def quest_page():
    if "team_id" not in session:
        return redirect(url_for("login_page"))

    team_id = session["team_id"]

    stage_upped = controller.up_stage_if_needed(team_id=team_id, timestamp=time.time())

    team_info = controller.get_team_info(team_id)

    if request.method == "POST":
        code = request.form["code"]
        stage_upped |= controller.team_enter_code(team_id=team_id, code=code)

    if team_info.finished:
        return redirect(url_for("end_page"))

    if stage_upped:
        return redirect(url_for("quest_page"))

    stage = controller.config.stages[team_info.stage]
    stage_start_time = team_info.stage_entered_timestamps[-1]

    hints = [HintView(hint, stage_start_time) for hint in stage.hints]

    override_open_stages = None
    if stage_upped:
        override_open_stages = [team_info.stage]

    standings_view = StandingsTableView.open_stages_from_request(
        standings_data=controller.get_standings_data(),
        override=override_open_stages,
        override_default=[team_info.stage],
    )

    return render_template(
        "stage.html",
        stage_content=f"stages/stage{team_info.stage}.html",
        team_info=team_info,
        stage=stage,
        stage_start_time=stage_start_time,
        standings=standings_view,
        hints=hints,
    )


@app.route("/end")
def end_page():
    if "team_id" not in session:
        return redirect(url_for("login_page"))

    team_id = session["team_id"]
    team_info = controller.get_team_info(team_id)

    if not team_info.finished:
        return redirect(url_for("quest_page"))

    with controller.lock:
        standings_data = controller.get_standings_data()

    standings_view = StandingsTableView.open_stages_from_request(
        standings_data=standings_data,
    )

    return render_template(
        "end.html",
        standings=standings_view,
        team_info=team_info,
    )


@app.route("/standings", methods=["GET", "POST"])
def standings_page():
    with controller.lock:
        standings_data = controller.get_standings_data()

    standings_view = StandingsTableView.open_stages_from_request(
        standings_data=standings_data,
    )

    return render_template("standings.html", standings=standings_view)


@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    if "admin_id" not in session:
        return redirect(url_for("login_page"))

    with controller.lock:
        standings_data = controller.get_standings_data()

    standings_view = StandingsTableView.open_stages_from_request(
        standings_data=standings_data,
    )

    admin_id = session["admin_id"]

    admin_info = controller.get_admin_info(admin_id)

    return render_template(
        "admin.html",
        standings=standings_view,
        admin_info=admin_info,
        standings_data=controller.get_standings_data(),
    )


@app.route("/logout", methods=["GET", "POST"])
def logout_page():
    if "admin_id" in session:
        del session["admin_id"]
    if "team_id" in session:
        del session["team_id"]

    return redirect(url_for("login_page"))


@click.option(
    "-c",
    "--config_path",
    required=True,
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
)
@click.option(
    "-e",
    "--event_log_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("events.yaml"),
)
@click.option(
    "-p",
    "--port",
    type=int,
    default=5000,
)
def run_server(config_path: Path, event_log_path: Path, port: int):
    with open(config_path) as f:
        config = yaml.full_load(f)
        schema = OmegaConf.create(QuestConfig())
        quest_config = OmegaConf.merge(schema, config["quest"])

    controller.load(config=quest_config, event_log_path=event_log_path)

    controller.admin_start()

    if not controller.is_game_started:
        controller.game_start()

    app.config["SECRET_KEY"] = config["flask_secret_key"]

    register_filters(app)

    app.run(host="0.0.0.0", port=port, debug=True, extra_files=[config_path])


if __name__ == "__main__":
    click.command(run_server)()
