# 後端程式碼總體檢報告（Backend Code Review）

> 檢查範圍：`backend/` 目錄（config、app factory、8 個路由模組、7 個 service、7 支 scripts、資料模型）
> 檢查日期：2026-08-23

---

## 目錄

- [一、嚴重安全／隱私問題（需立刻修正）](#一嚴重安全隱私問題需立刻修正)
- [二、「未實作、只回傳固定結果」的地方](#二未實作只回傳固定結果的地方)
- [三、設計不合理的問題](#三設計不合理的問題)
- [四、建議修正優先順序](#四建議修正優先順序)

---

## 一、嚴重安全／隱私問題（需立刻修正）

### 1.1 資料庫帳密明文寫死並提交至 Git

**位置**：`backend/config.py:52-81`

- Neon 資料庫連線字串（含帳號密碼 `npg_E8YtPAK0aMrX...`）直接寫在程式碼中，且已提交至版本控制。
- 更嚴重的是：`DevelopmentConfig`、`TestingConfig`、`ProductionConfig` **三個環境全部指向同一個資料庫**，測試資料會直接污染正式資料。

**修正方向**：
1. 從 `config.py` 移除所有寫死的連線字串，改為 `os.environ.get('DATABASE_URL')` 且無預設值。
2. **立即更換已洩漏的 Neon 資料庫密碼**（就算移除程式碼，密碼仍留在 git 歷史中）。

### 1.2 /api/recommend 與 /api/track_click 無任何驗證

**位置**：`backend/app/routes/recommend.py:26, 67`

- 兩個端點皆未加上 `@login_required`。
- `/api/recommend` 的 `user_id` 由 query parameter 傳入，任何人皆可查詢**任何員工**的推薦結果。
- 推薦結果中包含 `turnover_risk_detected`（離職風險預測分數，見 `services/recommendation.py:93`），等於**無需登入即可取得全公司每位員工的離職風險預測**——這是極敏感的 HR 資料。
- `/api/track_click` 可偽造任何使用者的點擊紀錄，污染推薦系統與 HR 儀表板統計。

**修正方向**：
1. 兩個端點加上 `@login_required`。
2. `user_id` 改從 JWT token 取得（`request.current_user['user_id']`），不接受前端任意傳入。
3. 一般員工端的推薦結果**不應回傳** `turnover_risk_detected`，風險分數只應出現在 HR 端（並需 role 檢查）。

### 1.3 登出 Token 黑名單機制失效

**位置**：`backend/app/services/auth.py:21`

- `_token_blacklist = set()` 是 in-memory 集合：
  - gunicorn 多 worker 模式下各 process 不共享，只有處理該請求的 worker 認得黑名單。
  - 服務重啟即清空，已登出的 token 全部復活（token 效期 24 小時）。

**修正方向**：改用 Redis / DB 儲存黑名單（key 為 token 的 jti 或 hash，並設 TTL = token 剩餘效期）；或改用短期 token + refresh token 架構。

### 1.4 Production 入口預設載入 Development 設定

**位置**：`backend/app/__init__.py:91`、`backend/run.py:19`

- gunicorn 入口 `app = create_app()` 未指定 config 名稱，預設為 `development`（`DEBUG=True`）。
- 部署時若忘記設定 `FLASK_CONFIG=production`，等於帶著 Flask debug mode 上線（會暴露 traceback、原始碼與互動式除錯器）。

**修正方向**：正式環境入口應預設 `production` 並在缺少 `DATABASE_URL` 時直接拋錯拒絕啟動，而非靜默 fallback。

### 1.5 角色授權以硬編碼 email 決定

**位置**：`backend/scripts/import_employees.py:74`

```python
'role': 'hr' if user_email == 'william.larotonda@company.com' else 'employee',
```

- 匯入腳本以特定 email 硬編碫決定誰是 HR，任何人只要拿到這個 email 的資料就自動成為 HR。
- 角色應由 CSV 欄位（如 `role` 欄）或匯入參數明確指定，並在匯入後人工覆核。

### 1.6 SECRET_KEY 有不安全的預設值

**位置**：`backend/config.py:29`

- `SECRET_KEY` 有預設字串 `'dev-secret-key-請更換為安全的隨機字串'`，正式環境若漏設環境變數，JWT 簽名金鑰形同公開。
- 修正方向：production 環境缺少 `SECRET_KEY` 時應啟動失敗。

---

## 二、「未實作、只回傳固定結果」的地方

以下為 API 表面上有回應、但內容為硬編碼／假數據／與名稱不符的項目：

| # | 位置 | 問題描述 |
|---|------|----------|
| 1 | `services/hr_dashboard.py:169-173` | 總覽指標的變化量全是硬編碼假數據：`stress_index_change: 1.2`、`high_risk_change: -2.1`、`engagement_change: 5.4`，註解自己承認「暫時給個合理變動值」。前端顯示的「較前期 ±X%」趨勢變化是假的。應實作本期 vs 前期的真實對比計算。 |
| 2 | `services/hr_dashboard.py:391` | `lastActive: "最近 30 天內"` 只要該 cohort 有過任何一次點擊就顯示，**完全沒有檢查時間是否在 30 天內**。應改為比較最後點擊時間。 |
| 3 | `services/hr_dashboard.py:386` | `role: "General Staff"` 直接硬編碼，未從 DB 的職稱／職位資料取得。 |
| 4 | `routes/hr_actions.py:176` | 回饋率（feedback rate）分母是拍腦袋固定值：`rate = (feedback_count / 10) * 100`，註解承認「假設每月推播 4 篇，做個展示用」。應以實際推播次數（inbox_messages 中 type=recommendation 的數量）作為分母。 |
| 5 | `routes/hr_actions.py:216` | 兌換紀錄 API 的 `points_redeemed` 直接回傳**目前剩餘積分**而非本次實際兌換的點數，註解標明「簡化示範」。應另外記錄每次兌換的交易明細。 |
| 6 | `routes/hr_actions.py:98-154` | `/hr/model-performance` 的 `accuracy` 實際上只是 like 在 like+dislike 中的佔比，並非任何推薦模型或 ML 模型的準確率，指標名稱有誤導性；`engagement_rate` 的分子（全部期間點擊者）與分母（曾收到推薦者）時間範圍不一致。 |
| 7 | `scripts/batch_weekly.py:76-82` | 「週批次重新訓練推薦模型」實際是把 **5 篇硬編碼假文章（A001–A005，連向量都是寫死的）** dump 成 `recommendation_model.pkl`，會覆蓋掉以真實 DB 文章建立的模型。 |
| 8 | `scripts/batch_weekly.py:111, 163` | `compute_user_vectors` 存取 `log.tags`，但 `ClickLog` model 根本沒有 `tags` 欄位，執行必拋 `AttributeError`（證明此腳本從未成功跑過）；另外 `record.vector = vector.tolist()` 直接塞 Python list 進 Text 欄位，與 `vector_updater.py` 使用的 `json.dumps` 格式不相容，就算修好也會讓 `json.loads` 解析失敗。 |
| 9 | `services/recommendation.py:155-179` | `calculate_personal_vector_from_csv`「個人化初始向量」並非 ML，只是一串 if-else 規則（Sales 部門→人際、IT/Production→壓力、年資<1→壓力...）；風險調整權重 0.8 / 0.7 / 0.5 皆為無依據的 magic number。 |
| 10 | `services/hr_dashboard.py:357` | Adoption（採用率）定義被刻意改成「點擊 ≥ 12 次的深度使用者」以美化數字；tenure 分桶（<10 / 10–12 / 12–15 / 15+ 年）是針對特定示範資料集的分布硬切的，不具一般性。 |

---

## 三、設計不合理的問題

### ~~3.1 推薦引擎繞過資料庫回頭讀 CSV~~

**位置**：`backend/app/services/recommendation.py:27-31, 181-194`

- ~~`User` model 已完整定義 42 個 ML 特徵欄位（`pg_models.py:48-91`），但推薦引擎每次呼叫 `get_user_data_from_csv()` 都重新從磁碟讀兩份 CSV，完全沒用到 DB 裡的資料。~~
- ~~兩份 CSV 用 `zip()` 靠「行號」對齊縫合，**只要順序不一致就全部錯位**（資料筆數目前剛好都是 303，但沒有任何唯一鍵驗證）。~~
- ~~`PROJECT_ROOT` 預設 `D:\AffecCare\AffecCare`（Windows 路徑），部署到 Zeabur/Linux 時 CSV 與 `voluntary_risk.pkl` 全部找不到，風險分數會**靜默變成 0**（只有 log，API 不會報錯）。~~

✅ **修正狀態**：離職預測模型與所有的 ML 特徵欄位已被徹底移除，系統已改為純 3 大分類推薦架構，完全不依賴 CSV 與 `.pkl`。

### 3.2 沒有資料庫遷移機制

**位置**：`backend/app/__init__.py:83`、`backend/scripts/sync_db.py`

- 每次啟動都執行 `db.create_all()`（不會修改已存在的表結構）。
- Schema 變更靠手寫 `ALTER TABLE` 的 `sync_db.py`，沒有版本控管。
- **修正方向**：導入 Flask-Migrate（Alembic），移除啟動時的 `create_all()`。

### 3.3 效能問題：N+1 查詢與全表載入

**位置**：`backend/app/services/hr_dashboard.py`

- `get_department_overview()`：對每個部門迴圈執行 3 個 query，且把整個 `ClickLog` 表（`db.session.query(ClickLog).filter(...).all()`）載入記憶體只為了算分類統計——應改用 SQL `GROUP BY` 聚合。
- `get_category_trends()`：6 週趨勢 = 6 次獨立 query + 每次 `Article.query.all()`。
- `routes/hr_actions.py:feedback_stats` 與 `routes/support.py:get_all_tickets`：迴圈內逐筆 `User.query.get()`（N+1）。
- `list_articles` 的 `per_page` 無上限（可傳 `per_page=100000`）。

### 3.4 重複功能端點且權限不一致

- `POST /api/inbox/push-recommendations`（`routes/inbox.py:152`，權限 hr+manager）
- `POST /api/hr/actions/push-recommendations`（`routes/hr_actions.py:40`，權限只有 hr）

兩者做同一件事（產生推薦並推送至 inbox），應合併為一個並統一權限。

### 3.5 危險操作缺乏防呆

- `POST /api/hr/actions/reset-points`（`routes/hr_actions.py:243`）：一鍵將全公司積分與回饋次數歸零，無二次確認、無 audit log、無備份。
- 兌換（`/hr/rewards/redeem`）也沒有記錄任何交易歷史，扣點後即無法追溯。

### 3.6 測試腳本已過期且會污染資料庫

**位置**：`backend/scripts/test_api.py`

- 登入 payload 使用 `user_id` 欄位，但現行 `/api/auth/login`（`routes/auth.py:56`）只接受 `email`，整支腳本會連環失敗——顯示登入格式改版後測試沒有跟著更新。
- 腳本直接對（與 production 共用的）資料庫寫入再刪除，不是隔離的測試環境；也沒有用 pytest / unittest 等框架，無法自動化判斷成敗（只是印 PASS/FAIL）。
- **修正方向**：改用 pytest + Flask test client + 獨立測試資料庫。

### 3.7 雜項問題

| 位置 | 問題 |
|------|------|
| `routes/recommend.py:100-105` | `track_click` 的 `article_id` 不驗證是否存在（ClickLog 也無 FK），可寫入垃圾資料；`timestamp` 完全信任前端傳入字串，可偽造任意時間。`data` 為 None 時 `data if ... else` 判斷會直接 AttributeError（`required_fields` 檢查前未先判 None）。 |
| `routes/support.py:create_ticket` | `category` 不驗證是否為合法值（stress/interpersonal/career/other），可存入任意字串。 |
| `config.py:42` | `JSON_AS_ASCII` 在 Flask 3 已失效（改為 `app.json.ensure_ascii = False`），目前中文其實仍會被跳脫。 |
| ~~`app/services/evaluate_recommender.py:15`~~ | ~~`from recommendation import ...` 只在 services 目錄內直接執行才成立；且產出的 `evaluation_charts.png` 被放進程式目錄。~~ ✅ **已解決**（此舊測試檔已隨 ML 模型一併移除） |
| `requirements.txt` | 缺少 `werkzeug`（目前靠 Flask 附帶安裝）、~~`matplotlib`（evaluate_recommender 用到）~~、`requests`（scripts 用到）；`pandas==3.0.1` 版本號需確認存在。 |
| `models/pg_models.py:359` | `to_preview()` 註解承認同時回傳 preview 與完整 content，「摘要版本」名不符實（列表 API 回傳全部內文，浪費頻寬）。 |
| `routes/inbox.py:push_recommendations` | 迴圈內逐位使用者呼叫 `get_recommendations()`，~~每次都重讀兩份 CSV~~，大量使用者時極慢；且無交易包裹，中途失敗會推播一半。 |
| `backend/article/` 目錄 | AI 文章 CSV 與 DB 內文章可能不同步（`generate_batch_report.py` 讀 CSV、API 讀 DB），同一篇文章有兩個真相來源。 ✅ **部分解決**（`generate_batch_report.py` 已刪除） |

---

## 四、建議修正優先順序

### P0 — 立刻處理（安全洩漏）

1. **更換 Neon 資料庫密碼**，並從 `config.py` 移除寫死的連線字串（改環境變數）。

### P1 — 高（權限與假數據）

2. `/api/recommend`、`/api/track_click` 加 `@login_required`，user_id 改由 token 取得；員工端推薦結果移除 `turnover_risk_detected`。
3. `app/__init__.py` gunicorn 入口預設改為 production 設定，缺少 `SECRET_KEY` / `DATABASE_URL` 時拒絕啟動。
4. 修正 dashboard 三個假變化量（`stress_index_change` 等）為真實期間對比；修正 `lastActive` 邏輯；修正 feedback rate 分母。
5. 刪除或重寫 `scripts/batch_weekly.py`（目前會覆蓋真模型為假資料且必然執行失敗）。

### P2 — 中（架構合理化）

6. ~~推薦引擎改讀 DB 的 ML 特徵欄位；`PROJECT_ROOT` 改相對路徑；雙 CSV zip 對齊改為以唯一鍵 join。~~ ✅ **已解決**（推薦引擎已完全重構，無需依賴 CSV 與 ML 特徵）
7. 導入 Flask-Migrate，移除啟動時 `db.create_all()`。
8. Token 黑名單改 Redis/DB；或改短期 token + refresh token。
9. 合併兩個推播端點、統一權限；`reset-points` 加確認機制與 audit log。

### P3 — 低（品質與維護性）

10. 儀表板查詢改 SQL 聚合消除 N+1；`per_page` 加上限。
11. `test_api.py` 改寫為 pytest + 隔離測試資料庫。
12. 驗證 `track_click` 的 article_id / timestamp、`support` 的 category；修正 `JSON_AS_ASCII` 為 Flask 3 寫法；補齊 requirements.txt。
13. 兌換點數新增交易紀錄表（user_id、點數、時間、經手 HR），`points_redeemed` 回傳真實兌換明細。
