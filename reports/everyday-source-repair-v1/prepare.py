"""Metadata-only prospective extraction policy. Root reviews before execution."""
import hashlib,json,pathlib
R=pathlib.Path(__file__).resolve().parents[2];H=pathlib.Path(__file__).parent
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 prior=json.loads((R/'data/sft-readiness-v3/policy.json').read_text());files=prior['source_files'];assert len(files)==2
 names=['data/sft-readiness-v3/'+n for n in ('policy.json','candidates.sqlite','partial-candidate-manifest.json','candidate-verification.json','source-integrity.json','custody.json','quality-review.json')]
 for v in (4,5):names += [f'data/sft-readiness-v{v}/'+n for n in ('excluded.json','review.json','receipt.json')]
 names += ['data/sft-readiness-v6/excluded.json','data/sft-readiness-v6/receipt.json']
 names += ['reports/everyday-source-repair-v1/'+n for n in ('prepare.py','extract.py','grouping_draft.py','group_reviewed.py','check_grouping.py','REPAIR-PROTOCOL.md')]
 p=dict(state='prospective_full_history_review_intake_not_admitted',files=files,pins={n:sha(R/n) for n in names},source='everyday-conversations',expected=dict(raw=1130,old_train=811,known_excluded=41,cohort_only_train_reconsideration=770,unresolved=319),output='data/everyday-source-review-v1',limits=dict(seconds=600,rss_bytes=512*1024**2,output_bytes=50*1024**2,free_disk_bytes=20*1024**3),scope='Full raw histories retained; no old train reassignment, no unknown-to-untouched inference, no admission or fit truncation.')
 with (H/'intake-policy.json').open('x') as f:json.dump(p,f,indent=2);f.write('\n')
 print(sha(H/'intake-policy.json'))
if __name__=='__main__':main()
