"""NPC 人际关系网：态度、旧账、可聊的闲话

设计原则：
- 每个 NPC 只列出「会主动想起/提及」的关系
- attitude 分档：挚交/交好/面上客气/互不招惹/心存芥蒂/势同水火/生意往来/旧交/暧昧线人
- note 用来在对话中自然带出
"""
from typing import Any

NPC_RELATIONSHIPS: dict[str, list[dict[str, Any]]] = {
    "zhanggui": [
        {"target": "yaren", "attitude": "生意往来", "note": "给牙人抽过水，嫌他算盘太精但不敢得罪"},
        {"target": "bullya", "attitude": "面上恭敬", "note": "每月例钱不少，最怕他带班头来查账"},
        {"target": "biaotou", "attitude": "老主顾", "note": "镖局的人住店从不短银，夜里替他留门"},
        {"target": "yulaog", "attitude": "旧交", "note": "年轻时一起走过水货，翻船后各自上岸不提"},
        {"target": "aling", "attitude": "暧昧线人", "note": "让阿泠在画舫听消息，账上不走明路"},
        {"target": "lizheng", "attitude": "互不招惹", "note": "墟上人进城都住同福栈，里正却不亲自来"},
    ],
    "yaren": [
        {"target": "zhanggui", "attitude": "生意往来", "note": "同福栈的掌柜嘴紧，是好主顾；但抽水时从不手软"},
        {"target": "bullya", "attitude": "面上客气", "note": "衙门的人要打点，雷三是最便宜的「门」"},
        {"target": "lizheng", "attitude": "互不招惹", "note": "墟上鱼鳞册的来路不清白，周里正手里有他把柄"},
        {"target": "yizu", "attitude": "交好", "note": "驿卒能带口信，比驿站快三成——走的是私马"},
        {"target": "lika", "attitude": "心存芥蒂", "note": "厘卡抽头太狠，过路的货三成折在哨上"},
    ],
    "bullya": [
        {"target": "zhanggui", "attitude": "面上客气", "note": "同福栈按月交，不啰嗦，比别家省心"},
        {"target": "yaren", "attitude": "互不招惹", "note": "牙人消息灵但嘴巴更大，迟早惹事"},
        {"target": "lizheng", "attitude": "面上客气", "note": "墟上的丁口册子归他管，往来要留三分薄面"},
        {"target": "lika", "attitude": "面上客气", "note": "厘卡和县衙是两条线，管他的吏员与我同属一个班头"},
        {"target": "bangzhang", "attitude": "心存芥蒂", "note": "漕口帮人太横，押人时总要带十几号兄弟"},
    ],
    "biaotou": [
        {"target": "zhanggui", "attitude": "老主顾", "note": "沈掌柜厚道，走镖前后必在同福栈落脚"},
        {"target": "yizu", "attitude": "交好", "note": "驿卒能提前透「绿林帖子」的走向"},
        {"target": "hei", "attitude": "势同水火", "note": "野径黑店截过他一趟红货，至今未了"},
        {"target": "jianfei", "attitude": "势同水火", "note": "剪径匪的绊索废了他一个趟子手"},
        {"target": "shusheng", "attitude": "互不招惹", "note": "书院的人偶尔托镖送密信，不问内容只收钱"},
    ],
    "hei": [
        {"target": "biaotou", "attitude": "心存芥蒂", "note": "赵铁鹰记仇，他那趟红货还在后院地窖"},
        {"target": "jianfei", "attitude": "生意往来", "note": "剪径的给黑店供货——活口、硬货、消息"},
        {"target": "yaren", "attitude": "心存芥蒂", "note": "牙人来路不正的铜器，常往黑店里送"},
        {"target": "bullya", "attitude": "心存芥蒂", "note": "最怕皂隶带了县里缉文来踩盘子"},
        {"target": "jiang", "attitude": "互不招惹", "note": "从不过问风闻子说什么，只要不说出我的店名"},
    ],
    "jianfei": [
        {"target": "hei", "attitude": "生意往来", "note": "黑店老板娘是最大金主，剪的货八成交给她"},
        {"target": "biaotou", "attitude": "势同水火", "note": "镖局的刀太快，折过三个弟兄"},
        {"target": "yulaog", "attitude": "互不招惹", "note": "船家不惹岸上的事，但渡口是他的地盘"},
    ],
    "shuizu": [
        {"target": "yulaog", "attitude": "面上客气", "note": "船家知道水纹深浅，从不戳破我在暗处的动静"},
        {"target": "seng", "attitude": "心存芥蒂", "note": "卧佛寺的和尚偶尔在渡口烧纸驱鬼，碍事"},
    ],
    "yulaog": [
        {"target": "zhanggui", "attitude": "旧交", "note": "同福栈的沈掌柜，年轻时一起走水货翻的船"},
        {"target": "bangzhang", "attitude": "面上客气", "note": "漕口帮掌盘管水面上的规矩，渡口也在他的码头"},
        {"target": "lika", "attitude": "心存芥蒂", "note": "厘卡哨查船不查人——但我船上的人也是货"},
        {"target": "shuizu", "attitude": "互不招惹", "note": "水里有东西，我不说破，它不对我下手"},
    ],
    "aling": [
        {"target": "zhanggui", "attitude": "暧昧线人", "note": "沈掌柜帮我躲过债，我替他听画舫上的风声"},
        {"target": "shusheng", "attitude": "互不招惹", "note": "书院书生来画舫听曲，却不肯在人前承认"},
    ],
    "lizheng": [
        {"target": "yaren", "attitude": "互不招惹", "note": "牙人手里有来路不明的铜器——我知道，但不点破"},
        {"target": "bullya", "attitude": "面上客气", "note": "每年徭役册子交上去，要打点的人里雷三最便宜"},
        {"target": "yizu", "attitude": "交好", "note": "驿卒帮墟上带过逃丁的信，欠他一个人情"},
        {"target": "seng", "attitude": "面上客气", "note": "卧佛寺收过墟上的流民，须得登门致谢"},
    ],
    "yizu": [
        {"target": "yaren", "attitude": "交好", "note": "牙人会透「哪些货正要过站」，换我的私马消息"},
        {"target": "biaotou", "attitude": "交好", "note": "帮镖头绕过绿林帖子最凶的驿站"},
        {"target": "lizheng", "attitude": "交好", "note": "墟上里正欠我一个人情——替他家独子传的家信"},
        {"target": "shusheng", "attitude": "互不招惹", "note": "书院的人写清议帖，驿站传得最快也最怕惹上身"},
    ],
    "seng": [
        {"target": "lizheng", "attitude": "面上客气", "note": "墟上流民在寺外廊下暂住，是里正给的人情"},
        {"target": "shuizu", "attitude": "互不招惹", "note": "渡口的水事不清净，偶尔去烧纸驱一驱"},
    ],
    "bangzhang": [
        {"target": "yulaog", "attitude": "面上客气", "note": "渡口的老艄公懂水，帮里要用人时最先找他"},
        {"target": "lika", "attitude": "生意往来", "note": "厘卡哨的抽头——帮里按月给，单走的不归我管"},
        {"target": "bullya", "attitude": "心存芥蒂", "note": "县衙的皂隶来码头拿人，总要带十几号弟兄才叫得开门"},
    ],
    "shusheng": [
        {"target": "biaotou", "attitude": "互不招惹", "note": "托镖局送过密札——不想让人知道我写的什么"},
        {"target": "yizu", "attitude": "互不招惹", "note": "驿卒传文章快，但他也传消息——不知哪边更近"},
        {"target": "aling", "attitude": "互不招惹", "note": "画舫歌姬的调子里有县衙的案——别人听曲，我听词"},
    ],
    "lika": [
        {"target": "yulaog", "attitude": "心存芥蒂", "note": "船家的船太旧，条条该查——但他从不给抽头"},
        {"target": "bangzhang", "attitude": "生意往来", "note": "漕口帮按月孝敬，是大头；不敢在两卡之间动他的人"},
        {"target": "bullya", "attitude": "面上客气", "note": "衙门的皂隶和厘卡是两条线，井水不犯河水"},
    ],
    "jiang": [
        {"target": "hei", "attitude": "互不招惹", "note": "野店的事我知道——但说出来，酒钱就断了"},
        {"target": "yaren", "attitude": "互不招惹", "note": "牙人的生意七分话，三分谎——和我是一个行当"},
    ],
}


def who_knows(npc_id: str) -> list[dict[str, Any]]:
    """找出所有认识该 NPC 的角色，返回 (knower_id, attitude, note)"""
    out: list[dict[str, Any]] = []
    for knower_id, rels in NPC_RELATIONSHIPS.items():
        for rel in rels:
            if rel["target"] == npc_id:
                out.append({"knower": knower_id, "attitude": rel["attitude"], "note": rel["note"]})
    return out


def relationship_context(npc_id: str) -> str:
    """生成给该 NPC 注入的「人脉心念」文本块"""
    rels = NPC_RELATIONSHIPS.get(npc_id)
    if not rels:
        return ""
    lines = ["【你脑中映出的几张脸（以下人物你可能在对话中自然提起，不必硬塞）】"]
    for r in rels[:6]:
        target_id = r["target"]
        lines.append(f"· {target_id}（{r['attitude']}）：{r['note']}")
    return "\n".join(lines)
