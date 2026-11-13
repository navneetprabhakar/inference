def reconcile(current, updates):
    result = current.copy()
    for item, qty in updates.items():
        if qty is None:
            result.pop(item, None)
        else:
            result[item] = qty
    return result
