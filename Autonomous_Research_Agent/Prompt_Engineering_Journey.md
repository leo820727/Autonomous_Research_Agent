# AI Prompt Engineering Journey: Autonomous Research Agent
**AI 提示詞工程進化史：全自動分析代理人專案**

---

## 🌟 專案概述 (Project Overview)

**[中文]**
本專案的成功，並不僅僅是依賴 LLM 單一次的「萬能神諭」，而是透過**「迭代式提示詞工程 (Iterative Prompt Engineering)」**，像堆積木般將一個起初充滿錯誤、API 容易當機的基礎腳本，一步步精雕細琢成了具備商業價值（Business-Ready）的 SaaS 應用程式。以下節錄了我在開發過程中所使用的核心 Prompts（提示詞），藉以展示我如何透過精準的引導、對邊界案例（Edge Cases）的覺察，帶領 AI 模型從零到一建立流程、修正錯誤、建立防呆機制，最後完成跨平台的實戰部署。

**[English]**
The success of this project does not rely merely on a single "magic prompt" to an LLM. Instead, through **"Iterative Prompt Engineering"**, an initial, error-prone basic script was painstakingly sculpted into a Business-Ready SaaS application. Below are the core prompts used during development, demonstrating how precise guidance and awareness of edge cases led the AI model to build workflows from zero to one, correct errors, establish fail-safes, and finally deploy a cross-platform commercial product.

---

## 🛠 Phase 1: 從零到一的系統地基 (Foundation Construction: The Initial Spark)

**【目標 / Objective】：** 
**[中文]** 我需要 AI 幫我建構一個具備模組化、可擴展性的基礎專案架構，而不是全部塞在同一支凌亂的檔案裡。
**[English]** I needed the AI to build a modular, scalable foundational project architecture rather than stuffing everything into a single, messy script.

> **My Initial Prompt:**
> 「我想要建立一個『全自動化研究代理人 (Autonomous Research Agent)』。請使用 Python 與 Gemini API，流程如下：
> 1. 給予研究主題後，AI 先思考並生成 5 個關鍵字。
> 2. 將關鍵字丟給搜尋引擎，爬取網頁生資料儲存起來。
> 3. AI 統整所有爬下來的生資料，撰寫出一份深度的 Markdown 研究報告。
> 請幫我將程式碼『模組化 (Modularize)』，拆分成 planner.py (規劃)、scraper.py (抓取)、reporter.py (撰寫) 以及一支用來執行的 main.py。」

**【Prompt 技巧展現 / Prompting Skills Highlight】：**
* **[中文] 架構思維先決 (Architecture-First Thinking)**：一開始就強勢主導了程式的「模組化結構 (Modular Design)」，限制 AI 的輸出必須嚴格區分職責 (Separation of Concerns)，為後續的優化迭代打下極度健康的基礎。
* **[English] Architecture-First Thinking**: Dominating the "Modular Design" from the start. By restricting the AI's output to strictly separated duties (Separation of Concerns), it laid a healthy foundation for all future iterations and optimizations.

---

## 🛠 Phase 2: 突破搜尋瓶頸與「防幻覺」策略注入 (Breaking the Search Bottleneck & Anti-Hallucination Strategy)

**【目標 / Objective】：** 
**[中文]** 原先的爬蟲模組常抓到「行事曆」、「農民曆」或遇到高品質網站阻擋。我需要引導模型更換底層搜尋引擎，並實作一道「預審機制」。
**[English]** The original scraper often fetched irrelevant data like "calendars" or hit 403 blocks. I needed to guide the model to switch search engines and implement a "Pre-filtering mechanism".

> **My Prompt:**
> 「請徹底重構 scraper.py 的搜尋底層邏輯，棄用 duckduckgo_search，改用 Serper.dev (Google Search API)。實作智慧摘要過濾 (Snippet Filter)：先將這 10 筆結果的標題與摘要丟給 Gemini 進行『相關性打分 (0-100)』。如果是行事曆、農民曆、非產業分析內容，直接歸零。只對總分大於 75 分的網頁執行 fetch_content 抓全文。防禦機制：在抓取全文時，加入自定義的 User-Agent 模擬 Chrome，減少被阻擋機率。」

**【Prompt 技巧展現 / Prompting Skills Highlight】：**
* **[中文] 負面提示與閾值設定 (Negative Prompting & Thresholds)**：加入明確的 **反向表述 (Negative prompting)** (如：「行事曆直接歸零」)，對齊 AI 的判斷基準，並設定 **資源控制門檻** (打分>75 才爬文)，大幅節省 API 算力與網路成本。
* **[English] Negative Prompting & Thresholds**: Explicitly adding negative conditions ("calendars score zero") to align the AI's baseline, and setting resource thresholds (score > 75 to fetch) to drastically save API compute and network costs.

---

## 🛠 Phase 3: 解決 API 頻率限制與動態降級 (Rate Limit Avoidance & Dynamic Model Degradation)

**【目標 / Objective】：** 
**[中文]** 解決 Gemini API 報錯 429 (Quota Exceeded) 以及因「寫死模型名稱」導致的 404 Error 崩潰問題。
**[English]** Resolve Gemini API 429 (Quota Exceeded) errors and 404 crash issues caused by hardcoding model names.

> **My Prompt:**
> 「我的程式在呼叫 Gemini 1.5 pro 時依然報錯 404 或 429... 請幫我修正 planner, scraper 和 reporter 所有檔案：
> 加入一段代碼自動尋找正確且可用的模型名稱 (`genai.list_models()`)，絕對不能寫死。
> 狀態控制：能不能讓他每次都選用目前有配額的模型？如果遇到首選沒餘額，必須自動往下降級尋找替代方案並重試。」

**【Prompt 技巧展現 / Prompting Skills Highlight】：**
* **[中文] 高可用性系統思維 (High-Availability System Mindset)**：要求 AI 實現 **環境動態感知 (Environment Sensing)** 並建構「瀑布流降級備援鏈 (Waterfall Fallback)」，確保無論配額如何變動，程式的可靠性能接住不可控的網路錯誤。
* **[English] High-Availability System Mindset**: Forcing the AI to implement "Environment Sensing" and construct a "Waterfall Fallback Chain". This guarantees system reliability to catch uncontrollable network errors regardless of quota fluctuations.

---

## 🛠 Phase 4: 多租戶雲端部署與沙盒隔離 (Multi-Tenant Cloud UX & Sandbox Isolation)

**【目標 / Objective】：** 
**[中文]** 將純後端腳本，轉換為安全的商業 SaaS 介面，保護開發者的 API 機密，並避免多位客戶同時使用導致的伺服器檔案覆寫問題。
**[English]** Transform backend scripts into a secure commercial SaaS UI, protecting API secrets and avoiding server file overwrite issues caused by simultaneous multi-client usage.

> **My Prompt:**
> 「如果這個東西要給真正的客戶使用，實際要怎麼做？客戶也不能綁定使用我的 API。另外，目前所有的 Markdown 報告和生資料會互相覆蓋存到我本機的 raw_data 裡面，如果是發佈出去給多位客戶同時使用呢？」

**【Prompt 技巧展現 / Prompting Skills Highlight】：**
* **[中文] 目標受眾導向與邊界案例察覺 (Audience Alignment & Edge-Case Intuition)**：刻意不給技術解法（如要求用 React），而是以產品經理視角詢問最佳實務。這激發了 AI 導入 `Streamlit` 的 BYOK（客戶自帶金鑰）模式，並帶出了 `tempfile` 「閱後即焚沙盒機制」，完美實現多租戶 (Multi-tenant) 的雲端架構。
* **[English] Audience Alignment & Edge-Case Intuition**: Approaching the LLM with a Product Manager's perspective rather than dictating technical stacks. This prompted the AI to introduce Streamlit's BYOK (Bring Your Own Key) UX and the `tempfile` "burn-after-reading sandbox mechanism", perfectly realizing a reliable multi-tenant cloud architecture.

---

## 🛠 Phase 5: 切中商業痛點的格式轉換 (The Last Mile: Enterprise Format Exporting)

**【目標 / Objective】：** 
**[中文]** 企業 B2B 客戶不熟悉 Markdown 工程師用語格式，他們需要可以直接放進會議增刪修改的 Word 文件檔。
**[English]** Enterprise B2B clients are unfamiliar with Markdown. They require editable Word documents for corporate meetings.

> **My Prompt:**
> 「目前是生成一個 Markdown 檔，但交給企業客戶，是不是應該自動給他一個 Word (.docx) 檔案比較好？」

**【Prompt 技巧展現 / Prompting Skills Highlight】：**
* **[中文] 產品化同理心轉折 (Productization Empathy)**：用最簡短卻直擊痛點的對話，促使 AI 捨棄不穩定的開源轉換工具 (如 pandoc 套件相容問題)，改為親自開發出純淨的 `export.py` 工具。原生將多層級標題、列表完美轉換為 Word 檔案，達成落地的商業價值。
* **[English] Productization Empathy**: With a brief, insightful prompt focusing on user intent, the AI was compelled to abandon flaky open-source wrappers and custom-build an `export.py` tool. This natively parses Markdown elements into pristine Word files for corporate utilization, crossing the last mile of commercial value.

---

## 💡 總結 (Conclusion)

**[中文]**
這個專案證明了，一位優秀的 AI Prompt Engineer 價值不在於「一次生成完美無缺的 Code」，而是在遭遇不斷的 Error 與實務阻礙時的「引導力」。透過：
1. **解構問題 (Deconstruction)**
2. **抽象化防呆設計 (Defensive Design)**
3. **商業營運收斂 (Commercial Convergence)**
這些層層推進的 Prompt，才得以將粗糙的文字模型，轉化為具備高容錯、良好 UX 的自動化軟體資產。

**[English]**
This project proves that the true value of an elite AI Prompt Engineer does not lie in "generating perfect code on the first try". It relies entirely on the **"Guidance Power"** when facing relentless errors and practical bottlenecks. Through:
1. **Problem Deconstruction**
2. **Abstract Defensive Design**
3. **Commercial Convergence**
These progressively stacked prompts are the true catalyst that forged a raw language model into a highly-tolerant, UX-friendly automated software asset.
