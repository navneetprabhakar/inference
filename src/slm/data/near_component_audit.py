"""Independent source-graph traversal for final near-component verification."""
# Creator: Navneet Prabhakar
from collections import Counter,deque
from slm.data.schema import digest


def reconstruct(records,roots,facet_sources,near_pairs,*,max_edges=2000000):
    n=len(records)
    if len(roots)!=n or any(r['sid']!=i for i,r in enumerate(records)):raise ValueError('Complete canonical source coverage required')
    edges=set();representatives={};pairs=0
    def edge(a,b):
        if not 0<=a<n or not 0<=b<n:raise ValueError('Graph endpoint outside source records')
        if a!=b:
            edges.add((min(a,b),max(a,b)))
            if len(edges)>max_edges:raise ValueError('Independent source-graph budget reached; no partial acceptance')
    for sid,root in enumerate(roots):
        if not isinstance(root,int) or not 0<=root<n or roots[root]!=root:raise ValueError('Final inherited roots required')
        edge(sid,root)
    for facet,sid in facet_sources:
        if not 0<=sid<n:raise ValueError('Facet source outside source records')
        if facet in representatives:
            if roots[sid]!=roots[representatives[facet]]:raise ValueError('Raw-identical mappings must share inherited exact root')
        else:representatives[facet]=sid
    for a,b in near_pairs:
        if a>=b or a not in representatives or b not in representatives:raise ValueError('Canonical mapped near endpoints required')
        edge(representatives[a],representatives[b]);pairs+=1
    graph=[[] for _ in range(n)]
    for a,b in edges:graph[a].append(b);graph[b].append(a)
    visited=bytearray(n);final=[None]*n;components={}
    for start in range(n):
        if visited[start]:continue
        queue=deque([start]);visited[start]=1;members=[]
        while queue:
            sid=queue.popleft();members.append(sid)
            for other in graph[sid]:
                if not visited[other]:visited[other]=1;queue.append(other)
        root=min(roots[sid] for sid in members)
        fixed=max(records[sid]['fixed'] for sid in members);blocked=max(records[sid]['blocked'] for sid in members)
        components[root]=dict(root=root,group_id=digest(sorted(records[sid]['eid'] for sid in members)),members=len(members),heldout_priority=fixed,blocked=blocked)
        for sid in members:final[sid]=root
    withheld=Counter()
    for sid,r in enumerate(records):
        if r['candidate']:
            c=components[final[sid]]
            if c['heldout_priority']:withheld['heldout_family']+=1
            if c['blocked']:withheld['blocked_family']+=1
    return dict(roots=final,components=components,candidate_withheld=dict(withheld),near_facet_links_consumed=pairs,unique_source_graph_edges=len(edges))


def verify(reconstruction,root_rows,component_rows,receipt):
    count=0
    for sid,row in enumerate(root_rows):
        if sid>=len(reconstruction['roots']) or row!=dict(sid=sid,root=reconstruction['roots'][sid]):raise ValueError('Final component root differs from independent graph')
        count+=1
    if count!=len(reconstruction['roots']):raise ValueError('Final component root coverage incomplete')
    seen=set()
    for row in component_rows:
        root=row['root']
        if root in seen or reconstruction['components'].get(root)!=row:raise ValueError('Final component identity or witness flags differ')
        seen.add(root)
    if seen!=set(reconstruction['components']):raise ValueError('Final component coverage incomplete')
    for key,expected in [('records',count),('components',len(seen)),('candidate_withheld',reconstruction['candidate_withheld']),('near_facet_links_consumed',reconstruction['near_facet_links_consumed'])]:
        if receipt.get(key)!=expected:raise ValueError('Component receipt accounting differs')
    return dict(records_checked=count,components_checked=len(seen),near_facet_pairs_consumed=reconstruction['near_facet_links_consumed'],unique_source_graph_edges=reconstruction['unique_source_graph_edges'])
