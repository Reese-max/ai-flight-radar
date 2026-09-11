"""Browser-only regression checks with intercepted synthetic API fixtures.

Run: python tests/browser_smoke.py
Requires playwright and Chromium. Never sends live flight/provider requests.
"""
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import threading
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = Path(os.getenv('UI_SCREENSHOTS_DIR', str(ROOT.parent / 'radar-ui-checks')))
OUTPUT.mkdir(exist_ok=True)

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(('127.0.0.1',0), partial(Handler, directory=str(ROOT/'web')))
threading.Thread(target=server.serve_forever, daemon=True).start()
base_url = f'http://127.0.0.1:{server.server_port}'
now = datetime.now(timezone.utc)
dep=(now+timedelta(days=50)).date().isoformat()
ret=(now+timedelta(days=54)).date().isoformat()
quotes=[]
for idx,(dest,price,prior) in enumerate([('FUK',5980,8),('NRT',7280,11),('OKA',4560,2)]):
    quotes.append(dict(id=f'00000000-0000-4000-8000-00000000000{idx}',origin='TPE',destination=dest,
        depart_date=dep,return_date=ret,trip_days=5,price_twd=price,currency='TWD',adults=1,cabin='economy',
        direct_only=True,airline='<script>window.untrustedExecuted=true</script>',
        searched_at=(now-timedelta(minutes=3)).isoformat(),expired=False,
        baseline_confident=prior>=5,baseline_twd=7870 if prior>=5 else None,
        drop_pct=24 if prior>=5 else None,prior_observed_days=prior,history_truncated=False,
        source='Google Flights',baggage_verified=False,
        source_url='https://www.google.com/travel/flights?q=TPE'))
config=dict(ui_version='2.0',public_mode=True,manual_scan_requires_key=True,
    origins=[dict(code='TPE',name='桃園國際機場',city='台北')],
    destinations=[dict(code=c,name=n+'機場',city=n) for c,n in [('FUK','福岡'),('NRT','東京'),('OKA','沖繩')]],
    routes=[dict(origin='TPE',destination=c) for c in ('FUK','NRT','OKA')],
    search_snapshots=34,last_quote_at=now.isoformat(),worker=dict(status='not_started',heartbeat_at=None),
    notifications=dict(ntfy=False,telegram=False),watchlist_scope='browser_only',source_count=1)
errors=[]
calls=[]
offline=False

def mock(route):
    url=route.request.url
    calls.append((route.request.method,url))
    path=urlparse(url).path
    if not url.startswith(base_url):
        route.abort()
        return
    if not path.startswith('/api/'):
        route.continue_()
        return
    if offline and path=='/api/ui/quotes':
        route.fulfill(status=503,content_type='application/json',body='{"detail":"test offline"}')
        return
    payload={}
    status=200
    if path=='/api/ui/config': payload=config
    elif path=='/api/ui/quotes': payload=dict(quotes=quotes,next_offset=None,demo=False)
    elif path.startswith('/api/ui/quote/'):
        payload=next((q for q in quotes if q['id']==path.rsplit('/',1)[-1]),{})
    elif path.startswith('/api/ui/dates/'):payload=dict(quotes=quotes[:1],truncated=False)
    elif path=='/api/ui/access':
        if route.request.headers.get('x-api-key')=='test-key-memory-only':payload=dict(authorized=True)
        else:status=401
    elif path=='/api/ui/parse':payload=dict(method='rule_based',requires_confirmation=True,intent=dict(
        origins=['TPE'],destinations=['FUK'],start_date=now.date().isoformat(),
        end_date=(now+timedelta(days=90)).date().isoformat(),min_duration=4,max_duration=5,max_budget_twd=8000))
    else: status=404
    route.fulfill(status=status,content_type='application/json',body=json.dumps(payload))

try:
    with sync_playwright() as p:
        chromium=os.getenv('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('chromium-browser')
        browser=p.chromium.launch(headless=True,**({'executable_path':chromium} if chromium else {}),args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':1080})
        context.route('**/*',mock)
        page=context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base_url,wait_until='networkidle')
        expect(page.locator('#results .flight-card')).to_have_count(3)
        page.screenshot(path=str(OUTPUT/'desktop.png'),full_page=True)
        # Modal validation, Escape, and focus restoration.
        page.get_by_role('button',name='篩選',exact=True).click()
        expect(page.locator('#filterDialog')).to_be_visible()
        page.locator('[name=min_days]').fill('10')
        page.locator('[name=max_days]').fill('4')
        page.get_by_role('button',name='套用條件',exact=True).click()
        expect(page.locator('#filterError')).to_contain_text('最多天數')
        page.keyboard.press('Escape')
        expect(page.locator('#filterDialog')).not_to_be_visible()
        assert page.evaluate('document.activeElement.textContent')=='篩選'
        # Unknown parsed conditions require review, not a live scan.
        page.locator('#nlpQuery').fill('福岡四天八千以內')
        page.locator('#searchButton').click()
        expect(page.locator('#filterDialog')).to_be_visible()
        expect(page.locator('#filterForm [name=max_price]')).to_have_value('8000')
        page.keyboard.press('Escape')
        # Detail text is escaped, source is safe, watchlist is browser-local.
        page.locator('#results .flight-card a').first.click()
        expect(page.locator('#detailContent .price.hero')).to_be_visible()
        assert page.evaluate('window.untrustedExecuted') is None
        expect(page.locator('#detailContent')).to_contain_text('<script>')
        page.locator('#detailContent').get_by_role('button',name='追蹤',exact=True).click()
        page.locator('#watchForm [name=name]').fill('<img src=x onerror=alert(1)>')
        page.get_by_role('button',name='儲存至此瀏覽器').click()
        page.locator('.sidebar [data-nav=watch]').click()
        expect(page.locator('#watchRows .watch-card')).to_have_count(1)
        expect(page.locator('#watchRows h3')).to_have_text('<img src=x onerror=alert(1)>')
        assert page.locator('#watchRows img').count()==0
        page.get_by_role('button',name='暫停',exact=True).click()
        expect(page.locator('#watchRows')).to_contain_text('已暫停')
        # No credential storage and no accidental public scan.
        page.locator('.sidebar [data-nav=settings]').click()
        page.locator('#apiKey').fill('test-key-memory-only')
        page.locator('#verifyKey').click()
        expect(page.locator('#keyStatus')).to_contain_text('驗證成功')
        storage=page.evaluate('JSON.stringify({local:{...localStorage},session:{...sessionStorage},url:location.href})')
        assert 'test-key-memory-only' not in storage
        page.locator('#clearKey').click()
        expect(page.locator('#apiKey')).to_have_value('')
        # Narrow screens do not overflow; major views stay usable.
        for width in (390,360):
            page.set_viewport_size({'width':width,'height':844})
            page.locator('.bottom-nav [data-nav=explore]').click()
            expect(page.locator('#results .flight-card')).to_have_count(3)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),f'overflow at {width}'
            if width==390:page.screenshot(path=str(OUTPUT/'mobile.png'),full_page=True)
            page.locator('.bottom-nav [data-nav=compare]').click()
            expect(page.locator('#historyRows .date-row')).to_have_count(1)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#historyRows .date-row').click()
            expect(page.locator('#detailContent .price.hero')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        # An API failure is not a fake zero-price result, and last data stays labeled.
        page.locator('#detailPage a[href="#explore"]').click()
        expect(page.locator('#results .flight-card')).to_have_count(3)
        offline=True
        page.locator('button[data-action=refresh]:visible').first.click()
        expect(page.locator('#serviceNotice')).to_contain_text('更新失敗')
        expect(page.locator('#results .flight-card')).to_have_count(3)
        assert not any(method=='POST' and url.endswith('/api/scan/trigger') for method,url in calls)
        assert not errors,errors
        browser.close()
    print('Browser smoke passed: desktop, 390/360 mobile, dialogs, detail, watchlist, credentials, failure states; no live scans.')
finally:
    server.shutdown()
