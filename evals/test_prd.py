"""Regression checks for the PRD.md structure validator (scripts/check_prd.py)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/check_prd.py'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
SECRET = 'sk-live-0123456789abcdef'

CHAPTERS = {
    '무엇인가': '차량별 연료 합계를 돌려주는 API 다.',
    '누가 쓰는가': '운영 담당자가 월별 보고서를 만들 때 쓴다.',
    '어떤 문제를 푸는가': '전에는 차량마다 따로 조회해야 했다.',
    '무엇을 하는가': '- 차량별 합계\n- 빈 차량 목록 처리',
    '어떻게 쓰는가': '`GET /fleet/totals` 를 호출한다.',
    '어떻게 동작하는가': '선박 키로 묶어 한 번에 합산한다 (`src/report.py:42`).',
    '비기능 요구': '해당 없음 — 이번 작업은 성능 경계를 약속하지 않았다.',
    '검증': '| 기준 | 결과 | 근거 |\n|---|---|---|\n| AC-1 | Pass | `pytest -k totals` 종료 코드 0 |\n| AC-2는 | Deferred | 배포 후 확인 |',
    '남은 일': '수용한 경고 1건, `REVIEW.md` 참고.',
    '이 문서의 한계': '배포 환경 성능은 다루지 않았다.',
}


def document(chapters=CHAPTERS, order=None, before='', after=''):
    names = order if order is not None else list(chapters)
    body = ''.join(f'## {name}\n\n{chapters[name]}\n\n' for name in names)
    return f'# 차량별 연료 합계\n\n{before}{body}{after}'


def replaced(name, text):
    value = dict(CHAPTERS)
    value[name] = text
    return document(value)


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp).resolve()
    path = root / 'PRD.md'
    spec = root / 'IA.md'
    spec.write_text('# 작업\n\n## 수용 기준\n\n- AC-1 합계가 같다\n- AC-2 배포 후 응답 시간\n\n```text\nAC-9 예시 안의 번호는 세지 않는다\n```\n', encoding='utf-8')
    legacy_spec = root / 'IA-legacy.md'
    legacy_spec.write_text('# Work\n\n## Acceptance criteria\n\n- totals match\n', encoding='utf-8')
    goal_met = root / 'run-goal.json'
    goal_met.write_text(json.dumps({'exit_reason': 'goal_met'}) + '\n', encoding='utf-8')
    capped = root / 'run-cap.json'
    capped.write_text(json.dumps({'exit_reason': 'iteration_cap'}) + '\n', encoding='utf-8')
    counts = {True: 0, False: 0}

    def check(text, valid, label, reason=None, spec_path=spec, run_json=None):
        path.write_text(text, encoding='utf-8')
        argv = [sys.executable, str(SCRIPT), str(path)]
        if spec_path is not None:
            argv += ['--spec', str(spec_path)]
        if run_json is not None:
            argv += ['--run-json', str(run_json)]
        result = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', env=ENV)
        assert (result.returncode == 0) == valid, (label, result.stdout, result.stderr)
        if valid:
            assert result.stdout.startswith('VALID: product document'), (label, result.stdout)
        else:
            assert result.stderr.startswith('INVALID: '), (label, result.stderr)
            assert reason is None or reason in result.stderr, (label, result.stderr)
            assert SECRET not in result.stderr + result.stdout, label
        counts[valid] += 1
        return result

    # Valid documents.
    check(document(), True, 'valid product document', run_json=goal_met)
    check(document(), True, 'structure only without a spec', spec_path=None)
    check(document(before='```markdown\n## 예시 제목\n```\n\n'), True, 'heading inside a fence is ignored')
    check(replaced('무엇을 하는가', '### 합계\n\n차량별로 합산한다.'), True, 'deeper headings inside a chapter')
    legacy = check(document(), True, 'spec without identifiers skips coverage', spec_path=legacy_spec)
    assert 'coverage not checked' in legacy.stdout, legacy.stdout

    # Chapter structure.
    names = list(CHAPTERS)
    check(document(order=names[:-1]), False, 'missing chapter', '이 문서의 한계')
    check(document(order=[names[1], names[0]] + names[2:]), False, 'chapters out of order', 'required order')
    check(document(order=names + ['남은 일']), False, 'duplicated chapter', 'more than once')
    check(document(after=f'## {SECRET}\n\n추가 장\n'), False, 'extra chapter does not echo its title', 'unexpected ## chapter')
    english = {('What it is' if name == '무엇인가' else name): text for name, text in CHAPTERS.items()}
    check(document(english), False, 'English heading', 'unexpected ## chapter')
    check(replaced('남은 일', ''), False, 'empty chapter', 'empty body')
    check(replaced('비기능 요구', '해당 없음.'), False, 'not applicable without a reason', '해당 없음 without a reason')
    check(replaced('무엇인가', f'A fleet totals API. {SECRET}'), False, 'chapter not in Korean does not echo it', 'not written in Korean')

    # Verification coverage.
    check(replaced('검증', '| 기준 | 결과 |\n|---|---|\n| AC-1 | Pass |'), False, 'criterion not reported', 'does not report: AC-2')
    check(replaced('검증', '| 기준 | 결과 |\n|---|---|\n| AC-1 | Pass |\n| AC-2 | 확인함 |'), False, 'criterion without a result token', 'without Pass, Fail, or Deferred')
    check(replaced('검증', '| 기준 | 결과 |\n|---|---|\n| AC-1 | Pass |\n| AC-2 | Deferred |\n| AC-3 | Pass |'), False, 'unknown criterion', 'does not define: AC-3')
    check(replaced('검증', '| 기준 | 결과 |\n|---|---|\n| AC-1 | Pass |\n```\n| AC-2 | Deferred |\n```'), False, 'criterion only inside a fence', 'does not report: AC-2')
    check(replaced('검증', '| 기준 | 결과 |\n|---|---|\n| AC-1 | Passed |\n| AC-2 | Deferred |'), False, 'result token must stand alone', 'AC-1')

    # Exit binding.
    check(document(), False, 'product document after a non-goal exit', 'only on a goal_met exit', run_json=capped)

print(f'PASS product document CLI: {counts[True]} valid documents and {counts[False]} rejection cases')
