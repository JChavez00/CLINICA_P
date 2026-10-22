"""Contexto CLI sin importar app.py, chatbot ni crear tablas al entrenar."""
from pathlib import Path
from flask import Flask
from config import Config
from models import db


def contexto(database=None):
    app = Flask("ml_cli", instance_path=str(Path(__file__).resolve().parent.parent / "instance"))
    app.config.from_object(Config)
    if database:
        app.config["SQLALCHEMY_DATABASE_URI"] = database
    db.init_app(app)
    return app
