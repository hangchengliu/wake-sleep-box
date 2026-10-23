# -*- coding: utf-8 -*-
"""意图识别：只负责判断“要不要触发设备动作/存笔记”，其余一律交给对话模型。"""
import re

PATTERNS = {
    "start_night": [r"开始守夜", r"启动守夜", r"进入守夜", r"开启守夜", r"我要睡了", r"我要睡觉", r"准备睡觉", r"晚安"],
    "stop_night": [r"结束守夜", r"停止守夜", r"关闭守夜", r"退出守夜", r"我起床了", r"我醒了", r"早安", r"起床了"],
    "record_dream": [r"记录梦境", r"记一下梦", r"我梦见", r"我梦到", r"做了个梦", r"刚才梦见"],
    "query_report": [r"晨报", r"昨晚.{0,4}(睡得|报告|怎么样)", r"睡眠报告"],
}
# 问句（“昨天梦到什么”）不是记录，要避免被 record_dream 抢走
QUESTION_HINT = re.compile(r"(什么|吗|呢|怎么|哪|[?？])")


def detect_intent(text):
    t = text.strip()
    for tool in ("record_dream", "start_night", "stop_night", "query_report"):
        if tool == "record_dream" and QUESTION_HINT.search(t) and not re.search(r"记录梦境|记一下梦", t):
            continue
        for p in PATTERNS[tool]:
            if re.search(p, t):
                args = {}
                if tool == "record_dream":
                    m = re.search(r"(?:记录梦境|记一下梦|我梦见|我梦到|做了个梦|刚才梦见)[，,：: ]*(.+)", t)
                    args["content"] = (m.group(1) if m else t).strip()
                return {"tool": tool, "args": args}
    return None


def confirm_text(intent):
    return {
        "start_night": "好的，开始守夜，晚安。",
        "stop_night": "早安，已结束守夜。",
        "record_dream": "梦境已记下。",
    }.get(intent["tool"], "收到。")
