"""Explicit continuation of a recovered, committed full-feature index."""
# Creator: Navneet Prabhakar
import sqlite3
from slm.data.facet_near import FacetStore


def resume(path,*,max_bytes,max_facets,max_features,max_shingles):
    store=FacetStore.__new__(FacetStore);store.db=sqlite3.connect(path)
    if store.db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise ValueError('Committed feature index is corrupt')
    if store.db.execute("SELECT name FROM sqlite_master WHERE name='prefixes'").fetchone():raise ValueError('Only unfinished feature-index continuation supported')
    if store.db.execute('SELECT complete FROM status').fetchall()!=[(0,)]:raise ValueError('Incomplete index required')
    store.db.executescript('PRAGMA synchronous=FULL; PRAGMA journal_mode=DELETE; PRAGMA cache_size=-8192; PRAGMA temp_store=FILE; CREATE TEMP TABLE incoming_features(feat BLOB PRIMARY KEY) WITHOUT ROWID; PRAGMA temp.cache_size=-2048;')
    store.db.execute('PRAGMA max_page_count='+str(max_bytes//4096))
    store.max_facets=max_facets;store.max_features=max_features;store.max_shingles=max_shingles
    store.facets=store.db.execute('SELECT count(*) FROM records').fetchone()[0]
    store.features=store.db.execute('SELECT coalesce(sum(n),0) FROM counts').fetchone()[0]
    if store.facets>max_facets or store.features>max_features:raise ValueError('Recovered index exceeds original cap')
    store.peak=store.db.execute('PRAGMA page_count').fetchone()[0]*4096;store.scratch_peak=0;store.pairs=0
    return store
