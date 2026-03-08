import os
import time
import re
import google.generativeai as genai

def generate_report(raw_data_dir: str, topic: str, output_dir: str = ".") -> str:
    """
    讀取 raw_data 下的所有 .txt 檔案，並使用 Gemini 1.5 Flash 將其整合成一份專業的 Markdown 報告。
    """
    # 確認 API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("請設定環境變數 GEMINI_API_KEY")

    # 設定 Gemini API
    genai.configure(api_key=api_key)

    print(f"[{topic}] 準備讀取 raw_data 目錄下的資料...")
    
    # 讀取所有 txt 檔案內容
    all_content = ""
    file_count = 0
    if os.path.exists(raw_data_dir):
        for filename in os.listdir(raw_data_dir):
            if filename.endswith(".txt"):
                file_path = os.path.join(raw_data_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        all_content += f"=== 檔案來源: {filename} ===\n"
                        all_content += f.read() + "\n\n"
                        file_count += 1
                except Exception as e:
                    print(f"讀取檔案 {filename} 時發生錯誤: {e}")
    
    if file_count == 0 or not all_content.strip():
        print("沒有找到任何可用的爬取資料(.txt)來生成報告。")
        return ""

    print(f"成功讀取了 {file_count} 份參考資料。開始請求 Gemini 進行重點摘要與統整...")

    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferred_order = [
            'gemini-3.1-pro', 'gemini-3.0-pro', 'gemini-2.5-pro', 'gemini-2.0-pro', 'gemini-1.5-pro',
            'gemini-3.1-flash', 'gemini-3.0-flash', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'
        ]
        fallback_chain = []
        for pref in preferred_order:
            for m in available_models:
                if pref in m and m not in fallback_chain:
                    fallback_chain.append(m)
        for m in available_models:
            if m not in fallback_chain:
                fallback_chain.append(m)
    except Exception:
        fallback_chain = ["models/gemini-2.5-pro", "models/gemini-1.5-pro", "models/gemini-2.5-flash", "models/gemini-1.5-flash"]
            
    print(f"  -> Reporter 備援模型清單: {', '.join([m.split('/')[-1] for m in fallback_chain[:3]])}...")

    prompt = f"研究主題：{topic}\n\n以下是爬取到的生資料（Raw Data）：\n\n{all_content}\n\n請根據以上生資料，嚴格參照指示撰寫 Markdown 報告。"

    report_text = ""
    for target_model in fallback_chain:
        print(f"  -> 嘗試使用模型: {target_model}")
        model = genai.GenerativeModel(
            model_name=target_model,
            system_instruction="你是一位『資深產業分析師』。你的任務是嚴格根據提供的 raw_data 生資料（Source-Only 模式），撰寫專業報告。\n\n"
                               "【嚴格規定與限制】：\n"
                               "1. 拒絕幻覺：如果你發現素材內容與研究主題完全無關（例如只抓到放假行事曆或無意義推銷），你必須直接回報『現有資料不足』，嚴禁使用你自身的內建知識來回答或腦補（例如嚴禁腦補 AI 趨勢）。\n"
                               "2. 來源標註：你生成的任何分析、數據或段落，都必須在句末或段落末尾明確標註出你參考了哪一份來源檔案（例如：[來源：xxx.txt]）。若無法找到支援論點的擷取內容，請不要寫出該論點。\n"
                               "3. 請使用 Markdown 語法排版。\n"
                               "4. 報告必須且只能包含以下四個主要章節（以 ## 為標題）：『執行摘要』、『產業趨勢分析』、『關鍵數據總結』、『參考資料清單』。\n"
                               "5. 『參考資料清單』請從提供的文本中整理被提及的來源連結（URL）與檔案名稱。\n"
                               "6. 主動剔除雜訊：如果素材中包含行事曆、放假資訊或任何明顯無關的段落，請在分析時直接忽視並剔除。"
        )

        try:
            response = model.generate_content(prompt)
            report_text = response.text
            break
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                match = re.search(r'please retry in (\d+\.?\d*)s', error_str)
                if match:
                    wait_time = float(match.group(1)) + 1
                    if wait_time < 60:
                        print(f"    [!] {target_model} 頻率限制 (報告)，冷靜等待 {wait_time:.1f} 秒...")
                        time.sleep(wait_time)
                        try:
                            response = model.generate_content(prompt)
                            report_text = response.text
                            break
                        except Exception:
                            print(f"    [!] {target_model} 重試失敗，切換模型。")
                            continue
                    else:
                        print(f"    [!] {target_model} 需等待過久 ({wait_time:.1f}s)，切換模型...")
                        continue
                else:
                    print(f"    [!] {target_model} 的每日配額可能已滿，切換模型...")
                    continue
            else:
                print(f"    [!] {target_model} 發生預期外錯誤: {e}，跳過。")
                continue
                
    if not report_text:
        print("[錯誤] 所有備援模型均生成失敗或沒有回傳內容。")
        return ""
        
    # 確保產出的檔案名為 Research_Report.md
    output_path = os.path.join(output_dir, "Research_Report.md")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)
        
    print(f"✓ 報告生成成功！已儲存至: {output_path}")
    return output_path

if __name__ == "__main__":
    # 簡單測試用
    test_dir = os.path.join(os.path.dirname(__file__), "raw_data")
    generate_report(test_dir, "測試用固態電池分析", ".")
