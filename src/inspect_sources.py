#!/usr/bin/env python3
import urllib.request
from bs4 import BeautifulSoup
import re
import json

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

# 1. Check SportsNavi
try:
    url = 'https://sports.yahoo.co.jp/basket/bleague/b1/schedule'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        html = r.read().decode('utf-8')
    print('SportsNavi len:', len(html))
    # Search for json or script tags
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script'):
        stext = script.string or ''
        if '__PRELOADED_STATE__' in stext or '__NEXT_DATA__' in stext or 'schedule' in stext:
            print('Found script with keyword! len:', len(stext), stext[:200])
except Exception as e:
    print('SportsNavi error:', e)

# 2. Check B.League official schedule
try:
    url = 'https://www.bleague.jp/schedule/?tab=1&year_index=2023&event=1'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        html = r.read().decode('utf-8')
    print('B.League len:', len(html))
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script'):
        src = script.get('src', '')
        stext = script.string or ''
        if 'api' in src or 'schedule' in src:
            print('Script src:', src)
        if 'api' in stext or 'game' in stext:
            print('Script inline preview:', stext[:150])
except Exception as e:
    print('B.League error:', e)

# 3. Check GitHub rintaromasuda/bleaguebydata
try:
    url = 'https://api.github.com/repos/rintaromasuda/bleaguebydata/contents'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode('utf-8'))
    print('bleaguebydata files:', [x['name'] for x in data])
except Exception as e:
    print('bleaguebydata error:', e)
