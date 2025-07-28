import os

current_directory = os.path.dirname(os.path.abspath(__file__))
log_directory = os.path.join(current_directory, 'loggers')
os.makedirs(log_directory, exist_ok=True)
log_filename = os.path.join(log_directory, 'app.log')

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "timed_rotating_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": log_filename,
            "when": "midnight",  # Время ротации (каждую полночь)
            "interval": 1,  # Интервал в днях
            "backupCount": 7,  # Количество сохраняемых архивов (0 - не сохранять)
            "formatter": "default",
            "encoding": "utf-8",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "main": {
            "handlers": ["console", "timed_rotating_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "routes": {
            "handlers": ["console", "timed_rotating_file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
