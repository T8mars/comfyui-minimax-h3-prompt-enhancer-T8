"""Minimal CPU adapter facade, without profiles, service control or inference."""
try:
    from ..strata_provider import StrataProviderError as StrataError, interrupted, strict_json as json_loads
except ImportError:
    from strata_provider import StrataProviderError as StrataError, interrupted, strict_json as json_loads


def text_unicode(value):
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise StrataError('Text must contain valid Unicode') from None
