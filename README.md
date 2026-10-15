# 台灣兒童 IgAN 共識投票網站

台灣腎臟醫學會兒童 IgAN 工作小組的修正式 Delphi 投票網站。

- 前端：`index.html`（靜態頁，GitHub Pages）
- 後端：Supabase（Auth email 驗證碼登入；Postgres + Row Level Security）
- 只有委員名單（`members` 表）中的 email 可以登入與投票。條文與投票資料不在本 repo。
- 頁面中的 Supabase URL 與 publishable key 是公開用的金鑰，資料存取由 RLS 控制。
