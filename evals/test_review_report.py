"""Regression checks for the REVIEW.md summary-block validator (scripts/check_review_report.py)."""
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
SCRIPT = ROOT / 'scripts/check_review_report.py'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
SECRET = 'sk-live-0123456789abcdef'


def block(report, info='json veriloop-report'):
    return f'```{info}\n{json.dumps(report, ensure_ascii=False, indent=2)}\n```\n'


def document(report, before='', after=''):
    return f'# Review\n\nThe gate held on the final candidate.\n\n{before}{block(report)}{after}'


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp).resolve()
    run_one = root / 'run-001.json'
    run_one.write_text(json.dumps({'exit_reason': 'no_progress', 'goal': 'g'}, indent=2) + '\n', encoding='utf-8')
    run_two = root / 'run-002.json'
    run_two.write_text(json.dumps({'exit_reason': 'goal_met', 'goal': 'g'}, indent=2) + '\n', encoding='utf-8')
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = {
        'report_version': '1', 'work': 'work-1 preserve ISO dates',
        'spec': {'path': 'docs/feature-x/IA.md', 'version': 'v1.2'},
        'current': {'run': 'work-1/run-002', 'exit_reason': 'goal_met', 'gate': 'hold', 'snapshot': 'sha256:abc', 'updated': '2026-10-19'},
        'runs': [
            {'run': 'work-1/run-001', 'exit_reason': 'no_progress', 'gate': 'not_run',
             'iterations': [{'iteration': 1, 'verdict': 'fail', 'failed_count': 2, 'warning_count': 0},
                            {'iteration': 2, 'verdict': 'fail', 'failed_count': 2, 'warning_count': 1}],
             'archive': {'path': '.agent-review/runs/001/run.json', 'sha256': digest(run_one)}},
            {'run': 'work-1/run-002', 'exit_reason': 'goal_met', 'gate': 'hold',
             'iterations': [{'iteration': 1, 'verdict': 'pass_with_warnings', 'failed_count': 0, 'warning_count': 1}],
             'archive': {'path': '.agent-review/runs/002/run.json', 'sha256': digest(run_two)}},
        ],
        'acceptance': [
            {'criterion': 'AC1', 'phase': 'loop', 'result': 'pass', 'evidence': 'exit 0'},
            {'criterion': 'AC2', 'phase': 'post_deploy', 'result': 'deferred', 'evidence': 'needs dev deploy'},
            {'criterion': 'AC3', 'phase': 'manual', 'result': 'pass', 'evidence': 'screen checked'},
        ],
        'oracles': [{'id': 'O1', 'invariant': 'dates round-trip', 'result': 'pass', 'historical': 2, 'rediscovered': 2}],
        'findings': [
            {'id': 'F1', 'severity': 'failed', 'title': 'Leap day dropped', 'status': 'pass', 'disposition': None},
            {'id': 'W1', 'severity': 'warning', 'title': 'Helper is long', 'status': 'accepted', 'disposition': 'accept'},
            {'id': 'W2', 'severity': 'warning', 'title': 'Old comment', 'status': 'pass', 'disposition': None},
        ],
        'open_items': [{'kind': 'deferred_acceptance', 'ref': 'AC2', 'note': 'run after the dev deploy'}],
    }
    path = root / 'REVIEW.md'
    counts = {True: 0, False: 0}

    def check(text, valid, label, reason=None, run_json=()):
        path.write_text(text, encoding='utf-8')
        argv = [sys.executable, str(SCRIPT), str(path)]
        for item in run_json:
            argv += ['--run-json', str(item)]
        result = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', env=ENV)
        assert (result.returncode == 0) == valid, (label, result.stdout, result.stderr)
        if valid:
            assert result.stdout.strip() == 'VALID: review report', (label, result.stdout)
        else:
            assert result.stderr.startswith('INVALID: '), (label, result.stderr)
            assert reason is None or reason in result.stderr, (label, result.stderr)
            assert SECRET not in result.stderr + result.stdout, label
        counts[valid] += 1

    def mutated(change):
        value = copy.deepcopy(report)
        change(value)
        return document(value)

    # Valid documents.
    check(document(report), True, 'valid report')
    check(document(report), True, 'run.json digests match', run_json=[run_one, run_two])
    example = '~~~markdown\n' + block({'example': True}) + '~~~\n\n'
    check(document(report, before=example), True, 'tagged example inside a tilde fence is ignored')
    check(document(report, before='```json\n{"verdict": "pass", "findings": []}\n```\n\n'), True, 'untagged JSON block is ignored')
    capped = copy.deepcopy(report)
    capped['current'].update(exit_reason='iteration_cap', gate='fail')
    capped['runs'][1].update(exit_reason='iteration_cap', gate='fail')
    capped['findings'][0]['status'] = 'open'
    capped['acceptance'][0]['result'] = 'fail'
    check(document(capped), True, 'goal rules apply only to goal_met')

    # Block discovery and parsing.
    check(document(report, after=block(report)), False, 'two report blocks', 'found 2')
    check(f'# Review\n\n{block(report, "json")}', False, 'zero report blocks', 'found 0')
    check(document(report)[:-4], False, 'unclosed report block', 'not closed')
    check(f'```json veriloop-report\nSummary: {json.dumps(report)}\n```\n', False, 'prose inside the block', 'invalid JSON')
    check('```json veriloop-report\n{"report_version": "1", "report_version": "1"}\n```\n', False, 'duplicate JSON key', 'duplicate JSON key')
    check(mutated(lambda r: r['findings'][0].update(severity=SECRET)), False, 'schema violation does not echo values', 'value is outside enum')
    check(mutated(lambda r: r.update(extra=SECRET)), False, 'unexpected key', 'unexpected keys')

    # Report semantics.
    check(mutated(lambda r: r['findings'][0].update(status='open')), False, 'goal_met with an open failed finding', 'unresolved failed finding')
    check(mutated(lambda r: r['findings'][0].update(status='recurred')), False, 'goal_met with a recurred failed finding', 'unresolved failed finding')
    check(mutated(lambda r: r['findings'][0].update(status='accepted')), False, 'goal_met with an accepted failed finding', 'unresolved failed finding')
    check(mutated(lambda r: r['runs'][1]['iterations'][0].update(verdict='fail', failed_count=1, warning_count=0)), False, 'goal_met after a failing last iteration', 'failing last iteration')
    check(mutated(lambda r: r['runs'][0].update(run='001')), False, 'run not named <work id>/run-NNN', 'run-NNN')
    check(document(report, after='\n## Late note\n\nAdded after the block.\n'), False, 'content after the report block', 'last content')
    check(mutated(lambda r: r.update(open_items=[])), False, 'deferred acceptance without an open item', 'lacks a deferred_acceptance open item')
    check(mutated(lambda r: r['open_items'][0].update(kind='follow_up')), False, 'deferred acceptance with the wrong open item kind', 'lacks a deferred_acceptance')
    check(mutated(lambda r: r['acceptance'][1].update(phase='loop')), False, 'deferred loop-phase acceptance', 'cannot be deferred')
    check(mutated(lambda r: r['findings'][1].update(status='open', disposition=None)), False, 'open warning without a disposition', 'needs a disposition')
    check(mutated(lambda r: r['findings'][1].update(disposition=None)), False, 'accepted warning without a disposition', 'needs a disposition')
    check(mutated(lambda r: r['findings'][0].update(disposition='accept')), False, 'failed finding with a disposition', 'cannot carry a disposition')
    check(mutated(lambda r: r['current'].update(run='work-1/run-001')), False, 'current is not the last run', 'not the last run')
    check(mutated(lambda r: r['current'].update(gate='fail')), False, 'current gate disagrees with the last run', 'current.gate')
    check(mutated(lambda r: r['runs'][0].update(run='work-1/run-002')), False, 'duplicate run ids', 'run ids')
    check(mutated(lambda r: r['acceptance'][2].update(criterion='AC1')), False, 'duplicate criteria', 'criteria are not unique')
    check(mutated(lambda r: r['findings'][2].update(id='W1')), False, 'duplicate finding ids', 'ids are not unique')
    check(mutated(lambda r: r['acceptance'][0].update(result='blocked')), False, 'goal_met with a blocked loop criterion', 'loop-phase criterion to pass')
    check(mutated(lambda r: r['oracles'][0].update(rediscovered=1)), False, 'goal_met with a weak oracle', 'rediscovered fewer')
    check(mutated(lambda r: r['oracles'][0].update(result='fail')), False, 'goal_met with a failing oracle', 'passing oracle')
    check(mutated(lambda r: r['oracles'][0].update(rediscovered=3)), False, 'oracle claims more than it had', 'exceeds historical')
    check(mutated(lambda r: (r['current'].update(gate='fail'), r['runs'][1].update(gate='fail'))), False, 'goal_met without a held gate', 'held gate')
    check(mutated(lambda r: r['runs'][0]['archive'].update(sha256='A' * 64)), False, 'uppercase digest', 'lowercase hex')

    # Archived run.json binding.
    tampered = root / 'run-002-tampered.json'
    tampered.write_bytes(run_two.read_bytes() + b' ')
    check(document(report), False, 'run.json digest mismatch', 'matches no archived run', run_json=[tampered])
    swapped = root / 'run-swapped.json'
    swapped.write_text(json.dumps({'exit_reason': 'goal_met', 'goal': 'first'}) + '\n', encoding='utf-8')
    check(mutated(lambda r: r['runs'][0]['archive'].update(sha256=digest(swapped))), False,
          'run.json exit reason disagrees with its entry', 'exit_reason disagrees', run_json=[swapped])

print(f'PASS review report CLI: {counts[True]} valid documents and {counts[False]} rejection cases')
