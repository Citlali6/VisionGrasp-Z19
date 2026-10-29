import json
from pathlib import Path

from fpga.sort_guard.host.replay import main, replay

FIXTURE = Path(__file__).parent/'fixtures/synthetic_stable.jsonl'


def test_synthetic_replay_has_one_model_permit_and_no_hardware_claim(capsys):
    assert main([str(FIXTURE)]) == 0
    results = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(results) == 5
    assert all(r['hardware_accessed'] is False and r['evidence_level'] == 'software_model' for r in results)
    assert all(r['synthetic_fixture'] is True for r in results)
    assert results[-1]['result'] == dict(job_id=1, frame_sequence=13, permit_count=1)


def test_replay_stops_at_bad_frame_without_consume():
    events = [json.loads(line) for line in FIXTURE.read_text().splitlines()]
    events[2]['status']['capture_sequence'] = 999
    results, success = replay(events)
    assert not success and len(results) == 3
    assert results[-1]['outcome'] == 'rejected'
    assert all(r.get('op') != 'consume' for r in results)


def test_invalid_file_and_malformed_records_are_reported(tmp_path, capsys):
    assert main([str(tmp_path)]) == 2
    fixture = tmp_path/'bad.jsonl'
    fixture.write_text('{broken JSON', encoding='utf-8')
    assert main([str(fixture)]) == 2
    for line in capsys.readouterr().err.splitlines():
        result = json.loads(line)
        assert result['evidence_level'] == 'software_model' and not result['hardware_accessed']
    results, success = replay([{'op': 'arm'}])
    assert not success and results[0]['outcome'] == 'rejected'
