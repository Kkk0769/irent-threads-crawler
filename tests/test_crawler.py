import argparse
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import threads_irent as crawler


class CrawlerTests(unittest.TestCase):
    def test_global_limit(self):
        batch = [{'permalink': f'https://www.threads.com/@a/post/P{i}',
                  'text': 'irent 很好用' if i % 2 else 'irent 很爛'} for i in range(45)]
        raw, scanned = [], set()
        crawler.collect_batch(batch[:20], raw, scanned, 30, 'test', 'first')
        crawler.collect_batch(batch, raw, scanned, 30, 'test', 'second')
        self.assertEqual(len(raw), 30)
        self.assertEqual(len(crawler.prepare(raw, [])), 15)

    def test_api_limit(self):
        args = argparse.Namespace(query=['irent', 'irent 爛'], pages=5, delay=1, max_posts=30)
        payload = {'data': [{'permalink': f'https://www.threads.com/@a/post/P{i}', 'text': 'irent 爛'} for i in range(35)],
                   'paging': {'cursors': {'after': 'NEXT'}}}
        raw, warnings = [], []
        with patch.dict('os.environ', {'THREADS_ACCESS_TOKEN': 'secret'}), \
             patch('threads_irent.urlopen', return_value=io.StringIO(json.dumps(payload))) as request:
            crawler.api_collect(args, raw, warnings)
            self.assertEqual(request.call_count, 1)
            self.assertIn('limit=30', request.call_args.args[0].full_url)
            self.assertEqual(len(raw), 30)

    def test_word_content(self):
        from docx import Document
        from word_export import export_word
        content = 'irent 客服很爛。' * 30
        url = 'https://www.threads.com/@a/post/ABC'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.docx'
            export_word([{'text': content, 'permalink': url}], path, '完成', 1)
            doc = Document(path)
            paragraphs = doc.paragraphs
            index = next(i for i, p in enumerate(paragraphs) if content in p.text)
            self.assertIn(url, paragraphs[index + 1]._p.xml)
            self.assertTrue(any(r.target_ref == url for r in doc.part.rels.values()))

    def test_canonical_and_dedup(self):
        url = 'https://www.threads.net/@person/post/ABC?x=1'
        self.assertEqual(crawler.canonical_url(url), 'https://www.threads.com/@person/post/ABC')
        self.assertIsNone(crawler.canonical_url('https://evil.com/@person/post/ABC'))
        self.assertIsNone(crawler.canonical_url('javascript:alert(1)'))
        rows = crawler.prepare([
            {'permalink': url, 'text': 'irent 客服很爛'},
            {'permalink': 'https://www.threads.com/@person/post/ABC', 'text': 'irent 客服很爛，打不通'},
            {'permalink': 'https://www.threads.com/@person/post/DEF', 'text': 'irent 很好用'},
        ], [])
        self.assertEqual(len(rows), 1)
        self.assertIn('打不通', rows[0]['matched_words'])
        self.assertEqual(rows[0]['number'], 1)

    def test_relevance_and_normalization(self):
        self.assertFalse(crawler.classify('其他租車很爛', []))
        self.assertFalse(crawler.classify('irental broken', []))
        self.assertIn('爛', crawler.classify('ＩＲＥＮＴ 很爛', []))
        self.assertEqual(crawler.classify('irent 超級難用', ['難用']), ['難用'])

    def test_export_escapes_html_and_keeps_order(self):
        rows = crawler.prepare([{'permalink': 'https://www.threads.com/@test/post/A',
                                 'text': 'irent 很爛 <script>alert(1)</script>'}], [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            crawler.export([], rows, ['<warning>'], path, 'partial')
            output = (path / 'results.html').read_text(encoding='utf-8')
            self.assertNotIn('<script>', output)
            self.assertIn('&lt;script&gt;', output)
            data = json.loads((path / 'results.json').read_text(encoding='utf-8'))
            self.assertEqual(data['status'], 'partial')
            self.assertEqual(data['results'][0]['number'], 1)

    def test_api_pagination_and_partial_failure(self):
        args = argparse.Namespace(query=['irent'], pages=3, delay=1, max_posts=30)
        first = {'data': [{'text': 'irent 爛', 'permalink': 'https://www.threads.com/@x/post/A'}],
                 'paging': {'cursors': {'after': 'NEXT'}}}
        raw, warnings = [], []
        with patch.dict('os.environ', {'THREADS_ACCESS_TOKEN': 'secret'}), \
             patch('threads_irent.time.sleep'), \
             patch('threads_irent.urlopen', side_effect=[io.StringIO(json.dumps(first)),
                   HTTPError('https://graph.threads.net', 429, 'limited', {}, None)]) as request:
            with self.assertRaisesRegex(RuntimeError, '429'):
                crawler.api_collect(args, raw, warnings)
            self.assertEqual(len(raw), 1)
            self.assertIn('after=NEXT', request.call_args.args[0].full_url)
            self.assertNotIn('secret', request.call_args.args[0].full_url)

    def test_dom_does_not_mix_adjacent_posts(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            try:
                page = browser.new_page()
                page.set_content('''<main><article><a href="https://www.threads.com/@a/post/A">日期</a><p>irent 很好用，今天租車順利出發，旅程非常愉快，下次還會再租。</p></article>
                <article><a href="https://www.threads.com/@b/post/B">日期</a><p>irent 客服很爛，電話一直打不通，車子還發不動，等了很久。</p></article></main>''')
                rows = crawler.prepare(page.evaluate(crawler.EXTRACT), [])
                self.assertEqual([row['permalink'] for row in rows], ['https://www.threads.com/@b/post/B'])
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
