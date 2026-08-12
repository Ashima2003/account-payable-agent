import contextvars
import logging
import sys

# Set once per unit of work (a helpdesk/invoice work_id, an ingestion scan,
# an outbox relay batch) via `trace(...)`, then read back automatically by
# _TraceIdFilter on every log record emitted anywhere during that block --
# including inside db/repository.py's query logging, clients/mcp_db_client.py's
# tool-call logging, and the LLM call sites -- without having to thread an
# id through every function's parameters. journalctl -u ap-agent | grep
# '\[<id>\]' then shows one cycle's DB/LLM/MCP operations in order.
_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


class _TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id_var.get()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(trace_id)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    handler.addFilter(_TraceIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


class trace:
    """Context manager -- tags every log record emitted inside the block
    with `trace_id`. Nests correctly (restores the previous value on
    exit), though in practice each worker only opens one per item."""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self._token = None

    def __enter__(self) -> "trace":
        self._token = _trace_id_var.set(self.trace_id)
        return self

    def __exit__(self, *exc_info) -> None:
        _trace_id_var.reset(self._token)


def current_trace_id() -> str:
    return _trace_id_var.get()
