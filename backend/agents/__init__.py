"""NPC 智能体 — 大脑、心智初始化。"""
from backend.agents.brain import (  # noqa: F401
    CROSS_REFLECT_MAX_TARGETS,
    CROSS_REFLECT_MIN_OBS,
    SHICHEN_LIST,
    _deduplicate_observations,
    _plan_deviation_analysis,
    _reflect_sentiment_impact,
    _select_with_recency,
    cross_reflect,
    import_seeds,
    plan_day,
    record_observation,
    reflect,
)
from backend.agents.game_state import (  # noqa: F401
    get_or_init_mind,
)
