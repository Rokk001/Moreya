"""Measure fresh asset preparation separately from unchanged validation work."""
from contextvars import ContextVar
from functools import wraps
import json
import time

_current = ContextVar('asset_check_timing', default=None)


# Attribute nested preparation to its outer call exactly once, without changing exceptions.
def preparation(function):
    # Preserve the function's return or exception while attributing only outer setup time.
    @wraps(function)
    def measured(*args, **kwargs):
        state = _current.get()
        if state is None or state['preparing']:
            return function(*args, **kwargs)
        state['preparing'] = True
        started = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            state['setup'] += time.perf_counter() - started
            state['preparing'] = False
    return measured


# Time a constructor or converter without altering its implementation or caching its result.
@preparation
def prepare(function, *args, **kwargs):
    return function(*args, **kwargs)


# Emit measured preparation and validation phases even when a real assertion fails.
def profile_check(function):
    # Restore the caller's measurement context on both success and failure.
    @wraps(function)
    def measured(*args, **kwargs):
        state = {'setup': 0.0, 'preparing': False}
        token = _current.set(state)
        started = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - started
            _current.reset(token)
            for name, seconds in (('setup', state['setup']), ('test', max(0.0, elapsed - state['setup']))):
                print('ODP_TEST_PHASE ' + json.dumps({'name': name, 'seconds': seconds}))
    return measured
