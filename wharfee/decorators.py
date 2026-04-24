# -*- coding: utf-8
import functools


def if_exception_return(ex_type, then_result):
    def decorator(f):
        @functools.wraps(f)
        pass
    return decorator
