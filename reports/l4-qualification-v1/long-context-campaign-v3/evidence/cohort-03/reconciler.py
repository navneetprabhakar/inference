from collections.abc import Mapping

def reconcile(current, updates):
    def validate(item, qty, *, allow_none):
        if not isinstance(item, str) or not item:
            raise ValueError(f"Invalid key: {item!r}")
        if qty is None and allow_none:
            return
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
            raise ValueError(f"Invalid quantity for {item!r}: {qty!r}")

    for item, qty in current.items():
        validate(item, qty, allow_none=False)

    result = current.copy()
    seen = set()
    pairs = updates.items() if isinstance(updates, Mapping) else updates

    for item, qty in pairs:
        validate(item, qty, allow_none=True)
        if item in seen:
            raise ValueError(f"Duplicate update for {item!r}")
        seen.add(item)

        if qty is None:
            result.pop(item, None)
        else:
            result[item] = qty

    return result
