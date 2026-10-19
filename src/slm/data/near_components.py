"""Propagate full near-facet links over checked exact-plus-containment roots."""
# Creator: Navneet Prabhakar
from collections import Counter
from slm.data.schema import digest


class Components:
    def __init__(self,records,roots):
        self.records=records;self.parent=list(roots);self.facet_source={};self.links=0
        if len(records)!=len(roots):raise ValueError('Complete inherited root coverage required')
        for sid,r in enumerate(records):
            if r['sid']!=sid or type(roots[sid]) is not int or not 0<=roots[sid]<len(roots):raise ValueError('Canonical source IDs and inherited roots required')
            if self.parent[self.parent[sid]]!=self.parent[sid]:raise ValueError('Inherited roots must be final direct roots')
            if r['fixed'] not in (0,1,2) or r['blocked'] not in (0,1) or r['candidate'] not in (0,1):raise ValueError('Explicit immutable witness flags required')

    def find(self,sid):
        while self.parent[sid]!=sid:self.parent[sid]=self.parent[self.parent[sid]];sid=self.parent[sid]
        return sid

    def register(self,facet_sid,source_sid):
        if not 0<=source_sid<len(self.records):raise ValueError('Facet source outside inherited records')
        if facet_sid in self.facet_source:
            if self.find(source_sid)!=self.find(self.facet_source[facet_sid]):raise ValueError('Raw-identical facet mappings must already share inherited exact root')
        else:self.facet_source[facet_sid]=source_sid

    def link(self,a,b):
        if a not in self.facet_source or b not in self.facet_source:raise ValueError('Near facet endpoint lacks source mapping')
        x,y=self.find(self.facet_source[a]),self.find(self.facet_source[b]);self.parent[max(x,y)]=min(x,y);self.links+=1

    def result(self):
        groups={};roots=[];withheld=Counter()
        for sid,r in enumerate(self.records):
            root=self.find(sid);roots.append(root)
            g=groups.setdefault(root,dict(root=root,members=[],heldout_priority=0,blocked=0))
            g['members'].append(r['eid']);g['heldout_priority']=max(g['heldout_priority'],r['fixed']);g['blocked']=max(g['blocked'],r['blocked'])
        for sid,r in enumerate(self.records):
            if r['candidate']:
                g=groups[roots[sid]]
                if g['heldout_priority']:withheld['heldout_family']+=1
                if g['blocked']:withheld['blocked_family']+=1
        components=[dict(root=root,group_id=digest(sorted(g['members'])),members=len(g['members']),heldout_priority=g['heldout_priority'],blocked=g['blocked']) for root,g in sorted(groups.items())]
        return dict(roots=roots,components=components,near_facet_links_consumed=self.links,candidate_withheld=dict(withheld))
