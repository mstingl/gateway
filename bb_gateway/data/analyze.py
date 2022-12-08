import asyncio
import logging
from typing import Coroutine, Iterable, Optional
from sentry_sdk import start_span
from sentry_sdk.tracing import Span
from .load import load_data


_logger = logging.getLogger(__name__)


async def analyze_data(values: dict, headers: dict = {}, parent: Optional[dict] = None, max_level: Optional[int] = None, _cache: Optional[dict] = None, _parent_span: Optional[Span] = None):
    """
    Load referenced data into `values`, performing an in-place update.
    """

    if _cache is None:
        _cache = {}

    cleanup_callbacks = []

    def enrich_data(values, key: Optional[str] = None, parent: Optional[dict] = None, *, level: int = 0, _parent_span: Span) -> Iterable[Coroutine]:
        with _parent_span.start_child(op='enrich_data', description=key) as _span:
            if isinstance(values, list):
                for i, item in enumerate(values):
                    yield from enrich_data(item, key=f'{key}[{i}]', parent=parent, level=level + 1, _parent_span=_span)

            if not isinstance(values, dict):
                return

            if '$rel_at' in values:
                return

            if max_level and level > max_level:
                _logger.debug("MAXIMUM RECURSION DEPTH REACHED %s", values)
                return

            keys = list(values.keys())
            if parent:
                values['_parent'] = parent
                cleanup_callbacks.append(lambda: values.pop('_parent', None))

            def process_value(key, value):
                if key == '$rel':
                    yield load_data(value, values, headers, _cache, _parent_span=_span)

                else:
                    yield from enrich_data(value, key=key, parent=values, level=level + 1, _parent_span=_span)

            for key in keys:
                yield from process_value(key, values[key])

    with (_parent_span.start_child if _parent_span else start_span)(op='load_referenced_data') as _span:
        _tasks = list(enrich_data(values, parent=parent, _parent_span=_span))
        await asyncio.gather(*_tasks, return_exceptions=True)

    with (_parent_span.start_child if _parent_span else start_span)(op='load_referenced_data.cleanup'):
        for callback in cleanup_callbacks:
            callback()
