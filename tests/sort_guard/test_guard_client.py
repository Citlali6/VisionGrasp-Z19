import pytest

from fpga.sort_guard.host import guard_client as r
from fpga.sort_guard.host.model import SoftwareGuard
from fpga.sort_guard.host.validation import StreamIdentity, ValidationError
from .helpers import IDENTITY, status

CONFIG = r.Config((10, 20, 100, 100), 50, 400, 3, 3, 1000)


def setup_guard(sequence=10, config=CONFIG):
    model = SoftwareGuard()
    client = r.GuardClient(model)
    client.initialize()
    client.arm(status(sequence), identity=IDENTITY, now=100.1, config=config, job_id=1)
    return model, client


def feed(client, sequence, **kwargs):
    value = status(sequence, stamp=100.+sequence/100., **kwargs)
    return value, client.feed(value, identity=IDENTITY, now=value['published_monotonic']+.1)


def ready():
    model, client = setup_guard()
    for seq in (11, 12, 13):
        value, result = feed(client, seq)
    assert result['status'] & r.READY
    return model, client, value


def test_constructor_never_accesses_transport_and_identity_checked_first():
    class NoIO:
        def read32(self, offset):
            raise AssertionError('constructor must not read')
        def write32(self, offset, value):
            raise AssertionError('constructor must not write')
    r.GuardClient(NoIO())
    model = SoftwareGuard()
    model.read32 = lambda offset: 0
    with pytest.raises(r.GuardError, match='ID/version'):
        r.GuardClient(model).initialize()
    assert not model.writes


@pytest.mark.parametrize('failed_offset', [r.ID, r.VERSION])
@pytest.mark.parametrize('method', ['initialize', 'recover'])
def test_unidentified_device_read_failure_never_causes_any_write(failed_offset, method):
    model = SoftwareGuard()
    read = model.read32
    def failing(offset):
        if offset == failed_offset:
            raise OSError('unidentified endpoint')
        return read(offset)
    model.read32 = failing
    client = r.GuardClient(model)
    with pytest.raises(r.TransportError):
        getattr(client, method)()
    assert model.writes == []
    with pytest.raises(r.GuardError, match='identity'):
        client.cancel()
    assert model.writes == []


def test_recovery_does_not_reuse_previous_identity_on_failed_probe():
    model, client = setup_guard()
    model.writes.clear()
    def fail(_offset):
        raise OSError('transport remapped')
    model.read32 = fail
    with pytest.raises(r.TransportError):
        client.recover()
    assert model.writes == []


def test_arm_snapshots_baseline_and_full_config_without_committing_old_frame():
    model, client = setup_guard()
    assert model.writes == list(zip(r.CFG, (1, 10, 10, 20, 100, 100, 50, 400, 3, 3, 1000)))+[(r.COMMAND, r.ARM)]
    assert model.sequence == 10 and model.stable == 0 and not model.ready
    with pytest.raises(r.GuardError, match='local task already active'):
        client.arm(status(), identity=IDENTITY, now=100.1, config=CONFIG, job_id=2)


def test_frame_shadow_commit_and_single_consume_acknowledgement():
    model, client, value = ready()
    commands = [v for offset, v in model.writes if offset == r.COMMAND]
    assert commands == [r.ARM, r.FRAME_COMMIT, r.FRAME_COMMIT, r.FRAME_COMMIT]
    assert model.shadow[0x098] == 3 and model.shadow[0x09c] == 1
    permit = client.consume(value, identity=IDENTITY, now=100.3)
    assert permit == r.Permit(job_id=1, frame_sequence=13, permit_count=1)
    with pytest.raises(r.GuardError, match='no local armed task'):
        client.consume(value, identity=IDENTITY, now=100.3)
    assert model.permits == 1


@pytest.mark.parametrize('config', [
    r.Config((0, 0, 640, 359), 1, 100, 3, 1, 100),
    r.Config((20, 0, 10, 100), 1, 100, 3, 1, 100),
    r.Config((0, 0, 100, 100), 0, 100, 3, 1, 100),
    r.Config((0, 0, 100, 100), 100, 99, 3, 1, 100),
    r.Config((0, 0, 100, 100), 1, 100, 0, 1, 100),
    r.Config((0, 0, 100, 100), 1, 100, 3, 1, 0),
])
def test_invalid_configuration_never_writes(config):
    model, client = SoftwareGuard(), None
    client = r.GuardClient(model)
    client.initialize()
    with pytest.raises(ValidationError):
        client.arm(status(), identity=IDENTITY, now=100.1, config=config, job_id=1)
    assert model.writes == []


@pytest.mark.parametrize('sequence', [10, 9, 10+2**31])
def test_duplicate_reversed_and_ambiguous_sequence_cancel_task(sequence):
    model, client = setup_guard()
    with pytest.raises(r.GuardError, match='duplicate, reversed or reset'):
        client.feed(status(sequence, stamp=100.2), identity=IDENTITY, now=100.3)
    assert not model.active and not model.ready and model.permits == 0


def test_serial_wrap_and_skipped_capture_sequences_are_supported():
    model, client = setup_guard(sequence=0xfffffffe)
    for seq, stamp in ((0xffffffff, 100.2), (0, 100.4), (3, 100.6)):
        result = client.feed(status(seq, stamp=stamp), identity=IDENTITY, now=stamp+.1)
    assert result['status'] & r.READY and model.sequence == 3


@pytest.mark.parametrize('change', ['session', 'camera', 'request', 'geometry', 'reset'])
def test_changed_binding_or_hardware_reset_requires_new_arm(change):
    model, client = setup_guard()
    value, identity = status(11, stamp=100.2), IDENTITY
    if change == 'session':
        identity = StreamIdentity(IDENTITY.camera_id, 'session-2')
    elif change == 'camera':
        identity = StreamIdentity('other-camera', IDENTITY.session_id)
    elif change == 'request':
        value['request_id'] += 1
        value['request']['request_id'] += 1
        value['target']['request_id'] += 1
    elif change == 'geometry':
        value['width'] += 1
    else:
        model.reset()
    with pytest.raises(r.GuardError):
        client.feed(value, identity=identity, now=100.3)
    assert not model.active and model.permits == 0


def test_invalid_input_and_stale_consumption_revoke_existing_ready():
    model, client, value = ready()
    with pytest.raises(ValidationError, match='stale'):
        client.consume(value, identity=IDENTITY, now=103.)
    assert not model.ready and model.permits == 0
    model, client, value = ready()
    value['pl_sequence'] -= 1
    with pytest.raises(ValidationError):
        client.feed(value, identity=IDENTITY, now=100.3)
    assert not model.ready and model.permits == 0


def test_partial_frame_io_failure_never_commits_and_requires_recovery():
    model, client = setup_guard()
    original = model.write32
    failed = []
    def write(offset, value):
        if offset == 0x08c and not failed:
            failed.append(True)
            raise OSError('injected bus failure')
        original(offset, value)
    model.write32 = write
    with pytest.raises(r.TransportError):
        feed(client, 11)
    assert (r.COMMAND, r.FRAME_COMMIT) not in model.writes
    assert not client.initialized and not model.active and model.permits == 0
    client.recover()
    client.arm(status(11, stamp=100.2), identity=IDENTITY, now=100.3, config=CONFIG, job_id=2)
    assert model.active and model.job == 2


def test_read_error_and_unacknowledged_consume_never_return_a_permit():
    model, client, value = ready()
    read = model.read32
    model.read32 = lambda offset: True if offset == r.STATUS else read(offset)
    with pytest.raises(r.TransportError):
        client.consume(value, identity=IDENTITY, now=100.3)
    assert not client.initialized and model.permits == 0
    model, client, value = ready()
    write = model.write32
    model.write32 = lambda offset, value: None if (offset, value) == (r.COMMAND, r.CONSUME) else write(offset, value)
    with pytest.raises(r.GuardError, match='acknowledgement'):
        client.consume(value, identity=IDENTITY, now=100.3)
    assert not client.initialized and not model.active


def test_busy_cancels_and_job_ids_cannot_be_reused():
    model, client = setup_guard()
    client.set_busy(True)
    assert not model.active and model.cancelled and client.job_id is None
    client.set_busy(False)
    with pytest.raises(r.GuardError, match='cannot be reused'):
        client.arm(status(), identity=IDENTITY, now=100.1, config=CONFIG, job_id=1)
    client.arm(status(), identity=IDENTITY, now=100.1, config=CONFIG, job_id=2)
    assert model.job == 2 and model.stable == 0


def test_timeout_and_counter_wrap_have_explicit_evidence():
    model, client, value = ready()
    model.advance(CONFIG.timeout_cycles)
    with pytest.raises(r.GuardError, match='not ready'):
        client.consume(value, identity=IDENTITY, now=100.3)
    assert model.timed_out and model.permits == 0
    model, client, value = ready()
    model.permits = 0xffffffff
    permit = client.consume(value, identity=IDENTITY, now=100.3)
    assert permit.permit_count == 0 and model.consumed


def test_uncommitted_new_observation_cannot_consume_old_ready():
    model, client, value = ready()
    with pytest.raises(r.GuardError, match='exact last committed'):
        client.consume(status(14, stamp=100.2), identity=IDENTITY, now=100.3)
    assert model.permits == 0 and not model.active
