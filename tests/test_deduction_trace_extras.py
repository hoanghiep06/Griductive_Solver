"""Test các tính năng mới của DeductionTrace: trạng thái, clear, nạp lại từ JSON, thời gian."""

import json

import pytest

from src.agent.deduction_trace import (
    DeductionStep,
    DeductionTrace,
    SATMetrics,
    TraceStatus,
    build_step,
)


def make_step(index, char="A1", verdict="CRIMINAL", **kw):
    return build_step(
        step_index=index,
        character_id=char,
        verdict=verdict,
        kb_version=index - 1,
        revealed_clues=[{"clue_id": "c1"}],
        sat_metrics_list=[{"decisions": 3, "backtracks": 1, "runtime": 0.002}],
        **kw,
    )


def test_new_trace_is_in_progress():
    trace = DeductionTrace("p", 3)
    assert trace.status is TraceStatus.IN_PROGRESS
    assert not trace.is_finished and not trace.is_solved


@pytest.mark.parametrize("status", [TraceStatus.SOLVED, TraceStatus.STUCK, TraceStatus.INCONSISTENT])
def test_mark_finished_records_status(status):
    trace = DeductionTrace("p", 3)
    trace.mark_finished(status)
    assert trace.status is status
    assert trace.is_finished
    assert trace.to_dict()["status"] == status.value


def test_mark_finished_without_status_keeps_status():
    trace = DeductionTrace("p", 3)
    trace.mark_finished()
    assert trace.is_finished
    assert trace.status is TraceStatus.IN_PROGRESS


def test_mark_finished_accepts_string_and_rejects_garbage():
    trace = DeductionTrace("p", 3)
    trace.mark_finished("SOLVED")
    assert trace.is_solved
    with pytest.raises(ValueError):
        trace.mark_finished("NOT_A_STATUS")


def test_clear_resets_everything_but_identity():
    trace = DeductionTrace("p", 3)
    trace.record(make_step(1))
    trace.mark_finished(TraceStatus.SOLVED)
    trace.clear()
    assert trace.step_count == 0
    assert trace.status is TraceStatus.IN_PROGRESS
    assert not trace.is_finished
    assert trace.puzzle_id == "p"
    trace.record(make_step(1))  # step_index bắt đầu lại từ 1


def test_new_fields_on_step():
    step = make_step(1, newly_revealed_clue_id="c7", elapsed_ms=12.5)
    assert step.newly_revealed_clue_id == "c7"
    assert step.elapsed_ms == 12.5
    d = step.to_dict()
    assert d["newly_revealed_clue_id"] == "c7" and d["elapsed_ms"] == 12.5
    assert "Mở: c7" in step.format_summary()


def test_negative_elapsed_rejected():
    with pytest.raises(ValueError):
        make_step(1, elapsed_ms=-1)


def test_total_elapsed():
    trace = DeductionTrace("p", 3)
    trace.record(make_step(1, elapsed_ms=10))
    trace.record(make_step(2, char="A2", verdict="INNOCENT", elapsed_ms=5.5))
    assert trace.total_elapsed_ms() == pytest.approx(15.5)
    assert trace.to_dict()["total_elapsed_ms"] == pytest.approx(15.5)


def test_json_roundtrip(tmp_path):
    trace = DeductionTrace("puzzle_x", 4)
    trace.record(make_step(1, evidence_clue_ids=["c1"], support_cell_ids=["B2"],
                           newly_revealed_clue_id="c5", elapsed_ms=3.0))
    trace.record(make_step(2, char="A2", verdict="INNOCENT", elapsed_ms=4.0))
    trace.mark_finished(TraceStatus.STUCK)

    path = tmp_path / "trace.json"
    trace.save_json(str(path))
    loaded = DeductionTrace.load_json(str(path))

    assert loaded.to_dict() == trace.to_dict()
    assert loaded.status is TraceStatus.STUCK
    assert loaded.steps[0].support_cell_ids == ("B2",)
    assert loaded.steps[0].minimal_evidence is True
    assert loaded.steps[1].verdict == "INNOCENT"
    assert loaded.total_metrics() == trace.total_metrics()


def test_from_dict_accepts_old_format_without_new_fields():
    old = {
        "puzzle_id": "old",
        "grid_size": 3,
        "start_time": "2026-01-01T00:00:00",
        "end_time": None,
        "steps": [{
            "step_index": 1, "character_id": "A1", "verdict": "CRIMINAL", "kb_version": 0,
            "clue_ids": ["c1"], "explanation": "x",
            "metrics": {"sat_calls": 2, "decisions": 1, "propagations": 0, "backtracks": 0, "runtime_ms": 1.0},
            "timestamp": "2026-01-01T00:00:01",
        }],
    }
    trace = DeductionTrace.from_dict(json.loads(json.dumps(old)))
    step = trace.steps[0]
    assert trace.status is TraceStatus.IN_PROGRESS
    assert step.support_cell_ids == () and step.minimal_evidence is False
    assert step.newly_revealed_clue_id is None and step.elapsed_ms == 0.0
    assert step.metrics == SATMetrics(sat_calls=2, decisions=1, runtime_ms=1.0)


def test_from_dict_rejects_out_of_order_steps():
    data = DeductionTrace("p", 3).to_dict()
    data["steps"] = [make_step(2).to_dict()]
    with pytest.raises(ValueError):
        DeductionTrace.from_dict(data)