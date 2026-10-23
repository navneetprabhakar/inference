"""Discard module-held tracing arrays before direct inference outside mx.compile."""
def bind_compute_views(engine):
    from mlx.utils import tree_unflatten
    engine.model.update(tree_unflatten([(key,value.astype(engine.dtype)) for key,value in engine.params.items()]))
    return engine.model
