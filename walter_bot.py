import os
import requests
import time
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# ── הגדרות (נטענות ממשתני סביבה) ──
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID   = os.environ['TELEGRAM_CHAT_ID']
TWITTER_USERNAME   = 'DeItaone'         # Walter Bloomberg
CHECK_INTERVAL_SEC = 5                  # סריקה כל 5 שניות

NITTER_INSTANCES = [
    'https://nitter.privacydev.net',
    'https://nitter.poast.org',
    'https://nitter.nl',
    'https://nitter.it',
    'https://nitter.cz',
]


def send_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    try:
        r = requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f'Telegram error: {e}')
        return False


def fetch_tweets(base):
    try:
        r = requests.get(
            f'{base}/{TWITTER_USERNAME}',
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=15
        )
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, 'html.parser')
        tweets = []
        for item in soup.select('.timeline-item'):
            if item.select_one('.retweet-header'):
                continue
            content = item.select_one('.tweet-content')
            link_el = item.select_one('.tweet-link')
            if not content:
                continue
            text = content.get_text(separator=' ', strip=True)
            tweet_id = link_el['href'].split('/')[-1] if link_el else text[:40]
            link = f'https://x.com/{TWITTER_USERNAME}/status/{tweet_id}'
            tweets.append({'id': tweet_id, 'text': text, 'link': link})
        return tweets
    except Exception as e:
        print(f'Nitter error {base}: {e}')
        return []


def get_instance():
    for inst in NITTER_INSTANCES:
        try:
            r = requests.get(f'{inst}/{TWITTER_USERNAME}', timeout=10)
            if r.status_code == 200 and 'timeline' in r.text:
                print(f'Instance active: {inst}')
                return inst
        except:
            continue
    return None


def fmt(t):
    now = datetime.now(timezone.utc).strftime('%H:%M UTC')
    return (
        f'📡 <b>Walter Bloomberg</b> | {now}\n'
        f'─────────────────\n'
        f'{t["text"]}\n\n'
        f'🔗 <a href="{t["link"]}">מקור</a>'
    )


# ── הרצה ──
if __name__ == '__main__':
    print('=' * 50)
    print('Walter Bloomberg Bot starting...')
    print(f'   Tracking: @{TWITTER_USERNAME}')
    print(f'   Interval: {CHECK_INTERVAL_SEC} seconds')
    print('=' * 50)

    send_telegram(
        '✅ <b>Walter Bloomberg Bot הופעל!</b>\n'
        'עוקב אחרי @DeItaone\n'
        f'סריקה כל {CHECK_INTERVAL_SEC} שניות 🚀'
    )

    seen = set()
    instance = get_instance()
    first = True
    fail_count = 0

    while True:
        try:
            tweets = fetch_tweets(instance) if instance else []

            if not tweets:
                fail_count += 1
                if fail_count >= 3:
                    print('[!] Searching for alternative instance...')
                    instance = get_instance()
                    fail_count = 0
                time.sleep(30)
                continue

            fail_count = 0

            if first:
                seen = {t['id'] for t in tweets}
                print(f'[Init] {len(seen)} existing tweets — waiting for new ones...')
                first = False
            else:
                new = [t for t in tweets if t['id'] not in seen]
                for t in reversed(new):
                    ok = send_telegram(fmt(t))
                    status = 'OK' if ok else 'FAIL'
                    print(f'[{status}] {t["text"][:70]}')
                    seen.add(t['id'])
                    time.sleep(0.5)

            time.sleep(CHECK_INTERVAL_SEC)

        except KeyboardInterrupt:
            print('\n[!] Bot stopped.')
            send_telegram('🔴 <b>Walter Bloomberg Bot הופסק.</b>')
            break
        except Exception as e:
            print(f'[Error] {e}')
            time.sleep(15)
