import os
import asyncio
import requests
import json
from datetime import datetime, timezone

# ── הגדרות (נטענות ממשתני סביבה) ──
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID   = os.environ['TELEGRAM_CHAT_ID']
AUTH_TOKEN          = os.environ.get('TWITTER_AUTH_TOKEN', '')
CT0                 = os.environ.get('TWITTER_CT0', '')
TARGET_USER         = 'DeItaone'
CHECK_INTERVAL_SEC  = 5

# Twitter internal API bearer token (public, embedded in twitter.com JS)
BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA'

SESSION = requests.Session()


def setup_session():
    SESSION.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Authorization': f'Bearer {BEARER_TOKEN}',
        'x-csrf-token': CT0,
        'x-twitter-auth-type': 'OAuth2Session',
        'x-twitter-active-user': 'yes',
        'x-twitter-client-language': 'en',
    })
    SESSION.cookies.set('auth_token', AUTH_TOKEN, domain='.x.com')
    SESSION.cookies.set('ct0', CT0, domain='.x.com')


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


def get_user_id(screen_name):
    """Get Twitter user ID from screen name."""
    url = 'https://x.com/i/api/graphql/xmU6X_CKVnQ5lSrCbAmJsg/UserByScreenName'
    variables = json.dumps({
        "screen_name": screen_name,
        "withSafetyModeUserFields": True
    })
    features = json.dumps({
        "hidden_profile_subscriptions_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "subscriptions_verification_info_is_identity_verified_enabled": True,
        "subscriptions_verification_info_verified_since_enabled": True,
        "highlights_tweets_tab_ui_enabled": True,
        "responsive_web_twitter_article_notes_tab_enabled": True,
        "subscriptions_feature_can_gift_premium": True,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
    })
    params = {'variables': variables, 'features': features}
    try:
        r = SESSION.get(url, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data['data']['user']['result']['rest_id']
    except Exception as e:
        print(f'[Error] get_user_id: {e}')
    return None


def get_user_tweets(user_id):
    """Get latest tweets from a user."""
    url = 'https://x.com/i/api/graphql/Y9WM4Id6UcGFE8Z-rnEEhg/UserTweets'
    variables = json.dumps({
        "userId": user_id,
        "count": 20,
        "includePromotedContent": False,
        "withQuickPromoteEligibilityTweetFields": False,
        "withVoice": False,
        "withV2Timeline": True,
    })
    features = json.dumps({
        "rweb_tipjar_consumption_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "rweb_video_timestamps_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
    })
    params = {'variables': variables, 'features': features}

    try:
        r = SESSION.get(url, params=params, timeout=15)
        if r.status_code != 200:
            print(f'[!] Twitter API returned {r.status_code}')
            return []

        data = r.json()
        tweets = []

        # Parse timeline entries
        instructions = data.get('data', {}).get('user', {}).get('result', {}).get('timeline_v2', {}).get('timeline', {}).get('instructions', [])
        for instruction in instructions:
            entries = instruction.get('entries', [])
            for entry in entries:
                content = entry.get('content', {})
                item = content.get('itemContent', {})
                if not item:
                    # Try nested items (conversation threads)
                    items = content.get('items', [])
                    for sub in items:
                        item = sub.get('item', {}).get('itemContent', {})
                        tweet = extract_tweet(item)
                        if tweet:
                            tweets.append(tweet)
                    continue
                tweet = extract_tweet(item)
                if tweet:
                    tweets.append(tweet)

        return tweets

    except Exception as e:
        print(f'[Error] get_user_tweets: {e}')
        return []


def extract_tweet(item):
    """Extract tweet data from a timeline item."""
    try:
        result = item.get('tweet_results', {}).get('result', {})
        if not result:
            return None

        # Handle tweet with tombstone or other non-tweet results
        if result.get('__typename') not in ('Tweet', 'TweetWithVisibilityResults'):
            return None

        if result.get('__typename') == 'TweetWithVisibilityResults':
            result = result.get('tweet', {})

        legacy = result.get('legacy', {})
        if not legacy:
            return None

        tweet_id = legacy.get('id_str', '')
        text = legacy.get('full_text', '')

        if not tweet_id or not text:
            return None

        return {'id': tweet_id, 'text': text}
    except Exception:
        return None


def main():
    print('=' * 50)
    print('Walter Bloomberg Bot starting...')
    print(f'   Tracking: @{TARGET_USER}')
    print(f'   Interval: {CHECK_INTERVAL_SEC} seconds')
    print('=' * 50)

    if not AUTH_TOKEN or not CT0:
        print('[!] Missing TWITTER_AUTH_TOKEN or TWITTER_CT0')
        send_telegram('🔴 <b>Walter Bot: Missing cookies</b>')
        return

    setup_session()
    print('[Auth] Session configured with cookies')

    # Get user ID
    user_id = get_user_id(TARGET_USER)
    if not user_id:
        print(f'[Error] Could not find user @{TARGET_USER}')
        send_telegram(f'🔴 <b>Walter Bot: Could not find @{TARGET_USER}</b>')
        return

    print(f'[Init] Found @{TARGET_USER} (ID: {user_id})')

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
            tweets = get_user_tweets(user_id)

            if not tweets:
                fail_count += 1
                print(f'[!] No tweets returned (fail #{fail_count})')
                if fail_count >= 30:
                    print('[!] Too many failures. Cookies may have expired.')
                    send_telegram('🔴 <b>Walter Bot: Cookies expired</b>')
                    return
                import time
                time.sleep(30)
                continue

            fail_count = 0

            if first:
                seen = {t['id'] for t in tweets}
                print(f'[Init] {len(seen)} existing tweets — waiting for new ones...')
                first = False
            else:
                new_tweets = [t for t in tweets if t['id'] not in seen]
                for t in reversed(new_tweets):
                    ok = send_telegram(fmt(t['text'], t['id']))
                    status = 'OK' if ok else 'FAIL'
                    print(f'[{status}] {t["text"][:70]}')
                    seen.add(t['id'])
                    import time
                    time.sleep(0.5)

            import time
            time.sleep(CHECK_INTERVAL_SEC)

        except KeyboardInterrupt:
            print('\n[!] Bot stopped.')
            send_telegram('🔴 <b>Walter Bloomberg Bot הופסק.</b>')
            break
        except Exception as e:
            print(f'[Error] {e}')
            fail_count += 1
            import time
            time.sleep(30)


if __name__ == '__main__':
    main()
