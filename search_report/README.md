# Stock Report Search System

Hệ thống tự động tìm kiếm các báo cáo tài chính (Integrated Reports & Corporate Governance Reports) từ nhiều nguồn khác nhau cho các công ty niêm yết trên sàn chứng khoán Nhật Bản.

## 📋 Tổng Quan

```mermaid
graph TB
    A[Input: Stock Code 6920.T] --> B{Report Type}
    
    B -->|Integrated Report| C_IR[Search IR]
    B -->|Governance Report| C_GOV[Search Governance Report]
    
    C_IR --> D[Company Website]
    D --> D5[Automation BOT]
    D --> D1[SearXNG Search + LLM Validation]
    
    C_GOV --> C2[Company Site]
    C_GOV --> C3[Nikkei Site]
    C_GOV --> C4[JPX Site]
    
    C2 --> D5
    C2 --> D1
    
    C3 --> D1
    C4 --> D4[Playwright Scraper]
    
    D1 --> E[Normalize Results]
    D4 --> E
    D5 --> E
    
    
    E --> G[Select Latest Report]
```

## 🎯 Chức Năng Chính

### 1️⃣ **Search On Company Site**
Tìm kiếm báo cáo trực tiếp trên website của công ty

**Input:**
- Stock code (e.g., `"6920.T"`)
- Search keyword (e.g., `"integrated report"`, `"corporate governance report"`)

**Steps:**
1. Fetch company name & website từ yfinance
2. Tạo search query: `site:{domain} {keyword} filetype:pdf`
3. Gọi SearXNG để tìm kiếm
4. Sử dụng LLM validate và filter kết quả tốt nhất
5. Extract date & URL từ best result

**Output:**
```json
{
  "url": "https://example.com/report.pdf",
  "detected_date": "2024-05-15"
}
```

**Functions:**
- `on_company_site_search()` - Search 1 stock code
- `on_company_site_search_save_evaluate()` - Search & save danh sách

**Files:** `search_on_company_site.py`

---

### 2️⃣ **Search On Nikkei**
Tìm kiếm báo cáo từ Nikkei TDNET database

**Input:**
- Stock code (e.g., `"6920.T"`)
- Company name (e.g., `"Lasertec Corporation"`)

**Steps:**
1. Fetch company name từ yfinance
2. Tạo search query: `site:www.nikkei.com/markets/ir/irftp/data/tdnr/tdnetg3 CORPORATE GOVERNANCE {company_name} filetype:pdf`
3. Gọi SearXNG để tìm kiếm
4. Sử dụng LLM validate và filter kết quả tốt nhất
5. Extract date & URL từ best result

**Output:**
```json
{
  "url": "https://www.nikkei.com/markets/.../report.pdf",
  "detected_date": "2024-03-20"
}
```

**Functions:**
- `nikkei_governance_search()` - Search 1 stock code
- `nikkei_governance_search_save_evaluate()` - Search & save danh sách

**Files:** `search_on_nikkei.py`

---

### 3️⃣ **Search On JPX**
Tìm kiếm báo cáo từ Japan Exchange Group database (Playwright Scraper)

**Input:**
- Stock code (e.g., `"6920.T"`)

**Steps:**
1. Launch Playwright browser
2. Navigate tới JPX website: `https://www2.jpx.co.jp/tseHpFront/JJK020030Action.do`
3. Input stock code vào search form
4. Click "Search" button
5. Click "Basic information" button
6. Click "Corporate governance" tab
7. Extract Japanese governance table
8. Parse PDF link & date từ table rows
9. Return latest entry

**Output:**
```json
{
  "date": "2024/05/15",
  "pdf_url": "https://www2.jpx.co.jp/...report.pdf"
}
```

**Classes & Methods:**
- `JPXGovernanceScraper` class
  - `get_latest_governance(stock_code)` - Get latest governance PDF for 1 stock
  - `_search_stock()` - Step 3-4
  - `_open_basic_information()` - Step 5
  - `_open_governance_tab()` - Step 6
  - `_get_japanese_governance_table()` - Step 7
  - `_extract_latest_row()` - Step 8-9

**Functions:**
- `jpx_governance_search_save_evaluate()` - Search & save danh sách

**Files:** `search_on_jpx.py`

---

### 4️⃣ **Search Combine**
Kết hợp kết quả từ 3 nguồn, chọn báo cáo mới nhất

**Flow:**
```mermaid
graph TB
    A[Stock Code] --> B["Search Source 1: Company Site"]
    A --> C["Search Source 2: Nikkei"]
    A --> D["Search Source 3: JPX"]
    
    B --> E[Normalize Results]
    C --> E
    D --> E
    
    E --> F["Parse Dates"]
    F --> G["Compare & Select Latest"]
    G --> H["Return Best Result"]
```

**Key Features:**
- Tự động fetch thông tin từ yfinance
- So sánh ngày tháng từ các nguồn
- Chọn báo cáo mới nhất

**Files:** `search_combine.py`

---

### 5️⃣ **Search Fallback**
Tìm kiếm báo cáo với chiến lược fallback: JPX → Company Site → Nikkei

**Flow:**
```mermaid
flowchart TD
    A["Start: Search Governance Report"]
    
    A --> B["1. JPX Search"]
    B --> B1{Is PDF?}
    B1 -->|Yes| G["✅ Return URL + Date<br/>Source: JPX"]
    B1 -->|No/Fail| C["2. Company Site Search"]
    
    C --> C1{Is PDF?}
    C1 -->|Yes| G
    C1 -->|No/Fail| D["3. Nikkei Search"]
    
    D --> D1{Is PDF?}
    D1 -->|Yes| G
    D1 -->|No/Fail| H["❌ Return None<br/>All sources failed"]
    
    G --> I["Save to CSV"]
    H --> I
```

**Chiến lược:**
1. **Ưu tiên JPX** - Tìm trên JPX trước (date chính xác nhất)
2. **Fallback Company Site** - Nếu JPX fail/not PDF, thử Company Site
3. **Fallback Nikkei** - Nếu Company Site fail/not PDF, thử Nikkei
4. **Kết quả None** - Nếu tất cả fail, return None

**Key Features:**
- ✅ Tự động fetch info từ yfinance
- ✅ Kiểm tra PDF validation (chỉ nhận file .pdf)
- ✅ Capture date publication của report
- ✅ Lưu kết quả ngay lập tức (append mode)
- ✅ Xử lý lỗi gracefully

**Output CSV columns:**
- `stock_code` - Mã chứng chỉ (e.g., "6920.T")
- `company_name` - Tên công ty
- `url` - PDF URL
- `source` - Nguồn tìm được ('jpx', 'company_site', 'nikkei')
- `report_date` - Ngày publication của report
- `success` - True/False
- `error_message` - Thông báo lỗi (nếu có)

**Functions:**
- `search_governance_fallback()` - Search 1 stock code
- `search_governance_fallback_batch()` - Search & save danh sách

**Files:** `search_governance_fallback.py`

---

### 6️⃣ **Automation Bot**
Bot tự động duyệt web tìm báo cáo bằng LLM

**Flow:**
```mermaid
graph LR
    A[Start URL] --> B[Crawl Page]
    B --> C[Extract Links]
    C --> D["LLM Analysis"]
    D --> E{Found PDF?}
    E -->|Yes| F["Return PDF URL"]
    E -->|No| G[Select Next URL]
    G --> B
```

**Tính năng:**
- LLM phân tích links
- Tự động theo dõi cycle (không lặp lại URLs)
- Max iterations = 5 để tránh vô hạn loop
- Validation PDF trước khi return

**Files:** `automation_bot.py`

---


