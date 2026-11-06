# AffecCare MCP (Model Context Protocol) 架構設計與實作規劃

本文件記錄 AffecCare EAP 平台加入 Model Context Protocol (MCP) 功能的整體架構規範、安全隔離設計、傳輸協定與工具清單。

---

## 1. 架構概述與目標

AffecCare 後端（獨立部署於 `affeccare-api.sk5s.org`）將在 `/mcp` 端點提供符合最新 MCP 規範的遠端服務，讓企業 HR 與一般員工能夠透過各類 AI Agent（例如 Claude Desktop、Cursor、企業專屬 Agent 等）安全地操作平台功能。

### 核心原則
1. **無狀態 Streamable HTTP (Stateless)**：採用最新的單一 `POST /mcp` 端點，每個請求直接返回 `application/json`（JSON-RPC 2.0），`GET` 回傳 `405 Method Not Allowed`。不佔用持續長連線，完美相容現有 Gunicorn 同步執行緒架構。
2. **零重複業務邏輯 (Adapter Pattern)**：MCP 層作為協定適配層，直接複用現有 `app/services/*`（CMS、推薦系統、收件匣、EAP 諮詢工單等）。
3. **強制角色與資料邊界隔離 (Strict RBAC & ABAC)**：
   - HR 與員工具有完全隔離的工具集。
   - `tools/list` 依權限動態遮蔽非所屬工具（避免 Prompt 膨脹與盲猜攻擊）。
   - `tools/call` 強制執行身分與資料屬主檢查（防範 IDOR 越權存取）。
   - 恪守 EAP 隱私防護，HR 僅能存取去識別化或聚合後之洞察資料。

---

## 2. 通訊協定與傳輸架構

### 端點設計
* **URL**: `POST https://affeccare-api.sk5s.org/mcp`
* **Headers**:
  * `Authorization: Bearer <JWT_or_OAuth_Token>`
  * `Content-Type: application/json`
* **支援的 JSON-RPC 2.0 方法**:
  1. `initialize`: 協商協定版本與 capabilities（支援 tools）。
  2. `notifications/initialized`: 客戶端確認初始化完成。
  3. `ping`: 心跳檢測，回應 `{}`。
  4. `tools/list`: 依據呼叫者 Token 角色回傳可用工具清單與 JSON Schema。
  5. `tools/call`: 執行具體工具，驗證角色、解析參數並調用後端 Service。
* **GET 請求行為**:
  * `GET /mcp` 直接回傳 `405 Method Not Allowed`，告知本端點支援無狀態 Streamable HTTP POST。

---

## 3. 身分驗證機制 (Authentication)

* **標準 Bearer 驗證**：除 `initialize` 外，所有 `/mcp` 請求均須透過 HTTP Header `Authorization: Bearer <token>` 傳遞（`initialize` 允許未認證請求以支援協定版本與 capabilities 探索）。
* **雙軌認證支援**：
  1. **OAuth 2.0 端點支援**：
     - 提供 `/api/oauth/authorize` 與 `/api/oauth/token`（支援 Authorization Code + PKCE 流程），供支援標準 OAuth 的外部 AI Agent 透過彈出視窗完成登入。
     - **Open Redirect 防護**：`redirect_uri` 實施嚴格白名單校驗，目前開放：
       - 本機開發與 MCP 客戶端：`localhost` / `127.0.0.1`（HTTP/HTTPS，任意 port）
       - 外部 AI Agent：`https://claude.ai/*`、`https://chatgpt.com/*`
     - **授權碼單次使用 (One-time use) 防重放**：授權碼寫入資料庫 `oauth_authorization_codes` 表，兌換後立即標記失效。
  2. **Personal Access Token (PAT) / JWT 支援**：
     - 相容現有 JWT Token 格式（包含 `user_id`, `role`, `exp`），供終端配置（如 `claude_desktop_config.json`）直接使用。

---

## 4. 權限與工具清單 (Tool Catalog)

### A. HR 工具群 (`role: hr`)

| 工具名稱 (`name`) | 職責與描述 | 底層對應 Service / Route |
| :--- | :--- | :--- |
| `hr_retrain_recommendation_model` | **訓練推薦模型**：重新從員工反應紀錄計算使用者特徵向量，並清除推薦快取。 | `app.services.vector_updater.rebuild_all_vectors` + `app.services.recommendation.invalidate_recommendation_model` |
| `hr_get_model_training_status` | 查詢推薦模型狀態（最後訓練時間、反應總數、準確度、參與率）。 | `app.routes.hr_actions._format_relative_time` 與相關指標聚合 |
| `hr_get_macro_insights` | 取得部門層級宏觀身心健康洞察與壓力維度指標（去識別化/聚合）。 | `app.services.hr_dashboard` |
| `hr_list_articles` | 搜尋與分頁查詢系統中的所有文章與狀態。 | `app.services.cms.list_articles` |
| `hr_get_article` | 取得單一文章完整內容、標籤與點擊成效統計。 | `app.services.cms.get_article` + `get_article_stats` |
| `hr_create_article` | 建立新 EAP 文章（標題、內文、標籤、狀態 draft/published）。 | `app.services.cms.create_article` |
| `hr_update_article` | **更新現有文章**（編輯內容、更新分類標籤或修改發佈狀態）。 | `app.services.cms.update_article` |
| `hr_delete_article` | 刪除或下架指定文章。 | `app.services.cms.delete_article` |
| `hr_broadcast_push` | 觸發推薦系統批次推播至員工收件匣。 | `app.routes.hr_actions.push_recommendations` |
| `hr_list_support_tickets` | 取得員工心理諮詢與支援工單列表。 | `app.models.pg_models.SupportTicket` 查詢 |
| `hr_reply_support_ticket` | 回覆員工諮詢工單。 | `app.routes.support.reply_ticket` |
| `hr_close_support_ticket` | 結案指定諮詢工單。 | `app.routes.support.close_ticket` |

---

### B. 員工工具群 (`role: employee`)

> **注意**：依業務需求，目前**不開放**員工透過 MCP 主動取得推薦文章。推薦內容一律由系統推播至員工收件匣。

| 工具名稱 (`name`) | 職責與描述 | 安全限制 (IDOR 防護) |
| :--- | :--- | :--- |
| `employee_get_inbox` | 取得個人收件匣訊息（支援僅查未讀）。 | 強制以 Token 中的 `user_id` 查詢，禁止傳入他人 ID。 |
| `employee_mark_inbox_read` | 將指定收件匣訊息標記為已讀。 | 必須校驗該訊息確實屬於當前 `user_id`。 |
| `employee_get_saved_messages` | **取得已收藏/儲存的收件匣訊息清單**（含完整訊息內文）。 | 僅能查詢當前 `user_id` 收藏的項目。 |
| `employee_save_inbox_message` | 收藏/儲存指定訊息至個人清單。 | 必須校驗訊息所屬權。 |
| `employee_unsave_inbox_message` | 取消收藏指定訊息。 | 必須校驗訊息所屬權。 |
| `employee_submit_feedback` | 對文章提交回饋（按讚/倒讚/評分），自動微調個人偏好向量並累積點數。 | 自動記錄當前 `user_id` 的反應。 |
| `employee_create_support_ticket` | 提出新的員工諮詢/EAP 協助請求。 | 綁定當前 `user_id` 建立工單。 |
| `employee_get_my_tickets` | 查看自己提出的諮詢工單進度與 HR 回覆。 | 僅過濾當前 `user_id` 的工單。 |

---

## 5. 安全與防護規範

1. **參數注入防護**：員工工具的 Schema 不提供 `user_id` 參數，後端由驗證通過的 Token 自動注入上下文，杜絕越權。
2. **錯誤處理 (Error Codes & Formats)**：
   - **協定層錯誤 (JSON-RPC Error Codes)**：
     - 未認證或 Token 過期：回傳 JSON-RPC code `-32001` (Unauthorized) 搭配 HTTP 401。
     - JSON 解析錯誤：回傳 JSON-RPC code `-32700` (Parse error)。
     - 請求結構無效：回傳 JSON-RPC code `-32600` (Invalid Request)。
     - 不支援的 MCP 方法：回傳 JSON-RPC code `-32601` (Method not found)。
     - 方法參數錯誤（如 tools/call 缺少 name）：回傳 JSON-RPC code `-32602` (Invalid params)。
   - **工具執行層錯誤 (MCP Tool Call Result)**：
     - 若工具執行失敗、參數驗證錯誤、或是該角色無權執行指定工具，依據 MCP 規範在 `result` 中回傳 `isError: true` 與對應錯誤訊息文字 `content: [{"type": "text", "text": "..."}]`。
3. **審計日誌 (Audit Logging)**：
   - 記錄所有工具呼叫：`[MCP] user={user_id} role={role} tool={name} status={success/fail}`。
