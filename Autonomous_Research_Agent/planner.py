import os
import json
import time
import re
import google.generativeai as genai

def generate_plan(topic: str) -> list:
    """
    根據使用者輸入的主題，扮演資深研究主管，將主題拆解成 5 個具體的搜尋指令。
    """
    # 讀取環境變數中的 API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("請設定環境變數 GEMINI_API_KEY")

    # 設定 Gemini API
    genai.configure(api_key=api_key)

    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # 打造一個最新到最舊的智能下降優先級 (越前面越優先)
        preferred_order = [
            'gemini-3.1-pro', 'gemini-3.0-pro', 'gemini-2.5-pro', 'gemini-2.0-pro', 
            'gemini-1.5-pro', 'gemini-3.1-flash', 'gemini-3.0-flash', 
            'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'
        ]
        fallback_chain = []
        for pref in preferred_order:
            for m in available_models:
                if pref in m and m not in fallback_chain:
                    fallback_chain.append(m)
        
        # 若都沒有符合的，把全部可用模型加進清單
        for m in available_models:
            if m not in fallback_chain:
                fallback_chain.append(m)
    except Exception:
        fallback_chain = ["models/gemini-2.5-pro", "models/gemini-2.5-flash", "models/gemini-1.5-pro", "models/gemini-1.5-flash"]

    print(f"  -> Planner 備援模型清單: {', '.join([m.split('/')[-1] for m in fallback_chain[:3]])}...")

    prompt = f"請拆解以下研究主題：{topic}"
    response = None

    # 瀑布式切換機制：自動挑選有 Quota 的模型
    for target_model in fallback_chain:
        print(f"  -> 正在嘗試使用模型: {target_model}")
        model = genai.GenerativeModel(
            model_name=target_model,
            system_instruction="你是一位『資深研究主管』。你的任務是將使用者或團隊輸入的研究主題，拆解成 5 個具體的搜尋指令。\n\n"
                               "規則：\n"
                               "1. 你必須只輸出一個 JSON Array 格式的結果，包含這 5 個搜尋字串。\n"
                               "2. 不要加上任何其他的問候語、解釋，或者是 Markdown 標籤 (例如 ```json)。\n"
                               "3. 範例格式：[\"搜尋指令 1\", \"搜尋指令 2\", \"搜尋指令 3\", \"搜尋指令 4\", \"搜尋指令 5\"]",
            generation_config={"response_mime_type": "application/json"}
        )
        
        try:
            response = model.generate_content(prompt)
            break # 成功取得回應就跳脫迴圈
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "quota" in error_msg:
                match = re.search(r'please retry in (\d+\.?\d*)s', error_msg)
                if match:
                    wait_t = float(match.group(1)) + 1
                    # 如果只需等一小段時間 (例如小於 40 秒)，我們就等一下繼續用好模型
                    if wait_t < 40:
                        print(f"    [!] {target_model} 頻率限制 (RPM)，冷靜等待 {wait_t:.1f} 秒...")
                        time.sleep(wait_t)
                        try:
                            response = model.generate_content(prompt)
                            break
                        except Exception:
                            print(f"    [!] {target_model} 重試後依然失敗，切換下一模型。")
                            continue
                    else:
                        print(f"    [!] {target_model} 需要等待過久 ({wait_t:.1f}s)，切換至下一模型...")
                        continue
                else:
                    print(f"    [!] {target_model} 的每日配額 (Quota) 可能已耗盡，切換至下一模型...")
                    continue
            else:
                print(f"    [!] {target_model} 發生預期外錯誤: {e}，跳過。")
                continue

    if not response:
        print("無法取得 Planner 的回應，可能 API 均超出限制。")
        return []

    try:
        # 將回應的字串轉回 Python 的 list
        search_queries = json.loads(response.text)
        return search_queries
    except json.JSONDecodeError as e:
        print("無法解析模型回傳的 JSON 格式：", e)
        print("原始回傳內容：", response.text)
        return []

if __name__ == "__main__":
    # 簡單的測試執行
    test_topic = "2026 固態電池技術突破"
    print(f"測試主題: {test_topic}")
    try:
        plan = generate_plan(test_topic)
        print("生成的搜尋計畫：")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    except Exception as e:
        print("執行發生錯誤:", e)
