# Threads iRent 負評連結工具

目標累積 100 個不重複的疑似負評連結，固定輸出到同一份 output/results.docx。Word 每行只有「序號＋可點擊網址」，保留舊連結並接續編號。

## 使用

需要 Python 3.10 以上及 Chrome。雙擊 start.cmd，在瀏覽器登入 Threads，再回到命令視窗按 Enter。完成後自動開啟同一份 Word。執行前請關閉 Word 結果檔，避免被鎖定。

```powershell
python -m pip install -r requirements.txt
python threads_irent.py --login --target-links 100
```

已登入可省略 --login。使用 Edge 可加 --channel msedge。

## 累積與停止

output/link_history.json 保存歷次連結。首次使用會匯入同目錄舊 results.json。每批新連結都會立即保存歷史紀錄；正常結束或 Ctrl+C 中止時重建同一份 Word。Word 若被鎖住，歷史仍保留，下次執行會重新產生。程式不讀取手動修改的 Word，請保留歷史檔並使用同一目錄。

原有 5 筆時，新連結從第 6 筆開始；累積到 100 筆就停止，不是讀取 100 篇就停止。已達目標的再次執行只更新匯出，不開瀏覽器搜尋。若原本已有超過 100 筆，不刪除舊紀錄。

搜尋頁仍從平台提供的起點顯示，但已收錄的網址會跳過且不占當次新貼文額度。工具繼續往下捲並搜尋多組關鍵詞，不能保證回到上次的精準位置，也不保證能取得 100 個結果。歷史清單只記錄入選連結，先前未入選的文章可能再次被檢查。

預設每詞最多捲動 150 次，API 每詞最多 40 頁，當次最多處理 2000 篇新的不重複貼文作為安全界限。可用 --scrolls、--pages、--max-posts 調整。平台限制、登入提示、無更多結果或達安全界限時會保存進度並顯示尚未達標，下次再繼續累積。這些設定不解除平台限制。

## 結果與限制

Word 只放編號與網址；results.json、results.html、results.txt 和 raw.json 為當次資料及診斷，下次會覆寫。累積連結與登入狀態只留本機，不上傳 GitHub。

負評依關鍵詞初篩，可能誤判或漏抓，請開原文確認。未展開長文、圖片、影片及未載入留言可能漏抓。

API 模式需設定具 threads_keyword_search 權限的環境變數 THREADS_ACCESS_TOKEN，再使用 --source api。不要分享 Token 或 .threads-profile。

## 測試

python -m unittest discover -s tests -v
