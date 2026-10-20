"""Carry sealed discarded work into a new finite English experiment ledger."""
# Creator: Navneet Prabhakar
import sqlite3
from pathlib import Path
from slm.english_learning import Meter as OriginalMeter
from slm.data.stream_hash import sha


class Meter(OriginalMeter):
    def __init__(self, path, contract_hash, maximum=100000000, phase_maximum=78000000, *, prior):
        self.prior = dict(prior)
        self._check_prior()
        db = sqlite3.connect('file:'+str(Path(prior['path']).resolve())+'?mode=ro', uri=True)
        try:
            self.prior_total = db.execute('SELECT coalesce(sum(positions),0) FROM charges').fetchone()[0]
            self.prior_preliminary = db.execute("SELECT coalesce(sum(positions),0) FROM charges WHERE phase IN ('common','mlx','cuda')").fetchone()[0]
        finally:
            db.close()
        if self.prior_total != prior['positions'] or self.prior_preliminary != prior['preliminary_positions']:
            raise ValueError('Sealed prior work totals differ; never refund discarded work')
        super().__init__(path, contract_hash, maximum, phase_maximum)

    def _check_prior(self):
        if sha(self.prior['path']) != self.prior['sha256']:
            raise ValueError('Sealed prior physical ledger changed')

    def reserve(self, phase, cursor, positions):
        if type(positions) is not int or positions < 1:
            raise ValueError('Positive complete work reservation required')
        self._check_prior()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            total = self.db.execute('SELECT coalesce(sum(positions),0) FROM charges').fetchone()[0]
            current = self.db.execute('SELECT coalesce(sum(positions),0) FROM charges WHERE phase=?', (phase,)).fetchone()[0]
            preliminary = self.db.execute("SELECT coalesce(sum(positions),0) FROM charges WHERE phase IN ('common','mlx','cuda')").fetchone()[0]
            if (self.prior_total + total + positions > self.maximum
                or current + positions > self.phase_maximum
                or (phase in ('common','mlx','cuda') and self.prior_preliminary + preliminary + positions > 2000000)):
                raise ValueError('Cumulative physical budget including discarded work exhausted')
            self.db.execute('INSERT INTO charges VALUES(?,?,?,?)', (phase, cursor, positions, 'reserved'))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def total(self):
        self._check_prior()
        return self.prior_total + super().total()
