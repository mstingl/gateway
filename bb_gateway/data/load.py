import logging
import asyncio
from typing import Any, Optional, Tuple
from aiohttp.client import ClientResponse
from sentry_sdk.tracing import Span
from .utils import resolve_placeholder, get_cache_key


_logger = logging.getLogger(__name__)


async def load_data(value, values: dict, headers, _cache: dict, _cleanup_callbacks: list, _parent_span: Span):
    rel_path = [resolve_placeholder(part, curr_obj=values) for part in value.split('/')]
    cache_key = get_cache_key(rel_path, curr_obj=values, **values)
    values['$rel'] = '/'.join(rel_path)

    with _parent_span.start_child(op='load_data', description=value) as _span:
        data = {}
        try:
            with _span.start_child(op='load_data.fetch') as __span:
                _logger.debug("LOAD START %s", cache_key)
                try:
                    _response, related = await _load_related_data(rel_path, cache_key=cache_key, curr_obj=values, headers=headers, **values, _cache=_cache, _cleanup_callbacks=_cleanup_callbacks, _parent_span=__span)

                except asyncio.TimeoutError as error:
                    _logger.warning("Timeout loading related data on %s", value)
                    raise ValueError({
                        'status': 504,
                    })

                else:
                    _logger.debug("LOAD DONE %s", cache_key)

                _span.set_tag('data.source', 'upstream')
                _span.set_http_status(_response.status)

            if not _response.ok:
                raise ValueError({
                    'status': _response.status,
                    'data': await (_response.json() if 'application/json' in _response.content_type else _response.text()),
                })

        except Exception as error:
            _logger.warning("Cannot load data from %s", value)
            data['$error'] = error.args[0]

        else:
            data.update(related)

            _span.set_tag('cache_control', _response.headers.get('cache-control'))

        values.update(data)

        return values


def _load_related_data(
    relation: list[str],
    cache_key: str,
    curr_obj: dict,
    headers: dict = {},
    id: Optional[str] = None,
    *,
    _cache: dict,
    _cleanup_callbacks: list,
    _parent_span: Span,
    **lookup,
) -> asyncio.Task[Tuple[ClientResponse, Any]]:
    from ..resolver_proxy import proxy

    try:
        del headers['content-length']

    except KeyError:
        pass

    if id:
        return proxy(
            method='GET',
            service=relation[1],
            path='/'.join([*relation[2:], id]),
            params='',
            headers=headers,
            timeout=3.0,
            _cache=_cache,
            _cleanup_callbacks=_cleanup_callbacks,
            _parent_span=_parent_span,
        )

    elif '$rel_params' in curr_obj:
        raise NotImplementedError

    else:
        raise NotImplementedError
