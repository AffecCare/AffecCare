# 後端安全弱點盤點報告 (Backend Security Findings)

> 範圍：`backend/` (Flask + SQLAlchemy + OAuth 2.0/MCP)。目標：RCE / 資料外洩。
> 驗證環境：本機 `testing` 設定，以 `app.test_client()` 與 PoC 腳本實測。

## 0. 總結

- **未發現直接的程式碼層 RCE**（無 `eval/exec/subprocess/pickle/yaml/marshal`、無檔案上傳、無反序列化不可信輸入）。
- **可達成 RCE/資料外洩的路徑**：
  1. **SSRF** (`oauth.py` CIMD 抓取) → 內網/雲端 metadata → 憑證外洩 → 可能 RCE。
  2. **OAuth 授權碼竊取** (open redirect，反斜線繞過) → 帳號接管 → 全部資料外洩。
  3. **弱/洩漏的 SECRET_KEY** → JWT 偽造 → 身分冒用。
  4. **`.env` 內含真實 DB 密碼** → 資料庫直接外洩。
- 其餘為權限/隱私/DoS 類弱點（見第 5 節）。

---

## 1. SSRF：CIMD metadata 抓取跟隨重新導向 (高)

**位置**：`backend/app/routes/oauth.py`
- `_is_safe_cimd_url()` (line ~70)：僅檢查「初始 URL」。
- `fetch_cimd_metadata()` (line ~151)：使用 `urllib.request.urlopen(req, timeout=3.0)`，**預設跟隨 HTTP 302 重新導向**，且未限制最終主機/IP。

**影響**：攻擊者把 `client_id` 設為合法 HTTPS URL（通過 `_is_safe_cimd_url`），該 URL 回 302 到 `http://127.0.0.1:...`、`http://169.254.169.254/...`（雲端 metadata）或任意內網服務，伺服器會把回應內容拉回並解析為 JSON。即使解析失敗，回應本體/錯誤訊息可能洩漏；對回傳 JSON 的內網管理 API 可取得資料。

**實測證據**（PoC）：
```
# 本機模擬：public /cimd -> 302 -> http://127.0.0.1:8766/secret
$ python poc
STATUS 200 URL http://127.0.0.1:8766/secret
BODY b'INTERNAL SECRET'
```
`urllib` 默默跟隨重新導向並取得內網回應，`_is_safe_cimd_url` 對重新導向目標無任何檢查。

**修復方向**：使用不跟隨重新導向的 opener（`urllib.request.build_opener(urllib.request.HTTPRedirectHandler` 覆寫 `redirect_request` 回 None，或用 `requests` 設 `allow_redirects=False`），並對「最終 URL」與每個中繼 URL 重跑 `_is_safe_cimd_url`/IP 檢查；同時封鎖 link-local (`169.254.0.0/16`)、loopback、private、reserved、unspecified（目前 `is_private` 已涵蓋多數，但重新導向繞過）。

---

## 2. OAuth 授權碼竊取：反斜線 open redirect (高)

**位置**：`backend/app/routes/oauth.py` `is_allowed_redirect_uri()` (line ~300)。

**根因**：Python `urllib.parse.urlsplit` 不把 `\` 視為路徑分隔符，但瀏覽器 (WHATWG URL) 會把 `\` 正規化為 `/`，並把 `host\@domain` 解析 differently。結果：
- 輸入 `https://evil.com\@claude.ai/cb`：`urlsplit` 認為 hostname = `evil.com\@claude.ai`? 實測 `is_allowed_redirect_uri` 回 **True**（因為字串比對/endswith 邏輯）。
- 瀏覽器正規化後 origin = `https://evil.com`，authorization code 被送到攻擊者網域。

**實測證據**：
```
$ python: is_allowed_redirect_uri("https://evil.com\\@claude.ai/cb") -> True
$ node:    new URL("https://evil.com\\@claude.ai/cb").href
           -> https://evil.com/@claude.ai/cb   (origin = https://evil.com)
$ POST /oauth/authorize (redirect_uri=該值) -> 200
  redirect_url: https://evil.com\@claude.ai/cb?code=<AUTH_CODE>
  (瀏覽器導向後 code 送達 evil.com)
```
攻擊者取得 authorization code → 兌換 access token → 以受害者身分存取所有 API（收件匣、支援工單、HR 資料若受害者為 HR）→ 資料外洩。

**修復方向**：在 allowlist 檢查前先以與瀏覽器一致的方式正規化（把 `\` 替換為 `/`、拒絕含 userinfo 的 URL、或直接用 `urllib.parse` 後再驗證 `netloc` 不含 `\`/`@`），並明確拒絕任何含 `\`、`@` 的 redirect_uri。建議白名單比對改為「hostname 完全相等」而非 `endswith`。

---

## 3. 弱/可預測的 SECRET_KEY 與 JWT 偽造 (高)

**位置**：`.env`（工作目錄）：
```
SECRET_KEY=your-secret-key-here
```
**位置**：`backend/app/services/auth.py` `generate_token`/`verify_token` 使用 `HS256` + `SECRET_KEY`。

**影響**：攻擊者知道預設字串即可自行簽發任意 `user_id`/`role` 的 JWT（含 `role=hr`/`admin`），通過 `@login_required` 與 MCP/OAuth 全部端點 → 身分冒用 → 資料外洩 / 管理操作。本機測試設定下 `SECRET_KEY` 為 `your-secret-key-here`，production 若未覆寫（或 `.env` 誤用）同樣成立。

**修復方向**：production 啟動時若 `SECRET_KEY` 缺失/為已知弱值則拒絕啟動（`validate_config` 已檢查缺失，但未檢查弱值）；輪換金鑰；縮短 token 有效期並加入 refresh token。

---

## 4. `.env` 明文資料庫憑證 (嚴重，營運)

**位置**：`backend/.env`（未進 git，但存在工作目錄）：
```
DATABASE_URL=postgresql://postgres:sCxmC31xSqzZ1CVayI8tJEmw7L1yngBjyed2mDkCa8FA40EY4Pw3W10h1mA886qp@162.35.105.101:31240/postgres
```
**影響**：任何人取得該檔案（備份、log、CI artifact、共享主機）即可直接連線 PostgreSQL → 全部資料外洩。另 `FLASK_CONFIG=development` 在本機以開發設定跑，`DEBUG=True` 可能暴露 traceback。

**修復方向**：立即輪換 DB 密碼；`.env` 不入版控（已 gitignore，確認 CI/備份也不含）；production 強制 `FLASK_CONFIG=production`。

---

## 5. 其他弱點

### 5.1 Token 黑名單 in-memory (中)
`app/services/auth.py:21` `_token_blacklist = set()`。多 worker / 重啟後已登出 token 復活（24h 有效期）。修復：Redis/DB + TTL，或短期 token + refresh token。

### 5.2 Host Header Injection (中)
`app/routes/oauth.py` `get_external_base_url()` 信任 `X-Forwarded-Host`。攻擊者可讓 OAuth metadata/redirect 指向惡意主機 → phishing / 授權碼導向。修復：白名單允許的 host。

### 5.3 活動日誌隱私邊界 (中)
`app/services/activity_log.py` `get_activity_logs()`：`if user_id:` 才過濾；若 `user_id` 為空/falsy，回傳**所有使用者**日誌。路由目前一律帶入 current_user，但任何未來呼叫/空值都會造成跨使用者資料洩漏。修復：強制要求 user_id，空值時拒絕而非全表。

### 5.4 角色提升：HR 可建立 admin 帳號 (中)
`app/services/auth.py` `hr_register_user()`：`role=data.get('role', 'employee')` 完全信任輸入；`/api/auth/register` 僅要求 hr/manager。HR 可建立 `role=admin`（若系統有 admin 特權）或任意角色。修復：白名單允許角色 + 僅 admin 可建 admin。

### 5.5 無速率限制 (中)
登入 / token / OAuth 端點無 rate limit → 暴力破解密碼/授權碼。修復：Flask-Limiter。

### 5.6 LIKE 萬用字元注入 (低)
`cms.py`/`activity_log.py` 將 `search` 直接拼入 `f'%{search}%'` 作為 LIKE pattern；SQL 注入不存在（參數化），但 `%`/`_` 可擴大匹配範圍 → 資料列舉。修復：escape LIKE wildcards。

### 5.7 `track_click` 信任前端 timestamp / 未驗證 article_id (低)
`app/routes/recommend.py` `track_click`：`timestamp` 完全信任前端字串；`article_id` 不驗證存在。資料完整性問題，非 RCE。

### 5.8 `per_page` 無上限 (低)
`list_articles` 可傳 `per_page=100000` → 記憶體/DoS。修復：上限（已部分限制 activity_log 100，cms 未）。

### 5.9 支援工單 category 不驗證 (低)
`support.py` `create_ticket` 不驗證 category 合法值。

---

## 6. 已檢查且未發現直接 RCE 的項目

- 無 `eval`/`exec`/`compile`/`__import__`/`runpy`/`importlib` 執行不可信輸入。
- 無 `subprocess`/`os.system`/`os.popen`/`pty`。
- 無 `pickle`/`marshal`/`yaml.load`/`json.loads(..., object_hook=...)` 反序列化不可信資料（JSON 解析使用標準 `json.loads`，無 object_hook）。
- 無檔案上傳端點 (`request.files`)、無 `send_file`/`send_from_directory`、無路徑拼接讀檔。
- 無 XML 解析 (`etree`/`lxml`/`fromstring`)。
- `render_template_string` 僅用固定 `LOGIN_TEMPLATE`，使用者輸入作為 context 變數且 Jinja autoescape 啟用 → 無 SSTI/XSS（但 `config.SECRET_KEY` 可被模板讀取，因 template 固定且不渲染使用者提供的模板，不可由攻擊者觸發；仍建議避免在模板暴露 config）。
- SQLAlchemy 全部使用 ORM/參數化查詢，無字串拼接 SQL（`sync_db.py` 的 f-string 僅拼接硬編碼常數）。

---

## 7. 建議優先順序

P0：輪換 DB 密碼與 SECRET_KEY；修復 SSRF 重新導向；修復反斜線 open redirect。
P1：JWT 偽造防護、Host 白名單、Token 黑名單持久化、活動日誌隱私邊界。
P2：速率限制、角色白名單、LIKE 萬用字元 escape、輸入驗證、per_page 上限。
P3：弱點掃描/依賴審計、Flask-Migrate、pytest 隔離測試。
