"""Regression checks for the runtime result-validation command."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp).resolve()
    staging = root / 'stage'
    staging.mkdir()
    artifact = staging / 'evidence.txt'
    artifact.write_text('safe evidence')
    data = json.loads((ROOT / 'evals/fixtures/archives/developer-clean.json').read_text())
    data['artifacts'] = []
    for c in data['checks']:
        c['artifact_path'] = None
    def check(value, valid):
        payload = root / 'result.json'
        payload.write_text(value if isinstance(value,str) else json.dumps(value))
        result = subprocess.run([sys.executable,str(ROOT/'scripts/check_worker_result.py'),str(payload),'--role','developer','--staging-root',str(staging)],capture_output=True)
        assert (result.returncode == 0) == valid, result.stderr.decode()
    check(data,True)
    bad=copy.deepcopy(data);bad['checks'][0]['evidence']='x'*513;check(bad,False)
    bad=copy.deepcopy(data);bad['checks'][0]['kind']='assertion';bad['checks'][0]['exit_code']=0;check(bad,False)
    check('prefix '+json.dumps(data),False)
    check('{"role":"developer","role":"fixer"}',False)
    check(' '*16385,False)
    good=copy.deepcopy(data)
    good['artifacts']=[{'path':str(artifact),'bytes':artifact.stat().st_size,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}]
    good['checks'][0]['artifact_path']=str(artifact)
    check(good,True)
    bad=copy.deepcopy(good);bad['artifacts'][0]['sha256']='0'*64;check(bad,False)
    bad=copy.deepcopy(good);bad['checks'][0]['artifact_path']=None;check(bad,False)
    outside=root/'outside.txt';outside.write_bytes(artifact.read_bytes())
    bad=copy.deepcopy(good);bad['artifacts'][0]['path']=str(outside);bad['checks'][0]['artifact_path']=str(outside);check(bad,False)
    link=staging/'link.txt';link.symlink_to(artifact)
    bad=copy.deepcopy(good);bad['artifacts'][0]['path']=str(link);bad['checks'][0]['artifact_path']=str(link);check(bad,False)
print('PASS runtime CLI: 2 valid results and 9 rejection cases')
