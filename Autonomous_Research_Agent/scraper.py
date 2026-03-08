import os
import time
import json
import random
import requests
import re
import google.generativeai as genai
from newspaper import Article, ArticleException, Config

class ResearchScraper:
    def __init__(self, raw_data_dir: str = "raw_data"):
        """
        初始化 ResearchScraper 類別，並確保 raw_data 目錄存在。
        """
        # 以目前目錄為基準建立 raw_data 的資料夾路徑
        self.raw_data_dir = os.path.join(os.path.dirname(__file__), raw_data_dir)
        os.makedirs(self.raw_data_dir, exist_ok=True)

    def _get_fallback_chain(self, prefer_flash=True):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: return ["models/gemini-2.5-flash"]
        genai.configure(api_key=api_key)
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if prefer_flash:
                preferred_order = ['gemini-3.1-flash', 'gemini-3.0-flash', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-3.1-pro', 'gemini-3.0-pro', 'gemini-2.5-pro', 'gemini-1.5-pro']
            else:
                preferred_order = ['gemini-3.1-pro', 'gemini-3.0-pro', 'gemini-2.5-pro', 'gemini-2.0-pro', 'gemini-1.5-pro', 'gemini-3.1-flash', 'gemini-3.0-flash', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
            
            chain = []
            for pref in preferred_order:
                for m in available_models:
                    if pref in m and m not in chain: chain.append(m)
            for m in available_models:
                if m not in chain: chain.append(m)
            return chain
        except Exception:
            return ["models/gemini-2.5-flash", "models/gemini-1.5-flash"] if prefer_flash else ["models/gemini-2.5-pro", "models/gemini-1.5-pro"]

    def search_web(self, query: str, topic: str, is_fallback: bool = False) -> list:
        """
        利用 Serper.dev (Google Search API) 搜尋給定的關鍵字，回傳前 10 個結果的標題與連結。
        確保 gl="tw" 與 hl="zh-tw"，並支援回退測試。
        """
        # 意圖感知搜尋：根據 topic 簡單判斷語言來設定參數
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in topic)
        gl_param = "tw" if has_chinese else "us"
        hl_param = "zh-tw" if has_chinese else "en"
        
        # 關鍵字強化：自動加上更精確的詞組避免通用結果
        clean_query = f"{query.strip()} 產業分析 OR 供應鏈報告" if not is_fallback else query.strip()
        print(f"[{time.strftime('%H:%M:%S')}] 正在透過 Serper.dev 搜尋: {clean_query} (地區: {gl_param}, 語言: {hl_param})")
        
        serper_api_key = os.getenv("SERPER_API_KEY")
        if not serper_api_key:
            print("[錯誤] 未設定 SERPER_API_KEY 環境變數，無法搜尋。請至 serper.dev 申請並設定。")
            return []

        results = []
        try:
            url = "https://google.serper.dev/search"
            payload = json.dumps({
              "q": clean_query,
              "gl": gl_param,
              "hl": hl_param,
              "num": 10
            })
            headers = {
              'X-API-KEY': serper_api_key,
              'Content-Type': 'application/json'
            }
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json()
            
            organic_results = data.get("organic", [])
            for idx, r in enumerate(organic_results, start=1):
                results.append({
                    "id": idx,
                    "title": r.get("title", ""),
                    "href": r.get("link", ""),
                    "body": r.get("snippet", "")
                })
        except Exception as e:
            print(f"搜尋過程中發生錯誤 ({clean_query}): {e}")
            time.sleep(2)
            
        if results:
            print("  -> 正在針對前 10 筆結果摘要進行 LLM 評分過濾...")
            filtered_results = self.filter_titles(topic, results)
            
            # 如果為字串 "FALLBACK" 或全空，代表方向偏離或不合格
            if (not filtered_results or filtered_results == "FALLBACK") and not is_fallback:
                print("  -> 前 10 筆摘要全數被剔除或方向偏離。啟動 Fallback 自動修改關鍵字重新搜尋...")
                new_query = self.rewrite_query(topic, clean_query)
                print(f"  -> 將關鍵字變更為 '{new_query}'，重新搜尋...")
                return self.search_web(new_query, topic, is_fallback=True)
                
            if filtered_results == "FALLBACK":
                return []
                
            return filtered_results
            
        return results

    def filter_titles(self, topic: str, results: list) -> list:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: return results
            
        prompt_items = []
        for r in results:
            title = r.get("title", "")
            # Snippet 智慧篩選：在本機端先行剃除明顯無關的雜訊，節省 API 配額
            if any(bad in title for bad in ["行事曆", "假期", "中醫診所", "放假", "維基百科", "農民曆"]):
                print(f"    -> [本機過濾] 發現明顯無關標題 ('{title}')，直接捨棄。")
                continue
            prompt_items.append(f"[{r['id']}] 標題:{title} | 摘要:{r.get('body', '')}")
            
        if not prompt_items:
            return []
            
        snippet_text = "\n".join(prompt_items)

        prompt = (f"研究主題：{topic}\n\n"
                  f"請對以下搜尋結果摘要進行『相關性打分 (0-100)』：\n"
                  f"{snippet_text}\n\n"
                  f"請直接回傳 JSON 分數對應表：")
                  
        fallback_chain = self._get_fallback_chain(prefer_flash=True)
        reply = ""
        
        for target_model in fallback_chain:
            model = genai.GenerativeModel(
                model_name=target_model,
                system_instruction="你是一個研究員。任務是從搜尋摘要中判斷該連結的內容與主題的關聯度，並給予分數(0-100)。判斷標準：『此連結的內容是否能回答使用者的問題？』如果是行事曆、農民曆、非產業分析內容，直接給 0 分。只回傳 JSON 格式分數對應表，例如: {\"1\": 85, \"2\": 0, \"3\": 65}，不要任何廢話。"
            )
            try:
                res = model.generate_content(prompt)
                reply = res.text.strip()
                break
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg:
                    match = re.search(r'please retry in (\d+\.?\d*)s', error_msg)
                    if match:
                        wait_t = float(match.group(1)) + 1
                        if wait_t < 40:
                            print(f"    [!] {target_model} 頻率限制 (預審)，冷靜等待 {wait_t:.1f} 秒...")
                            time.sleep(wait_t)
                            try:
                                res = model.generate_content(prompt)
                                reply = res.text.strip()
                                break
                            except Exception:
                                print(f"    [!] {target_model} 重試失敗，切換下一模型。")
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
                        
        if not reply:
            return []

        # 處理可能夾帶的 ```json ... ``` 等標記
        if reply.startswith("```json"): reply = reply[7:-3].strip()
        elif reply.startswith("```"): reply = reply[3:-3].strip()
        
        scores = json.loads(reply)
        
        # 從回傳解析分數，過濾、排序
        scored_results = []
        max_score = 0
        for r in results:
            str_id = str(r['id'])
            if str_id in scores:
                score = int(scores[str_id])
                max_score = max(max_score, score)
                if score >= 60:
                    scored_results.append((score, r))
                    print(f"    -> [預審通過] ID {str_id} 獲得分數 {score}，保留以供爬文。")
                else:
                    print(f"    -> [分數過低] ID {str_id} 得到 {score} 分，捨棄。")

        # 防呆機制：如果所有摘要分數都低於 40 分，觸發 fallback
        if scores and max_score < 40:
            print("    -> [防呆機制] 搜尋結果分數全面低於 40，方向完全錯誤！")
            return "FALLBACK"

        # 依分數從高到低排，只取前 5 名
        scored_results.sort(key=lambda x: x[0], reverse=True)
        filtered = [item[1] for item in scored_results[:5]]

        return filtered

    def rewrite_query(self, topic: str, query: str) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: return query
            
        prompt = (f"主題為 '{topic}'，但關鍵字 '{query}' 搜尋到的全是無意義內容。\n"
                  "請回傳一個『修改過』的字串：例如拿掉年份、讓關鍵字更通用、或改搜像是『供應鏈分析』等字眼。\n"
                  "規則：只回傳純文字關鍵字，不包含引號。")
                  
        fallback_chain = self._get_fallback_chain(prefer_flash=True)
        for target_model in fallback_chain:
            model = genai.GenerativeModel(model_name=target_model)
            try:
                res = model.generate_content(prompt)
                return res.text.strip().replace('"', '').replace("'", "")
            except Exception:
                continue
        return topic

    def fetch_content(self, url: str) -> str:
        """
        利用 newspaper 抓取指定 URL 的純文字內容。防禦層級：User-Agent 偽裝以降低 403 機率。
        """
        try:
            config = Config()
            config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            
            article = Article(url, config=config)
            # 必須先 download() 再 parse()
            article.download()
            article.parse()
            # 若無純文字，則回傳空白字串
            return article.text if article.text else ""
        except ArticleException as e:
            # 處理 403 錯誤或禁止爬蟲抓取的網站
            print(f"    -> [爬取失敗] 可能遭遇 403 阻擋或網站不存在 ({url})，跳過並自動切換下一筆。")
            return ""
        except Exception as e:
            print(f"    -> [未知錯誤] 抓取發生未預期的錯誤 ({url})，跳過。")
            return ""

    def check_relevance(self, topic: str, content: str) -> bool:
        """
        利用 Gemini 進行快速評估，判斷內容是否有實質相關性。
        """
        if not topic or len(content.strip()) < 50:
            return False
            
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            # 沒設定 API Key 時預設放行
            return True

        # 設定 API
        genai.configure(api_key=api_key)
        
        try:
            model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in model_list if '1.5-pro' in m), 
                                next((m for m in model_list if '1.5-flash' in m), model_list[0]))
        except Exception:
            target_model = "models/gemini-1.5-flash"
                
        # 為了加快判斷速度與節省 token，只餵入前 800 字
        preview_text = content[:800]
        
        prompt = (f"請判斷此內容是否與主題 '{topic}' 具有研究價值與高度相關性？\n"
                  f"如果是通用的行事曆、放假資訊或無意義的廣告導購，請回傳 REJECT。\n"
                  f"只要內容具備與主題相關的數據、分析、趨勢、或任何實質深度資訊，請回傳 ACCEPT。\n\n"
                  f"文字片段：\n{preview_text}")
                  
        fallback_chain = self._get_fallback_chain(prefer_flash=True)
        result_text = ""
        
        for target_model in fallback_chain:
            model = genai.GenerativeModel(
                model_name=target_model,
                system_instruction="你是一個資料過濾員，任務是嚴格驗證文章內容與主題的相關性。你只能回傳 'ACCEPT' 或 'REJECT'，不能包含任何其他廢話。"
            )
            try:
                response = model.generate_content(prompt)
                result_text = response.text.strip().upper()
                break # 成功
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg:
                    match = re.search(r'please retry in (\d+\.?\d*)s', error_msg)
                    if match:
                        wait_t = float(match.group(1)) + 1
                        if wait_t < 40:
                            print(f"    [!] {target_model} 頻率限制 (內容驗證)，冷靜等待 {wait_t:.1f} 秒...")
                            time.sleep(wait_t)
                            try:
                                response = model.generate_content(prompt)
                                result_text = response.text.strip().upper()
                                break
                            except Exception:
                                continue
                        else:
                            continue
                    else:
                        continue
                else:
                    continue
            
        if "ACCEPT" in result_text:
            return True
        else:
            return False

    def run_scraping_task(self, queries: list, topic: str = "未提供主題"):
        """
        接收一個搜尋詞列表，對每個詞進行搜尋、抓取內文，加入語義判斷後存檔。
        """
        if not queries:
            print("提供的查詢列表為空。")
            return

        for idx, query in enumerate(queries, start=1):
            print(f"\n--- 開始處理第 {idx}/{len(queries)} 個關鍵字: '{query}' ---")
            
            # 1. 搜尋
            search_results = self.search_web(query, topic)
            if not search_results:
                print(f"找不到 '{query}' 的相關結果，跳過此關鍵字。")
                continue

            # 準備該關鍵字的合併內文內容及紀錄標記
            aggregated_content = f"搜尋關鍵字: {query}\n\n"
            has_content_added = False

            # 2. 爬文
            for res_idx, result in enumerate(search_results, start=1):
                title = result["title"]
                href = result["href"]
                print(f"  > 嘗試抓取第 {res_idx} 篇: {title} ({href})")
                
                content = self.fetch_content(href)
                
                # 如果沒有抓取到內容，顯示提示並略過
                if not content.strip():
                    print(f"    -> 警告: 無法讀取內容或內容為空")
                    continue
                
                # 語義判斷：如果有關連才放入 merged_content
                print(f"    -> 正在評估內容與 '{topic}' 的相關性...")
                is_relevant = self.check_relevance(topic, content)
                
                if not is_relevant:
                    print(f"    -> 判斷結果: [無關] (可能是雜訊/行事曆)，已被剔除。")
                    continue
                else:
                    print(f"    -> 判斷結果: [相關] 成功收錄！")
                
                # 將內容合併進變數中
                aggregated_content += f"=== 結果 {res_idx}: {title} ===\n"
                aggregated_content += f"來源網址: {href}\n\n"
                aggregated_content += content + "\n\n"
                has_content_added = True
            
            # 如果整串搜尋都沒抓到符合的內容，就不存檔
            if not has_content_added:
                print(f"!!! 此關鍵字 '{query}' 之下未能抓到具相關分析價值的內容，略過存檔。")
                continue
            
            # 3. 檔名生成與存檔
            # 清理檔名可能的非法字元 (簡易處理)
            safe_filename = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in query)
            file_path = os.path.join(self.raw_data_dir, f"{safe_filename}.txt")
            
            try:
                # 使用 utf-8 寫入以解決中大文字與特殊符號的問題
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(aggregated_content)
                print(f"✓ 成功儲存 '{query}' 的爬取結果至: {file_path}")
            except Exception as e:
                print(f"寫入檔案時發生錯誤 ({file_path}): {e}")

if __name__ == "__main__":
    # 簡單的測試執行
    test_queries = [
        "2026 固態電池 商業化 進展",
        "固態電池 技術瓶頸 2026"
    ]
    scraper = ResearchScraper()
    scraper.run_scraping_task(test_queries, topic="2026固態電池")
