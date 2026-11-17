#!/usr/bin/python3
"""Inject invalid test credentials only for this test's payload upload."""
import json,os,sys
from pathlib import Path
a=sys.argv[1:]
if len(a)>=4 and a[:2]==['storage','cp'] and Path(a[2]).name=='payload.pt' and a[3].startswith(os.environ['FAULT_ALLOWED_PREFIX']+'/checkpoint-'):
 Path(os.environ['FAULT_UPLOAD_MARKER']).write_text(json.dumps({'payload_upload_intercepted':True,'destination':a[3],'fault':'invalid test access token; production credentials unchanged'})+'\n')
 a=['--access-token-file='+os.environ['FAULT_TOKEN_FILE'],*a]
os.execv(os.environ['FAULT_REAL_GCLOUD'],[os.environ['FAULT_REAL_GCLOUD'],*a])
