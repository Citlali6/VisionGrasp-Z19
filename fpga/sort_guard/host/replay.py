"""Replay JSONL records into a software model. Never connects to hardware."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .guard_client import GuardClient, Config, GuardError
from .model import SoftwareGuard
from .validation import StreamIdentity, ValidationError


def replay(events):
    model, results = SoftwareGuard(), []
    client = GuardClient(model)
    client.initialize()
    for index, event in enumerate(events, 1):
        result = dict(index=index, evidence_level='software_model', hardware_accessed=False)
        try:
            if type(event) is not dict:
                raise ValidationError('record must be a JSON object')
            op = event.get('op')
            result.update(op=op, synthetic_fixture=event.get('synthetic_fixture') is True)
            if op in ('arm', 'frame', 'consume'):
                identity = StreamIdentity(**event['identity'])
                args = dict(status=event['status'], identity=identity, now=event['producer_now'])
                if op == 'arm':
                    value = client.arm(**args, config=Config(**event['config']), job_id=event['job_id'])
                elif op == 'frame':
                    value = client.feed(**args)
                else:
                    value = asdict(client.consume(**args))
                result['result'] = value
            elif op == 'advance':
                model.advance(event['cycles'])
                result['age_cycles'] = model.age
            elif op == 'busy':
                client.set_busy(event['value'])
            elif op == 'cancel':
                client.cancel()
            elif op == 'reset':
                model.reset()
                client.initialize()
            else:
                raise ValidationError('unknown replay operation')
            result['outcome'] = 'accepted'
        except (GuardError, ValidationError, KeyError, TypeError, ValueError, OSError) as exc:
            result.update(outcome='rejected', error=str(exc))
            results.append(result)
            return results, False
        results.append(result)
    return results, True


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline JSONL replay into a software register model; no hardware access')
    parser.add_argument('fixture', type=Path)
    args = parser.parse_args(argv)
    try:
        if not args.fixture.is_file() or args.fixture.stat().st_size > 4*1024*1024:
            raise ValidationError('input must be a regular JSONL file of at most 4 MiB')
        lines = args.fixture.read_text(encoding='utf-8').splitlines()
        events = [json.loads(line) for line in lines if line.strip()]
        if not events:
            raise ValidationError('empty replay')
        results, success = replay(events)
        for result in results:
            print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0 if success else 2
    except (OSError, ValueError) as exc:
        print(json.dumps(dict(evidence_level='software_model', hardware_accessed=False,
                              outcome='rejected', error=str(exc)), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
