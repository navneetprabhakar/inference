"""Distinguish unavailable response work from exhausted global allowances."""
# Creator: Navneet Prabhakar


class Unavailable(Exception):
    pass


def once(cache,key,length,producer):
    def request():
        try:return producer()
        except (ValueError,OSError,TimeoutError):
            raise Unavailable('Bounded range transfer/validation unavailable; no retry') from None
    # Reservation/cache errors occur outside request(), so budget/integrity
    # failures never become skippable transport errors.
    return cache.fetch(key,length,request)
