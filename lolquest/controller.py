from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from threading import RLock
import time
from typing import Dict
from typing import List

from lolquest.configuration import QuestConfig
from lolquest.configuration import StageConfig
from lolquest.configuration import TaskConfig
import yaml


@dataclass
class TaskCompletionInfo:
    timestamp: float
    time_since_stage_entered: float
    points: int


@dataclass
class Message:
    timestamp: float
    text: str
    safe: bool = False


@dataclass
class TeamInfo:
    name: str
    stage: int
    stage_entered_timestamps: List[float]
    bonus_points: int = 0
    total_points: int = 0
    total_time: float = 0
    finished: bool = False
    completed_tasks: Dict[str, TaskCompletionInfo] = field(default_factory=dict)
    messages: List[Message] = field(default_factory=list)


@dataclass
class AdminInfo:
    name: str


@dataclass
class StandingsData:
    team_order: List[str]
    team_info: Dict[str, TeamInfo]
    stages: List[StageConfig]
    stage_points: Dict[str, List[int]]
    stage_max_points: Dict[str, List[int]]


class Controller:
    """Main class for controlling the flow of the quest"""

    def __init__(self):
        self.lock = RLock()
        self.team_info: Dict[str, TeamInfo] = {}
        self.admin_info: Dict[str, AdminInfo] = {}
        self.is_game_started = False

    def load(self, config: QuestConfig, event_log_path: Path):
        """Loads the config and event log"""
        self.config = config
        self.event_log_path = event_log_path
        self._load_event_log()
        self._replay_event_log()

    def get_standings_data(self):
        team_ids = [team.id for team in self.config.teams]

        team_order = sorted(
            team_ids,
            key=lambda team_id: (
                -self.team_info[team_id].total_points,
                self.team_info[team_id].total_time,
            ),
        )

        stage_points = {
            team_id: [
                sum(
                    completion.points
                    for task in stage.tasks
                    if (
                        completion := self.team_info[team_id].completed_tasks.get(
                            task.id, None
                        )
                    )
                    is not None
                )
                for stage in self.config.stages
            ]
            for team_id in team_ids
        }

        stage_max_points = {
            team_id: [
                sum(task.max_points for task in stage.tasks)
                for stage in self.config.stages
            ]
            for team_id in team_ids
        }

        return StandingsData(
            team_order=team_order,
            team_info=self.team_info,
            stages=self.config.stages,
            stage_points=stage_points,
            stage_max_points=stage_max_points,
        )

    def get_team_info(self, team_id: str):
        """Returns info for a given team"""
        return self.team_info[team_id]

    def get_admin_info(self, admin_id: str):
        """Returns info for a given admin"""
        return self.admin_info[admin_id]

    def team_login(self, team_id: str, password: str):
        for team in self.config.teams:
            if team_id == team.id and password == team.password:
                return True
        return False

    def admin_login(self, admin_id: str, password: str):
        for admin in self.config.admins:
            if admin_id == admin.id and password == admin.password:
                return True
        return False

    def up_stage_if_needed(self, team_id: str, timestamp: float):
        """
        Moves the team to next stage if required (i.e. timeout or all tasks completed)

        Returns:
            True if moved to next stage, else False
        """
        with self.lock:
            team_info = self.team_info[team_id]

            if team_info.finished:
                return

            stage = self.config.stages[team_info.stage]
            stage_entered_time = team_info.stage_entered_timestamps[-1]

            if timestamp >= stage_entered_time + stage.duration:
                # Time on stage ended
                self._up_stage(
                    team_info=team_info,
                    timestamp=stage_entered_time + stage.duration,
                    timeout=True,
                )
                return True

            elif all(task.id in team_info.completed_tasks for task in stage.tasks):
                # All tasks completed
                self._up_stage(
                    team_info=team_info,
                    timestamp=timestamp,
                    timeout=False,
                )
                return True

            return False

    def game_start(self):
        """
        Starts the game
        """

        with self.lock:
            timestamp = time.time()

            self._log_event(
                "game_start",
                timestamp=timestamp,
            )

            self._game_start(timestamp=timestamp)

    def team_enter_code(self, team_id: str, code: str):
        """
        Team enters code

        Return:
            True if moved to next stage, else False
        """

        with self.lock:
            timestamp = time.time()

            self._log_event(
                "team_enter_code",
                team_id=team_id,
                code=code,
                timestamp=timestamp,
            )

            return self._team_enter_code(
                team_id=team_id,
                code=code,
                timestamp=timestamp,
            )

    def add_bonus(self, admin_id: str, team_id: str, points: int):
        """
        Add bonus (maybe negative) to a team's points
        """

        with self.lock:
            timestamp = time.time()

            self._log_event(
                "add_bonus",
                admin_id=admin_id,
                team_id=team_id,
                points=points,
                timestamp=timestamp,
            )

            return self._add_bonus(
                admin_id=admin_id,
                team_id=team_id,
                points=points,
                timestamp=timestamp,
            )

    def _log_event(self, event_name: str, timestamp: float, **kwargs):
        """Logs event"""

        self.event_log.append(
            {
                "event": event_name,
                "timestamp": timestamp,
                "params": kwargs,
            }
        )

        self._dump_event_log()

    def _load_event_log(self):
        """Loads event log from json file"""

        if not self.event_log_path.exists():
            self.event_log = []
            self._dump_event_log()
        else:
            with open(self.event_log_path) as f:
                self.event_log = yaml.full_load(f)
                if self.event_log is None:
                    self.event_log = []

    def _dump_event_log(self):
        """Dumps event log to json file"""

        with open(self.event_log_path, "w") as f:
            yaml.dump(self.event_log, f)

    def _replay_event_log(self):
        """Replays all the events of the quest from log"""
        MAPPING = {
            "team_enter_code": self._team_enter_code,
            "game_start": self._game_start,
            "add_bonus": self._add_bonus,
        }
        for event in self.event_log:
            MAPPING[event["event"]](timestamp=event["timestamp"], **event["params"])

    def _game_start(self, timestamp: float):
        self.team_info = {
            team.id: TeamInfo(
                name=team.name, stage=0, stage_entered_timestamps=[timestamp]
            )
            for team in self.config.teams
        }
        self.admin_info = {
            admin.id: AdminInfo(name=admin.name) for admin in self.config.admins
        }
        self.is_game_started = True

    def _team_enter_code(self, team_id: str, code: str, timestamp: float):
        """Enter code logic"""

        team_info = self.team_info[team_id]

        if team_info.finished:
            return False

        self.up_stage_if_needed(team_id=team_id, timestamp=timestamp)

        stage = self.config.stages[team_info.stage]
        time_since_stage_entered = timestamp - team_info.stage_entered_timestamps[-1]

        code_accepted = False

        for task in stage.tasks:
            if self.config.case_sensitive_codes:
                code_matched = task.code == code
            else:
                code_matched = task.code.lower() == code.lower()

            if code_matched and task.id not in team_info.completed_tasks:
                points = self._get_points_for_completed_task(
                    task_config=task,
                    time_since_stage_entered=time_since_stage_entered,
                )

                team_info.total_points += points
                if task.counts_towards_total_time:
                    team_info.total_time += time_since_stage_entered

                team_info.completed_tasks[task.id] = TaskCompletionInfo(
                    timestamp=timestamp,
                    time_since_stage_entered=time_since_stage_entered,
                    points=points,
                )

                code_accepted = True

        message_text = f"Введено код: {code}. "
        if code_accepted:
            message_text += "Код зараховано!"
        else:
            message_text += "Неправильний код!"

        team_info.messages.append(
            Message(
                timestamp=timestamp,
                text=message_text,
            )
        )

        stage_upped = self.up_stage_if_needed(team_id=team_id, timestamp=timestamp)

        return stage_upped

    def _add_bonus(self, admin_id: str, team_id: str, points: int, timestamp: float):
        team_info = self.team_info[team_id]
        team_info.bonus_points += points
        team_info.total_points += points

        if points >= 0:
            message_text = f"<b>Вам нараховано бонус {points} балів</b>"
        else:
            message_text = f"<b>Вам нараховано штраф {points} балів</b>"

        team_info.messages.append(
            Message(
                timestamp=timestamp,
                text=message_text,
                safe=True,
            )
        )

    @staticmethod
    def _get_points_for_completed_task(
        task_config: TaskConfig, time_since_stage_entered: float
    ):
        return int(
            task_config.max_points
            * sum(
                p.percent / 100
                for p in task_config.scoring
                if p.completed_before >= time_since_stage_entered
            )
        )

    def _up_stage(self, team_info: TeamInfo, timestamp: float, timeout: bool):
        team_info.stage += 1
        team_info.stage_entered_timestamps.append(timestamp)
        if team_info.stage == len(self.config.stages):
            team_info.finished = True
            team_info.messages.append(
                Message(
                    timestamp=timestamp,
                    text="Ви прийшли на фініш!",
                )
            )
        else:
            if timeout:
                team_info.messages.append(
                    Message(
                        timestamp=timestamp,
                        text=f"Час на етапі вийшов. Ви перейшли на етап {team_info.stage}.",
                    )
                )
            else:
                team_info.messages.append(
                    Message(
                        timestamp=timestamp,
                        text=f"Всі завдання виконано. Ви перейшли на етап {team_info.stage}.",
                    )
                )

            message = self.config.stages[team_info.stage].message

            if message is not None:
                team_info.messages.append(
                    Message(
                        timestamp=timestamp,
                        text=message,
                        safe=True,
                    )
                )
