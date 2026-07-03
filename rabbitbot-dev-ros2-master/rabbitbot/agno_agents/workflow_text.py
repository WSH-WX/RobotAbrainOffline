"""语音文本解析（提取称呼/首访判断/空输入检测/姓氏表）。从 workflow.py 拆出，行为不变。"""

import re


COMMON_SURNAMES = [
    "欧阳", "司马", "上官", "诸葛", "东方", "夏侯", "皇甫", "尉迟", "公孙", "司徒",
    "赵", "钱", "孙", "李", "周", "吴", "郑", "王", "冯", "陈", "褚", "卫", "蒋", "沈",
    "韩", "杨", "朱", "秦", "尤", "许", "何", "吕", "施", "张", "孔", "曹", "严", "华",
    "金", "魏", "陶", "姜", "戚", "谢", "邹", "喻", "柏", "水", "窦", "章", "云", "苏",
    "潘", "葛", "奚", "范", "彭", "郎", "鲁", "韦", "昌", "马", "苗", "凤", "花", "方",
    "俞", "任", "袁", "柳", "鲍", "史", "唐", "费", "廉", "岑", "薛", "雷", "贺", "倪",
    "汤", "滕", "殷", "罗", "毕", "郝", "邬", "安", "常", "乐", "于", "时", "傅", "皮",
    "卞", "齐", "康", "伍", "余", "元", "卜", "顾", "孟", "平", "黄", "和", "穆", "萧",
    "尹", "姚", "邵", "湛", "汪", "祁", "毛", "禹", "狄", "米", "贝", "明", "臧", "计",
    "伏", "成", "戴", "宋", "庞", "熊", "纪", "舒", "屈", "项", "祝", "董", "梁", "杜",
    "阮", "蓝", "闵", "席", "季", "麻", "强", "贾", "路", "娄", "危", "江", "童", "颜",
    "郭", "梅", "盛", "林", "刁", "钟", "徐", "邱", "骆", "高", "夏", "蔡", "田", "胡",
    "凌", "霍", "虞", "万", "支", "柯", "昝", "管", "卢", "莫", "经", "房", "裘", "缪",
    "干", "解", "应", "宗", "丁", "宣", "邓", "郁", "单", "杭", "洪", "包", "左", "石",
    "崔", "吉", "龚", "程", "邢", "裴", "陆", "荣", "翁", "荀", "羊", "於", "惠", "甄",
    "曲", "家", "封", "芮", "储", "靳", "汲", "邴", "糜", "松", "井", "段", "富", "巫",
    "乌", "焦", "巴", "弓", "牧", "隗", "山", "谷", "车", "侯", "宓", "蓬", "全", "郗",
    "班", "仰", "秋", "仲", "伊", "宫", "宁", "仇", "栾", "暴", "甘", "钭", "厉", "戎",
    "祖", "武", "符", "刘", "詹", "龙", "叶", "幸", "司", "黎", "白", "蒲", "邰", "赖",
    "卓", "蔺", "屠", "蒙", "池", "乔", "阴", "胥", "能", "苍", "闻", "莘", "党", "翟",
    "谭", "贡", "劳", "逄", "姬", "申", "扶", "堵", "冉", "宰", "郦", "雍", "郤", "璩",
    "桑", "桂", "濮", "牛", "寿", "通", "边", "扈", "燕", "冀", "郏", "浦", "尚", "农",
    "温", "别", "庄", "晏", "柴", "瞿", "阎", "充", "慕", "连", "茹", "习", "宦", "艾",
    "鱼", "容", "向", "古", "易", "慎", "戈", "廖", "庾", "终", "暨", "居", "衡", "步",
    "都", "耿", "满", "弘", "匡", "国", "文", "寇", "广", "禄", "阙", "东", "殴", "利",
    "师", "巩", "聂", "晁", "勾", "敖", "融", "冷", "訾", "辛", "阚", "那", "简", "饶",
    "空", "曾", "毋", "沙", "乜", "养", "鞠", "须", "丰", "巢", "关", "蒯", "相", "查",
    "后", "荆", "红", "游", "竺", "权", "逯", "盖", "益", "桓", "公",
]
def _find_common_surname(value):
    for surname in COMMON_SURNAMES:
        if value.startswith(surname):
            return surname
    return ""
def _extract_leader_calling(text):
    text = (text or "").strip()
    normalized_text = re.sub(r"[\s，。！？?、,.!]+", "", text)
    title_candidates = [
        "副总经理", "总经理", "董事长", "副主任", "负责人", "主任", "书记", "部长",
        "院长", "局长", "处长", "科长", "总监", "经理", "教授", "博士", "副总", "总",
    ]

    title = ""
    for candidate in title_candidates:
        if candidate in normalized_text:
            title = candidate
            break

    surname = ""
    for marker in ["免贵姓", "我姓", "姓", "我叫", "叫", "我是", "本人是"]:
        index = normalized_text.find(marker)
        if index < 0:
            continue
        surname = _find_common_surname(normalized_text[index + len(marker):])
        if surname:
            break

    if not surname:
        title_pattern = "|".join(re.escape(candidate) for candidate in title_candidates)
        match = re.search(r"([\u4e00-\u9fff]{1,2})(?:" + title_pattern + r")", normalized_text)
        if match:
            surname = _find_common_surname(match.group(1))

    if surname and title:
        return f"{surname}{title}"
    if surname:
        return f"{surname}领导"
    if title:
        return f"{title}"
    return "领导"
def _parse_first_visit_answer(text):
    normalized_text = re.sub(r"[\s，。！？?、,.!]+", "", text or "")
    if normalized_text == "":
        return "unknown"

    repeat_keywords = [
        "不是第一次", "不止一次", "以前来过", "之前来过", "已经来过", "我来过",
        "来过很多次", "来过好多次", "来过几次", "来过多次", "来过一次", "来过",
        "很多次", "好多次", "好几次", "几次了", "多次", "经常来", "常来",
        "第二次", "第三次", "第四次", "第2次", "第3次", "第4次",
        "不是", "不",
    ]
    first_keywords = [
        "第一次", "首次", "头一次", "初次", "第一回来", "头回来", "刚来", "第一次来",
        "没来过", "没有来过", "从没来过", "从来没来过", "没到过", "没去过", "是第一次",
    ]
    yes_words = {"是", "是的", "对", "对的", "没错", "嗯", "嗯嗯"}
    no_words = {"不是", "不是的", "不", "不对", "没有"}

    # 先判断“非第一次”，避免“不是第一次”被“第一次”误判为 first。
    if any(keyword in normalized_text for keyword in repeat_keywords) or normalized_text in no_words:
        return "repeat"
    if any(keyword in normalized_text for keyword in first_keywords) or normalized_text in yes_words:
        return "first"
    return "unknown"
def _is_empty_stt_text(text):
    return text is None or text.strip() in {"", "<REC_TIMEOUT>", "<REC_STOP>", "Timeout"}
