"""
NutriTrack Pro — Logging centralisé
Écrit dans nutritrack.log (rotation à 1 Mo, 3 fichiers conservés).
"""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nutritrack.log")

_handler = RotatingFileHandler(
    _LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
)
_handler.setFormatter(logging.Formatter(
    "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"nutritrack.{name}")
    if not logger.handlers:
        logger.addHandler(_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
