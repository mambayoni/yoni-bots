#!/usr/bin/env python3
"""
סיכום בוקר כלכלי אוטומטי → טלגרם
רץ כל יום ב-09:15 (שעון ישראל)
"""

import os
import anthropic
import requests
import httpx
import re
import time
import schedule
from datetime import datetime
import sys

# ─── הגדרות ───────────────────────────
ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
TELEGRAM_TOKEN   = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ.get('MORNING_CHAT_ID', '410791143')
os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY
# ──────────────────────────────────────

# מקורות חדשות — דגש על מניות ספציפיות וחדשות חברות
SOURCES = {
    # === מקורות עיקריים לחדשות מניות ===
    "ביזפורטל חדשות שוק ההון": "https://www.bizportal.co.il/capitalmarket/news",
    "ביזפורטל שוק ההון": "https://www.bizportal.co.il/capitalmarket",
    "מאיה - הודעות חברות": "https://maya.tase.co.il/reports/company",
    "גלובס שוק ההון": "https://www.globes.co.il/news/home.aspx?nagish=1&fid=585",
    # === מקורות כלליים ===
    "גלובס ראשי": "https://www.globes.co.il/news/home.aspx?nagish=1&fid=2",
    "דה מרקר שוק ההון": "https://www.themarker.com/markets",
    "ICE חדשות": "https://ice.co.il/news",
    "פאנדר": "https://www.funder.co.il",
    "ynet כלכלה": "https://www.ynet.co.il/economy",
    "גלובס נדלן": "https://www.globes.co.il/news/home.aspx?nagish=1&fid=943",
}

SYSTEM_PROMPT = """אתה מסכם חדשות בוקר לסוחר יומי בבורסת ת"א.

⛔ כללי ברזל:
- אסור להמציא. אסור להמציא אחוזי שינוי, מחירים, או נתונים שלא כתובים במפורש במקורות.
- אם מספר לא מופיע במקורות — אל תכתוב מספר. פשוט תמצת את הכתבה.
- רק חדשות של היום — {today}. מה שקרה אתמול זה כבר היסטוריה. אם הכתבה מתייחסת לאירוע של אתמול או לפני — תתעלם לחלוטין.
- כתוב רק עברית. פורמט טלגרם.

סגנון:
- קצר וממוצת. שורה אחת לכל מניה/כתבה.
- פורמט: *שם חברה* — תמצית הכתבה בשורה אחת
- דוגמה: *רפאל* — רשות החברות גיבשה טיוטה להנפקה במסלול עוקף בורסה
- דוגמה: *TSG ביטחון* — זינקה 275% מאז הנפקה, יוצאת לרכישות
- אל תוסיף ניתוח או פרשנות משלך. רק תמצית מה שכתוב."""


def clean_html(html: str) -> str:
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL)
    html = re.sub(r'<br\s*/?>', '\n', html)
    html = re.sub(r'<li[^>]*>', '\n- ', html)
    html = re.sub(r'</?(p|div|h[1-6]|tr|td|th)[^>]*>', '\n', html)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    html = html.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    html = html.replace('&nbsp;', ' ').replace('&quot;', '"')
    return html.strip()


def fetch_page(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            text = clean_html(resp.text)
            return text[:10000]
    except Exception as e:
        print(f"  ! error fetching {url}: {e}")
        return ""


def build_user_prompt(pages: dict) -> str:
    now = datetime.now()
    today_he = now.strftime("%d/%m/%Y")
    day_names = ["שני","שלישי","רביעי","חמישי","שישי","שבת","ראשון"]
    day_heb = day_names[now.weekday()]

    parts = [
        f"צור סיכום בוקר כלכלי ליום {day_heb}, {today_he}.\n",
        f"היום הוא {today_he}. השתמש אך ורק בידיעות שפורסמו היום — {today_he}.\n",
        "ידיעות מתאריכים קודמים — התעלם לחלוטין.\n\n",
        "להלן תוכן עמודי החדשות מ-10 מקורות שונים:\n",
    ]
    for source_name, content in pages.items():
        if content:
            parts.append(f"\n--- {source_name} ---\n{content}\n")

    parts.append(f"""
פורמט הפלט — קצר וממוצת:

*בוקר טוב* ⭐
*יום {day_heb}, {today_he}*

*📊 חדשות מניות*
[שורה אחת לכל חברה שיש עליה כתבה היום. פורמט: *שם חברה* — תמצית הכתבה. ציין כמה שיותר חברות.]

*🌍 שווקים*
[שורה-שתיים על וול סטריט, חוזים עתידיים, מדדים — רק מה שכתוב במקורות]

*🏦 מאקרו*
[ריבית, שקל-דולר, אינפלציה — רק אם יש]

*⛽ אנרגיה וגיאו*
[נפט, גז, מתיחויות — רק אם יש]

⛔ אל תמציא שום מספר. אל תוסיף פרשנות. רק תמצת כתבות שקיימות במקורות.
""")
    return "".join(parts)


def generate_briefing(pages: dict) -> str:
    today = datetime.now().strftime("%d/%m/%Y")
    system = SYSTEM_PROMPT.replace("{today}", today)
    client = anthropic.Anthropic()
    print("  Sending to Claude...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": build_user_prompt(pages)}],
    )
    return message.content[0].text


def fix_markdown(text: str) -> str:
    lines = text.split('\n')
    fixed = []
    for line in lines:
        count = line.count('*')
        if count % 2 != 0:
            idx = line.rfind('*')
            line = line[:idx] + line[idx+1:]
        fixed.append(line)
    return '\n'.join(fixed)


def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    text = fix_markdown(text)
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    success = True
    for chunk in chunks:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown",
        }, timeout=10)
        if not resp.ok:
            print(f"  Markdown failed, sending as plain text")
            resp = requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
            }, timeout=10)
            if not resp.ok:
                print(f"  Telegram error: {resp.text}")
                success = False
    return success


def run_briefing():
    print(f"\n{'='*50}")
    print(f"  Morning Briefing — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*50}")

    pages = {}
    success_count = 0
    fail_count = 0

    for label, url in SOURCES.items():
        print(f"  Fetching {label}...")
        content = fetch_page(url)
        pages[label] = content
        if content:
            success_count += 1
            print(f"  V {label} — {len(content)} chars")
        else:
            fail_count += 1
            print(f"  X {label} — failed")

    print(f"\n  Fetch summary: {success_count} ok, {fail_count} failed")

    if success_count < 2:
        print("  ! Less than 2 sources succeeded. Skipping.")
        return

    print("\n  Generating briefing...")
    briefing = generate_briefing(pages)
    print(f"  Briefing ready ({len(briefing)} chars)")

    print("\n  Sending to Telegram...")
    if send_telegram(briefing):
        print("  V Sent successfully!")
    else:
        print("  X Failed to send")


if __name__ == "__main__":
    # Run immediately on startup
    print("Morning Briefing Bot starting...")
    print(f"  Scheduled for 09:15 Israel time (06:15 UTC)")
    run_briefing()

    # Schedule daily at 06:15 UTC = 09:15 Israel time
    schedule.every().day.at("06:15").do(run_briefing)

    print("\nWaiting for next scheduled run...")
    while True:
        schedule.run_pending()
        time.sleep(30)
