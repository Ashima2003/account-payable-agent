import logging

import uvicorn

from api.app import app

log = logging.getLogger("ap_agent.dashboard")

HOST = "0.0.0.0"
PORT = 8000


def run():
    log.info("starting dashboard on %s:%s", HOST, PORT)
    # log_config=None: don't let uvicorn install its own logging handlers
    # (colored console output, separate access-log formatting) -- its
    # loggers then just propagate to the root logger main.py already
    # configured, so dashboard requests get the same trace-tagged format
    # as everything else instead of a visually inconsistent second style.
    uvicorn.run(app, host=HOST, port=PORT, log_config=None)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    run()
