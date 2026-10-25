import json

ops = []

# --- SLIDE 0 (Cover: p) ---
# Delete default placeholders
ops.append({"op": "delete-element", "element": "i0"})
ops.append({"op": "delete-element", "element": "i1"})

# Background
ops.append({"op": "set-background", "slide": "p", "color": "#0A1128"})

# Top badge
ops.append({
    "op": "add-textbox",
    "slide": "p",
    "text": "🌙 2026 HACKATHON DEMO DAY",
    "x": 230, "y": 45, "width": 260, "height": 28,
    "font_size": 11, "bold": True, "color": "#00F5D4",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})

# Main Title
ops.append({
    "op": "add-textbox",
    "slide": "p",
    "text": "Wake · 睡眠环境守夜盒",
    "x": 40, "y": 95, "width": 640, "height": 65,
    "font_size": 42, "bold": True, "color": "#FFFFFF",
    "alignment": "center", "font_family": "Montserrat"
})

# Subtitle
ops.append({
    "op": "add-textbox",
    "slide": "p",
    "text": "“只测房间，不测人” —— 卧室微环境的无感守护与因果印证",
    "x": 40, "y": 165, "width": 640, "height": 35,
    "font_size": 17, "color": "#CADCFC",
    "alignment": "center", "font_family": "Roboto"
})

# Divider line
ops.append({
    "op": "add-shape",
    "slide": "p",
    "shape_type": "RECTANGLE",
    "x": 260, "y": 215, "width": 200, "height": 3,
    "background_color": "#00F5D4"
})

# Philosophy punchline
ops.append({
    "op": "add-textbox",
    "slide": "p",
    "text": "灵感源于当代青年自救哲学与穿戴设备的 Screenless 极简演进",
    "x": 40, "y": 235, "width": 640, "height": 30,
    "font_size": 13, "color": "#8892B0",
    "alignment": "center", "font_family": "Roboto"
})

# Presenters badge
ops.append({
    "op": "add-textbox",
    "slide": "p",
    "text": "开发者：刘航成 & 夏工  |  ESP32-S3 + Web Bluetooth",
    "x": 160, "y": 300, "width": 400, "height": 38,
    "font_size": 14, "bold": True, "color": "#FFFFFF",
    "background_color": "#162238", "alignment": "center",
    "font_family": "Roboto"
})

# Speaker Notes
ops.append({
    "op": "set-notes",
    "slide": "p",
    "text": "[0:00-0:15] 各位评委好，我是刘航成，这是夏工。今天我们带来的项目是：Wake 睡眠环境守夜盒。"
})


# --- SLIDE 1 (Hook & Youth Culture: SLIDE_1) ---
ops.append({"op": "add-slide", "layout": "BLANK", "id": "SLIDE_1"})
ops.append({"op": "set-background", "slide": "SLIDE_1", "color": "#0B132B"})

# Header
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_1",
    "text": "破冰：面对不确定性的当代青年自救哲学",
    "x": 40, "y": 25, "width": 640, "height": 45,
    "font_size": 26, "bold": True, "color": "#FFFFFF",
    "font_family": "Montserrat"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_1",
    "text": "“喝大水，睡大觉，练薄肌，做黄毛” —— 为什么【睡大觉】成了最后的防御阵地？",
    "x": 40, "y": 68, "width": 640, "height": 25,
    "font_size": 13, "color": "#00F5D4",
    "font_family": "Roboto"
})

# Card Left
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_1",
    "text": "🌪️ 现实痛点：巨大的外部不确定性",
    "x": 40, "y": 105, "width": 305, "height": 36,
    "font_size": 16, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_1",
    "text": "• 面对经济周期与内卷，年轻人不再迷信宏大叙事\n• 情绪出口转向身体掌控力的回归：喝水、睡眠、健身\n• 「睡大觉」不仅是生理修复，更是当代人最后的精神避难所与充电桩",
    "x": 40, "y": 141, "width": 305, "height": 175,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 145,
    "font_family": "Roboto"
})

# Card Right
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_1",
    "text": "🛌 讽刺现状：越想睡好，越陷焦虑",
    "x": 375, "y": 105, "width": 305, "height": 36,
    "font_size": 16, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_1",
    "text": "• 买昂贵手环、戴戒指睡觉，清晨却面对手表的“低分审判”\n• 手环只能冷酷地判定：“昨晚浅睡醒了 3 次，睡眠得分 68”\n• 但手环永远无法回答核心因果：你昨晚究竟为什么被吵醒？",
    "x": 375, "y": 141, "width": 305, "height": 175,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 145,
    "font_family": "Roboto"
})

# Bottom punchline
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_1",
    "text": "👉 核心症结：我们用尽力气监测自己的身体，却完全忽视了我们睡觉的那间屋子。",
    "x": 40, "y": 335, "width": 640, "height": 35,
    "font_size": 14, "bold": True, "color": "#FFD166",
    "background_color": "#1F2B48", "alignment": "center",
    "font_family": "Roboto"
})

ops.append({
    "op": "set-notes",
    "slide": "SLIDE_1",
    "text": "[0:15-0:50] 开场和大家分享一个年轻人的梗：“喝大水，睡大觉，练薄肌，做黄毛”。在不确定性的当下，大家发现睡大觉成了最后的自救阵地。但讽刺的是，许多人戴着 Apple Watch 睡觉，每天早上被低分焦虑折磨，手环只会告诉你“你醒了三次”，却从没告诉你“为什么醒”。"
})


# --- SLIDE 2 (Industry Insight: Screenless: SLIDE_2) ---
ops.append({"op": "add-slide", "layout": "BLANK", "id": "SLIDE_2"})
ops.append({"op": "set-background", "slide": "SLIDE_2", "color": "#0A1128"})

# Header
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_2",
    "text": "行业洞察：为什么 Screenless（无屏）赢得了睡眠？",
    "x": 40, "y": 25, "width": 640, "height": 45,
    "font_size": 26, "bold": True, "color": "#FFFFFF",
    "font_family": "Montserrat"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_2",
    "text": "从 Apple Watch 到 Whoop、Oura Ring，穿戴设备的底层胜利在于极度克制的“无感”",
    "x": 40, "y": 68, "width": 640, "height": 25,
    "font_size": 13, "color": "#00F5D4",
    "font_family": "Roboto"
})

# 3 Columns
# Col 1
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_2",
    "text": "1. 无感穿戴的秘密",
    "x": 40, "y": 105, "width": 195, "height": 34,
    "font_size": 15, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_2",
    "text": "• Whoop 与 Oura 的爆发，根源在于 Screenless（无屏）\n• 极度轻巧、长续航\n• 彻底让用户在入睡时忘记设备的存在",
    "x": 40, "y": 139, "width": 195, "height": 175,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 140,
    "font_family": "Roboto"
})

# Col 2
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_2",
    "text": "2. 睡眠卫生铁律：无光",
    "x": 260, "y": 105, "width": 195, "height": 34,
    "font_size": 15, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_2",
    "text": "• 医学睡眠卫生（Sleep Hygiene）首要原则：绝对的黑暗\n• 屏幕蓝光抑制褪黑素\n• 无屏设计在生理层面上杜绝了夜间任何光污染",
    "x": 260, "y": 139, "width": 195, "height": 175,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 140,
    "font_family": "Roboto"
})

# Col 3
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_2",
    "text": "3. 卧室微环境的大断层",
    "x": 485, "y": 105, "width": 195, "height": 34,
    "font_size": 15, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_2",
    "text": "• 身上戴的设备已走向无屏\n• 但床头却充斥着发光的手机、亮眼的带屏音箱、甚至带红外补光的摄像头！\n• 卧室微环境成了最大污染区",
    "x": 485, "y": 139, "width": 195, "height": 175,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 140,
    "font_family": "Roboto"
})

# Bottom
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_2",
    "text": "“既然身体的监测已经无屏无感，为什么卧室环境不能同样无感、无光、无压？”",
    "x": 40, "y": 335, "width": 640, "height": 35,
    "font_size": 14, "bold": True, "color": "#00F5D4",
    "background_color": "#1F2B48", "alignment": "center",
    "font_family": "Roboto"
})

ops.append({
    "op": "set-notes",
    "slide": "SLIDE_2",
    "text": "[0:50-1:30] 观察当前的睡眠穿戴市场，Apple Watch 固然强大，但 Whoop 和 Oura Ring 异军突起。它们的秘诀是什么？是 Screenless（无屏化）带来的终极无感。无屏不仅让重量极轻，更因为医学上睡眠卫生第一法则就是“绝对的黑暗”。可荒谬的是：手环无屏了，我们床头却还充斥着亮晃晃的手机屏幕。"
})


# --- SLIDE 3 (Product & Philosophy: SLIDE_3) ---
ops.append({"op": "add-slide", "layout": "BLANK", "id": "SLIDE_3"})
ops.append({"op": "set-background", "slide": "SLIDE_3", "color": "#0F1A3A"})

# Header
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_3",
    "text": "产品定位：Wake 守夜盒 —— 卧室的 Screenless 守护",
    "x": 40, "y": 25, "width": 640, "height": 45,
    "font_size": 26, "bold": True, "color": "#FFFFFF",
    "font_family": "Montserrat"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_3",
    "text": "把 Screenless 哲学贯彻到底 —— “只测房间，不测人” 的三大克制设计",
    "x": 40, "y": 68, "width": 640, "height": 25,
    "font_size": 13, "color": "#00F5D4",
    "font_family": "Roboto"
})

# 3 Pillars
# P1
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_3",
    "text": "🌑 真正 0 Lux 零光污染",
    "x": 40, "y": 105, "width": 195, "height": 34,
    "font_size": 15, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_3",
    "text": "• 入睡后硬件背光物理切断供电\n• 整机处于 0 Lux 绝对黑暗状态\n• 睡觉彻底摆脱枕边手机通知，告别睡前无休止刷屏",
    "x": 40, "y": 139, "width": 195, "height": 175,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 140,
    "font_family": "Roboto"
})

# P2
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_3",
    "text": "🔒 坚决不开摄像头",
    "x": 260, "y": 105, "width": 195, "height": 34,
    "font_size": 15, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_3",
    "text": "• 全黑卧室普通摄像头完全失效\n• 红外补光刺眼且严重侵犯隐私\n• 双麦分贝包络 + 多传感器状态机，极致守护卧室安全感",
    "x": 260, "y": 139, "width": 195, "height": 175,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 140,
    "font_family": "Roboto"
})

# P3
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_3",
    "text": "🔗 因果互补数据链",
    "x": 485, "y": 105, "width": 195, "height": 34,
    "font_size": 15, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_3",
    "text": "• 不与 Apple Watch / Oura 争夺生理诊断指标\n• 充当手环数据的解密者\n• 为手表生理异常提供物理房间维度的完整因果解释",
    "x": 485, "y": 139, "width": 195, "height": 175,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 140,
    "font_family": "Roboto"
})

# Bottom
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_3",
    "text": "⚡ 硬件底座：ESP32-S3 双核 AI 向量加速  |  ES7210 四通道双麦  |  Web Bluetooth 5Hz 实时推流",
    "x": 40, "y": 335, "width": 640, "height": 35,
    "font_size": 13, "bold": True, "color": "#FFFFFF",
    "background_color": "#1F2B48", "alignment": "center",
    "font_family": "Roboto"
})

ops.append({
    "op": "set-notes",
    "slide": "SLIDE_3",
    "text": "[1:30-2:15] 这就是我们的解决方案：Wake 守夜盒。我们坚持“只测房间，不测人”。三大设计哲学：第一，真 0 Lux 灭屏，背光物理断电；第二，坚决不开摄像头，保护最私密的卧室安全；第三，因果互补，做手环的数据解密者。"
})


# --- SLIDE 4 (Live Demo: SLIDE_4) ---
ops.append({"op": "add-slide", "layout": "BLANK", "id": "SLIDE_4"})
ops.append({"op": "set-background", "slide": "SLIDE_4", "color": "#0B132B"})

# Header
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_4",
    "text": "现场高能互动：Live Demo 整夜守护四部曲",
    "x": 40, "y": 25, "width": 640, "height": 45,
    "font_size": 26, "bold": True, "color": "#FFFFFF",
    "font_family": "Montserrat"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_4",
    "text": "现场 100 秒实机交互：ESP32-S3 硬件联手 Web Bluetooth 仪表盘全流程响应",
    "x": 40, "y": 68, "width": 640, "height": 25,
    "font_size": 13, "color": "#00F5D4",
    "font_family": "Roboto"
})

# 4 Steps
step_data = [
    ("① 一键入睡", "按 K3 实体键", "屏幕背光硬件彻底断电，整机进入 0 Lux 纯黑守护状态，零干扰。", 40),
    ("② 突发噪音冲击", "现场用力拍桌", "板载双麦瞬间捕获 65dB 噪音峰值，大屏折线图实时红线飙升报警。", 200),
    ("③ 起夜柔和微光", "手掠过红外感应", "WS2812 灯环仅亮起 1 颗 5% 暖黄呼吸微光，照亮脚边而不伤褪黑素。", 360),
    ("④ 清晨语音复盘", "点击清晨唤醒", "Web Speech 朗读晨报：“得分 76 分，主因突发噪音，建议关紧窗户”。", 520)
]

for title, act, desc, x in step_data:
    ops.append({
        "op": "add-textbox",
        "slide": "SLIDE_4",
        "text": title,
        "x": x, "y": 105, "width": 145, "height": 32,
        "font_size": 14, "bold": True, "color": "#FFFFFF",
        "background_color": "#1C2541", "alignment": "center",
        "font_family": "Roboto"
    })
    ops.append({
        "op": "add-textbox",
        "slide": "SLIDE_4",
        "text": f"【动作】\n{act}\n\n【响应】\n{desc}",
        "x": x, "y": 137, "width": 145, "height": 180,
        "font_size": 12, "color": "#CADCFC",
        "background_color": "#162238", "line_spacing": 135,
        "font_family": "Roboto"
    })

# Bottom
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_4",
    "text": "🌐 免安装 App：基于 Web Bluetooth 原生 API，打开 Chrome 浏览器即连即测！",
    "x": 40, "y": 335, "width": 640, "height": 35,
    "font_size": 14, "bold": True, "color": "#00F5D4",
    "background_color": "#1F2B48", "alignment": "center",
    "font_family": "Roboto"
})

ops.append({
    "op": "set-notes",
    "slide": "SLIDE_4",
    "text": "[2:15-3:30] 现在进入 Live Demo。现场模拟入睡过程：按 K3 灭屏进入 0 Lux；（拍桌）现场拍一下，看大屏噪音瞬间被抓取；夜间起夜，PIR 感应柔和暖光亮起；早晨起来，音箱自动用自然语音播报诊断。"
})


# --- SLIDE 5 (Killer Feature: Dual Timeline: SLIDE_5) ---
ops.append({"op": "add-slide", "layout": "BLANK", "id": "SLIDE_5"})
ops.append({"op": "set-background", "slide": "SLIDE_5", "color": "#0A1128"})

# Header
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_5",
    "text": "核心杀手锏：双轨交叉印证 —— 解密“浅睡易醒”",
    "x": 40, "y": 25, "width": 640, "height": 45,
    "font_size": 26, "bold": True, "color": "#FFFFFF",
    "font_family": "Montserrat"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_5",
    "text": "将手环测得的【生理异常点】，与守夜盒测得的【环境破坏点】时序毫秒级对齐",
    "x": 40, "y": 68, "width": 640, "height": 25,
    "font_size": 13, "color": "#00F5D4",
    "font_family": "Roboto"
})

# Top Rail (Apple Watch)
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_5",
    "text": "⌚ Apple Watch / Oura 睡眠分期生理轨（现象）",
    "x": 40, "y": 105, "width": 640, "height": 30,
    "font_size": 14, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_5",
    "text": "00:30 入睡  ➜  02:10 深度睡眠  ➜  【03:18:15 异常清醒 / 心率突增到 88bpm】  ➜  04:00 浅睡\n👉 手表判定：“你在 03:18 异常清醒，睡眠质量受损”。（手表无法回答为什么）",
    "x": 40, "y": 135, "width": 640, "height": 65,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 140,
    "font_family": "Roboto"
})

# Bottom Rail (Wake Box)
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_5",
    "text": "🌙 Wake 卧室环境物理数据轨（因果根源）",
    "x": 40, "y": 215, "width": 640, "height": 30,
    "font_size": 14, "bold": True, "color": "#00F5D4",
    "background_color": "#1C2541", "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_5",
    "text": "00:30 (32dB) ➜  02:10 (30dB) ➜  【03:15:20 突发噪音冲击：64.2 dB（窗外渣土车轰鸣）】 ➜  04:00 (33dB)\n👉 Wake 诊断：“噪音后 2 分钟生理惊醒，因果成立！建议关紧临街窗户，预防浅睡”。",
    "x": 40, "y": 245, "width": 640, "height": 65,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 140,
    "font_family": "Roboto"
})

# Value banner
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_5",
    "text": "🎯 颠覆性价值：从「被动接受手表的低分焦虑」，走向「主动改善卧室物理环境」！",
    "x": 40, "y": 330, "width": 640, "height": 40,
    "font_size": 14, "bold": True, "color": "#0A1128",
    "background_color": "#00F5D4", "alignment": "center",
    "font_family": "Roboto"
})

ops.append({
    "op": "set-notes",
    "slide": "SLIDE_5",
    "text": "[3:30-4:15] 这就是 Wake 最有价值的地方——双轨交叉印证。上面是 Apple Watch 测出的清醒点 03:18，下面是 Wake 测出的 03:15 突发 64dB 噪音。因果链一目了然：用户不是神经衰弱，而是被窗外货车吵醒了。这彻底消除了手环给用户的“低分焦虑”，给出了明确的物理改善建议。"
})


# --- SLIDE 6 (Booth Expo & Closing: SLIDE_6) ---
ops.append({"op": "add-slide", "layout": "BLANK", "id": "SLIDE_6"})
ops.append({"op": "set-background", "slide": "SLIDE_6", "color": "#0A1128"})

# Header
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_6",
    "text": "让睡眠重归宁静 · 欢迎移步展位亲自上手体验",
    "x": 40, "y": 25, "width": 640, "height": 45,
    "font_size": 26, "bold": True, "color": "#FFFFFF",
    "font_family": "Montserrat"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_6",
    "text": "喝大水，睡大觉 —— 打造属于每个现代人的深夜无感避风港",
    "x": 40, "y": 68, "width": 640, "height": 25,
    "font_size": 13, "color": "#00F5D4",
    "font_family": "Roboto"
})

# Left Box: Booth
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_6",
    "text": "🎪 展台巡演体验（Booth Expo）",
    "x": 40, "y": 105, "width": 310, "height": 34,
    "font_size": 15, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_6",
    "text": "• 展台位置：黑客松项目展示区（刘航成 & 夏工）\n• 现场上手玩法：\n  ① 亲自拍桌测试：体验高灵敏分贝瞬态冲击\n  ② 体验真·0 Lux 灭屏与起夜 5% 暖黄呼吸灯\n  ③ 试听纯前端 Web Audio 实时算法合成的粉红噪音雨声",
    "x": 40, "y": 139, "width": 310, "height": 175,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 140,
    "font_family": "Roboto"
})

# Right Box: Tech & Vision
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_6",
    "text": "🛠️ 极客架构与高可行性",
    "x": 370, "y": 105, "width": 310, "height": 34,
    "font_size": 15, "bold": True, "color": "#FFFFFF",
    "background_color": "#1C2541", "alignment": "center",
    "font_family": "Roboto"
})
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_6",
    "text": "• 低 BOM 成本：ESP32-S3 + 标准 I2C/SPI 外设，易量产\n• 双 OTA 分区：非破坏性固件升级，保障运行可靠\n• 极简前端：Web Bluetooth 零门槛跨平台通信\n• 隐私安全：纯本地边缘计算，零敏感音频上传",
    "x": 370, "y": 139, "width": 310, "height": 175,
    "font_size": 13, "color": "#CADCFC",
    "background_color": "#162238", "line_spacing": 140,
    "font_family": "Roboto"
})

# Footer
ops.append({
    "op": "add-textbox",
    "slide": "SLIDE_6",
    "text": "🌙 Project Wake | 开发者：刘航成 & 夏工 | 感谢各位评委与观众！",
    "x": 40, "y": 335, "width": 640, "height": 35,
    "font_size": 14, "bold": True, "color": "#00F5D4",
    "background_color": "#1F2B48", "alignment": "center",
    "font_family": "Roboto"
})

ops.append({
    "op": "set-notes",
    "slide": "SLIDE_6",
    "text": "[4:15-5:00] 总结收尾：我们用极其克制的 Screenless 理念打造了 Wake，让睡眠回归睡眠。我们桌上运行着实物与实时 Web Bluetooth 仪表盘，欢迎各位评委在随后的巡演环节移步我们展位，亲自拍桌上手体验！谢谢大家！"
})

with open("batch.json", "w", encoding="utf-8") as f:
    json.dump(ops, f, ensure_ascii=False, indent=2)

print(f"Generated batch.json with {len(ops)} operations.")
