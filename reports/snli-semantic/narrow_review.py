from sample import sample
from strict import narrow
if __name__=='__main__':
    for k,rows in sorted(sample(12,'snli-narrow-a',filter_pred=narrow).items()):
        print(k)
        for r in rows:print(r['pair_id'],r['premise'],'|',r['hypothesis'])
