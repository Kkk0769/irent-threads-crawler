# Threads iRent 負評連結工具

每次最多處理 60 篇不重複貼文，篩選疑似負評，Word 只放「序號＋可點擊網址」，每筆一行。

## 使用

需要 Python 3.10 以上及 Chrome。雙擊 start.cmd，在工具瀏覽器登入 Threads，回到命令視窗按 Enter。完成後自動開啟 output/results.docx。執行前請先關閉上次的 Word，避免無法覆寫。

手動執行：

```powershell
python -m pip install -r requirements.txt
python threads_irent.py --login --max-posts 60
```

已登入可省略 --login。使用 Edge 可加 --channel msedge。

## 自動接續

output/link_history.json 保存历次負評網址。每次加入新網址後重新產生 Word，保留舊連結並排除重複。例如原有 5 筆，下次第一筆新網址編為 6，接著是 7。第一次使用新版會自動匯入同目錄舊 results.json 的結果。

請保留 link_history.json 並使用同一個輸出目錄。程式依此檔案接續，不會讀取手動編輯的 Word。用 --output 指定新目錄會建立獨立清單。歷史檔損壞時停止匯出以免覆蓋舊資料。

Word 僅放序號與網址。results.json、results.html、results.txt 與 raw.json 保留當次結果及診斷，下次會覆寫。歷史清單、結果與 .threads-profile 登入資料只保存在本機，不上傳 GitHub。

## 範圍

60 篇是跨搜尋詞去重後、負評篩選前的當次處理上限，不保證取得 60 篇負評或 60 個新連結。歷次收錄的貼文仍可能出現在搜尋結果並占當次額度，但不會重複加入 Word。累積 Word 可超過 60 筆。网站可能預載更多文章，工具不會因此增加收錄上限。

關鍵詞可能誤判或漏抓，請點開原文確認。未展開長文、圖片與影片內容可能漏抓。登入、驗證、平台限制或結果不足時，可能少於 60 篇；此設定無法解除平台流量限制。Ctrl+C 中止會嘗試保存已取得的資料。

## API 模式

設定具 threads_keyword_search 權限的本機環境變數 THREADS_ACCESS_TOKEN 後，執行 python threads_irent.py --source api --max-posts 60。請勿分享 Token 或登入資料。

## 測試

python -m unittest discover -s tests -v
