from flask import Flask


def format_hhmmss(seconds: float):
    hours = int(seconds / 3600)
    minutes = int(seconds % 3600 / 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_mmss(seconds: float):
    minutes = int(seconds / 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"


def register_filters(app: Flask):
    app.add_template_filter(format_mmss)
    app.add_template_filter(format_hhmmss)
