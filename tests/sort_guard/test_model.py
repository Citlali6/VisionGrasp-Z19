import pytest

from fpga.sort_guard.host import guard_client as r
from .helpers import IDENTITY, status
from .test_guard_client import setup_guard, feed, CONFIG


def direct_frame(model, sequence, *, box=(20, 30, 39, 49), count=100, flags=3):
    for offset, value in zip(r.FRAME_REGS, (sequence, count, *box, flags, model.job)):
        model.write32(offset, value)
    model.write32(r.COMMAND, r.FRAME_COMMIT)


def test_fixed_anchor_stops_gradual_drift_and_requires_new_segment():
    model, client = setup_guard()
    for seq, shift in ((11, 0), (12, 2), (13, 4)):
        feed(client, seq, box=[20+shift, 30, 39+shift, 49])
    assert model.stable == 0 and not model.ready and model.reason == 5
    for seq in (14, 15, 16):
        feed(client, seq, box=[24, 30, 43, 49])
    assert model.ready and model.stable == 3


def test_roi_area_bounds_and_zero_target_revoke_ready():
    config = r.Config((20, 30, 39, 49), 50, 100, 1, 0, 1000)
    model, client = setup_guard(config=config)
    feed(client, 11, count=50)
    assert model.ready
    feed(client, 12, count=100)
    assert model.ready
    feed(client, 13, count=101)
    assert not model.ready
    feed(client, 14, count=100)
    feed(client, 15, box=[19, 30, 38, 49])
    assert not model.ready
    feed(client, 16, count=100)
    feed(client, 17, count=0, box=[65535, 65535, 0, 0])
    assert not model.ready and model.stable == 0


def test_active_configuration_is_snapshot_not_mutable_staging():
    model, client = setup_guard()
    model.write32(0x060, 1)
    model.write32(0x068, 1)
    feed(client, 11)
    assert model.stable == 1 and not model.ready
    model.advance(100)
    assert model.active and model.config[0x068] == 1000


def test_duplicate_and_invalid_frames_cannot_refresh_age():
    model, _ = setup_guard()
    direct_frame(model, 11)
    model.advance(50)
    direct_frame(model, 11)
    assert model.age == 50 and model.stable == 1
    direct_frame(model, 10)
    assert model.age == 50 and model.stable == 1
    direct_frame(model, 12, flags=1)
    assert model.age == 50 and model.stable == 0
    direct_frame(model, 13, count=0, flags=3)
    assert model.age == 0 and model.stable == 0


def test_timeout_boundary_has_priority_over_frame_and_consume():
    for command in (r.FRAME_COMMIT, r.CONSUME):
        model, _ = setup_guard(config=r.Config((10, 20, 100, 100), 50, 400, 1, 3, 10))
        direct_frame(model, 11)
        model.advance(9)
        assert model.active and model.ready
        with pytest.raises(OSError, match='timeout boundary'):
            model.write32(r.COMMAND, command)
        assert model.timed_out and not model.active and model.age == 10
        assert model.permits == 0
    model, _ = setup_guard()
    model.advance(CONFIG.timeout_cycles)
    assert model.age == CONFIG.timeout_cycles and model.timed_out


def test_busy_cancels_before_command_and_never_auto_resumes():
    model, _ = setup_guard()
    model.set_external_busy(True)
    model.write32(r.COMMAND, r.CANCEL)
    assert not model.active and model.cancelled and model.reason == 8
    model.set_external_busy(False)
    assert not model.active and model.permits == 0
    with pytest.raises(OSError):
        model.write32(r.COMMAND, r.CONSUME)


def test_reset_removes_shadow_configuration_and_permit():
    model, _ = setup_guard()
    direct_frame(model, 11)
    direct_frame(model, 12)
    direct_frame(model, 13)
    model.write32(r.COMMAND, r.CONSUME)
    model.reset()
    assert model.read32(r.STATUS) == 0 and model.read32(r.PERMIT_COUNT) == 0
    assert all(model.read32(offset) == 0 for offset in r.CFG+r.FRAME_REGS)
    with pytest.raises(OSError, match='valid configuration'):
        model.write32(r.COMMAND, r.ARM)


def test_external_busy_survives_reset_and_blocks_arm_until_released():
    model, _ = setup_guard()
    model.set_external_busy(True)
    model.reset()
    assert model.external_busy and model.read32(r.STATUS) == r.EFFECTIVE_BUSY
    assert model.read32(r.PERMIT_COUNT) == 0 and model.read32(r.ACTIVE_JOB) == 0
    client = r.GuardClient(model)
    with pytest.raises(r.GuardError, match='busy'):
        client.initialize()
    assert not client.initialized
    values = (2, 10, 10, 20, 100, 100, 50, 400, 3, 3, 1000)
    for offset, value in zip(r.CFG, values):
        model.write32(offset, value)
    with pytest.raises(OSError, match='busy'):
        model.write32(r.COMMAND, r.ARM)
    assert not model.active and model.permits == 0
    model.set_external_busy(False)
    assert not model.active
    client.recover()
    client.arm(status(), identity=IDENTITY, now=100.1, config=CONFIG, job_id=2)
    assert model.active and model.job == 2 and not model.ready
