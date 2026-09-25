"""Collect public Threads posts and flag potential iRent complaints."""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import re
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DEFAULT_QUERIES = ['irent', 'iRent 客服', 'irent 爛', 'irent 扣款', 'irent 故障', '和雲 行動服務']
NEGATIVE = ['抱怨', '爛', '烂', '雷', '糟', '差勁', '失望', '不滿', '不爽', '生氣',
            '傻眼', '扯', '垃圾', '噁心', '惡劣', '離譜', '崩潰', '後悔', '受不了',
            '不推薦', '不推', '拒用', '抵制', '投訴', '申訴', '客訴', '踩雷',
            '故障', '無法', '不能', '沒辦法', '打不通', '聯絡不到', '找不到車',
            '發不動', '開不了', '還不了', '租不了', '登不進', '閃退', '當機',
            '亂扣', '多扣', '重複扣款', '亂收', '退款', '不退', '罰款', '臭',
            '髒', '蟑螂', '煙味', '菸味', '危險', '漏油', '爆胎', '刁難',
            '踢皮球', '騙', '坑人', '貴', '等太久', '問題', '遠離', '拖吊', '不應該',
            '停成這樣', '難用', '不合理', '出包', '出事', 'bug', 'broken', 'terrible']
BRAND = re.compile(r'(?<![a-z])i\s*rent(?![a-z])|和雲', re.I)


def canonical_url(value: str) -> str | None:
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or parsed.hostname not in {'threads.net', 'www.threads.net', 'threads.com', 'www.threads.com'}:
        return None
    match = re.fullmatch(r'/(@[^/]+)/post/([A-Za-z0-9_-]+)/?', parsed.path)
    return f'https://www.threads.com/{match[1]}/post/{match[2]}' if match else None


def post_key(url: str) -> str:
    return url.rsplit('/', 1)[-1]


def classify(text: str, extra: list[str]) -> list[str]:
    normalized = unicodedata.normalize('NFKC', text).lower()
    if not BRAND.search(normalized):
        return []
    return list(dict.fromkeys(word for word in NEGATIVE + extra if word.lower() in normalized))


def prepare(raw: list[dict], extra: list[str]) -> list[dict]:
    unique = {}
    for item in raw:
        url = canonical_url(item.get('permalink', ''))
        text = item.get('text', '').strip()
        if not url or not text:
            continue
        key = post_key(url)
        if key not in unique or len(text) > len(unique[key]['text']):
            unique[key] = {**item, 'permalink': url, 'text': text}
    results = []
    for item in unique.values():
        hits = classify(item['text'], extra)
        if hits:
            excerpt = re.sub(r'\s+', ' ', item.get('title_text') or item['text']).strip()
            results.append({**item, 'number': len(results) + 1,
                            'title': excerpt[:80] + ('…' if len(excerpt) > 80 else ''),
                            'matched_words': hits, 'assessment': '疑似負評，需人工確認'})
    return results


def api_collect(args, raw, warnings):
    scanned = set()
    token = os.environ.get('THREADS_ACCESS_TOKEN', '').strip()
    if not token:
        raise RuntimeError('API 模式需要環境變數 THREADS_ACCESS_TOKEN，且具備 threads_keyword_search 權限。')
    for query in args.query:
        cursor = None
        seen = set()
        for _ in range(args.pages):
            params = {'q': query, 'search_type': 'RECENT', 'search_mode': 'KEYWORD',
                      'fields': 'id,text,permalink,timestamp', 'limit': min(50, args.max_posts - len(scanned))}
            if cursor:
                params['after'] = cursor
            request = Request('https://graph.threads.net/keyword_search?' + urlencode(params),
                              headers={'Authorization': 'Bearer ' + token})
            try:
                with urlopen(request, timeout=30) as response:
                    payload = json.load(response)
            except HTTPError as exc:
                code = exc.code
                exc.close()
                raise RuntimeError(f'Threads API HTTP {code}；請檢查權限、Token 或使用額度。已取得資料會保存。') from None
            except (URLError, TimeoutError):
                raise RuntimeError('Threads API 網路連線失敗。已取得資料會保存。') from None
            if 'error' in payload:
                raise RuntimeError('Threads API 回傳錯誤，請檢查權限與 Token。')
            batch = payload.get('data', [])
            collect_batch(batch, raw, scanned, args.max_posts, 'Threads API', query)
            print(f'搜尋 {query}：本頁取得 {len(batch)} 筆', flush=True)
            if len(scanned) >= args.max_posts:
                warnings.append(f'已達本次 {args.max_posts} 篇不重複貼文上限，停止搜尋。')
                return
            cursor = payload.get('paging', {}).get('cursors', {}).get('after')
            if not batch or not cursor or cursor in seen:
                break
            seen.add(cursor)
            time.sleep(args.delay)
        else:
            warnings.append(f'{query} 達 API 頁數上限，可能仍有更多文章。')


# Select the smallest surrounding card with one distinct post URL. Never use
# page-wide text: unrelated complaints must not be attached to another URL.
EXTRACT = r'''() => {
  const links = [...document.querySelectorAll('a[href*="/post/"]')];
  const key = href => {try {return new URL(href, location.href).pathname.match(/\/@[^/]+\/post\/([\w-]+)/)?.[1]} catch {return null}};
  const rows = [];
  for (const a of links) {
    if (!key(a.href)) continue;
    let node = a.parentElement, candidate = null;
    for (let depth = 0; node && depth < 14; depth++, node = node.parentElement) {
      const ids = new Set([...node.querySelectorAll('a[href*="/post/"]')].map(x => key(x.href)).filter(Boolean));
      if (ids.size > 1) break;
      const content = node.innerText || '';
      if (ids.size === 1 && content.length > 30 && content.length < 15000) candidate = node;
    }
    if (candidate) {
      const timer = candidate.querySelector('time');
      const lines = candidate.innerText.split('\n');
      const timeIndex = timer ? lines.findIndex(line => line.trim() === timer.innerText.trim()) : -1;
      const content = (timeIndex >= 0 ? lines.slice(timeIndex + 1) : lines).join('\n').split('\n翻譯')[0];
      rows.push({permalink: a.href, text: candidate.innerText, title_text: content,
        timestamp: timer?.getAttribute('datetime') || ''});
    }
  }
  return rows;
}'''


def collect_batch(batch, raw, scanned, limit, source, query):
    """Count unique posts before sentiment filtering, across all queries."""
    for item in batch:
        if len(scanned) >= limit:
            break
        url = canonical_url(item.get('permalink', ''))
        if not url or post_key(url) in scanned:
            continue
        scanned.add(post_key(url))
        raw.append({**item, 'permalink': url, 'source': source, 'query': query})


def browser_collect(args, raw, warnings):
    scanned = set()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError('請先執行 python -m pip install -r requirements.txt') from None
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(ROOT / '.threads-profile'), channel=args.channel, headless=args.headless,
            viewport={'width': 1280, 'height': 900}, locale='zh-TW')
        try:
            page = context.pages[0] if context.pages else context.new_page()
            if args.login:
                page.goto('https://www.threads.com/', wait_until='domcontentloaded', timeout=45000)
                input('請在開啟的獨立瀏覽器登入 Threads，完成後回到此視窗按 Enter：')
            empty_queries = 0
            for query in args.query:
                print(f'搜尋 Threads：{query}', flush=True)
                page.goto('https://www.threads.com/search?' + urlencode({'q': query, 'serp_type': 'default'}),
                          wait_until='domcontentloaded', timeout=45000)
                try:
                    page.wait_for_selector('a[href*="/post/"]', timeout=15000)
                except Exception:
                    empty_queries += 1
                    warnings.append(f'{query} 未出現貼文連結：可能需要登入、被限制，或沒有搜尋結果。')
                    if empty_queries >= 2:
                        raise RuntimeError('連續兩次搜尋無法讀取貼文，已停止。請以 --login 登入後重試；遇到驗證請手動完成。')
                    continue
                empty_queries = 0
                seen = set()
                relevant = set()
                stale = 0
                for _ in range(args.scrolls):
                    page.wait_for_timeout(args.delay * 1000)
                    batch = page.evaluate(EXTRACT)
                    before = len(seen)
                    collect_batch(batch, raw, scanned, args.max_posts, 'Threads 網頁文字（可能含介面文字）', query)
                    branded = [item for item in raw if BRAND.search(unicodedata.normalize('NFKC', item['text']))]
                    relevant.update(item['permalink'] for item in branded)
                    seen.update(post_key(item['permalink'].split('?')[0].rstrip('/')) for item in batch)
                    print(f'  已讀取 {len(scanned)}/{args.max_posts} 篇；疑似負評 {len(prepare(raw, args.negative_word))} 篇', flush=True)
                    if len(scanned) >= args.max_posts:
                        warnings.append(f'已達本次 {args.max_posts} 篇不重複貼文上限，停止搜尋。')
                        return
                    body = page.locator('body').inner_text()
                    login_gate = any(label in body for label in ['登入以取得更多', 'Log in to see more', 'Log in to view more'])
                    if login_gate and not relevant:
                        raise RuntimeError('Threads 顯示登入提示與無關推薦內容，尚未取得 iRent 搜尋結果。請執行 --login，在工具瀏覽器登入後重試。')
                    if login_gate:
                        warnings.append(f'{query} 出現登入提示，只能取得部分公開文章。')
                        break
                    stale = stale + 1 if len(seen) == before else 0
                    if stale >= 3:
                        break
                    page.mouse.wheel(0, 1600)
                print(f'  讀取 {len(seen)} 個貼文網址，其中 {len(relevant)} 個提及品牌', flush=True)
                if not seen:
                    warnings.append(f'{query} 有連結但無法辨識貼文區塊，網站結構可能已變更。')
                else:
                    warnings.append(f'{query} 僅涵蓋本次已載入文章，不代表全部搜尋結果。')
                    if not relevant:
                        warnings.append(f'{query} 未讀到品牌相關文字，可能只有推薦內容，不能據此判定沒有負評。')
        finally:
            context.close()


def update_link_history(rows, output):
    """Persist links before replacing current-run files; migrate earlier results."""
    history_path = output / 'link_history.json'
    source = history_path if history_path.exists() else output / 'results.json'
    previous = []
    if source.exists():
        try:
            payload = json.loads(source.read_text(encoding='utf-8'))
            previous = payload['results']
            if not isinstance(previous, list):
                raise ValueError('results must be a list')
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(f'歷史紀錄 {source.name} 無法讀取，為避免遺失舊連結，已停止匯出。') from exc
    merged, seen = [], set()
    for item in previous + rows:
        if not isinstance(item, dict):
            raise RuntimeError('歷史紀錄格式錯誤，已停止匯出以保留舊資料。')
        url = canonical_url(item.get('permalink', ''))
        if not url:
            raise RuntimeError('歷史紀錄含無效網址，已停止匯出以保留舊資料。')
        if post_key(url) in seen:
            continue
        seen.add(post_key(url))
        merged.append({'number': len(merged) + 1, 'permalink': url})
    temporary = output / 'link_history.tmp'
    temporary.write_text(json.dumps({'results': merged}, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(history_path)
    return merged


def export(raw, rows, warnings, output, status):
    output.mkdir(parents=True, exist_ok=True)
    history = update_link_history(rows, output)
    metadata = {'status': status, 'collected_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'raw_count': len(raw), 'result_count': len(rows), 'warnings': warnings,
                'ordering': '首次找到的順序；非全站時間排序', 'results': rows}
    (output / 'results.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'raw.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
    escape = html.escape
    items = '\n'.join(f'<li><a href="{escape(r["permalink"], quote=True)}" target="_blank" rel="noopener noreferrer">{escape(r["title"])}</a><p>{escape(r["permalink"])}</p><small>命中詞：{escape("、".join(r["matched_words"]))}</small><details><summary>檢視原文文字</summary><pre>{escape(r["text"])}</pre></details></li>' for r in rows)
    notes = ''.join(f'<li>{escape(w)}</li>' for w in warnings)
    document = f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>iRent 疑似負評清單</title>
<style>body{{font:17px/1.7 system-ui,sans-serif;max-width:960px;margin:40px auto;padding:0 24px;color:#222}}a{{color:#065eb5}}li{{margin:20px 0}}p,small{{overflow-wrap:anywhere;color:#555}}pre{{white-space:pre-wrap;font:inherit}}summary{{cursor:pointer}}</style>
<h1>iRent 疑似負評清單</h1><p>共 {len(rows)} 筆｜狀態：{escape(status)}｜依首次找到的順序排列</p>
<p>標題為原文前 80 字摘要。關鍵詞篩選可能誤判或漏抓，需開啟原文確認；不代表已找出 Threads 所有負評。</p>
<ol>{items}</ol><h2>擷取紀錄</h2><ul>{notes}</ul></html>'''
    (output / 'results.html').write_text(document, encoding='utf-8')
    lines = ['# iRent 疑似負評清單', '', f'狀態：{status}；共 {len(rows)} 筆。標題取自原文前段，依首次找到順序排列。', '']
    for r in rows:
        lines.extend([f'{r["number"]}. {r["title"]}', f'   {r["permalink"]}', ''])
    lines.extend(['注意：關鍵詞篩選需人工確認，不保證完整。', *warnings])
    (output / 'results.txt').write_text('\n'.join(lines), encoding='utf-8')
    from word_export import export_word
    export_word(history, output / 'results.docx', status, len(raw))


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('必須至少為 1')
    return number


def main():
    parser = argparse.ArgumentParser(description='搜尋 Threads 的 iRent 疑似負評，列出編號、標題與網址。')
    parser.add_argument('--source', choices=['browser', 'api'], default='browser')
    parser.add_argument('--login', action='store_true', help='開啟獨立瀏覽器，等待手動登入')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--channel', choices=['chrome', 'msedge'], default='chrome')
    parser.add_argument('--query', action='append', help='可重複指定，取代預設搜尋詞')
    parser.add_argument('--negative-word', action='append', default=[], help='新增負評關鍵詞')
    parser.add_argument('--scrolls', type=positive, default=15)
    parser.add_argument('--pages', type=positive, default=5)
    parser.add_argument('--max-posts', type=positive, default=60, help='跨搜尋詞合計讀取上限，去重後計算，預設 60 篇（非負評數量）')
    parser.add_argument('--delay', type=positive, default=3)
    parser.add_argument('--output', type=Path, default=ROOT / 'output')
    args = parser.parse_args()
    if args.login and args.headless:
        parser.error('--login 不能與 --headless 同時使用')
    args.query = args.query or DEFAULT_QUERIES
    raw, warnings = [], []
    status = '完成本次擷取（非完整全站資料）'
    failed = False
    try:
        (api_collect if args.source == 'api' else browser_collect)(args, raw, warnings)
    except KeyboardInterrupt:
        failed = True
        status = '使用者中止，保存部分資料'
    except Exception as exc:
        failed = True
        status = '擷取未完成'
        # Avoid dumping network URLs or browser diagnostics that could contain secrets.
        warnings.append(str(exc) if isinstance(exc, RuntimeError) else f'{type(exc).__name__}：讀取失敗，請檢查網路、瀏覽器是否已安裝，或關閉上次的工具瀏覽器後重試。')
    rows = prepare(raw, args.negative_word)
    if not raw and not failed:
        status = '未取得文章（無法據此判定沒有負評）'
    try:
        export(raw, rows, warnings, args.output.resolve(), status)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    except (ImportError, PermissionError) as exc:
        print('Word 匯出失敗：請確認已安裝 requirements.txt 的套件，並關閉正在開啟的 results.docx 後重試。其他格式已保存。')
        return 1
    print(f'{status}：{len(rows)} 筆疑似負評。\nWord：{args.output.resolve() / "results.docx"}')
    for warning in warnings:
        print('注意：' + warning)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
