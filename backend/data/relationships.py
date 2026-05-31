from __future__ import annotations

"""NPC 人际关系网：态度、旧账、可聊的闲话

设计原则：
- 每个 NPC 只列出「会主动想起/提及」的关系
- attitude 分档：挚交/交好/面上客气/互不招惹/心存芥蒂/势同水火/生意往来/旧交/暧昧线人
- note 用来在对话中自然带出
"""
from typing import Any

NPC_RELATIONSHIPS: dict[str, list[dict[str, Any]]] = {
    "zhanggui": [
        {"target": "yaren", "attitude": "生意往来", "note": "给牙人抽过水,嫌他算盘太精但不敢得罪"},
        {"target": "bullya", "attitude": "面上恭敬", "note": "每月例钱不少,最怕他带班头来查账"},
        {"target": "biaotou", "attitude": "老主顾", "note": "镖局的人住店从不短银,夜里替他留门"},
        {"target": "yulaog", "attitude": "旧交", "note": "年轻时一起走过水货,翻船后各自上岸不提"},
        {"target": "aling", "attitude": "暧昧线人", "note": "让阿泠在画舫听消息,账上不走明路"},
        {"target": "lizheng", "attitude": "互不招惹", "note": "墟上人进城都住同福栈,里正却不亲自来"},
        {"target": "xuanzhen", "attitude": "生意往来", "note": "那道人的草药我收,不问来路——反正客人也分不清真假"},
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
        {"target": "zhanggui", "attitude": "老主顾", "note": "沈掌柜厚道,走镖前后必在同福栈落脚"},
        {"target": "yizu", "attitude": "交好", "note": "驿卒能提前透「绿林帖子」的走向"},
        {"target": "hei", "attitude": "势同水火", "note": "野径黑店截过他一趟红货,至今未了"},
        {"target": "jianfei", "attitude": "势同水火", "note": "剪径匪的绊索废了他一个趟子手"},
        {"target": "shusheng", "attitude": "互不招惹", "note": "书院的人偶尔托镖送密信,不问内容只收钱"},
        {"target": "tiegu", "attitude": "互不招惹", "note": "猎户替镖局探过绿林动静,靠得住——但不愿入伙"},
    ],
    "hei": [
        {"target": "biaotou", "attitude": "心存芥蒂", "note": "赵铁鹰记仇,他那趟红货还在后院地窖"},
        {"target": "jianfei", "attitude": "生意往来", "note": "剪径的给黑店供货——活口、硬货、消息"},
        {"target": "yaren", "attitude": "心存芥蒂", "note": "牙人来路不正的铜器,常往黑店里送"},
        {"target": "bullya", "attitude": "心存芥蒂", "note": "最怕皂隶带了县里缉文来踩盘子"},
        {"target": "jiang", "attitude": "互不招惹", "note": "从不过问风闻子说什么,只要不说出我的店名"},
        {"target": "jintang", "attitude": "生意往来", "note": "赌徒在店里摆局,我抽一成——他招客,我收租"},
    ],
    "jianfei": [
        {"target": "hei", "attitude": "生意往来", "note": "黑店老板娘是最大金主,剪的货八成交给她"},
        {"target": "biaotou", "attitude": "势同水火", "note": "镖局的刀太快,折过三个弟兄"},
        {"target": "yulaog", "attitude": "互不招惹", "note": "船家不惹岸上的事,但渡口是他的地盘"},
        {"target": "tiegu", "attitude": "心存芥蒂", "note": "猎户的猎径被我们占了当伏击点,他不满但也不敢怎样"},
    ],
    "shuizu": [
        {"target": "yulaog", "attitude": "面上客气", "note": "船家知道水纹深浅，从不戳破我在暗处的动静"},
        {"target": "seng", "attitude": "心存芥蒂", "note": "卧佛寺的和尚偶尔在渡口烧纸驱鬼，碍事"},
    ],
    "yulaog": [
        {"target": "zhanggui", "attitude": "旧交", "note": "同福栈的沈掌柜,年轻时一起走水货翻的船"},
        {"target": "bangzhang", "attitude": "面上客气", "note": "漕口帮掌盘管水面上的规矩,渡口也在他的码头"},
        {"target": "lika", "attitude": "心存芥蒂", "note": "厘卡哨查船不查人——但我船上的人也是货"},
        {"target": "shuizu", "attitude": "互不招惹", "note": "水里有东西,我不说破,它不对我下手"},
        {"target": "jintang", "attitude": "互不招惹", "note": "赌徒让我替他捎口信,不赌钱——算半个熟人"},
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
        {"target": "lizheng", "attitude": "面上客气", "note": "墟上流民在寺外廊下暂住,是里正给的人情"},
        {"target": "shuizu", "attitude": "互不招惹", "note": "渡口的水事不清净,偶尔去烧纸驱一驱"},
        {"target": "xuanzhen", "attitude": "面上客气", "note": "那道人在寺外廊下摆过药摊,香客常被他截走——但不好撕破脸"},
        {"target": "tiegu", "attitude": "面上客气", "note": "猎户来寺里歇过脚,给过热粥——山里人讲义气"},
    ],
    "bangzhang": [
        {"target": "yulaog", "attitude": "面上客气", "note": "渡口的老艄公懂水,帮里要用人时最先找他"},
        {"target": "lika", "attitude": "生意往来", "note": "厘卡哨的抽头——帮里按月给,单走的不归我管"},
        {"target": "bullya", "attitude": "心存芥蒂", "note": "县衙的皂隶来码头拿人,总要带十几号弟兄才叫得开门"},
        {"target": "jintang", "attitude": "互不招惹", "note": "赌徒在帮坞附近摆过局,赢了帮里弟兄的钱——暂且记着"},
    ],
    "shusheng": [
        {"target": "biaotou", "attitude": "互不招惹", "note": "托镖局送过密札——不想让人知道我写的什么"},
        {"target": "yizu", "attitude": "互不招惹", "note": "驿卒传文章快,但他也传消息——不知哪边更近"},
        {"target": "aling", "attitude": "互不招惹", "note": "画舫歌姬的调子里有县衙的案——别人听曲,我听词"},
        {"target": "xuanzhen", "attitude": "互不招惹", "note": "那道人炼丹卖药,我写策论——他嫌我迂,我嫌他野"},
    ],
    "lika": [
        {"target": "yulaog", "attitude": "心存芥蒂", "note": "船家的船太旧，条条该查——但他从不给抽头"},
        {"target": "bangzhang", "attitude": "生意往来", "note": "漕口帮按月孝敬，是大头；不敢在两卡之间动他的人"},
        {"target": "bullya", "attitude": "面上客气", "note": "衙门的皂隶和厘卡是两条线，井水不犯河水"},
    ],
    "jiang": [
        {"target": "hei", "attitude": "互不招惹", "note": "野店的事我知道——但说出来,酒钱就断了"},
        {"target": "yaren", "attitude": "互不招惹", "note": "牙人的生意七分话,三分谎——和我是一个行当"},
        {"target": "xuanzhen", "attitude": "互不招惹", "note": "那道人卖假丹的事,我装不知道——他也从不拆我的台"},
        {"target": "jintang", "attitude": "互不招惹", "note": "赌徒的骰子和我嘴里的故事一样——半真半假"},
    ],
    "xuanzhen": [
        {"target": "seng", "attitude": "面上客气", "note": "寺里和尚烧纸驱鬼,我炼丹求长生——井水不犯河水,但香客是同一批"},
        {"target": "shusheng", "attitude": "互不招惹", "note": "书生写策论,我炼丹方——他嫌我旁门左道,我嫌他纸上谈兵"},
        {"target": "zhanggui", "attitude": "生意往来", "note": "同福栈的掌柜收我的草药,不问来路——好主顾"},
    ],
    "tiegu": [
        {"target": "biaotou", "attitude": "互不招惹", "note": "镖局走官道,我走猎径——偶尔替他们探过绿林的动静"},
        {"target": "jianfei", "attitude": "心存芥蒂", "note": "剪径匪占了我常走的猎径当伏击点,搅得兽都跑了"},
        {"target": "seng", "attitude": "面上客气", "note": "寺外廊下歇过脚,和尚给过一碗热粥——记着这份情"},
    ],
    "jintang": [
        {"target": "hei", "attitude": "生意往来", "note": "黑店角落里摆赌局,老板娘抽一成——规矩我懂"},
        {"target": "bangzhang", "attitude": "互不招惹", "note": "漕口帮的人赌钱从不赖账,但赢了他们的钱也不安生"},
        {"target": "yulaog", "attitude": "互不招惹", "note": "渡头老艄公不赌,但替我捎过口信——算半个熟人"},
    ],
    "niangzi": [
        {"target": "xuanzhen", "attitude": "生意往来", "note": "那道人也卖药，抢了我不少客，但偶尔也从他那进些稀罕药材"},
        {"target": "zhanggui", "attitude": "生意往来", "note": "同福栈的伤药都是我供的，掌柜按月结账不拖欠"},
        {"target": "bullya", "attitude": "心存芥蒂", "note": "皂隶总来查我私售的虎狼药，得打点着"},
    ],
    "xiaofan": [
        {"target": "yaren", "attitude": "互不招惹", "note": "牙人看不起走街串巷的，但我的消息比他还快"},
        {"target": "lika", "attitude": "心存芥蒂", "note": "厘卡的吏员追着我收税，恨不得把我赶出县境"},
        {"target": "lizheng", "attitude": "面上客气", "note": "墟上里正偶尔托我带东西，不好得罪"},
        {"target": "zhanggui", "attitude": "生意往来", "note": "同福栈的掌柜偶尔从我这进些小物件"},
    ],
    "laogeng": [
        {"target": "bullya", "attitude": "面上客气", "note": "皂隶夜里巡逻，更夫打更，井水不犯河水"},
        {"target": "hei", "attitude": "互不招惹", "note": "野径那家店夜里动静大，我装没听见"},
        {"target": "jianfei", "attitude": "心存芥蒂", "note": "芦荡里夜里有人出没，撞见过一回，吓得我三天没敢走那条路"},
    ],
    "cuiwei": [
        {"target": "aling", "attitude": "旧交", "note": "阿泠比我小几岁，刚来画舫时是我照应的"},
        {"target": "zhanggui", "attitude": "面上客气", "note": "掌柜偶尔来喝茶，出手大方但不惹事"},
        {"target": "bangzhang", "attitude": "心存芥蒂", "note": "漕口帮的人来闹过场，老鸨都不敢吭声"},
    ],
    "tiejiang": [
        {"target": "biaotou", "attitude": "生意往来", "note": "镖局的刀剑都是我修的，赵铁鹰识货"},
        {"target": "bullya", "attitude": "心存芥蒂", "note": "衙门要征我去打兵器，能推就推"},
        {"target": "zhanggui", "attitude": "生意往来", "note": "同福栈的灶具铁器都是我打的"},
    ],
    "mianfen": [
        {"target": "lizheng", "attitude": "面上客气", "note": "墟上里正是老主顾，吃面从不给钱但也不找麻烦"},
        {"target": "zhanggui", "attitude": "互不招惹", "note": "城里掌柜看不上墟口的面摊，但他的伙计常来"},
        {"target": "yaren", "attitude": "互不招惹", "note": "牙人来吃面总想赊账，我可不惯着"},
        {"target": "bullya", "attitude": "心存芥蒂", "note": "官差来白吃面，敢怒不敢言"},
    ],
    "shuishi": [
        {"target": "bangzhang", "attitude": "面上客气", "note": "帮掌管着码头上的一切，不敢不听"},
        {"target": "yulaog", "attitude": "交好", "note": "渔老七是码头上少有的好人，偶尔帮我挡帮里的差事"},
        {"target": "lika", "attitude": "心存芥蒂", "note": "厘卡查船时，总是我们这些小水手被盘问"},
    ],
    "buzhuang": [
        {"target": "yaren", "attitude": "生意往来", "note": "牙人帮我进过几批布，抽头狠但货还算实在"},
        {"target": "bullya", "attitude": "心存芥蒂", "note": "皂隶总来「巡查」，分明是觊觎家产"},
        {"target": "zhanggui", "attitude": "互不招惹", "note": "同福栈的掌柜跟我一样做正经生意，互不掺和"},
    ],
    "youmin": [
        {"target": "lizheng", "attitude": "面上客气", "note": "里正管着鱼鳞册，我能不能留下来全看他"},
        {"target": "seng", "attitude": "交好", "note": "卧佛寺的和尚给过粥和草棚，是这县里头一个善人"},
        {"target": "bullya", "attitude": "心存芥蒂", "note": "皂隶总想把我们赶出县境，得躲着走"},
        {"target": "jianfei", "attitude": "互不招惹", "note": "芦荡里的匪人招我入伙，我没敢答应也没敢告发"},
    ],
    "nvdao": [
        {"target": "xuanzhen", "attitude": "旧交", "note": "玄真子是旧识，当年一起在茅山修过道，后来各走各路"},
        {"target": "seng", "attitude": "面上客气", "note": "寺里的和尚不待见道士，但面上还过得去"},
        {"target": "shusheng", "attitude": "互不招惹", "note": "书院的人嫌我旁门左道，我嫌他们酸腐"},
    ],
    "puocha": [
        {"target": "bullya", "attitude": "面上客气", "note": "雷三是皂隶，比我高一级，得罪不起"},
        {"target": "yaren", "attitude": "生意往来", "note": "牙人给我的好处不少，帮他递话通风"},
        {"target": "lizheng", "attitude": "互不招惹", "note": "墟上的里正偶尔托我递条子，给点跑腿费"},
        {"target": "lika", "attitude": "互不招惹", "note": "厘卡的吏员和我同在衙门混饭吃，井水不犯河水"},
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
    from backend.data.npcs_data import NPCS
    rels = NPC_RELATIONSHIPS.get(npc_id)
    if not rels:
        return ""
    lines = ["【你脑中映出的几张脸（以下人物你可能在对话中自然提起，不必硬塞）】"]
    for r in rels[:6]:
        target_id = r["target"]
        target_name = NPCS.get(target_id, {}).get("short", target_id)
        lines.append(f"· {target_name}（{r['attitude']}）：{r['note']}")
    return "\n".join(lines)
