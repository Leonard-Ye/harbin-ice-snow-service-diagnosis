import pandas as pd
import asyncio
import os
import json
import logging
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === 配置区 ===
API_KEY = os.getenv("LLM_API_KEY", "your_api_key_here")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-chat")

# V7.2.1 已验证通过，正式开启全量运行！
TEST_MODE = False
TEST_OUTPUT_FILE = 'v7_2_1_test_results.json'

ALLOWED_ASPECTS = [
    "交通出行", "行程规划", "景区游玩", "景观打卡", "休闲娱乐", "餐饮消费",
    "住宿体验", "购物特产", "城市人文", "服务管理", "气候环境", "安全保障",
    "咨询求助", "其他"
]

ALLOWED_PERSONAS = ["亲子家庭", "情侣伴侣", "朋友结伴", "独自出行", "银发老人", "未知"]

ALLOWED_PAINPOINTS = [
    "交通拥堵", "停车困难", "接驳不便", "排队时间长", "人流拥挤", "卫生条件差",
    "价格虚高", "商业欺诈", "服务态度差", "管理混乱", "设施老旧", "气候严寒",
    "防寒不足", "路面湿滑", "安全隐患", "其他痛点"
]

PROMPT_TEMPLATE = """
你是一个严谨的城市规划与旅游舆情分析专家。请阅读游客评论，严格输出 JSON 格式，供哈尔滨冰雪旅游服务设施优化研究使用。

【输出字段】

1. "Locations":
提取评论中提及的具体地点，包括景区、街道、商圈、餐厅、酒店、车站等。若无明确地点，输出 []。

2. "Aspect":
从以下 14 个维度中选择评论的最核心主题：
[交通出行, 行程规划, 景区游玩, 景观打卡, 休闲娱乐, 餐饮消费, 住宿体验, 购物特产, 城市人文, 服务管理, 气候环境, 安全保障, 咨询求助, 其他]

【核心主题裁决规则】
- 优先级 1（安全保障）：必须是真实的生命危险、受伤滑倒或急救。单纯“被吓到、查房、物价惊人”不算生命安全。
- 优先级 2（服务管理）：仅当核心负面体验由服务主体（司机、前台、商家、保安、景区管理方）的具体行为直接导致。若全篇在骂餐饮难吃，只顺带提了司机一句，以餐饮为准。
- 优先级 3（负面优先）：同存正负体验时，以负面痛点所在的维度为核心 Aspect。
- 【咨询求助路由】：只要是第一人称主动询问“怎么玩、求推荐、可以玩什么、哪里好玩、怎么穿、避雷吗”，即使涉及路线或玩法，也一律归为“咨询求助”。
- 【信息输出型路由】：攻略合集、Top10、清单、本地人忠告，属于信息输出，绝不归为“咨询求助”！
  - 美食榜单、民间米其林、必吃 -> 餐饮消费
  - 伴手礼、特产清单、必买 -> 购物特产
  - 路线、攻略、保姆级指南、避雷指南 -> 行程规划
  - 拍照地、出片、打卡点合集 -> 景观打卡
  - 洗浴、酒吧、KTV、萌宠乐园 -> 休闲娱乐

3. "Sentiment":
判断核心 Aspect 的情绪：
- 1：正面
- 0：中立
- -1：负面
规则：
- 排队久、物价高、服务差、体验受损等客观负面，强制判为 -1。若文本没有明确旅游设施痛点，只是泛泛负面情绪（如“不会再来、无聊”），判为 0。
- 若文本出现“冷死了、冻麻了、风太大、穿少了”等明确体感受损表达，应至少记录气候环境的负向（可作主 Aspect 或 SecondaryAspect）。
- 纯提问、攻略输出、无明显情绪表达，判为 0。
- Aspect = 咨询求助 时，Sentiment 强制为 0。

4. "PainPoints":
仅当 Sentiment = -1 时提取。必须且只能从以下标准词库中选择 1-3 个：
[交通拥堵, 停车困难, 接驳不便, 排队时间长, 人流拥挤, 卫生条件差, 价格虚高, 商业欺诈, 服务态度差, 管理混乱, 设施老旧, 气候严寒, 防寒不足, 路面湿滑, 安全隐患, 其他痛点]
规则：
- Sentiment 为 1 或 0 时，PainPoints 必须输出 []。
- “商业欺诈”仅用于宰客、黄牛、强制消费、虚假宣传、退票困难等违法或违规行为。
- “管理混乱”仅用于排队组织混乱、园区调度混乱、退票流程混乱、现场秩序混乱、突发事件处置混乱等明确管理问题；普通“不好玩、无聊、氛围差”禁止判为管理混乱。
- “其他痛点”仅当无法映射到标准词库时使用，禁止与其他已匹配痛点并列输出。

5. "TouristPersona":
从以下选项中选择：[亲子家庭, 情侣伴侣, 朋友结伴, 独自出行, 银发老人, 未知]
规则：
- 年龄（如81年）、单身、发帖人性别、提及合照、或使用“大哥/姐妹/宝子”等，均不能单独作为判定依据。
- 必须有明确同行关系（带娃/老公/男朋友/闺蜜/爸妈）才可推断。
- 无确凿线索一律输出“未知”。

6. "SecondaryAspect":
若评论中存在非核心但有明确情绪的信息，弱提取为数组，如：[{"Aspect": "景观打卡", "Sentiment": 1}]。若无输出 []。

【严格输出要求】
只输出 JSON，不输出解释性文字。不得输出 Markdown 符号。
"""

def extract_json_from_text(text):
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)
    
    start = text.find('{')
    if start != -1:
        bracket_level = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                bracket_level += 1
            elif text[i] == '}':
                bracket_level -= 1
                if bracket_level == 0:
                    return text[start:i+1]
                    
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return match.group(0)
    
    return None

async def process_text(client, sem, text, row_id, ip_location, publish_time):
    async with sem:
        retries = 2
        for attempt in range(retries + 1):
            try:
                await asyncio.sleep(1)
                
                request_kwargs = {
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": "You strictly output valid JSON based on the rules. Do not include markdown formatting or extra text."},
                        {"role": "user", "content": f"{PROMPT_TEMPLATE}\n\n评论文本：\n\"{text}\""}
                    ],
                    "temperature": 0.1
                }
                
                if "deepseek" not in MODEL_NAME.lower():
                    request_kwargs["response_format"] = {"type": "json_object"}
                
                response = await client.chat.completions.create(**request_kwargs)
                
                content = response.choices[0].message.content.strip()
                json_str = extract_json_from_text(content)
                
                if not json_str:
                    raise ValueError("No valid JSON structure found in output.")
                
                result = json.loads(json_str)
                
                # --- 硬校验与兜底逻辑 ---
                locations = result.get("Locations", [])
                if not isinstance(locations, list):
                    locations = [str(locations)] if locations else []
                
                secondary = result.get("SecondaryAspect", [])
                if not isinstance(secondary, list):
                    secondary = []
                
                aspect = result.get("Aspect", "其他")
                if aspect not in ALLOWED_ASPECTS:
                    aspect = "其他"
                
                persona = result.get("TouristPersona", "未知")
                if persona not in ALLOWED_PERSONAS:
                    persona = "未知"
                
                try:
                    sentiment_val = int(result.get("Sentiment", 0))
                except Exception:
                    sentiment_val = 0
                
                if sentiment_val not in [-1, 0, 1]:
                    sentiment_val = 0
                
                pts = result.get("PainPoints", [])
                if not isinstance(pts, list):
                    pts = []
                pts = [p for p in pts if p in ALLOWED_PAINPOINTS]
                
                if sentiment_val == -1 and len(pts) == 0:
                    if aspect == "其他":
                        sentiment_val = 0
                        pts = []
                    else:
                        pts = ["其他痛点"]
                
                if sentiment_val in [0, 1]:
                    pts = []
                
                final_result = {
                    "source_id": row_id,
                    "OriginalText": text,
                    "Locations": locations,
                    "Aspect": aspect,
                    "Sentiment": sentiment_val,
                    "PainPoints": pts,
                    "TouristPersona": persona,
                    "SecondaryAspect": secondary,
                    "ip_location": ip_location,
                    "publish_time": publish_time,
                    "extract_status": "success" if attempt == 0 else "retry_success"
                }
                return final_result
                
            except Exception as e:
                logging.warning(f"Row {row_id} attempt {attempt+1} failed: {e}")
                if attempt == retries:
                    return {
                        "source_id": row_id, "OriginalText": text, "Locations": [], "Aspect": "其他", 
                        "Sentiment": 0, "PainPoints": [], "TouristPersona": "未知", "SecondaryAspect": [],
                        "ip_location": ip_location, "publish_time": publish_time,
                        "extract_status": "fallback"
                    }

async def main():
    if API_KEY == "your_api_key_here":
        print("====== [严重警告] ======")
        print("未检测到有效的 LLM_API_KEY 环境变量！")
        print("Powershell 中请执行: $env:LLM_API_KEY='您的真实API_KEY'")
        print("然后重新运行: python llm_extractor.py")
        print("========================")
        return

    try:
        from openai import AsyncOpenAI
        from tqdm.asyncio import tqdm
    except ImportError:
        print("缺少依赖 openai 或 tqdm。请运行 pip install openai tqdm 后重试。")
        return

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL, max_retries=5)
    
    input_path = 'cleaned_data.csv'
    output_path = 'structured_sentiment.csv'
    
    if not os.path.exists(input_path):
        print(f"找不到输入文件 {input_path}。如果您下载的是 cleaned_data(1).csv，请将其重命名为 cleaned_data.csv")
        return

    df = pd.read_csv(input_path)
    
    if TEST_MODE:
        total_to_process = min(100, len(df))
        print(f"============== V7.2.1 首件检验模式开启 ==============")
    else:
        total_to_process = len(df)
        print(f"============== V7.2.1 全量运行模式开启 ==============")
        print(f"即将抽取全部 {total_to_process} 条数据，预计需要数小时，请耐心等待。")

    texts = df['text'].head(total_to_process).tolist()
    ips = df['ip_location'].head(total_to_process).tolist()
    times = df['publish_time'].head(total_to_process).tolist()
    
    sem = asyncio.Semaphore(1)
    
    tasks = []
    for i, text in enumerate(texts):
        tasks.append(process_text(client, sem, text, i, ips[i], times[i]))
        
    print("开始调用大模型 API...")
    results = await tqdm.gather(*tasks)
    
    if TEST_MODE:
        with open(TEST_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        print(f"\n[V7.2.1 检验完毕]！请审查 {TEST_OUTPUT_FILE}")
    else:
        parsed_results = []
        for r in results:
            parsed_results.append({
                "source_id": r.get("source_id"),
                "OriginalText": r.get("OriginalText", ""),
                "Locations": "、".join(r.get("Locations", [])),
                "Aspect": r.get("Aspect"),
                "Sentiment": r.get("Sentiment"),
                "PainPoints": "、".join(r.get("PainPoints", [])),
                "TouristPersona": r.get("TouristPersona", "未知"),
                "SecondaryAspect": json.dumps(r.get("SecondaryAspect", []), ensure_ascii=False),
                "ip_location": r.get("ip_location", ""),
                "publish_time": r.get("publish_time", ""),
                "extract_status": r.get("extract_status")
            })
        res_df = pd.DataFrame(parsed_results)
        res_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"全量数据提取完成！已保存至 {output_path}")

        success = sum(1 for r in results if r['extract_status'] == 'success')
        retry = sum(1 for r in results if r['extract_status'] == 'retry_success')
        fallback = sum(1 for r in results if r['extract_status'] == 'fallback')
        print("\n============= 全量数据质量报告 =============")
        print(f"总处理条数: {total_to_process}")
        print(f"完美一次性解析 (Success): {success} (约 {success/total_to_process*100:.2f}%)")
        print(f"触发重试后解析 (Retry): {retry} (约 {retry/total_to_process*100:.2f}%)")
        print(f"彻底提取失败兜底 (Fallback): {fallback} (约 {fallback/total_to_process*100:.2f}%)")
        print("============================================")

if __name__ == '__main__':
    asyncio.run(main())
