#!/usr/bin/env python3
"""Point-in-time goal audit. Reads local evidence; never trains, approves or spends."""
# Creator: Navneet Prabhakar
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from slm.common.config import Config
from slm.data.build import verify
from slm.data.review import training_examples
from slm.data.schema import digest


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_text())


def audit(output):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    config=Config(**read('configs/target-81m.json'));assert config.parameter_count==80765440
    packet_path=Path('data/official-split-audit-v1/pending-review.json');packet_before=sha(packet_path);packet=read(packet_path)
    sample=Path('data/official-split-audit-v1/curated');manifest=verify(sample);sample_report=read(sample/'report.json')
    assert sha(sample/'manifest.json')==packet['dataset_manifest_sha256']
    source_ids=set(read(sample/'sources.json'))
    reader_refusal=None
    try:list(training_examples(sample))
    except ValueError as exc:reader_refusal=str(exc)
    assert reader_refusal is not None
    source_approvals=sum(v['approved'] is True for v in packet['source_reviews'].values())
    row_approvals=sum(v['decision']['approved'] is True for v in packet['examples'].values())
    # Never silently retain pending-input classifications after the audited baseline changes.
    if source_approvals or row_approvals or packet['human_attestation']:
        raise ValueError('Review input changed; update requirement classifications before publishing this audit')
    real_releases=[];manifest_count=0
    for path in sorted(Path('data').rglob('manifest.json')):
        manifest_count+=1
        if not (path.parent/'sources.json').is_file():continue
        m=read(path)
        if m.get('release')!='training':continue
        sources=set(read(path.parent/'sources.json'))
        if sources&source_ids:
            real_releases.append({'path':str(path.parent),'source_ids':sorted(sources),'checked_train_records':sum(1 for _ in training_examples(path.parent))})
    if real_releases:raise ValueError('A public training release now exists; re-audit tokenizer/pilot readiness rather than preserving old blockers')
    suite=read('data/evaluation-candidates-v1/suite-review.json');output_review=read('data/evaluation-candidates-v1/output-review.json')
    approved_cases=sum(v['approved'] is True for v in suite['cases'].values())
    if suite['human_attestation'] or approved_cases:raise ValueError('Evaluation review changed; update classifications')
    stage_policy=read('configs/stage-screen-proposal-v1.json');assert stage_policy['status']=='proposed'
    numeric=read('reports/milestone-twenty-two-summary.json');assert numeric['strict_state_trajectory_gate_passed'] is False
    proposal=Path('docs/portability-acceptance-proposal.md').read_text();assert 'Status: proposed; no existing gate changed or waived.' in proposal
    tokenizer=read('reports/milestone-eight-tokenizer-mechanics.json');assert not tokenizer['production_frozen'] and tokenizer['selected_vocab_size'] is None
    scale=read('reports/milestone-eleven-reader-scale.json');assert scale['neural_updates']==0 and scale['public_training_examples_used']==0
    teacher=read('reports/milestone-twenty-eight-summary.json');assert teacher['actual_training_approvals']==0
    journals=[]
    for name in ('cli-pilot-v1','cli-pilot-v2'):
        path=Path('data/teacher')/name/'journal.sqlite'
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
            halted,limit=db.execute('SELECT halted,max_requests FROM budget').fetchone()
            states=dict(db.execute('SELECT status,COUNT(*) FROM requests GROUP BY status').fetchall())
        journals.append({'name':name,'halted':bool(halted),'limit':limit,'states':states,'reserved_slots':sum(states.values()),'sha256':sha(path)})
    assert sum(j['reserved_slots'] for j in journals)==17 and journals[1]['states']['complete']==14
    paths=sorted([*Path('src/slm').rglob('*.py'),*Path('scripts').glob('*.py')])
    mains=[]
    for path in paths:
        tree=ast.parse(path.read_text())
        if any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='main' for n in tree.body):mains.append(str(path))
    pilot_main_found=Path('src/slm/train.py').is_file() and 'src/slm/train.py' in mains
    assert not any('def main(' in Path(p).read_text() for p in ('src/slm/common/training.py','src/slm/common/curriculum.py'))
    test_path=Path('reports/milestone-thirty-three-tests.xml')
    if not test_path.exists():test_path=Path('reports/milestone-thirty-two-tests.xml')
    if not test_path.exists():test_path=Path('reports/milestone-thirty-one-tests.xml')
    if not test_path.exists():test_path=Path('reports/milestone-twenty-nine-tests.xml')
    t=ET.parse(test_path).getroot().find('testsuite')
    tests={k:int(t.attrib[k]) for k in ('tests','failures','errors','skipped')};tests['passed']=tests['tests']-tests['skipped']-tests['failures']-tests['errors']
    refs={}
    items=[]
    def item(id,section,requirement,status,evidence,limit):
        for path in evidence:
            if not Path(path).is_file():raise ValueError('Missing audit evidence: '+path)
            refs[path]=sha(path)
        items.append({'id':id,'goal_section':section,'requirement':requirement,'status':status,'evidence':evidence,'scope_or_missing_proof':limit})
    # Implementation and its delivered behavior are deliberately classified separately.
    for id,text,paths_,limit in [
      ('C01','Canonical random initialization and tied architecture',['src/slm/common/config.py','configs/target-81m.json'],'Fresh config count is 80,765,440; this is not a language-trained checkpoint.'),
      ('C02','Canonical unquantized model checkpoint and conventions',['src/slm/common/checkpoint.py','tests/test_portability.py'],'FP32 reference format; compressed exports remain separate.'),
      ('C03','FP32 optimizer moments, recipe, step and cursor state',['src/slm/common/training.py','tests/test_resume.py'],'Reference training state v1/v2 plus curriculum v3; not a main-run artifact.'),
      ('C04','Atomic update-boundary save, corruption and interrupted-save checks',['src/slm/common/training.py','tests/test_resume.py'],'The checked API exists; see P02 for current pilot orchestration status.'),
      ('C05','Accumulation weighting, clip/decay/bias correction and tails',['src/slm/common/training.py','tests/test_accumulation.py'],'Reference optimizer behavior is tested; no new numerical acceptance is inferred.'),
      ('C06','Mixture order, family exposure and stage-local schedule resume',['src/slm/data/mixture.py','src/slm/data/curriculum.py','src/slm/common/curriculum.py'],'Finite reference manifests and receipts, not a sustained language curriculum.'),
    ]:item(id,'1',text,'implemented_reference',paths_,limit)
    item('N01','2','Tiny MLX/CPU forward/gradient/100-update controls','implemented_reference',['docs/milestone-one.md','docs/milestone-three.md','tests/test_portability.py'],'Tiny tolerances do not establish full-depth training trajectories.')
    item('N02','2','Actual NVIDIA checkpoint/continuation validation','retained_hardware_evidence',['reports/milestone-twenty-one-summary.json','reports/milestone-twenty-one-cleanup.json'],'Retained T4 validation, not a fresh hardware or cloud-resource query.')
    item('N03','2','Full exact MLX/CUDA/MLX state transfer and context inference','retained_hardware_evidence',['reports/milestone-twenty-one-summary.json','reports/milestone-seven-cuda-context.json'],'242,296,320 weight/moment values checked; finite synthetic continuation is not learned quality.')
    item('N04','2','Accepted full-size multi-update training portability','failed_gate',['reports/milestone-twenty-two-summary.json','docs/portability-acceptance-proposal.md'],'Trajectory failure remains recorded; state/inference/quality versus strict-trajectory policy needs user input.')
    item('N05','2','Reduced-precision and optimized numerical validation','missing',['src/slm/eval/precision.py','src/slm/backends/mlx_backend.py','src/slm/backends/torch_backend.py'],'FP64 diagnostic is not BF16/FP16 production support. Reference acceptance precedes optimization.')
    item('D01','3','Pinned source provenance/card/license sample acquisition','implemented_reference',['src/slm/data/acquire.py','src/slm/data/schema.py'],'Four sources, first-N schema/yield samples; no representative clearance or bulk download.')
    item('D02','3','Prose/messages/Dolly/OASST adapters and complete tree reconstruction','implemented_reference',['src/slm/data/adapters.py','configs/source-audit-v1.json'],'Initial inspected source formats; the wider source shortlist is not fully audited.')
    item('D03','3','English/quality/privacy filtering suitable for real training','partial',['src/slm/data/curation.py','src/slm/data/review.py'],'Pattern redaction and declared language are incomplete; 901 current rows remain content-unreviewed.')
    item('D04','3','Exact/near deduplication, grouped splits and official holdouts','partial',['src/slm/data/curation.py','src/slm/data/partitions.py','src/slm/data/holdout.py'],'Bounded grouping and exact evaluation isolation; not scalable global semantic contamination proof or full OASST Parquet text verification.')
    item('D05','3','Approved public source and example release','pending_input',['data/official-split-audit-v1/pending-review.json','src/slm/data/review.py'],'Zero source/example approvals; sample-only reader refuses training.')
    item('D06','3','Production bulk intake, global grouping and quality reporting','partial',['src/slm/data/staging.py','tests/test_staging.py','docs/disk-backed-corpus-staging.md'],'Disk-backed sample-only JSONL staging preserves exact syntactic grouping with explicit limits; no representative corpus throughput, source admission, semantic decontamination, resumable intake or direct Parquet stream. Legacy builder/packets remain bounded; v2 explicit-row verification and downstream approved-row/text intake are disk-backed. Other mixture/lineage/BPE state is not globally bounded.')
    item('D07','3','Scalable admission backed by representative human audit','missing',['src/slm/data/review_stream.py','docs/corpus-admission-proposal.md'],'Disk-backed v2 still admits explicit rows only. The corpus-admission contract is proposed with no accepted sampling/error thresholds or actual judgments. Forty decisions cannot approve the other 861 or a corpus.')
    item('D08','3','Verified token shards, source counts and repeat exposure','implemented_reference',['src/slm/data/tokenized.py','src/slm/data/mixture.py'],'Processed, supervised and unique prepared positions differ; prior 2.6M reader probe has zero neural updates.')
    item('T01','4','Train-only 16K/24K BPE comparison tooling and slice measurements','implemented_reference',['src/slm/common/tokenizer.py','src/slm/eval/tokenizer.py'],'Candidate builder uses a checked text spool/generator and streaming record digest; BPE internal vocabulary state still grows. Retained synthetic comparison yielded 432 tokens for both requested sizes; no production selection.')
    item('T02','4','Frozen production vocabulary selected from representative eligible data','missing',['reports/milestone-eight-tokenizer-mechanics.json','reports/milestone-eight-data-gates.json'],'No production candidate, selection or freeze. Vocabulary choice and target count must follow actual yield/efficiency.')
    item('T03','4','Disjoint structural IDs, raw-content isolation and serialization','implemented_reference',['src/slm/common/tokenizer.py','src/slm/common/tool_serialization.py','tests/test_tokenizer.py'],'No raw content special-token interpretation; typed and continuation formats are versioned.')
    item('H01','5','Configurable CLI-only teacher and disabled API fallback','implemented_reference',['src/slm/teacher/cli.py','configs/teacher-cli-pilot.json','configs/teacher-disabled.json'],'Requested Luna identity is pinned; CLI does not report resolved model identity.')
    item('H02','5','Real small teacher pilot/cache/lineage/usage evidence','retained_pilot_evidence',['reports/milestone-twenty-eight-summary.json','reports/milestone-twenty-eight-host-bridge.json'],'14 successful candidates, two families; 17/20 reservations, no adapter-enforced settled-dollar cap.')
    item('H03','5','Conversation/clarification/correction/style/tool/student-failure generation','partial',['src/slm/teacher/scenarios.py','src/slm/teacher/bridge.py','reports/milestone-twenty-eight-summary.json'],'All task shapes have fixture tests; real data is narrow arithmetic. Genuine trained-student failure mining is not demonstrated.')
    item('H04','5','Human/rights/category-approved teacher data and broad validation','pending_input',['docs/milestone-twenty-nine.md','src/slm/data/review.py'],'No actual account/source evidence, human approval or mature-category pilot. Surface-distinct style outputs are not meaning/style acceptance.')
    item('H05','5','Executable host normalization and reviewed continuation masks','partial',['src/slm/teacher/bridge.py','src/slm/common/supervision.py'],'Multiplication mapping only; partial historical tool exchanges unsupported. Historical assistant mistakes have zero direct loss.')
    item('H06','5','Source-bound offline review workflow','implemented_reference',['src/slm/data/review_console.py','src/slm/data/review_console.html','reports/milestone-twenty-nine-summary.json'],'Teacher gates work in synthetic DOM/Python controls; actual browser layout/download remains unverified and actual rights remain absent.')
    item('P01','6','Target architecture count and full-depth tiny-overfit checks','retained_reference_evidence',['configs/target-81m.json','reports/milestone-six-fullsize.json'],'Random initialization and synthetic checks only; full trajectory criterion still fails.')
    item('P02','6','General bounded reviewed-data pilot execution command','implemented_reference' if pilot_main_found else 'missing',
        ['src/slm/train.py','tests/test_train.py','docs/reviewed-data-pilot-runner.md'] if pilot_main_found else ['src/slm/common/training.py','src/slm/common/curriculum.py','src/slm/eval/benchmark.py'],
        'Reference runner now binds reviewed content, budgets, managed checkpoints and resume/stage receipts. Synthetic local tests are not the real language pilot; actual CUDA wrapper validation remains open.' if pilot_main_found else 'No general reviewed-data pilot command found.')
    item('P03','6','Actual 1M-token English smoke training','missing',['reports/milestone-eleven-reader-scale.json','docs/project-ledger.md'],'No eligible production tokenizer/data or 1M neural-update run; synthetic reader positions do not meet this requirement.')
    item('P04','6','Actual 10M-token laptop language pilot','missing',['docs/project-ledger.md','reports/milestone-seven-mlx-benchmark.json'],'No trained language checkpoint or sustained run. Short benchmark is not this pilot.')
    item('P05','6','Optional evidence-driven 50M extension','conditional_deferred',['docs/slm-training-plan.md'],'Optional after measured 1M/10M results, not an unconditional required paid run.')
    item('P06','6','Sustained throughput/memory/restarts/checkpoint-overhead report','partial',['reports/milestone-seven-mlx-benchmark.json','reports/milestone-fifteen-dense-benchmark.json'],'Only short synthetic timing/resume evidence; no sustained real-data pilot or thermal profile.')
    item('G01','7','Authorized CUDA validation and retained cleanup records','retained_hardware_evidence',['reports/milestone-twenty-one-summary.json','reports/milestone-twenty-one-cleanup.json'],'USD 7 conservative allowance of USD 10 validation-only ceiling; settled billing unknown.')
    item('G02','7','Main training hardware/pricing/quota/storage/spending decision','pending_input',['docs/goal-prompt.md','docs/slm-training-plan.md'],'No main-training budget. Fresh full-instance quotes/availability required only before an authorized paid run.')
    item('G03','7','Actual staged 100M/1B/3B/10B evaluated checkpoints','missing',['docs/slm-training-plan.md','docs/project-ledger.md'],'No main pretraining performed; stages are planned experiments, not proof these token budgets suffice.')
    item('G04','7','Measured complete cost per million useful training tokens','missing',['reports/milestone-seven-cuda-benchmark.json'],'Short synthetic T4 timing is not current complete instance pricing or sustained production economics.')
    item('S01','8','Assistant-only/tool-call/termination masks and family grouping','implemented_reference',['src/slm/common/tokenizer.py','src/slm/common/tool_serialization.py','src/slm/data/curation.py'],'Mechanically tested masks; no actual conversation/style/tool SFT checkpoint.')
    item('S02','8','Conversation SFT with general replay and measured regression','missing',['src/slm/data/mixture.py','src/slm/data/curriculum.py','docs/slm-training-plan.md'],'Mixture support exists, but no 50K real approved conversation set or trained/reviewed baseline.')
    item('S03','8','Meaning-preserving five styles and recovery across turns','missing',['src/slm/teacher/styles.py','reports/milestone-twenty-eight-style-audit.json'],'Teacher guidance/cues exist; no learned student capability or human accepted pair evaluation.')
    item('S04','8','Independent SFW/mature content behavior and category approvals','pending_input',['docs/dataset-and-teacher-plan.md','src/slm/data/review.py'],'No mature source inventory/actual training/suite approval; style labels do not imply content categories.')
    item('S05','8','Five to ten supported tools and learned no-call/clarify/arguments','partial',['src/slm/tools/local.py','reports/milestone-twenty-one-summary.json'],'Five local handlers exist; actual random students fail seven scripted-control tasks. Learned correctness remains unproved.')
    item('S06','8','Dependent calls/preference tuning/RL only when justified','conditional_deferred',['docs/goal-prompt.md','src/slm/inference/tools.py'],'Do not promote optional later techniques before single-call correctness and useful SFT.')
    item('R01','9','Application-owned discovery/schema/execution/results/call limits','implemented_reference',['src/slm/tools/local.py','src/slm/tools/protocol.py','src/slm/inference/tools.py'],'Reference local handlers and bounded host integration; not unrestricted action authorization.')
    item('R02','9','Actual MCP stdio and bounded Streamable HTTP transport','implemented_reference',['src/slm/mcp/transport.py','src/slm/mcp/registry.py','src/slm/mcp/http.py','reports/milestone-twenty-one-summary.json'],'Local SDK process/HTTP and retained CUDA scripted controls; production OAuth/authorization is not implemented.')
    item('R03','9','Untrusted tool-result handling and first-attempt error reporting','implemented_reference',['src/slm/inference/tools.py','src/slm/mcp/transport.py','src/slm/mcp/http.py'],'No automatic outcome replay; missing result remains unknown. Model resistance is not proven by schema controls.')
    item('R04','9','Learned end-to-end task completion on both deployment backends','missing',['reports/milestone-twenty-one-summary.json','reports/milestone-seventeen-summary.json'],'Scripted success and random-student negative controls are not a useful learned model.')
    item('X01','10','ESCI splits/query families and retrieval/ranker comparison','conditional_deferred',['docs/slm-training-plan.md'],'Correctly gated after core conversation/tool capability; no ESCI adapter/data/ranker experiment yet.')
    item('X02','10','Domain replay, relevance/regression and full latency/memory','conditional_deferred',['docs/slm-training-plan.md'],'No core checkpoint exists to specialize or protect; do not substitute ESCI for language pretraining.')
    item('X03','10','Quantized exports checked against unquantized learned reference','conditional_deferred',['docs/slm-training-plan.md','src/slm/common/checkpoint.py'],'No accepted learned baseline or deployment-quality comparison; reference FP32 storage is not quantization.')
    item('E01','Evaluation','500 human-reviewed initial cases and accepted stage policy','pending_input',['data/evaluation-candidates-v1/suite-review.json','configs/stage-screen-proposal-v1.json'],'500 candidate cases exist, zero approved. Stage policy remains proposed.')
    item('E02','Evaluation','Adequate held-out slice coverage, human rubrics and uncertainty','partial',['src/slm/eval/conversation.py','src/slm/eval/stage.py','src/slm/eval/cases.py'],'Scoring/screens exist; no accepted mature suite, blind human grades or useful student behavior.')
    item('E03','Evaluation','Tool/clarification/turn/meaning/style/unsupported-claim targets','missing',['docs/slm-training-plan.md','reports/milestone-seventeen-summary.json'],'95%/95%/90%/90%/90% and <=1% unsupported-claim targets have no learned-model release evidence.')
    item('E04','Evaluation','Constrained schema/raw-versus-constrained and repair comparisons','partial',['src/slm/inference/tools.py','src/slm/eval/tools.py'],'Strict raw parsing/rejection and no-repair controls exist; no general constrained decoder or 99.5% learned-schema result.')
    item('E05','Evaluation','M4 p95 latency and 2K total incremental inference memory','missing',['reports/milestone-seven-mlx-benchmark.json','docs/slm-training-plan.md'],'Short training timing is neither p95 complete tool-generation latency nor full deployment memory.')
    item('O01','Ownership','Private repository, sole creator and cohesive milestone history','implemented_reference',['docs/project-ledger.md','docs/goal-prompt.md'],'Git/private visibility are verified separately at publication; dependency provenance is retained.')
    item('O02','Working rules','Ledger, explicit budgets and no unauthorized main runs','implemented_reference',['docs/project-ledger.md','configs/teacher-cli-pilot.json','reports/milestone-twenty-nine-summary.json'],'No inference that generation usage is free or that the validation budget covers pretraining.')
    files={str(p):sha(p) for p in paths};refs['pyproject.toml']=sha('pyproject.toml')
    report={'version':1,'creator':'Navneet Prabhakar','scope':'Read-only requirement/evidence audit of the original full goal; no promotion or approval tool',
      'goal_achieved':False,'criteria':items,'status_counts':dict(Counter(i['status'] for i in items)),
      'observations':{'target_parameters':config.parameter_count,'public_sample_rows':sample_report['retained_examples'],
        'public_sample_splits':sample_report['splits'],'public_language_labels':sample_report['language_labels'],'public_content_labels':sample_report['content_categories'],
        'reviewed_packet_rows':len(packet['examples']),'public_source_approvals':source_approvals,'public_row_approvals':row_approvals,
        'public_human_attestation':packet['human_attestation'],'public_review_packet_sha256':digest(packet),'public_sample_training_reader_refusal':reader_refusal,
        'public_training_releases_found':real_releases,'data_manifest_files_inspected':manifest_count,
        'candidate_evaluation_cases':len(suite['cases']),'approved_evaluation_cases':approved_cases,
        'evaluation_output_human_attestation':output_review['human_attestation'],'stage_policy_status':stage_policy['status'],
        'strict_trajectory_gate_passed':False,'production_tokenizer_selected_in_retained_report':False,
        'synthetic_reader_positions':scale['build']['processed_prediction_positions'],'synthetic_reader_neural_updates':0,
        'teacher_candidates':14,'teacher_approvals':0,'teacher_journals':journals,'combined_teacher_reserved_slots':17,
        'latest_local_suite':tests,'general_pilot_main_found':pilot_main_found,'entrypoints_inspected':mains},
      'next_independent_implementation':('Production intake/admission policy and scalable grouping, while data/tokenizer/portability inputs gate real 1M/10M pilots.' if pilot_main_found else 'Bounded reviewed-data pilot runner over existing trainers with verified source bindings, budgets and recovery; synthetic validation only until real input gates are resolved.'),
      'external_inputs':['Source terms and explicit review decisions for current public packet','Scalable admission/quality-policy approval before bulk corpus release',
        'Portability acceptance option A/B','Actual account/source evidence and human teacher judgments','Evaluation suite/policy/rubric review',
        'Main GCP budget/hardware decision at its later paid-run gate'],
      'new_training_updates':0,'new_teacher_launches':0,'new_cloud_jobs':0,'source_or_policy_approvals_changed':False,
      'historical_hardware_scope':'Retained reports only; no new CUDA run, cloud-resource query, availability/pricing check or billing verification.',
      'evidence_sha256':refs,'code_inventory_sha256':digest(files),'audit_script_sha256':sha(__file__),
      'limitations':['Statuses distinguish implemented reference behavior from real-data/learned capability; no aggregate readiness percentage.',
        'Inventory of Source-bearing training manifests is local only, not a claim about unseen external storage.',
        'Human attestations are evidence records, not cryptographic proof of judgment. No unsupported approval is inferred.']}
    assert sha(packet_path)==packet_before
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
    return {'criteria':len(items),'goal_achieved':False,'status_counts':report['status_counts'],'public_approvals':row_approvals,'new_training_updates':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(audit(a.output),sort_keys=True))
