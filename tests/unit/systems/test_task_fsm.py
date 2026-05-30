from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.systems.task_fsm import TaskFSM, TaskState, validate_bounty_fsm


class TestTaskFSMInit:
    def test_default_state_is_available(self):
        fsm = TaskFSM()
        assert fsm.current_state == TaskState.AVAILABLE

    def test_custom_initial_state(self):
        fsm = TaskFSM(initial_state=TaskState.LOCKED)
        assert fsm.current_state == TaskState.LOCKED


class TestCanTransition:
    def test_locked_to_available(self):
        fsm = TaskFSM(initial_state=TaskState.LOCKED)
        assert fsm.can_transition(TaskState.AVAILABLE) is True

    def test_available_to_in_progress(self):
        fsm = TaskFSM(initial_state=TaskState.AVAILABLE)
        assert fsm.can_transition(TaskState.IN_PROGRESS) is True

    def test_in_progress_to_completable(self):
        fsm = TaskFSM(initial_state=TaskState.IN_PROGRESS)
        assert fsm.can_transition(TaskState.COMPLETABLE) is True

    def test_completable_to_completed(self):
        fsm = TaskFSM(initial_state=TaskState.COMPLETABLE)
        assert fsm.can_transition(TaskState.COMPLETED) is True

    def test_any_to_abandoned(self):
        fsm = TaskFSM(initial_state=TaskState.IN_PROGRESS)
        assert fsm.can_transition(TaskState.ABANDONED) is True
        fsm2 = TaskFSM(initial_state=TaskState.COMPLETABLE)
        assert fsm2.can_transition(TaskState.ABANDONED) is True

    def test_locked_to_in_progress_invalid(self):
        fsm = TaskFSM(initial_state=TaskState.LOCKED)
        assert fsm.can_transition(TaskState.IN_PROGRESS) is False

    def test_completed_no_exit(self):
        fsm = TaskFSM(initial_state=TaskState.COMPLETED)
        assert fsm.can_transition(TaskState.AVAILABLE) is False
        assert fsm.can_transition(TaskState.IN_PROGRESS) is False

    def test_abandoned_no_exit(self):
        fsm = TaskFSM(initial_state=TaskState.ABANDONED)
        assert fsm.can_transition(TaskState.AVAILABLE) is False
        assert fsm.can_transition(TaskState.IN_PROGRESS) is False


class TestTransition:
    def test_valid_transition_updates_state(self):
        fsm = TaskFSM(initial_state=TaskState.AVAILABLE)
        fsm.transition(TaskState.IN_PROGRESS)
        assert fsm.current_state == TaskState.IN_PROGRESS

    def test_valid_transition_returns_true(self):
        fsm = TaskFSM(initial_state=TaskState.AVAILABLE)
        assert fsm.transition(TaskState.IN_PROGRESS) is True

    def test_invalid_transition_returns_false(self):
        fsm = TaskFSM(initial_state=TaskState.LOCKED)
        assert fsm.transition(TaskState.IN_PROGRESS) is False

    def test_invalid_transition_keeps_state(self):
        fsm = TaskFSM(initial_state=TaskState.LOCKED)
        fsm.transition(TaskState.IN_PROGRESS)
        assert fsm.current_state == TaskState.LOCKED

    def test_transition_logs_entry(self):
        fsm = TaskFSM(initial_state=TaskState.AVAILABLE)
        fsm.transition(TaskState.IN_PROGRESS)
        assert len(fsm.transition_log) == 1
        entry = fsm.transition_log[0]
        assert entry["from"] == TaskState.AVAILABLE.value
        assert entry["to"] == TaskState.IN_PROGRESS.value
        assert "timestamp" in entry


class TestSubSteps:
    def test_complete_step_marks_completed(self):
        fsm = TaskFSM()
        fsm.sub_steps = [{"key": "step1", "completed": False}]
        fsm.complete_step("step1")
        assert fsm.sub_steps[0]["completed"] is True

    def test_complete_step_adds_to_completed_steps(self):
        fsm = TaskFSM()
        fsm.sub_steps = [{"key": "step1", "completed": False}]
        fsm.complete_step("step1")
        assert "step1" in fsm.completed_steps

    def test_complete_step_unknown_returns_false(self):
        fsm = TaskFSM()
        fsm.sub_steps = [{"key": "step1", "completed": False}]
        assert fsm.complete_step("nonexistent") is False

    def test_complete_step_already_completed_returns_false(self):
        fsm = TaskFSM()
        fsm.sub_steps = [{"key": "step1", "completed": True}]
        assert fsm.complete_step("step1") is False

    def test_all_steps_completed_empty_returns_true(self):
        fsm = TaskFSM()
        assert fsm.all_steps_completed() is True

    def test_all_steps_completed_partial_returns_false(self):
        fsm = TaskFSM()
        fsm.sub_steps = [
            {"key": "step1", "completed": True},
            {"key": "step2", "completed": False},
        ]
        assert fsm.all_steps_completed() is False

    def test_all_steps_completed_all_done_returns_true(self):
        fsm = TaskFSM()
        fsm.sub_steps = [
            {"key": "step1", "completed": True},
            {"key": "step2", "completed": True},
        ]
        assert fsm.all_steps_completed() is True


class TestSerialization:
    def test_to_dict_structure(self):
        fsm = TaskFSM()
        d = fsm.to_dict()
        assert "current_state" in d
        assert "sub_steps" in d
        assert "completed_steps" in d
        assert "transition_log" in d

    def test_from_dict_restores_state(self):
        data = {
            "current_state": "in_progress",
            "sub_steps": [{"key": "s1", "completed": True}],
            "completed_steps": ["s1"],
            "transition_log": [{"from": "available", "to": "in_progress", "timestamp": 0}],
        }
        fsm = TaskFSM.from_dict(data)
        assert fsm.current_state == TaskState.IN_PROGRESS
        assert fsm.sub_steps == [{"key": "s1", "completed": True}]
        assert fsm.completed_steps == ["s1"]
        assert len(fsm.transition_log) == 1

    def test_round_trip(self):
        fsm = TaskFSM(initial_state=TaskState.LOCKED)
        fsm.transition(TaskState.AVAILABLE)
        fsm.transition(TaskState.IN_PROGRESS)
        fsm.sub_steps = [{"key": "s1", "completed": False}]
        fsm.complete_step("s1")
        d = fsm.to_dict()
        fsm2 = TaskFSM.from_dict(d)
        assert fsm2.to_dict() == d


class TestValidateBountyFsm:
    def test_no_task_fsm_returns_empty(self):
        bounty = {"id": "b1"}
        assert validate_bounty_fsm(bounty) == []

    def test_in_progress_without_active_bounty(self):
        bounty = {
            "id": "b1",
            "task_fsm": {"current_state": "in_progress", "sub_steps": [], "completed_steps": [], "transition_log": []},
        }
        violations = validate_bounty_fsm(bounty)
        assert len(violations) == 1
        assert "IN_PROGRESS" in violations[0]

    def test_completable_with_incomplete_steps(self):
        bounty = {
            "id": "b1",
            "active_bounty": True,
            "task_fsm": {
                "current_state": "completable",
                "sub_steps": [{"key": "s1", "completed": False}],
                "completed_steps": [],
                "transition_log": [],
            },
        }
        violations = validate_bounty_fsm(bounty)
        assert len(violations) == 1
        assert "子步骤未全部完成" in violations[0]

    def test_valid_state_no_violations(self):
        bounty = {
            "id": "b1",
            "active_bounty": True,
            "task_fsm": {
                "current_state": "in_progress",
                "sub_steps": [],
                "completed_steps": [],
                "transition_log": [],
            },
        }
        assert validate_bounty_fsm(bounty) == []
