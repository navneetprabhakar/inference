"""Original matched curriculum, gated by the independently passed duration test."""
import campaign as c
s=c.s
if __name__=='__main__':
    assert s.read(c.ROOT/'duration-result.json')['status']=='PASS'
    if not (c.ROOT/'fit-result.json').exists():s.save(c.ROOT/'fit-result.json',s.read(c.ROOT/'duration-result.json'))
    c.repair.run.main()
