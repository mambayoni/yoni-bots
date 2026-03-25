import os
import asyncio
import requests
import time
from datetime import datetime, timezone
from twikit import Client

# ── הגדרות (נטענות ממשתני סביבה) ──
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID   = os.environ['TELEGRAM_CHAT_ID']
TWITTER_USERNAME   = os.environ.get('TWITTER_USERNAME', 'mambamateo')
TWITTER_PASSWORD   = os.environ.get('TWITTER_PASSWORD', '')
TARGET_USER        = 'DeItaone'         # Walter Bloomberg
CHECK_INTERVAL_SEC = 10                 # סריקה כל 10 שניות

COOKIES_FILE = '/tmp/twitter_cookies.json'


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


def fmt(tweet_text, tweet_id):
    now = datetime.now(timezone.utc).strftime('%H:%M UTC')
    link = f'https://x.com/{TARGET_USER}/status/{tweet_id}'
    return (
        f'📡 <b>Walter Bloomberg</b> | {now}\n'
        f'─────────────────\n'
        f'{tweet_text}\n\n'
        f'🔗 <a href="{link}">מקור</a>'
    )


async def main():
    print('=' * 50)
    print('Walter Bloomberg Bot starting...')
    print(f'   Tracking: @{TARGET_USER}')
    print(f'   Interval: {CHECK_INTERVAL_SEC} seconds')
    print('=' * 50)

    client = Client('en-US')

    # Try loading saved cookies first
    try:
        client.load_cookies(COOKIES_FILE)
        print('[Auth] Loaded saved cookies')
    except Exception:
        print('[Auth] Logging in to Twitter...')
        try:
            await client.login(
                auth_info_1=TWITTER_USERNAME,
                auth_info_2=TWITTER_USERNAME,
                password=TWITTER_PASSWORD,
                cookies_file=COOKIES_FILE
            )
            print('[Auth] Login successful')
        except Exception as e:
            print(f'[Auth] Login failed: {e}')
            send_telegram(f'🔴 <b>Walter Bot: Login failed</b>\n{e}')
            return

    # Get user ID for DeItaone
    try:
        user = await client.get_user_by_screen_name(TARGET_USER)
        user_id = user.id
        print(f'[Init] Found @{TARGET_USER} (ID: {user_id})')
    except Exception as e:
        print(f'[Error] Could not find user @{TARGET_USER}: {e}')
        send_telegram(f'🔴 <b>Walter Bot: User not found</b>\n{e}')
        return

    send_telegram(
        '✅ <b>Walter Bloomberg Bot הופעל!</b>\n'
        'עוקב אחרי @DeItaone\n'
        f'סריקה כל {CHECK_INTERVAL_SEC} שניות 🚀'
    )

    seen = set()
    first = True
    fail_count = 0

    while True:
        try:
            tweets = await client.get_user_tweets(user_id, 'Tweets', count=20)

            if not tweets:
                fail_count += 1
                if fail_count >= 10:
                    print('[!] Too many failures, re-authenticating...')
                    try:
                        await client.login(
                            auth_info_1=TWITTER_USERNAME,
                            auth_info_2=TWITTER_USERNAME,
                            password=TWITTER_PASSWORD,
                            cookies_file=COOKIES_FILE
                        )
                        print('[Auth] Re-login successful')
                        fail_count = 0
                    except Exception as e:
                        print(f'[Auth] Re-login failed: {e}')
                        await asyncio.sleep(60)
                await asyncio.sleep(30)
                continue

            fail_count = 0

            if first:
                seen = {t.id for t in tweets}
                print(f'[Init] {len(seen)} existing tweets — waiting for new ones...')
                first = False
            else:
                new_tweets = [t for t in tweets if t.id not in seen]
                for t in reversed(new_tweets):
                    ok = send_telegram(fmt(t.text, t.id))
                    status = 'OK' if ok else 'FAIL'
                    print(f'[{status}] {t.text[:70]}')
                    seen.add(t.id)
                    await asyncio.sleep(0.5)

            await asyncio.sleep(CHECK_INTERVAL_SEC)

        except KeyboardInterrupt:
            print('\n[!] Bot stopped.')
            send_telegram('🔴 <b>Walter Bloomberg Bot הופסק.</b>')
            break
        except Exception as e:
            print(f'[Error] {e}')
            fail_count += 1
            await asyncio.sleep(15)


if __name__ == '__main__':
    asyncio.run(main())
