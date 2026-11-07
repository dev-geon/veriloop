"""Regression checks for the reviewer and gate result validation commands."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
PLAN = {'invariant': 'i', 'root_cause': 'r', 'affected_paths': ['a.py'], 'implementation_steps': ['s'],
        'verification_cases': ['v'], 'non_goals': []}
FINDING = {'severity': 'failed', 'title': 't', 'file': 'a.py', 'line': 1, 'confidence': 'confirmed',
           'fix_hint': 'f', 'repair_plan': PLAN}
FAILED = {'verdict': 'fail', 'findings': [FINDING]}
PASSED = {'verdict': 'pass', 'findings': []}
GATE = json.loads((ROOT / 'evals/fixtures/archives/clean-gate.json').read_text(encoding='utf-8'))
checks = 0


def run(script, payload, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'result.txt'
        path.write_bytes((payload if isinstance(payload, str) else json.dumps(payload)).encode('utf-8'))
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / script), str(path), *extra],
                              capture_output=True, text=True, encoding='utf-8', env=ENV)


def expect(script, payload, valid, label, *extra, reason=None, output=None):
    global checks
    result = run(script, payload, *extra)
    assert (result.returncode == 0) == valid, (label, result.stdout, result.stderr)
    assert 'Traceback' not in result.stderr, (label, result.stderr)
    if reason:
        assert reason in result.stderr, (label, result.stderr)
    if output:
        assert result.stdout.startswith(output), (label, result.stdout)
    checks += 1


def digest(payload):
    return hashlib.sha256((payload if isinstance(payload, str) else json.dumps(payload)).encode('utf-8')).hexdigest()


def report(value, info='json'):
    return f'## 리뷰\n\n본문\n\n```{info}\n{json.dumps(value)}\n```\n'


REVIEW = 'check_review_result.py'
expect(REVIEW, PASSED, True, 'raw JSON')
expect(REVIEW, FAILED, True, 'raw JSON with a finding')
expect(REVIEW, report(PASSED), True, 'plain fence')
expect(REVIEW, report(FAILED, 'json veriloop-review'), True, 'tagged fence')
expect(REVIEW, report(PASSED) + report(FAILED, 'json veriloop-review'), True, 'last block wins', output='VALID: fail, 1 findings')
expect(REVIEW, report(FAILED) + '\n후기\n', False, 'prose after the block', reason='text follows the result block')
expect(REVIEW, report(PASSED) + '```json\n{"verdict": "fail"', False, 'a later block left open', reason='not closed')
nested = '````markdown\n' + report(FAILED) + '````\n'
expect(REVIEW, nested + report(PASSED), True, 'a nested example is not a block', output='VALID: pass')
expect(REVIEW, nested, False, 'only a nested example', reason='no machine-readable JSON block')
separator = dict(FINDING, title='줄\u2028바꿈')
expect(REVIEW, '```json\n' + json.dumps({'verdict': 'fail', 'findings': [separator]}, ensure_ascii=False) + '\n```\n', True, 'U+2028 inside a JSON string', output='VALID: fail')
expect(REVIEW, '{"verdict": ' + '[' * 200000, False, 'very deep nesting', reason='INVALID')
secret = run(REVIEW, {'verdict': 'sk-live-secret', 'findings': []})
assert secret.returncode == 1 and 'sk-live-secret' not in secret.stderr + secret.stdout, secret.stderr
checks += 1
expect(REVIEW, '## 리뷰\n\n통과\n', False, 'no block', reason='no machine-readable JSON block')
expect(REVIEW, report(PASSED, 'json veriloop-report'), False, 'report block is not a result', reason='no machine-readable JSON block')
expect(REVIEW, {'verdict': 'pass', 'findings': [FINDING]}, False, 'pass with a finding', reason='pass must have no findings')
expect(REVIEW, {'verdict': 'fail', 'findings': []}, False, 'fail without a finding', reason='fail must contain')
expect(REVIEW, {'verdict': 'fail', 'findings': [dict(FINDING, repair_plan='fix it')]}, False, 'repair plan as a string', reason='repair_plan')
expect(REVIEW, '{"verdict": "pass", "verdict": "pass", "findings": []}', False, 'duplicate key', reason='duplicate JSON key')

expect(REVIEW, report(PASSED), True, 'the file the pointer named', '--sha256', digest(report(PASSED)))
expect(REVIEW, report(PASSED), False, 'another file than the pointer named', '--sha256', '0' * 64, reason='result digest mismatch')

GATE_SCRIPT = 'check_gate_result.py'
expect(GATE_SCRIPT, GATE, True, 'the file the pointer named', '--sha256', digest(GATE))
expect(GATE_SCRIPT, GATE, False, 'another file than the pointer named', '--sha256', '0' * 64, reason='result digest mismatch')
expect(GATE_SCRIPT, GATE, True, 'clean gate', output='VALID: hold')
expect(GATE_SCRIPT, '# 게이트\n\n```json veriloop-gate\n' + json.dumps(GATE) + '\n```\n', True, 'report ending in a tagged block', output='VALID: hold')
stuck = copy.deepcopy(GATE); stuck['gate'] = 'blocked'
expect(GATE_SCRIPT, stuck, False, 'blocked with no blocked probe', reason='blocked has no blocked probe')
expect(GATE_SCRIPT, GATE, True, 'matching snapshot', '--snapshot', GATE['snapshot'])
expect(GATE_SCRIPT, GATE, False, 'other snapshot', '--snapshot', 'sha256:other', reason='different snapshot')
renamed = copy.deepcopy(GATE); renamed['verdict'] = renamed.pop('gate')
expect(GATE_SCRIPT, renamed, False, 'verdict instead of gate', reason='missing required keys')
shaped = copy.deepcopy(GATE); shaped['probes'] = [{'id': 'p1', 'description': 'd', 'command': 'c', 'result': 'pass', 'evidence': 'e'}]
expect(GATE_SCRIPT, shaped, False, 'probe with the wrong fields', reason='missing required keys')
failing = copy.deepcopy(GATE); failing['probes'][0]['result'] = 'fail'
expect(GATE_SCRIPT, failing, False, 'held with a failed probe', reason='held with a failed probe')
expect(GATE_SCRIPT, 'gate: ' + json.dumps(GATE), False, 'prose before the object', reason='no machine-readable JSON block')
print(f'PASS result CLI: {checks} cases')
