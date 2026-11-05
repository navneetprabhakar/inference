from policy import final_stratum
from sample import sample
if __name__=='__main__':
    for k,rows in sorted(sample(12,'snli-final-safety-2',filter_pred=final_stratum).items()):
        print(k)
        for r in rows:print(r['pair_id'],r['premise'],'|',r['hypothesis'])
