"""Regression checks for the run archival command (scripts/archive_run.py)."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/archive_run.py'
spec = importlib.util.spec_from_file_location('contracts', ROOT / 'evals/run_contract_evals.py')
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
SECRET = 'sk-live-0123456789abcdef'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp).resolve()
    agent = root / '.agent-review'
    agent.mkdir()
    runs = agent / 'runs'
    staging = agent / 'staging'
    inputs = root / 'inputs'

    def make_staging():
        (staging / 'logs').mkdir(parents=True, exist_ok=True)
        (staging / 'evidence.txt').write_bytes(b'exit 0: ISO date preserved\n')
        (staging / 'logs' / 'check.txt').write_bytes(b'assertion observed\n')
        (staging / 'unreferenced.txt').write_bytes(b'must not be archived\n')

    def staging_state():
        if not staging.exists():
            return None
        return {str(p.relative_to(staging)): p.read_bytes() for p in staging.rglob('*') if p.is_file()}

    make_staging()
    evidence, check_log = staging / 'evidence.txt', staging / 'logs' / 'check.txt'

    stalled = {
        'role': 'developer', 'status': 'blocked', 'termination': 'timeout', 'changed_files': [],
        'checks': [], 'tool_failures': [], 'artifacts': [],
        'blocker': {'code': 'timeout', 'message': 'stalled: no progress for 20 minutes', 'needs_user_input': False},
    }
    completed = json.loads((ROOT / 'evals/fixtures/archives/developer-clean.json').read_text(encoding='utf-8'))
    completed['checks'][0]['artifact_path'] = str(evidence)
    completed['checks'].append({
        'kind': 'assertion', 'criterion': 'The formatter keeps the output observable', 'check': 'observe the log',
        'exit_code': None, 'result': 'pass', 'evidence': 'log line observed', 'artifact_path': 'logs/check.txt',
    })
    completed['artifacts'] = [
        {'path': str(evidence), 'bytes': evidence.stat().st_size, 'sha256': sha(evidence.read_bytes())},
        {'path': 'logs/check.txt', 'bytes': check_log.stat().st_size, 'sha256': sha(check_log.read_bytes())},
    ]
    gate = json.loads((ROOT / 'evals/fixtures/archives/clean-gate.json').read_text(encoding='utf-8'))
    run = {
        'goal': 'Preserve ISO dates', 'spec_path': 'docs/feature-x/IA.md', 'exit_reason': 'goal_met',
        'blind_mode': 'strict', 'relaxation': {'authorized': False, 'reason': None, 'authorization': None},
        'iterations': [{'iteration': 1, 'verdict': 'pass', 'independence': 'strict', 'failed_count': 0,
                        'warning_count': 0, 'review_file': 'scratch/reviews/review-1.md'}],
        'acceptance': [
            {'criterion': 'AC1', 'check': 'python -c "assert True"', 'result': 'pass', 'evidence': 'exit 0'},
            {'criterion': 'AC2', 'check': 'python -c "assert True"', 'phase': 'loop', 'result': 'pass', 'evidence': 'exit 0'},
            {'criterion': 'AC3', 'check': 'smoke the deployed API', 'phase': 'post_deploy', 'result': 'deferred', 'evidence': 'needs dev deploy'},
        ],
        'preceding_runs': ['runs/000'],
        'oracles': [{'id': 'O1', 'invariant': 'dates round-trip', 'reference': 'datetime.date.isoformat',
                     'generator': 'every day of 2024', 'budget': '366 cases', 'result': 'pass',
                     'strength': {'historical': 2, 'rediscovered': 2}, 'evidence': 'exit 0: 366/366'}],
        'model_substitutions': [{'role': 'reviewer', 'from': 'model-a', 'to': 'model-b',
                                 'reason': 'rate limited', 'authorization': 'config fallback_models'}],
        # Follow-up run: the stalled predecessor was archived by the preceding run.
        'worker_successions': [{'predecessor': 'runs/000/workers/dev-1.json', 'successor': 'staging/dev-2.json',
                                'reason': 'stalled', 'authorization': 'user approved succession'}],
        'worker_files': ['to be replaced'], 'gate_files': [],
        'gate': {'status': 'hold', 'snapshot': gate['snapshot'], 'independence': 'strict'},
    }
    review_text = '# Iteration 1\n\nNo findings.\n\n```json\n{"verdict": "pass", "findings": []}\n```\n'

    def archive(run_value=None, workers=None, gate_value=None, staging_dirs=None, extra=(), worker_paths=None,
                review_value=None):
        case = root / 'case'
        shutil.rmtree(case, ignore_errors=True)
        workers = workers if workers is not None else {'dev-2.json': completed}
        paths = worker_paths or [write_json(case / 'workers' / name, value) for name, value in workers.items()]
        gate_path = write_json(case / 'gate-1.json', gate if gate_value is None else gate_value)
        review_path = case / 'review-1.md'
        review_path.write_text(review_text if review_value is None else review_value, encoding='utf-8')
        run_path = write_json(case / 'run.json', run if run_value is None else run_value)
        argv = [sys.executable, str(SCRIPT), '--agent-review', str(agent), '--run-json', str(run_path),
                '--gate', str(gate_path), '--review', str(review_path)]
        for path in paths:
            argv += ['--worker', str(path)]
        for path in (staging_dirs if staging_dirs is not None else [staging]):
            argv += ['--staging', str(path)]
        return subprocess.run(argv + list(extra), capture_output=True, text=True, encoding='utf-8', env=ENV)

    def listing():
        return sorted(p.name for p in runs.iterdir()) if runs.exists() else []

    rejected = 0

    def expect_rejected(label, reason, **kwargs):
        global rejected
        before, state = listing(), staging_state()
        result = archive(**kwargs)
        assert result.returncode == 1, (label, result.stdout, result.stderr)
        assert result.stderr.startswith('INVALID: ') and reason in result.stderr, (label, result.stderr)
        assert SECRET not in result.stderr + result.stdout, label
        assert listing() == before, (label, listing())
        assert staging_state() == state, label
        rejected += 1

    # 1. Happy path: artifacts copied, paths rewritten relative to the run directory.
    result = archive()
    assert result.returncode == 0, result.stderr
    run_dir = runs / '001'
    assert result.stdout.startswith(f'ARCHIVED {run_dir} run.json sha256='), result.stdout
    assert listing() == ['001'], listing()
    run_json = json.loads((run_dir / 'run.json').read_text(encoding='utf-8'))
    contracts.validate_result('run', run_json)
    assert result.stdout.strip().endswith(sha((run_dir / 'run.json').read_bytes()))
    assert run_json['worker_files'] == ['workers/dev-2.json']
    assert run_json['gate_files'] == ['gates/gate-1.json']
    assert run_json['iterations'][0]['review_file'] == 'reviews/review-1.md'
    assert run_json['worker_successions'][0]['predecessor'] == 'runs/000/workers/dev-1.json'
    assert run_json['worker_successions'][0]['successor'] == 'workers/dev-2.json'
    assert run_json['oracles'] == run['oracles'] and run_json['model_substitutions'] == run['model_substitutions']
    archived = json.loads((run_dir / 'workers/dev-2.json').read_text(encoding='utf-8'))
    assert [a['path'] for a in archived['artifacts']] == ['artifacts/dev-2/evidence.txt', 'artifacts/dev-2/check.txt']
    assert [c['artifact_path'] for c in archived['checks']] == ['artifacts/dev-2/evidence.txt', 'artifacts/dev-2/check.txt']
    assert (run_dir / 'artifacts/dev-2/evidence.txt').read_bytes() == evidence.read_bytes()
    assert (run_dir / 'artifacts/dev-2/check.txt').read_bytes() == check_log.read_bytes()
    assert not any(p.name == 'unreferenced.txt' for p in run_dir.rglob('*'))
    assert (run_dir / 'gates/gate-1.json').read_bytes() == (root / 'case/gate-1.json').read_bytes()
    assert (run_dir / 'reviews/review-1.md').read_text(encoding='utf-8') == review_text
    contracts.validate_worker_semantics(archived, 'developer', 'archived', staging_root=run_dir)
    checked = subprocess.run([sys.executable, str(ROOT / 'scripts/check_worker_result.py'), str(run_dir / 'workers/dev-2.json'),
                              '--role', 'developer', '--staging-root', str(run_dir)], capture_output=True, env=ENV)
    assert checked.returncode == 0, checked.stderr
    assert staging_state() is not None, 'staging was removed without --delete-staging'

    # 2. Second archive gets 002; --delete-staging removes only the staging directory.
    result = archive(extra=['--delete-staging'])
    assert result.returncode == 0, result.stderr
    assert listing() == ['001', '002'], listing()
    assert not staging.exists() and agent.exists() and (run_dir / 'run.json').exists()
    assert (runs / '002/artifacts/dev-2/evidence.txt').exists()
    make_staging()

    # 3. Rejections: exit 1, no new run directory, no .partial left, staging intact.
    bad = copy.deepcopy(completed); bad['artifacts'][0]['sha256'] = '0' * 64
    expect_rejected('artifact digest mismatch', 'artifact digest is incorrect', workers={'dev-2.json': bad})
    bad = copy.deepcopy(completed); bad['artifacts'][1]['bytes'] += 1
    expect_rejected('artifact byte count mismatch', 'artifact size mismatch', workers={'dev-2.json': bad})
    bad = copy.deepcopy(run); bad['acceptance'][1]['result'] = 'deferred'
    expect_rejected('goal_met with a deferred loop-phase acceptance', 'loop-phase acceptance archived as deferred', run_value=bad)
    bad = copy.deepcopy(run); bad['acceptance'][0]['result'] = 'deferred'
    expect_rejected('deferred acceptance without a phase', 'loop-phase acceptance archived as deferred', run_value=bad)
    bad = copy.deepcopy(run); bad['acceptance'][2]['result'] = 'pass'
    expect_rejected('post-deploy acceptance archived as passed', 'post_deploy acceptance must be archived as deferred', run_value=bad)
    bad = copy.deepcopy(run); bad['oracles'][0]['strength'] = {'historical': 3, 'rediscovered': 2}
    expect_rejected('goal_met with a weak oracle', 'missing historical failures', run_value=bad)
    bad = copy.deepcopy(run); bad['oracles'][0]['strength'] = {'historical': 2, 'rediscovered': 3}
    expect_rejected('oracle claims more than it had', 'rediscovered more than it had', run_value=bad)
    bad = copy.deepcopy(run); bad['iterations'][0]['review_file'] = 'scratch/reviews/review-9.md'
    expect_rejected('iteration review missing from the archive', 'review_file is not an archived review', run_value=bad)
    expect_rejected('review without a JSON block', 'no machine-readable JSON block', review_value='# Iteration 1\n\nNo findings.\n')
    expect_rejected('review verdict disagrees with the iteration', 'verdict disagrees with its review',
                    review_value='# Iteration 1\n\n```json\n{"verdict": "fail", "findings": [{"severity": "failed", "title": "t", '
                                 '"file": "a.py", "line": 1, "confidence": "confirmed", "fix_hint": "f"}]}\n```\n')
    bad = copy.deepcopy(run); bad['oracles'][0]['result'] = 'blocked'
    expect_rejected('goal_met with a blocked oracle', 'not passing', run_value=bad)
    bad = copy.deepcopy(run); bad['model_substitutions'][0]['to'] = 'model-a'
    expect_rejected('model substitution that changes nothing', 'model substitution changed nothing', run_value=bad)
    bad = copy.deepcopy(run); bad['worker_successions'][0]['predecessor'] = 'workers/dev-2.json'
    expect_rejected('succession inside one run', 'bypasses fail-closed exit', run_value=bad)
    bad = copy.deepcopy(run); bad['worker_successions'][0]['predecessor'] = 'elsewhere/workers/dev-1.json'
    expect_rejected('succession from a run that is not preceding', 'not archived in a preceding run', run_value=bad)
    expect_rejected('work after an incomplete worker', 'work continued after an incomplete worker',
                    workers={'dev-1.json': stalled, 'dev-2.json': completed})
    expect_rejected('blocked worker in a goal_met run', 'requires exit_reason worker_blocked', workers={'dev-1.json': stalled})
    bad = copy.deepcopy(run); bad['worker_successions'][0]['successor'] = 'dev-9.json'
    expect_rejected('succession references an unknown worker', 'successor is not an archived worker', run_value=bad)
    bad = copy.deepcopy(run); bad['acceptance'][0]['result'] = 'fail'
    expect_rejected('goal_met with a failing loop acceptance', 'every loop-phase check to pass', run_value=bad)
    bad = copy.deepcopy(run); bad['gate']['status'] = 'fail'
    expect_rejected('goal_met without a held gate', 'requires a held gate', run_value=bad)
    bad = copy.deepcopy(run); bad['gate']['independence'] = SECRET
    expect_rejected('run schema violation does not echo values', '$.gate.independence: value is outside enum', run_value=bad)
    bad = copy.deepcopy(gate); bad['probes'] = []
    expect_rejected('invalid gate result', '$.probes: too few items', gate_value=bad)
    bad = copy.deepcopy(stalled); bad['status'] = 'completed'
    expect_rejected('worker semantics violation', 'completed worker has non-completed termination', workers={'dev-1.json': bad})
    outside = inputs / 'outside.txt'
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_bytes(evidence.read_bytes())
    bad = copy.deepcopy(completed); bad['artifacts'][0]['path'] = bad['checks'][0]['artifact_path'] = str(outside)
    expect_rejected('artifact outside staging', 'no --staging directory contains', workers={'dev-2.json': bad})
    expect_rejected('artifacts without a staging directory', 'no --staging directory contains', staging_dirs=[])
    expect_rejected('staging directory contains the archive', 'contains the run archive', staging_dirs=[agent], extra=['--delete-staging'])
    twins = [write_json(inputs / 'dev-1.json', stalled), write_json(inputs / 'dev-2.json', completed),
             write_json(inputs / 'other' / 'dev-2.json', completed)]
    expect_rejected('duplicate worker basenames', 'duplicate worker basename', worker_paths=twins)
    blocker = runs / '.003.partial'
    blocker.mkdir()
    expect_rejected('pre-existing partial directory', '.003.partial already exists')
    assert blocker.is_dir(), 'a partial directory the command did not create was removed'
    blocker.rmdir()

    # 4. Goal rules apply only to goal_met: a capped run may keep failing loop checks.
    capped = copy.deepcopy(run)
    capped.update(exit_reason='iteration_cap', gate={'status': 'fail', 'snapshot': gate['snapshot'], 'independence': 'strict'})
    capped['acceptance'][0]['result'] = 'fail'
    capped['oracles'][0]['strength'] = {'historical': 3, 'rediscovered': 1}
    result = archive(run_value=capped)
    assert result.returncode == 0, result.stderr
    assert listing() == ['001', '002', '003'], listing()
    assert not any(name.endswith('.partial') for name in listing())

    # 5. A stalled worker ends its run fail-closed as worker_blocked.
    blocked_run = {
        'goal': 'Preserve ISO dates', 'spec_path': 'docs/feature-x/IA.md', 'exit_reason': 'worker_blocked',
        'blind_mode': 'strict', 'relaxation': {'authorized': False, 'reason': None, 'authorization': None},
        'iterations': [], 'acceptance': [], 'worker_files': [], 'gate_files': [],
        'gate': {'status': 'not_run', 'snapshot': None, 'independence': None},
    }
    result = archive(run_value=blocked_run, workers={'dev-1.json': stalled})
    assert result.returncode == 0, result.stderr
    assert listing() == ['001', '002', '003', '004'], listing()
    assert json.loads((runs / '004/run.json').read_text(encoding='utf-8'))['worker_files'] == ['workers/dev-1.json']

print(f'PASS archive CLI: 4 archived runs and {rejected} rejection cases')
