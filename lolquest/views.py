import time
from typing import List
from uuid import uuid4

from flask import render_template
from lolquest.configuration import HintConfig
from lolquest.controller import StandingsData


class HintView:
    def __init__(self, hint: HintConfig, stage_start_time: float):
        self.hint = hint
        self.stage_start_time = stage_start_time

    def __html__(self):
        hint_time = self.stage_start_time + self.hint.timing
        if time.time() >= hint_time:
            html = self.hint.text
        else:
            html = render_template("hint.html", uuid=uuid4().hex, hint_time=hint_time)
        return html


class StandingsTableView:
    def __init__(self, standings_data: StandingsData, open_stages: List[int]):
        self.standings_data = standings_data
        self.open_stages = open_stages

    def __html__(self):
        return render_template(
            "standings_table.html",
            standings_data=self.standings_data,
            open_stages=self.open_stages,
        )
