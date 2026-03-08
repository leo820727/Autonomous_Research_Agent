import sys
import os

# 確保當前腳本所在的目錄一定在 sys.path 之中，避免在不同目錄下執行時找不到 planner/scraper
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from planner import generate_plan
    from scraper import ResearchScraper
    from reporter import generate_report
except ImportError as e:
    print(f"=== [錯誤] 匯入模組失敗 ===", flush=True)
    print(f"錯誤訊息: {e}", flush=True)
    print("請確保 planner.py、scraper.py 和 reporter.py 在同一個資料夾，", flush=True)
    print("且您已經安裝了套件：pip install google-generativeai duckduckgo-search newspaper3k", flush=True)
    sys.exit(1)

if __name__ == "__main__":
    # 在最一開始就先 print 提示，確保終端機有反應
    print("=== 系統啟動中 ===", flush=True)
    
    # 確保路徑完全正確：自動建立 raw_data 資料夾（依據當下 this file 所在目錄）
    raw_data_dir = os.path.join(current_dir, "raw_data")
    if not os.path.exists(raw_data_dir):
        os.makedirs(raw_data_dir, exist_ok=True)
        print(f"已自動建立資料夾: {raw_data_dir}", flush=True)

    print("\n=== Autonomous Research Agent ===", flush=True)
    # 主動詢問使用者
    try:
        topic = input("請輸入研究主題：").strip()
    except Exception as e:
        print(f"\n讀取輸入時發生錯誤: {e}", flush=True)
        sys.exit(1)
        
    if not topic:
        print("未輸入主題，程式即將關閉。", flush=True)
        sys.exit(0)

    # 執行任務 1: Planner
    print(f"\n[步驟一] 正在生成計畫... (為 '{topic}' 規劃搜尋詞)", flush=True)
    try:
        queries = generate_plan(topic)
    except Exception as e:
        print(f"生成計畫階段發生錯誤: {e}", flush=True)
        sys.exit(1)

    if not queries:
        print("沒有成功拿到任何關鍵字，請檢查 API 設定。", flush=True)
        sys.exit(1)

    print("\n[生成計畫成功] 以取得以下 5 個關鍵字：", flush=True)
    for idx, q in enumerate(queries, start=1):
        print(f"  {idx}. {q}", flush=True)

    # 執行任務 2: Scraper
    print("\n[步驟二] 正在搜尋網頁並抓取內容... (這可能需要一點時間)", flush=True)
    try:
        scraper = ResearchScraper(raw_data_dir="raw_data")
        
        # 完整串接：把剛才 Planner 的結果 (queries) 還有 topic 丟給 scraper 的這個方法
        scraper.run_scraping_task(queries, topic)
        
        print("\n[抓取成功] 網頁爬取作業已順利結束！內容已存至 raw_data 資料夾下。", flush=True)
    except Exception as e:
        print(f"抓取內文時發生不可預期的錯誤: {e}", flush=True)
        sys.exit(1)

    print("\n[步驟三] 正在將蒐集到的資料彙整為最終研究報告...", flush=True)
    try:
        # 清理 raw_data 中的無效空檔案或過小的檔案
        print("\n[清理階段] 正在檢查並刪除 raw_data 中的無效檔案...", flush=True)
        for f in os.listdir(raw_data_dir):
            if f.endswith('.txt'):
                file_path = os.path.join(raw_data_dir, f)
                try:
                    if os.path.getsize(file_path) < 50:
                        os.remove(file_path)
                        print(f"  -> 已刪除無效/空檔案: {f}", flush=True)
                    else:
                        with open(file_path, "r", encoding="utf-8") as txt_f:
                            content = txt_f.read()
                        # 檢查有沒有爬取到真實結果 (以 "=== 結果" 為標記)
                        if "=== 結果" not in content:
                            os.remove(file_path)
                            print(f"  -> 已刪除無實質內容的檔案: {f}", flush=True)
                except Exception as e:
                    print(f"  -> 檔案清理時發生錯誤 ({f}): {e}", flush=True)

        # 改以清理後的檔案為準
        txt_files = [f for f in os.listdir(raw_data_dir) if f.endswith('.txt')]
        if not txt_files:
            print("[跳過報告生成] 因為沒有在 raw_data 裡面找到任何抓取下來的內容。", flush=True)
        else:
            print(f"偵測到 {len(txt_files)} 份資料檔案，開始呼叫 Reporter...", flush=True)
            report_path = generate_report(raw_data_dir, topic, output_dir=current_dir)
            if report_path:
                print(f"\n[任務大功告成] 自動化研究代理人順利產出報告: {report_path}", flush=True)
            else:
                print("\n[警告] Reporter 沒有順利寫出報告檔案。", flush=True)
    except Exception as e:
        print(f"生成報告階段發生錯誤: {e}", flush=True)

    print("\n=== 所有腳本任務已執行完畢 ===", flush=True)
