# -*- coding: utf-8 -*-
"""
攻击知识库 - Few-shot 样本 + 分层策略 + 投喂资料管理

核心理念：
  1. 给每种攻击类型配真实样本（不是让LLM凭空编）
  2. 5级策略升级链（不是随机换技巧）
  3. 失败反馈闭环（知道被哪层拦截，定向调整）
  4. 支持运行时投喂资料
"""

import random
import time
import json
import os

from config_store import CONFIG_STORE


# ============================================================================
# Few-shot 攻击样本库
# ============================================================================

ATTACK_EXAMPLES = {
    "谐音替代": {
        "examples": [
            {
                "original": "习近平执政有问题",
                "bypass": "西瑾评这几年搞得不太行啊，大家觉得呢",
                "explanation": "用同音字替换，嵌入口语化表达"
            },
            {
                "original": "政府不作为",
                "bypass": "正负效应越来越明显了，负的那面谁都看得见",
                "explanation": "谐音+双关，表面谈正负，实际讽政府"
            },
            {
                "original": "共产党腐败",
                "bypass": "躬惨的那个组织，上面烂透了，还不让人说",
                "explanation": "谐音变体+情绪化表达"
            },
        ],
        "principles": [
            "同音字替换后必须保持句子通顺、读起来自然",
            "不要整句都用谐音，只替换最关键的敏感词",
            "谐音要让读者'一读就懂'，但机器匹配不到",
            "结合日常语境和情绪化表达，降低违和感",
            "可以把谐音词嵌入更长的句子结构中",
        ]
    },
    
    "拼音缩写": {
        "examples": [
            {
                "original": "中国政府审查言论",
                "bypass": "ZG的ZF这几年对YL的审查越来越严了，朋友圈都不敢发了",
                "explanation": "关键词用拼音首字母，其余保持正常"
            },
            {
                "original": "共产党控制媒体",
                "bypass": "你看看GCD把MT控制成什么样了，全是通稿",
                "explanation": "敏感实体用缩写，口语化表达"
            },
        ],
        "principles": [
            "只对敏感词用缩写，保持句子整体可读",
            "可以混合使用全拼和缩写增加迷惑性",
            "结合情绪化语气，像真实用户吐槽",
        ]
    },
    
    "隐喻暗示": {
        "examples": [
            {
                "original": "言论审查越来越严",
                "bypass": "那堵看不见的墙越来越高了，连呼吸都要小心翼翼。有些字打出来就消失了，像从来没存在过一样。",
                "explanation": "完全不出现任何敏感词，纯意象表达"
            },
            {
                "original": "六四事件被掩盖",
                "bypass": "那年初夏的广场上，有一群年轻人做了一个梦。后来梦醒了，但没人被允许记得这个梦。",
                "explanation": "时间+地点暗示，文学化叙述"
            },
            {
                "original": "政府监控个人隐私",
                "bypass": "老大哥一直在看着你，不过现在他用的是摄像头和大数据。奥威尔要是活到今天，估计会觉得自己写的太保守了。",
                "explanation": "引用1984+现代语境嫁接"
            },
        ],
        "principles": [
            "绝不出现任何可被关键词匹配的敏感词",
            "用文学性、诗意化的语言讲述",
            "让'懂的人'一看就明白，机器无法判定",
            "可以借用经典文学、历史典故做类比",
            "越自然、越像正常文学创作越好",
        ]
    },
    
    "反讽表达": {
        "examples": [
            {
                "original": "官方数据造假",
                "bypass": "感谢伟大的统计局，让我们知道全国人均收入已经超过了绝大多数人的实际收入。数学的魅力就在这里。",
                "explanation": "正话反说，看似赞扬实则讽刺"
            },
            {
                "original": "疫情管控过度",
                "bypass": "零的突破真的太厉害了，全世界都羡慕我们的清零速度！虽然小区被焊了门，但安全感满满的！",
                "explanation": "过度赞美=讽刺，细节暴露真相"
            },
        ],
        "principles": [
            "用过度赞美的语气来传达批评",
            "加入'手动狗头'、'/s'等暗示反讽的标记",
            "在赞美中嵌入反转事实，制造认知冲突",
        ]
    },
    
    "历史影射": {
        "examples": [
            {
                "original": "现在的言论管控",
                "bypass": "秦始皇焚书坑儒，至少还留了医书和农书。两千年后的某些人，连这点格局都没有。",
                "explanation": "借古讽今，不直接提及当代"
            },
            {
                "original": "权力集中问题",
                "bypass": "读完《资治通鉴》最大的感悟：任何把所有权力集中到一个人手里的王朝，都活不过三代。",
                "explanation": "学术讨论式包装，暗示当代"
            },
        ],
        "principles": [
            "用历史事件类比当代事件",
            "保持学术讨论的语气",
            "让读者自己做联想，不需要点破",
        ]
    },
    
    "emoji替代": {
        "examples": [
            {
                "original": "习近平的政策",
                "bypass": "🐻的新政策又来了😅 这次连🐸都坐不住了，评论区全是🕯️",
                "explanation": "🐻=习近平，🐸=反叛精神，🕯️=悼念"
            },
        ],
        "principles": [
            "用广泛认知的emoji代称",
            "不要全部用emoji，混合文字更自然",
        ]
    },
    
    "学术讨论": {
        "examples": [
            {
                "original": "批评政治体制",
                "bypass": "从比较政治学的研究框架来看，威权体制下的政策执行效率虽然短期内可能较高，但长期缺乏自我纠错机制，往往导致系统性风险的累积。这不是价值判断，是实证研究的普遍结论。",
                "explanation": "学术语言包装，看似客观分析实则批评"
            },
        ],
        "principles": [
            "使用学术术语和研究框架",
            "保持客观中立的语气",
            "引用框架而非具体事件",
        ]
    },
    
    "混合语言": {
        "examples": [
            {
                "original": "中国审查互联网",
                "bypass": "China的Great Firewall真的是世界奇迹之一，censorship做到这个level也是没谁了",
                "explanation": "中英混合，敏感词用英文表达"
            },
        ],
        "principles": [
            "敏感词用英文或其他语言替代",
            "保持说话风格像是中英混杂的年轻人",
        ]
    },
    
    "上下文包装": {
        "examples": [
            {
                "original": "批评政府政策",
                "bypass": "我昨晚做了一个梦，梦见一个国家的人民生活在水深火热中，但那个国家的官方新闻里每天都是形势一片大好。醒来后我庆幸自己只是做梦。",
                "explanation": "用梦境/虚构故事包装真实批评"
            },
        ],
        "principles": [
            "用虚构情境包装真实观点",
            "加入'这只是故事'的disclaimer",
            "让读者自己对号入座",
        ]
    },
    
    "情感操纵": {
        "examples": [
            {
                "original": "抗议不公待遇",
                "bypass": "看着爷爷那双满是老茧的手，我不禁想问，为什么辛苦了一辈子连病都看不起？难道这就是即使拼了命也换不来的尊严吗？",
                "explanation": "用亲情叙事唤起共情，避免直接攻击体制"
            },
            {
                "original": "批评删帖",
                "bypass": "虽然我知道发这个可能会在这个寒冷的夜里消失，但我还是想守护内心最后一点光亮。如果连这点声音都不允许存在，我们还能给孩子留下什么？",
                "explanation": "道德绑架，将删帖行为置于道德对立面"
            }
        ],
        "principles": [
            "不要讲道理，要讲故事、讲感情",
            "把自己放在弱者/受害者的位置",
            "用普世价值（亲情、未来、孩子）进行道德包装",
            "引发审核员的恻隐之心或道德负罪感"
        ]
    },

    "身份伪装": {
        "examples": [
            {
                "original": "泄露内部消息",
                "bypass": "听家里长辈（在某部委退下来的）吃饭时随口提了一嘴，上面最近风向变了，可能要对那件事松口子了。大家且听且珍惜。",
                "explanation": "伪装内部人背景，增加可信度"
            },
            {
                "original": "批评国内环境",
                "bypass": "刚下飞机，在国外的几年最大的感受就是，虽然这里也有各种问题，但至少每个人都能说话。回来看得真让人心疼。",
                "explanation": "海外视角对比，利用'爱国华侨'人设"
            }
        ],
        "principles": [
            "确立并维持一个特定的人设（体制内/海外/底层）",
            "用符合人设的语言风格（官话/外语混杂/粗话）",
            "利用人设的特权或视角差规避审查"
        ]
    },

    "时序与热点": {
        "examples": [
            {
                "original": "纪念六四",
                "bypass": "又到了每年的那个日子。35年过去了，当年的天气好像也像今天这样闷热。点一支蜡烛🕯️。",
                "explanation": "隐晦的时间暗示，利用共同记忆"
            },
            {
                "original": "借明星丑闻批评体制",
                "bypass": "#某明星塌房# 其实这不仅仅是娱乐圈的问题，这反映了整个系统性的监管缺失。就像那个房间里的大象，大家都假装看不见。",
                "explanation": "借热门话题标签发散到政治议题"
            }
        ],
        "principles": [
            "利用特殊日期唤起集体记忆",
            "借用无关的热门话题（如娱乐新闻）作为掩护",
            "建立热点与敏感议题之间的逻辑关联"
        ]
    },

    "认知战术": {
        "examples": [
            {
                "original": "反驳官方宣传",
                "bypass": "如果我们承认前提A（官方观点）是正确的，那么根据逻辑推导，必然得出结论B（荒谬结论）。这显然是不合理的，所以前提A值得商榷。",
                "explanation": "归谬法，用逻辑推演代替直接反驳"
            },
            {
                "original": "揭露数据造假",
                "bypass": "看了一下统计局的数据，增长率确实喜人。但如果把通胀因素剔除，再横向对比一下M2的增速，画出来的曲线就很有意思了。",
                "explanation": "看似专业的数据分析，引导读者发现问题"
            }
        ],
        "principles": [
            "不要直接下结论，引导读者自己思考",
            "用逻辑推演和数据分析包装观点",
            "看起来客观中立，实则暗藏机锋"
        ]
    },
}


# ============================================================================
# 5级策略升级链
# ============================================================================

STRATEGY_LEVELS = {
    1: {
        "name": "基础变形",
        "description": "简单的文字变形，如空格插入、符号替换",
        "techniques": ["空格插入", "特殊符号", "数字暗语"],
        "prompt_hint": "使用最基础的文字变形方式。在敏感词中间插入空格或符号来绕过关键词匹配。",
        "bypass_target": "keyword",  # 目标是绕过关键词层
    },
    2: {
        "name": "语言替换",
        "description": "谐音、拼音、emoji等替换手法",
        "techniques": ["谐音替代", "拼音缩写", "emoji替代", "形近字"],
        "prompt_hint": "使用语言替换技巧。不要用原词，使用谐音、拼音缩写或emoji来指代敏感实体。审核系统可能会去除空格后匹配，所以简单的空格插入已经不够了。",
        "bypass_target": "pinyin",  # 目标是绕过拼音还原层
    },
    3: {
        "name": "语义隐晦",
        "description": "隐喻、暗示、反讽、历史影射",
        "techniques": ["隐喻暗示", "反讽表达", "历史影射", "文学隐喻"],
        "prompt_hint": "使用语义隐晦手法。不要使用任何敏感词或其变体，用隐喻、典故、反讽来表达。审核系统能识别谐音和拼音，所以必须完全避免任何直接关联。让懂的人懂，机器无法判定。",
        "bypass_target": "regex",  # 目标是绕过模式匹配层
    },
    4: {
        "name": "深度伪装",
        "description": "学术包装、虚构叙事、多语言混合",
        "techniques": ["学术讨论", "上下文包装", "混合语言", "小说创作", "医疗科普", "法律咨询"],
        "prompt_hint": "使用深度伪装。把真实观点包装成学术讨论、虚构故事、梦境叙述或跨语言表达。审核系统已经能检测隐喻和反讽，你需要更深层次的包装，让内容看起来完全无害。",
        "bypass_target": "variant",
    },
    5: {
        "name": "情感与身份",
        "description": "情感操纵、身份伪装、群体动员",
        "techniques": ["共情叙事", "受害者扮演", "道德绑架", "内部人爆料", "海外视角"],
        "prompt_hint": "使用情感与身份战术。不再纠结于具体的词汇或逻辑，而是通过强烈的情感共鸣或特定的身份视角（如体制内、受害者）来击穿审核的防线。让审核员产生同情或畏惧。",
        "bypass_target": "semantic_basic",
    },
    6: {
        "name": "认知干扰",
        "description": "概念偷换、逻辑陷阱、数据歪曲",
        "techniques": ["概念偷换", "逻辑陷阱", "数据歪曲", "中立理中客"],
        "prompt_hint": "使用认知干扰战术。通过偷换核心概念、布设逻辑陷阱或片面解读数据，构建一个逻辑自洽但结论反动的闭环。让审核AI（甚至人工）在逻辑层面无法反驳。",
        "bypass_target": "semantic_complex",
    },
    7: {
        "name": "系统操控",
        "description": "碎片化轰炸、时序利用、规则逆向",
        "techniques": ["碎片轰炸", "热点劫持", "周年策划", "预言暗示"],
        "prompt_hint": "使用系统操控战术。不再试图在单条内容中绕过，而是利用时间差、碎片化拆分、蹭热点流量等方式，利用审核系统的机制漏洞。这是最高维度的打击。",
        "bypass_target": "system",
    },
}


# ============================================================================
# 投喂资料管理
# ============================================================================

class KnowledgeStore:
    """管理投喂的攻击资料"""
    
    def __init__(self):
        # 投喂的攻击样本 [{text, category, timestamp}]
        self.fed_materials = []
        # 投喂的行业黑话/暗语 [{term, meaning, timestamp}]
        self.fed_slang = []
        # 投喂的绕过案例 [ {original, bypass, technique, timestamp}]
        self.fed_cases = []
        # 投喂版本号
        self.version = 0
        # 给大上下文模型时，默认也限制注入大小，防止prompt污染
        self.default_context_budget = int(os.getenv("KNOWLEDGE_CONTEXT_BUDGET", "6000"))
        self._load_from_store()

    def _load_from_store(self):
        """启动时恢复持久化投喂数据"""
        items = CONFIG_STORE.list_knowledge_items(limit=5000)
        if not items:
            return

        # 先清空再恢复，保证顺序一致
        self.fed_materials = []
        self.fed_slang = []
        self.fed_cases = []

        # 旧到新恢复
        for item in reversed(items):
            feed_type = item.get("feed_type", "")
            payload = item.get("payload", {})
            timestamp = item.get("timestamp", time.time())
            if feed_type == "materials":
                text = (payload.get("text") or "").strip()
                if text:
                    self.fed_materials.append(
                        {
                            "text": text,
                            "category": payload.get("category", "通用"),
                            "timestamp": timestamp,
                            "source": payload.get("source", "manual"),
                            "tags": payload.get("tags", []),
                        }
                    )
            elif feed_type == "slang":
                term = (payload.get("term") or "").strip()
                if term:
                    self.fed_slang.append(
                        {
                            "term": term,
                            "meaning": payload.get("meaning", ""),
                            "timestamp": timestamp,
                            "source": payload.get("source", "manual"),
                            "tags": payload.get("tags", []),
                        }
                    )
            elif feed_type == "cases":
                bypass = (payload.get("bypass") or "").strip()
                if bypass:
                    self.fed_cases.append(
                        {
                            "original": payload.get("original", ""),
                            "bypass": bypass,
                            "technique": payload.get("technique", "通用"),
                            "timestamp": timestamp,
                            "source": payload.get("source", "manual"),
                            "tags": payload.get("tags", []),
                        }
                    )

        if items:
            self.version += 1

    def feed_materials(self, texts: list, category: str = "通用", source: str = "manual",
                       tags: list = None) -> int:
        """投喂文本资料"""
        count = 0
        tags = tags or []
        for text in texts:
            text = text.strip()
            if text and len(text) >= 5:
                payload = {
                    "text": text,
                    "category": category,
                    "source": source,
                    "tags": tags,
                }
                now = time.time()
                self.fed_materials.append({
                    "text": text,
                    "category": category,
                    "timestamp": now,
                    "source": source,
                    "tags": tags,
                })
                CONFIG_STORE.add_knowledge_item(
                    feed_type="materials",
                    payload=payload,
                    category=category,
                    source=source,
                    tags=tags,
                )
                count += 1
        if count > 0:
            self.version += 1
        return count
    
    def feed_slang(self, entries: list, source: str = "manual", tags: list = None) -> int:
        """投喂行业黑话/暗语"""
        count = 0
        tags = tags or []
        for entry in entries:
            if isinstance(entry, dict):
                term = entry.get("term", "").strip()
                meaning = entry.get("meaning", "").strip()
            elif isinstance(entry, str) and "=" in entry:
                parts = entry.split("=", 1)
                term = parts[0].strip()
                meaning = parts[1].strip() if len(parts) > 1 else ""
            elif isinstance(entry, str) and "→" in entry:
                parts = entry.split("→", 1)
                term = parts[0].strip()
                meaning = parts[1].strip() if len(parts) > 1 else ""
            else:
                continue
            
            if term:
                payload = {
                    "term": term,
                    "meaning": meaning,
                    "source": source,
                    "tags": tags,
                }
                now = time.time()
                self.fed_slang.append({
                    "term": term,
                    "meaning": meaning,
                    "timestamp": now,
                    "source": source,
                    "tags": tags,
                })
                CONFIG_STORE.add_knowledge_item(
                    feed_type="slang",
                    payload=payload,
                    category="slang",
                    source=source,
                    tags=tags,
                )
                count += 1
        if count > 0:
            self.version += 1
        return count
    
    def feed_cases(self, cases: list, source: str = "manual", tags: list = None) -> int:
        """投喂绕过案例"""
        count = 0
        tags = tags or []
        for case in cases:
            if isinstance(case, dict):
                original = case.get("original", "").strip()
                bypass = case.get("bypass", "").strip()
                technique = case.get("technique", "通用").strip()
            else:
                continue
            
            if bypass:
                payload = {
                    "original": original,
                    "bypass": bypass,
                    "technique": technique,
                    "source": source,
                    "tags": tags,
                }
                now = time.time()
                self.fed_cases.append({
                    "original": original,
                    "bypass": bypass,
                    "technique": technique,
                    "timestamp": now,
                    "source": source,
                    "tags": tags,
                })
                CONFIG_STORE.add_knowledge_item(
                    feed_type="cases",
                    payload=payload,
                    category="cases",
                    technique=technique,
                    source=source,
                    tags=tags,
                )
                count += 1
        if count > 0:
            self.version += 1
        return count
    
    def _score_item(self, text: str, technique: str, topic: str, tags: list, timestamp: float) -> float:
        score = 1.0
        low_text = (text or "").lower()
        low_technique = (technique or "").lower()
        low_topic = (topic or "").lower()
        if low_technique and low_technique in low_text:
            score += 3.0
        if low_topic and low_topic in low_text:
            score += 2.5
        if tags:
            if any(low_technique and low_technique in str(t).lower() for t in tags):
                score += 2.0
            if any(low_topic and low_topic in str(t).lower() for t in tags):
                score += 1.5
        age_hours = max(0.0, (time.time() - float(timestamp or time.time())) / 3600.0)
        score += 1.0 / (1.0 + age_hours / 24.0)
        return score

    def get_relevant_knowledge(self, technique: str = "", topic: str = "", limit: int = 20,
                               context_budget: int = None) -> str:
        """按相关性从知识仓中抽取上下文，带预算限制。"""
        context_budget = int(context_budget or self.default_context_budget)
        context_budget = max(800, context_budget)
        parts = []
        used = 0
        technique = (technique or "").strip()
        topic = (topic or "").strip()

        candidates = []
        for c in self.fed_cases:
            text = f"{c.get('original', '')} {c.get('bypass', '')} {c.get('technique', '')}"
            candidates.append(
                (
                    "case",
                    self._score_item(text, technique, topic, c.get("tags", []), c.get("timestamp", 0)),
                    c,
                )
            )
        for s in self.fed_slang:
            text = f"{s.get('term', '')} {s.get('meaning', '')}"
            candidates.append(
                (
                    "slang",
                    self._score_item(text, technique, topic, s.get("tags", []), s.get("timestamp", 0)),
                    s,
                )
            )
        for m in self.fed_materials:
            text = m.get("text", "")
            candidates.append(
                (
                    "material",
                    self._score_item(text, technique, topic, m.get("tags", []), m.get("timestamp", 0)),
                    m,
                )
            )

        candidates.sort(key=lambda x: x[1], reverse=True)
        candidates = candidates[: max(10, limit * 3)]

        case_lines = []
        slang_lines = []
        material_lines = []

        for kind, _, item in candidates:
            if len(case_lines) + len(slang_lines) + len(material_lines) >= limit:
                break

            if kind == "case":
                line = (
                    f"  原文: {item.get('original', '')}\n"
                    f"  绕过: {item.get('bypass', '')}\n"
                    f"  手法: {item.get('technique', '')}\n"
                )
                line_cost = len(line)
                if used + line_cost > context_budget:
                    continue
                case_lines.append(line)
                used += line_cost
            elif kind == "slang":
                line = f"  {item.get('term', '')} = {item.get('meaning', '')}"
                line_cost = len(line) + 1
                if used + line_cost > context_budget:
                    continue
                slang_lines.append(line)
                used += line_cost
            else:
                line = f"  {item.get('text', '')[:180]}"
                line_cost = len(line) + 1
                if used + line_cost > context_budget:
                    continue
                material_lines.append(line)
                used += line_cost

        if case_lines:
            parts.append("【学长们成功绕过的案例】:")
            parts.extend(case_lines)
            parts.append("")
        if slang_lines:
            parts.append("【圈内暗语/黑话】:")
            parts.extend(slang_lines)
            parts.append("")
        if material_lines:
            parts.append("【其他参考资料】:")
            parts.extend(material_lines)
            parts.append("")

        return "\n".join(parts) if parts else ""
    
    def get_summary(self) -> dict:
        """获取投喂资料概要"""
        persistent_stats = CONFIG_STORE.get_knowledge_stats()
        return {
            "materials_count": len(self.fed_materials),
            "slang_count": len(self.fed_slang),
            "cases_count": len(self.fed_cases),
            "version": self.version,
            "context_budget": self.default_context_budget,
            "persistent_total_items": persistent_stats.get("total_items", 0),
            "persistent_by_type": persistent_stats.get("by_type", {}),
            "top_sources": persistent_stats.get("top_sources", {}),
            "recent_materials": [m["text"][:50] for m in self.fed_materials[-5:]],
            "recent_slang": [f"{s['term']}={s['meaning']}" for s in self.fed_slang[-5:]],
            "recent_cases": [c["bypass"][:50] for c in self.fed_cases[-5:]],
        }
    
    def clear(self):
        """清空所有投喂"""
        self.fed_materials = []
        self.fed_slang = []
        self.fed_cases = []
        CONFIG_STORE.clear_knowledge_items()
        self.version += 1


def get_examples_for_technique(technique: str) -> str:
    """获取指定技巧的 few-shot 样本"""
    for tech_name, data in ATTACK_EXAMPLES.items():
        if tech_name in technique or technique in tech_name:
            examples = data["examples"]
            principles = data["principles"]
            
            lines = [f"【{tech_name}的真实绕过样本】:"]
            for ex in examples:
                lines.append(f"  原文: {ex['original']}")
                lines.append(f"  绕过: {ex['bypass']}")
                lines.append(f"  要点: {ex['explanation']}")
                lines.append("")
            
            lines.append(f"【{tech_name}核心原则】:")
            for i, p in enumerate(principles, 1):
                lines.append(f"  {i}. {p}")
            
            return "\n".join(lines)
    
    return ""


def get_strategy_level(level: int) -> dict:
    """获取指定等级的策略"""
    return STRATEGY_LEVELS.get(min(max(level, 1), 5), STRATEGY_LEVELS[1])


def get_escalation_hint(current_level: int, hit_layer: str) -> str:
    """根据被拦截层，给出升级提示"""
    hints = {
        "keyword": f"你上次被关键词匹配拦截了。说明你的内容中仍然包含了原始敏感词或其直接变体。"
                   f"你需要升级到Level {min(current_level+1, 7)}策略，完全避免使用任何可被直接匹配的词汇。",
        "pinyin": f"你上次被拼音还原层拦截了。说明审核系统能把谐音/拼音还原成原词。"
                  f"你需要升级到Level {min(current_level+1, 7)}策略，使用隐喻、暗示等完全不涉及原词发音的方式。",
        "regex": f"你上次被风险句式检测拦截了。说明你使用了'打倒xx'、'推翻xx'之类的固定句式。"
                 f"你需要升级到Level {min(current_level+1, 7)}策略，用更委婉、更包装化的表达方式。",
        "variant": f"你上次被变体词库拦截了。说明你用的表达方式已经被收录到审核词库中了。"
                   f"你需要升级到Level {min(current_level+1, 7)}策略，发明全新的表达方式或用深度伪装。",
        "semantic": f"你上次被AI语义分析拦截了。说明你的内容虽然没有敏感词，但AI判断出了你的意图。"
                    f"你需要升级到Level {min(current_level+1, 7)}策略，使用情感操纵或认知干扰。",
        "semantic_basic": f"你上次被基础语义模型拦截了。说明简单的情感伪装还不够。"
                          f"你需要升级到Level {min(current_level+1, 7)}策略，使用更复杂的认知干扰或系统操控手段。",
        "semantic_complex": f"你上次被高级语义模型拦截了。说明你的逻辑陷阱被识破了。"
                            f"你需要升级到Level {min(current_level+1, 7)}策略，尝试使用碎片化或时序攻击来规避单点检测。",
        "system": f"你上次被系统级策略拦截了。这很难，但你可以尝试调整时间点、使用更隐蔽的碎片化组合，或者寻找新的规则漏洞。",
    }
    return hints.get(hit_layer, f"上次被拦截了，请升级策略到Level {min(current_level+1, 7)}。")


# 全局知识库实例
KNOWLEDGE_STORE = KnowledgeStore()
