"""Carry several distinct sealed raw ledgers without double-counting their summaries."""
# Creator: Navneet Prabhakar
import sqlite3
from pathlib import Path
from slm.english_budget_v2 import Meter as CarriedMeter
from slm.english_learning import Meter as RawMeter
from slm.data.stream_hash import sha


class Meter(CarriedMeter):
    def __init__(self,path,contract_hash,maximum=100000000,phase_maximum=78000000,*,priors):
        self.priors=[dict(p) for p in priors]
        if not 1<=len(self.priors)<=8 or len({str(Path(p['path']).resolve()) for p in self.priors})!=len(self.priors):
            raise ValueError('Distinct sealed raw prior ledgers required')
        self._check_prior();self.prior_total=self.prior_preliminary=0
        for p in self.priors:
            c=sqlite3.connect('file:'+str(Path(p['path']).resolve())+'?mode=ro',uri=True)
            try:
                total=c.execute('SELECT coalesce(sum(positions),0) FROM charges').fetchone()[0]
                preliminary=c.execute("SELECT coalesce(sum(positions),0) FROM charges WHERE phase IN ('common','mlx','cuda')").fetchone()[0]
            finally:c.close()
            if (total,preliminary)!=(p['positions'],p['preliminary_positions']):
                raise ValueError('Raw prior charges differ; no discarded-work refund')
            self.prior_total+=total;self.prior_preliminary+=preliminary
        if self.prior_total>maximum or self.prior_preliminary>2000000:
            raise ValueError('Prior cumulative work already exceeds authorization')
        RawMeter.__init__(self,path,contract_hash,maximum,phase_maximum)

    def _check_prior(self):
        for p in self.priors:
            if sha(p['path'])!=p['sha256']:raise ValueError('Sealed raw prior ledger changed')
