"""Selection caps and excluded prior groups survive input reordering."""
# Creator: Navneet Prabhakar
from slm.data.parquet_selection import select


def test_distinct_balanced_bounded_and_order_independent():
    c={f'file{i}':[dict(index=j,rows=1000) for j in range(12)] for i in range(4)}
    a=select(c,'seed',10,3,set());b=select(dict(reversed(list(c.items()))),'seed',10,3,set())
    assert a==b and len(a)==10 and len({(r['file'],r['group']['index']) for r in a})==10
    assert all(sum(r['file']==f for r in a)<=3 for f in c)


def test_prior_acquired_group_and_empty_file_cannot_enter_selection():
    c={'first':[dict(index=0,rows=1000),dict(index=1,rows=1000)],'empty':[]}
    out=select(c,'seed',49,4,{('first',0)})
    assert out==[dict(file='first',group=dict(index=1,rows=1000))]
