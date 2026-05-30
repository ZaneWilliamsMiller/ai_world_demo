from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.systems.task_fsm import _TRANSITIONS, TaskFSM, TaskState
from hypothesis import given, settings

from tests.unit.property.strategies import st_task_state

ALL_STATES = set(TaskState)


@settings(max_examples=50)
@given(st_task_state())
def test_valid_state_is_in_legal_set(initial):
    fsm = TaskFSM(initial_state=initial)
    assert fsm.current_state in ALL_STATES


@settings(max_examples=50)
@given(st_task_state())
def test_available_only_to_in_progress_or_locked(target):
    fsm = TaskFSM(initial_state=TaskState.AVAILABLE)
    allowed = _TRANSITIONS[TaskState.AVAILABLE]
    if target not in allowed:
        assert fsm.transition(target) is False
        assert fsm.current_state == TaskState.AVAILABLE


@settings(max_examples=50)
@given(st_task_state())
def test_accepted_to_completed_or_abandoned(target):
    fsm = TaskFSM(initial_state=TaskState.IN_PROGRESS)
    allowed = _TRANSITIONS[TaskState.IN_PROGRESS]
    if target not in allowed:
        assert fsm.transition(target) is False
        assert fsm.current_state == TaskState.IN_PROGRESS


@settings(max_examples=50)
@given(st_task_state(), st_task_state())
def test_any_transition_stays_in_legal_set(initial, target):
    fsm = TaskFSM(initial_state=initial)
    fsm.transition(target)
    assert fsm.current_state in ALL_STATES


@settings(max_examples=50)
@given(st_task_state())
def test_terminal_states_no_exit(state):
    if state not in (TaskState.COMPLETED, TaskState.ABANDONED):
        return
    fsm = TaskFSM(initial_state=state)
    for target in TaskState:
        assert fsm.can_transition(target) is False


@settings(max_examples=50)
@given(st_task_state(), st_task_state())
def test_invalid_transition_preserves_state(initial, target):
    fsm = TaskFSM(initial_state=initial)
    allowed = _TRANSITIONS.get(initial, set())
    if target in allowed:
        return
    result = fsm.transition(target)
    assert result is False
    assert fsm.current_state == initial
