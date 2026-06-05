def run(*args, **kwargs):
    from clearink.user.interface import run as _run

    return _run(*args, **kwargs)

__all__ = ["run"]
