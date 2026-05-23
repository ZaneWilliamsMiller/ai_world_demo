# 迭代2：氛围注入 + 动态奇遇 + 奇遇-对话桥接

**日期**：2026-05-13
**融入技术**：SITS2026「感知代理→向量记忆」架构 + 2026 AI动态叙事引擎 + ai-paracosm Multi-Agent叙事生成

## AI调研发现

### 1. SITS2026 AIAgent架构（CSDN DeepNest）
四层耦合：感知代理 → 向量记忆 → LLM推理 → 动作桥接器
- NPC具备目标导向的自主演化能力，决策从玩家交互流中持续生成
- 向量记忆库（FAISS+增量LoRA）存储角色经历、关系图谱与情感权重
- 动作桥接器将自然语言动作映射至游戏行为节点
- 记忆演进型跨会话长时记忆 + 关系动态建模，检索延迟 < 890ms

### 2. SITS2026 Narrative Fusion Core
- 文本/语音/图像同步解析，200ms内生成带情感张力的跨媒体故事片段
- 企业通过REST API注入业务数据流触发动态叙事

### 3. StoryWeaver-2.0（MIT Media Lab + 腾讯AI Lab）
- 角色一致性建模 + 跨媒介情节对齐 + 伦理约束引擎
- 超越单次生成，支持迭代协作叙事

### 4. 长期叙事记忆最佳实践
- 最佳工具能跨会话追踪角色、次要情节和世界规则
- 持久故事记忆是AI叙事系统的核心竞争力

## 落地方案

### 核心架构：奇遇-对话桥接（Encounter-Dialogue Bridge）

**问题**：动态奇遇系统（迭代2基础）生成叙事碎片后只存在于事件流/风闻中，NPC无法自然感知和提及。

**解法**：当动态奇遇触发时，将感知记忆注入同地图所有NPC的记忆流，实现SITS2026「感知代理→向量记忆」的去中心化叙事记忆网络。

```
玩家移动 → should_trigger_encounter() → generate_dynamic_encounter() → apply_encounter()
    ↓                                                                    ↓
事件流 + 风闻                                              NPC记忆流感知注入
    ↓                                                                    ↓
前端天意/风闻气泡 ←────────────────────────────────────→ 后续对话中自然提及
```

### 关键设计决策

1. **NPC性格差异化记忆**：
   - 风闻子(jiang)：importance=7.0（"这等事哪能逃过我的耳目"）
   - 夜行NPC(hei/jianfei/shuizu)：夜间importance=5.5（"夜里的事我门儿清"）
   - 同势力NPC：场景含势力关键词时+1.5
   - 其他NPC：importance=4.0（"似乎有点什么动静"）

2. **NPC视角的感知记忆**：
   - 不是"玩家看到了什么"，而是"我隐约察觉到一些动静"
   - 记忆文本以「方才在{地图名}，我隐约察觉到一些动静：{场景}」格式
   - 保留暗示信息（或许...）

3. **对话注入的克制性**：
   - `format_encounter_perception_block()` 只取最近2小时的感知记忆
   - 不是每次都提及——只在记忆较新且较重要时才注入
   - 语气是「隐约察觉」，不是「全知全能」
   - 提示NPC「提及时不必详述，一笔带过即可」

4. **触发概率平衡**：
   - 基础12%，夜间+5%，恶劣天气+5%，荒野+6%，低心气+4%
   - 6时辰冷却，避免奇遇过频
   - 非战斗类，不锁死玩家

## 改动文件

| 文件 | 类型 | 改动说明 |
|------|------|----------|
| `backend/systems/encounter.py` | 新建 | 动态奇遇系统完整实现 |
| `backend/api/routes.py` | 修改 | /api/move后调用encounter三步流程 |
| `backend/models/player.py` | 修改 | 新增last_dynamic_encounter_tick字段 |
| `static/index.html` | 修改 | 新增#atmosphereText div |
| `static/game.css` | 修改 | .atmosphere-text样式 |
| `static/main.js` | 修改 | 氛围渲染+奇遇气泡+appendLog修复 |
| `backend/services/talk_service.py` | 修改 | 新增奇遇感知注入块 |
| `README.md` | 修改 | 更新日志 |

## 零LLM额外开销

- 奇遇生成：1次LLM调用（temperature=0.92, max_tokens=200），仅在触发时
- 感知记忆注入：纯本地操作，无LLM调用
- 对话注入块：纯启发式，无LLM调用
- 事件流/风闻写入：纯本地操作

## 测试验证

- [x] encounter.py 所有导出可正常import
- [x] talk_service.py 语法验证通过
- [x] PlayerState.npc_positions 字段存在
- [x] NPCS cell字段格式匹配（map_id, x, y）
- [x] format_encounter_perception_block 正确识别「方才在」前缀
