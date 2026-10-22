"""Pure fail-closed M1 stop rules; supervisor/worker integration is mandatory."""
from dataclasses import dataclass,field,asdict
from statistics import median
import math

class StopRun(RuntimeError):pass

def finite(*values):
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in values):
        raise StopRun('missing/nonfinite metric')

def cosine_rate(targets,cap,warmup=250000,peak=2e-4,minimum=2e-5):
    finite(targets,cap,warmup,peak,minimum)
    if targets<0 or cap<=warmup or not 0<minimum<=peak or warmup<=0 or targets>cap:raise ValueError('Invalid schedule')
    if targets<=warmup:return peak*targets/warmup
    return minimum+(peak-minimum)*.5*(1+math.cos(math.pi*(targets-warmup)/(cap-warmup)))

@dataclass
class Monitor:
    losses:list=field(default_factory=list)
    gradients:list=field(default_factory=list)
    dev:list=field(default_factory=list)
    diagnostics:list=field(default_factory=list)
    loss_streak:int=0
    gradient_streak:int=0
    update_streak:int=0
    dev_streak:int=0
    grammar_streak:int=0
    grounded_streak:int=0
    terminal:str|None=None

    def stop(self,reason):
        self.terminal=reason
        raise StopRun(reason)

    def alive(self):
        if self.terminal:raise StopRun(self.terminal)

    def update(self,*,loss,gradient_norm,update_ratio,targets,all_state_finite):
        self.alive()
        try:finite(loss,gradient_norm,update_ratio,targets)
        except StopRun:self.stop('missing/nonfinite update metric')
        if all_state_finite is not True:self.stop('nonfinite parameter/optimizer state')
        if min(loss,gradient_norm,update_ratio,targets)<0:self.stop('invalid negative update metric')
        self.loss_streak=self.loss_streak+1 if len(self.losses)>=100 and loss>2*median(self.losses[-100:]) else 0
        self.gradient_streak=self.gradient_streak+1 if targets>250000 and len(self.gradients)>=100 and gradient_norm>10*median(self.gradients[-100:]) else 0
        self.update_streak=self.update_streak+1 if update_ratio>.01 else 0
        if self.loss_streak>=5:self.stop('loss spike')
        if self.gradient_streak>=5:self.stop('gradient spike')
        if self.update_streak>=3:self.stop('parameter update spike')
        self.losses.append(loss);self.gradients.append(gradient_norm)

    def development(self,*,nll,after_pilot):
        self.alive()
        try:finite(nll)
        except StopRun:self.stop('missing/nonfinite development metric')
        if nll<=0:self.stop('invalid development NLL')
        self.dev_streak=self.dev_streak+1 if self.dev and nll>1.05*min(self.dev) else 0
        self.dev.append(nll)
        if after_pilot:
            if self.dev_streak>=2:self.stop('development regression')
            # Six new intervals after a reference checkpoint; 7 observations.
            if len(self.dev)>=7 and min(self.dev[-6:])>self.dev[-7]*.99:self.stop('development plateau')

    def diagnostic(self,*,train_nll,dev_nll,grammar,grounded,degenerate_outputs):
        self.alive()
        try:finite(train_nll,dev_nll,grammar,grounded,degenerate_outputs)
        except StopRun:self.stop('missing/nonfinite diagnostic')
        if min(train_nll,dev_nll)<=0 or not 0<=grammar<=1 or not 0<=grounded<=1 or type(degenerate_outputs) is not int or not 0<=degenerate_outputs<=20:self.stop('invalid diagnostic')
        if degenerate_outputs>=5:self.stop('generation collapse')
        if self.diagnostics:
            self.grammar_streak=self.grammar_streak+1 if grammar<=max(x[2] for x in self.diagnostics)-.1+1e-12 else 0
            self.grounded_streak=self.grounded_streak+1 if grounded<=max(x[3] for x in self.diagnostics)-.1+1e-12 else 0
        self.diagnostics.append((train_nll,dev_nll,grammar,grounded))
        if max(self.grammar_streak,self.grounded_streak)>=2:self.stop('behavioral regression')
        if len(self.diagnostics)>=3:
            old=self.diagnostics[-3]
            if train_nll<=old[0]*.95 and dev_nll>=old[1]*1.02:self.stop('overfitting')

    def copying(self,train_copies,heldout_copies):
        self.alive()
        if any(type(x) is not int or not 0<=x<=100 for x in (train_copies,heldout_copies)):self.stop('invalid copying count')
        if train_copies>5 and train_copies-heldout_copies>5:self.stop('copying concern')

    def state(self):return asdict(self)

@dataclass
class Resources:
    last_clock:float|None=None
    high_rss_since:float|None=None
    thermal_since:float|None=None
    terminal:str|None=None

    def observe(self,*,now,rss_gib,swap_growth_mib,free_disk_gib,heartbeat_at,thermal):
        if self.terminal:raise StopRun(self.terminal)
        reason=None
        try:finite(now,rss_gib,swap_growth_mib,free_disk_gib,heartbeat_at)
        except StopRun:reason='missing/nonfinite resource telemetry'
        if reason is None:
            if self.last_clock is not None and now<self.last_clock:reason='resource clock reversed'
            elif heartbeat_at>now or min(rss_gib,free_disk_gib)<0:reason='invalid resource telemetry'
            elif thermal not in ('nominal','fair','serious','critical'):reason='missing thermal telemetry'
            elif now-heartbeat_at>120:reason='heartbeat timeout'
            elif rss_gib>18:reason='instant RSS limit'
            elif swap_growth_mib>512:reason='swap limit'
            elif free_disk_gib<20:reason='disk limit'
            self.high_rss_since=(self.high_rss_since if self.high_rss_since is not None else now) if rss_gib>16 else None
            self.thermal_since=(self.thermal_since if self.thermal_since is not None else now) if thermal in ('serious','critical') else None
            if self.high_rss_since is not None and now-self.high_rss_since>=30:reason='sustained RSS limit'
            if self.thermal_since is not None and now-self.thermal_since>=60:reason='sustained thermal limit'
            self.last_clock=now
        if reason:self.terminal=reason;raise StopRun(reason)
