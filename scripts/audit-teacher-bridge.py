#!/usr/bin/env python3
"""Read-only real-cache composition audit; outputs are private pending previews."""
# Creator: Navneet Prabhakar
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from slm.teacher.bridge import normalize,sha
from slm.teacher.workflow import parse_json
from slm.data.schema import digest


def state(path):
    path=Path(path).resolve(strict=True)
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        halted,limit=db.execute('SELECT halted,max_requests FROM budget').fetchone()
        counts=dict(db.execute('SELECT status,COUNT(*) FROM requests GROUP BY status').fetchall())
    return {'halted':bool(halted),'max_requests':limit,'states':counts,'reserved_slots':sum(counts.values())}


def audit(records,journal,output,report_file,prior_journal=None):
    output,report_file=Path(output),Path(report_file);journal=Path(journal)
    if output.exists() or report_file.exists():raise FileExistsError('Fresh audit destinations required')
    if not 1<=len(records)<=20:raise ValueError('One to twenty bounded cached records required')
    before={'active':state(journal),'active_sha256':sha(journal)}
    if prior_journal:before.update(prior=state(prior_journal),prior_sha256=sha(prior_journal))
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.bridge-audit-',dir=output.parent))
    rows=[];reviews=[];seen=set()
    text=['# Pending teacher transcript review','', 'Creator: Navneet Prabhakar','',
        'These are unapproved candidate previews. No source license or account training-use permission is inferred. '
        'Review the complete composed transcript, including legacy reply ambiguity and historical assistant wrappers. '
        'No preview or worksheet is accepted as a training release.','']
    try:
        for path in map(Path,records):
            if path.stat().st_size>256*1024:raise ValueError('Bounded teacher record required')
            record=parse_json(path.read_text());preview=normalize(record,journal)
            key=record['request_key']
            if key in seen:raise ValueError('Duplicate request in bridge audit')
            seen.add(key);name=key+'.json';(temp/name).write_text(json.dumps(preview,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
            proof=preview['proof'];rows.append({'record_file':str(path),'record_file_sha256':sha(path),
                'request_key':key,'preview_file':name,'preview_file_sha256':sha(temp/name),
                'preview_sha256':digest(preview),'task':record['request']['scenario']['task'],'style':preview['style'],
                'family_id':preview['family_id'],'messages':len(preview['messages']),
                'history_assistant_wrappers':proof['history_assistant_wrappers'],
                'host_call_executed':proof['host_result'] is not None,
                'legacy_tool_reply_role_ambiguous':proof['legacy_tool_reply_role_ambiguous'],
                'training_eligible':False,'source_evidence_supplied':False})
            reviews.append({'request_key':key,'preview_sha256':digest(preview),
                'teacher_review':{k:None for k in preview['required_human_checks']},'note':''})
            text.extend(['## '+preview['scenario_id'],'',
                f"- Style: {preview['style']}; task: {rows[-1]['task']}; family: {preview['family_id']}",
                f"- Legacy tool-reply ambiguity: {proof['legacy_tool_reply_role_ambiguous']}",
                '- Pending review: reply meaning, style/content, historical conversion, host grounding; source rights remain separate.','',
                'Original teacher reply: '+record['validation']['candidate']['reply'],''])
            for message in preview['messages']:text.extend([message['role'].upper()+':',message['content'],''])
        (temp/'REVIEW.md').write_text('\n'.join(text))
        (temp/'review-worksheet.json').write_text(json.dumps({'kind':'preview-review-worksheet-only',
            'reviewer':None,'human_attestation':False,'source_terms_confirmed':False,'examples':reviews},indent=2)+'\n')
        after={'active':state(journal),'active_sha256':sha(journal)}
        if prior_journal:after.update(prior=state(prior_journal),prior_sha256=sha(prior_journal))
        if before!=after:raise ValueError('Journal changed during read-only bridge audit')
        scope='Cached teacher transcript composition; no new generation, source-rights evidence, release or model competence'
        report={'version':1,'scope':scope,'records':rows,'record_count':len(rows),
            'family_count':len({r['family_id'] for r in rows}),'tasks':dict(Counter(r['task'] for r in rows)),
            'host_arithmetic_executions':sum(r['host_call_executed'] for r in rows),
            'legacy_ambiguous_tool_replies':sum(r['legacy_tool_reply_role_ambiguous'] for r in rows),
            'new_teacher_launches':0,'api_calls':0,'cloud_jobs':0,'training_approvals':0,
            'journal_before':before,'journal_after':after,'journal_unchanged':True,
            'source_rights_verified':False,'free_text_meaning_verified':False,'style_content_verified':False,
            'source_sha256':{p:sha(p) for p in ('src/slm/teacher/bridge.py','src/slm/data/review.py',
                'src/slm/data/review_console.py','scripts/audit-teacher-bridge.py')},
            'private_artifacts':{p.name:sha(p) for p in sorted(temp.iterdir())}}
        os.rename(temp,output)
        report_file.parent.mkdir(parents=True,exist_ok=True)
        with report_file.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
    except BaseException:shutil.rmtree(temp,ignore_errors=True);raise
    return {'record_count':len(rows),'host_arithmetic_executions':report['host_arithmetic_executions'],
        'journal_unchanged':True,'new_teacher_launches':0,'training_approvals':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--record',action='append',required=True)
    p.add_argument('--journal',required=True);p.add_argument('--prior-journal');p.add_argument('--output',required=True);p.add_argument('--report',required=True)
    a=p.parse_args();print(json.dumps(audit(a.record,a.journal,a.output,a.report,a.prior_journal),sort_keys=True))
