import os
import sys
import io
import tempfile
import streamlit as st
import time
from contextlib import redirect_stdout

# 確保可以載入同目錄下的模組
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from planner import generate_plan
from scraper import ResearchScraper
from reporter import generate_report
from export import markdown_to_docx

# 設定網頁標題與寬度
st.set_page_config(page_title="Deep Research AI 助理", layout="wide")

st.title("🤖 Deep Research AI 分析助理")
st.markdown("輸入你的研究主題，AI 將自動為您拆解關鍵字、跨網搜尋、過濾內容並產出深度報告。")

# --- 側邊欄：API 金鑰設定 ---
with st.sidebar:
    st.header("🔑 API 金鑰設定")
    st.markdown("請在下方輸入您的 API 金鑰。系統為求安全，金鑰**僅在本次連線中使用**，我們絕對不會將其儲存於伺服器上。")
    
    with st.expander("💡 不知道如何獲取 API 金鑰？（點我查看教學）"):
        st.markdown("""
        **1. 獲取 Gemini API 金鑰 (完全免費)**
        - 前往 [Google AI Studio](https://aistudio.google.com/app/apikey)
        - 登入您的 Google 帳戶並點擊 `Create API key` 以建立新金鑰。
        
        **2. 獲取 Serper.dev API 金鑰 (註冊即送免費額度)**
        - 前往 [Serper.dev](https://serper.dev/) 註冊帳號
        - 登入後進入 Dashboard，您會免費獲得 **2,500 次** 企業級搜尋額度，直接複製 API Key 即可使用！
        """)
    
    st.divider()
    
    gemini_key = st.text_input("Gemini API Key", type="password", placeholder="AIzaSy...")
    serper_key = st.text_input("Serper.dev API Key", type="password", placeholder="2a0b...")
    
    if st.button("儲存金鑰"):
        if gemini_key and serper_key:
            os.environ["GEMINI_API_KEY"] = gemini_key
            os.environ["SERPER_API_KEY"] = serper_key
            st.success("金鑰已暫存於環境中！")
        else:
            st.error("請填寫完整的金鑰！")

# --- 主畫面：搜尋與執行 ---
topic = st.text_input("🎯 請輸入您的研究主題", placeholder="例如：2026 台灣 AI 伺服器未來趨勢分析")

# 初始化 session state
if 'research_done' not in st.session_state:
    st.session_state.research_done = False
if 'report_content' not in st.session_state:
    st.session_state.report_content = None
if 'docx_bytes' not in st.session_state:
    st.session_state.docx_bytes = None

if st.button("🚀 開始深度研究"):
    if not os.getenv("GEMINI_API_KEY") or not os.getenv("SERPER_API_KEY"):
        st.error("⚠️ 請先於左側欄位輸入並儲存您的 API 金鑰！")
    elif not topic:
        st.warning("⚠️ 請輸入研究主題！")
    else:
        st.info("系統開始運行，這可能需要幾分鐘的時間，請不要關閉或刷新網頁...")
        
        # 清空上一次的記錄
        st.session_state.research_done = False
        st.session_state.report_content = None
        st.session_state.docx_bytes = None
        
        # UI 狀態展示容器
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                session_raw_dir = os.path.join(temp_dir, "raw_data")
                os.makedirs(session_raw_dir, exist_ok=True)
                
                dummy_stdout = io.StringIO()
                with redirect_stdout(dummy_stdout):
                    
                    # [步驟一]
                    status_text.text("[1/3] 正在拆解研究主題並生成子關鍵字...")
                    queries = generate_plan(topic)
                    progress_bar.progress(15)
                    
                    if not queries:
                        st.error("❌ 無法生成搜尋計畫，請檢查 Gemini API 是否正常。")
                        st.stop()
                        
                    # [步驟二] 
                    status_text.text(f"[2/3] 正在透過 Serper.dev 掃描並篩選 {len(queries)} 個關鍵字的網頁資料...")
                    scraper = ResearchScraper(raw_data_dir=session_raw_dir)
                    scraper.run_scraping_task(queries, topic)
                    progress_bar.progress(65)
                    
                    for f in os.listdir(session_raw_dir):
                        if f.endswith('.txt'):
                            file_path = os.path.join(session_raw_dir, f)
                            if os.path.getsize(file_path) < 50:
                                os.remove(file_path)
                    
                    txt_files = [f for f in os.listdir(session_raw_dir) if f.endswith('.txt')]
                    if not txt_files:
                        st.error("❌ 搜尋引擎未抓取到任何符合標準的網頁內容。")
                        st.stop()
                        
                    # [步驟三] 
                    status_text.text("[3/3] 正在將數萬字的網頁資料彙整為最終 Markdown 報告...")
                    report_path = generate_report(session_raw_dir, topic, output_dir=temp_dir)
                
                # ==== 脫離攔截區塊 ====
                progress_bar.progress(100)
                status_text.text("✅ 所有任務執行完畢！")
                
                if report_path and os.path.exists(report_path):
                    st.snow()
                    
                    with open(report_path, "r", encoding="utf-8") as f:
                        st.session_state.report_content = f.read()
                    
                    # 生成 Word 報告供下載
                    safe_topic = "".join(x for x in topic[:10] if x.isalnum() or x in " _-")
                    docx_path = os.path.join(temp_dir, f"DeepResearch_{safe_topic}.docx")
                    markdown_to_docx(st.session_state.report_content, docx_path)
                    
                    with open(docx_path, "rb") as f:
                        st.session_state.docx_bytes = f.read()
                        
                    # 標記完成
                    st.session_state.research_done = True
                else:
                    st.error("❌ 報告生成失敗。")

        except Exception as e:
            st.error(f"執行過程中發生錯誤：{e}")

# --- 顯示已生成的報告 (這段獨立於 Button 判斷外，確保頁面重整不會消失) ---
if st.session_state.get('research_done') and st.session_state.get('report_content'):
    st.success("🎉 研究報告產出成功！請見下方結果：")
    
    st.write("#### 📑 選擇您的下載格式：")
    col1, col2 = st.columns(2)
    safe_topic = "".join(x for x in topic[:10] if x.isalnum() or x in " _-")
    
    with col1:
        st.download_button(
            label="📥 下載 Word 報告 (.docx)",
            data=st.session_state.docx_bytes,
            file_name=f"DeepResearch_{safe_topic}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )
    with col2:
        st.download_button(
            label="📥 下載 Markdown 原始檔 (.md)",
            data=st.session_state.report_content,
            file_name=f"DeepResearch_{safe_topic}.md",
            mime="text/markdown",
            use_container_width=True
        )
        
    st.markdown("---")
    st.markdown(st.session_state.report_content)
