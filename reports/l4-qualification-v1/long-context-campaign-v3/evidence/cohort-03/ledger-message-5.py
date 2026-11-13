from collections.abc import Mapping

def reconcile(current, updates):
    result = current.copy()
    seen = set()
    pairs = updates.items() if isinstance(updates, Mapping) else updates

    for item, qty in pairs:
        if item in seen:
            raise ValueError(f"Duplicate update for {item!r}")
        seen.add(item)

        if qty is None:
            result.pop(item, None)
        else:
            result[item] = qty

    return result
