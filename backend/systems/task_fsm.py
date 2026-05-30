"""任务状态机（FSM）— 轻量级有限状态机

管理悬赏任务的生命周期：
LOCKED → AVAILABLE → IN_PROGRESS → COMPLETABLE → COMPLETED
                                   ↘ ABANDONED
"""

from __future__ import annotations

import time
from enum import Enum


class TaskState(str, Enum):  # noqa: UP042
    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    COMPLETABLE = "completable"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.LOCKED: {TaskState.AVAILABLE},
    TaskState.AVAILABLE: {TaskState.IN_PROGRESS, TaskState.LOCKED},
    TaskState.IN_PROGRESS: {TaskState.COMPLETABLE, TaskState.ABANDONED},
    TaskState.COMPLETABLE: {TaskState.COMPLETED, TaskState.ABANDONED},
    TaskState.COMPLETED: set(),
    TaskState.ABANDONED: set(),
}


class TaskFSM:
    """轻量级任务状态机。"""

    __slots__ = (
        "_state",
        "completed_steps",
        "sub_steps",
        "transition_log",
    )

    def __init__(self, initial_state: TaskState = TaskState.AVAILABLE):
        self._state = initial_state
        self.sub_steps: list[dict] = []
        self.completed_steps: list[str] = []
        self.transition_log: list[dict] = []

    @property
    def current_state(self) -> TaskState:
        return self._state

    def can_transition(self, target: TaskState) -> bool:
        return target in _TRANSITIONS.get(self._state, set())

    def transition(self, target: TaskState) -> bool:
        if not self.can_transition(target):
            return False
        from_state = self._state
        self._state = target
        self.transition_log.append({
            "from": from_state.value,
            "to": target.value,
            "timestamp": time.time(),
        })
        return True

    def complete_step(self, step_key: str) -> bool:
        for step in self.sub_steps:
            if step["key"] == step_key and not step["completed"]:
                step["completed"] = True
                if step_key not in self.completed_steps:
                    self.completed_steps.append(step_key)
                return True
        return False

    def all_steps_completed(self) -> bool:
        if not self.sub_steps:
            return True
        return all(step["completed"] for step in self.sub_steps)

    def to_dict(self) -> dict:
        return {
            "current_state": self._state.value,
            "sub_steps": list(self.sub_steps),
            "completed_steps": list(self.completed_steps),
            "transition_log": list(self.transition_log),
        }

    @classmethod
    def from_dict(cls, data: dict) -> TaskFSM:
        fsm = cls(initial_state=TaskState(data["current_state"]))
        fsm.sub_steps = list(data.get("sub_steps", []))
        fsm.completed_steps = list(data.get("completed_steps", []))
        fsm.transition_log = list(data.get("transition_log", []))
        return fsm


def validate_bounty_fsm(bounty: dict) -> list[str]:
    """校验悬赏 FSM 状态是否合法，返回违规列表。"""
    violations: list[str] = []
    task_fsm_data = bounty.get("task_fsm")
    if not task_fsm_data:
        return violations

    fsm = TaskFSM.from_dict(task_fsm_data) if isinstance(task_fsm_data, dict) else task_fsm_data
    state = fsm.current_state

    if state == TaskState.IN_PROGRESS and not bounty.get("active_bounty"):
        violations.append(f"悬赏 {bounty.get('id', '?')} 状态为 IN_PROGRESS 但缺少 active_bounty")

    if state == TaskState.COMPLETABLE and fsm.sub_steps and not fsm.all_steps_completed():
        violations.append(f"悬赏 {bounty.get('id', '?')} 状态为 COMPLETABLE 但子步骤未全部完成")

    return violations
