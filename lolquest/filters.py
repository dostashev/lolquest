from uuid import uuid4

from flask import Flask
from jinja2.filters import do_mark_safe


def format_hhmmss(seconds: float):
    hours = int(seconds / 3600)
    minutes = int(seconds % 3600 / 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_mmss(seconds: float):
    minutes = int(seconds / 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"


def local_time(timestamp: float):
    uuid = uuid4().hex
    return do_mark_safe(
        f"""
        <text id="{uuid}"></text>
        <script>
            document.getElementById("{uuid}").innerText =
                new Date({timestamp} * 1000).toTimeString().slice(0, 8);
        </script>
        """
    )


def hidden_if(condition: bool):
    return do_mark_safe("class='hidden'" if condition else "")


def register_filters(app: Flask):
    app.add_template_filter(format_mmss)
    app.add_template_filter(format_hhmmss)
    app.add_template_filter(local_time)
    app.add_template_filter(hidden_if)
