"""Regression checks for the live progress recorder (scripts/report_progress.py)."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/report_progress.py'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
spec = importlib.util.spec_from_file_location('contracts', ROOT / 'evals/run_contract_evals.py')
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)
SCHEMA = json.loads((ROOT / 'schemas/progress.schema.json').read_text(encoding='utf-8'))


def run(agent_review, *args):
    return subprocess.run([sys.executable, str(SCRIPT), '--agent-review', str(agent_review), *args],
                          capture_output=True, text=True, env=ENV)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        ar = Path(tmp) / '.agent-review'
        ok = run(ar, '--id', 'work-20261104T051200Z', '--flow', 'work', '--step', 'develop', '--spec', 'docs/specs/a/IA.md', '--note', '배치 1\n구현')
        assert ok.returncode == 0, ok.stderr
        record_path = ar / 'progress' / 'work-20261104T051200Z.json'
        assert Path(ok.stdout.strip()) == record_path
        assert (ar / 'progress' / '.gitignore').read_text(encoding='utf-8').strip().endswith('*')
        for step, extra in (('review', ['--iteration', '1']), ('fix', []), ('review', ['--iteration', '2']), ('gate', []), ('archive', [])):
            assert run(ar, '--id', 'work-20261104T051200Z', '--flow', 'work', '--step', step, *extra).returncode == 0
        done = run(ar, '--id', 'work-20261104T051200Z', '--flow', 'work', '--step', 'archive', '--status', 'done', '--exit-reason', 'goal_met')
        assert done.returncode == 0, done.stderr
        record = json.loads(record_path.read_text(encoding='utf-8'))
        contracts.validate_schema(record, SCHEMA, SCHEMA)
        assert record['status'] == 'done' and record['exit_reason'] == 'goal_met'
        # 반복 번호와 명세 경로는 다음 호출에서 빠져도 이어진다.
        assert record['iteration'] == 2 and record['spec_path'] == 'docs/specs/a/IA.md'
        assert [h['step'] for h in record['history']] == ['develop', 'review', 'fix', 'review', 'gate', 'archive', 'archive']
        assert record['history'][0]['note'] == '배치 1 구현'
        assert not list((ar / 'progress').glob('.*.tmp'))

        draft = run(ar, '--id', 'draft-20261104T050000Z', '--flow', 'draft', '--step', 'interview', '--status', 'waiting_user')
        assert draft.returncode == 0, draft.stderr
        contracts.validate_schema(json.loads((ar / 'progress' / 'draft-20261104T050000Z.json').read_text(encoding='utf-8')), SCHEMA, SCHEMA)

        bad = [
            ['--id', 'x', '--flow', 'work', '--step', 'interview'],
            ['--id', 'x', '--flow', 'draft', '--step', 'design', '--iteration', '1'],
            ['--id', 'x', '--flow', 'work', '--step', 'review', '--iteration', '4'],
            ['--id', '../escape', '--flow', 'work', '--step', 'develop'],
            ['--id', 'x', '--flow', 'work', '--step', 'develop', '--spec', '../IA.md'],
            ['--id', 'x', '--flow', 'work', '--step', 'archive', '--status', 'done', '--exit-reason', 'no_progress'],
            ['--id', 'x', '--flow', 'work', '--step', 'develop', '--exit-reason', 'goal_met'],
            ['--id', 'work-20261104T051200Z', '--flow', 'draft', '--step', 'survey'],
        ]
        for args in bad:
            result = run(ar, *args)
            assert result.returncode != 0, args
        assert not (ar / 'progress' / 'x.json').exists()
        assert not (Path(tmp) / 'escape.json').exists()
    print('progress: ok')


if __name__ == '__main__':
    main()
