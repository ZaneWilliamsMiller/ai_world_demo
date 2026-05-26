from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

class StateUpdate(BaseModel):
    order: int = Field(0, ge=-3, le=3, description="秩序变化")
    truth: int = Field(0, ge=-3, le=3, description="求真变化")
    hope: int = Field(0, ge=-3, le=3, description="希望变化")
    chaos: int = Field(0, ge=-3, le=3, description="混乱变化")

class RepDelta(BaseModel):
    yamen: int = Field(0, ge=-2, le=2, description="衙门声望变化")
    biaoju: int = Field(0, ge=-2, le=2, description="镖局声望变化")
    caobang: int = Field(0, ge=-2, le=2, description="漕帮声望变化")
    shuyuan: int = Field(0, ge=-2, le=2, description="书院声望变化")
    lulin: int = Field(0, ge=-2, le=2, description="绿林声望变化")

class NpcResponseSchema(BaseModel):
    """NPC 对话回复与状态变更"""
    visible_text: str = Field(..., description="NPC 对玩家说的话（展示给玩家的正文），包含动作和神态描写。")
    favor_delta: int = Field(0, ge=-3, le=3, description="对眼前这位旅客态度的起伏")
    coin_delta: int = Field(0, ge=-200, le=200, description="玩家随身制钱的真实增减（赚到/付出/被讹/赏赐都用这一行写实数；无变化则 0)")
    items_gain: list[str] = Field(default_factory=list, description="玩家实际得到的信物/凭证/线索（每项≤8字）")
    items_lose: list[str] = Field(default_factory=list, description="玩家被夺/消耗/弃置之物（每项≤8字）")
    rep_delta: Optional[RepDelta] = Field(None, description="玩家在各势力的声望涨跌")
    events: list[str] = Field(default_factory=list, description="一句话江湖事件（≤40字），你叙述里真正发生或别处正在发生的事")
    permadeath: Optional[str] = Field(None, description="死因简述（仅真实江湖且确该死时填写）")
    state_update: Optional[StateUpdate] = Field(None, description="玩家气质四维的变化")
    vigor_delta: int = Field(0, ge=-60, le=60, description="玩家体力变化：奔走、打斗、伤口、酒色淘空都减；歇脚、温食、按摩、安寝都加。")
    spirit_delta: int = Field(0, ge=-60, le=60, description="玩家心气变化：恐惧、屈辱、丧友、被讹都减；得手、舒怀、贵人示好、雅事悟道都加。")
    escape_outcome: Optional[str] = Field(
        None,
        description=(
            "若玩家此前身陷险局（move_locked），本轮的脱困结果："
            "'success' 全身脱困；'progress' 暂占上风但未脱；'fail' 周旋失败仍困其中；"
            "正常对话或非险局时务必为 null。"
        ),
    )
    enslaved: Optional[str] = Field(
        None,
        description="若你判定本轮玩家因脱困失败而沦为囚徒/苦役/质押（不致死但失自由），写一句缘由；否则 null。",
    )
