import os
import urllib.request
import ssl
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string
import feedparser
import asyncio
import datetime
import edge_tts
import re

# הגדרות המערכת
SYSTEM_NUMBER = "0747097784"
PASSWORD = "595944"
SLUCHA = "3"
UPLOAD_PATH = f"ivr2:{SLUCHA}/"
CHECK_INTERVAL = 60  # זמן בין בדיקות בשניות

# פיד RSS וערוץ טלגרם
RSS_FEEDS = [
    "https://www.gov.il/he/collectors/news?officeId=2042b1a4-5ec1-44a9-84dc-764b19864cfa"
]
TELEGRAM_CHANNEL = "amitsegal"  # שם הערוץ בטלגרם

# סינון מילות מפתח
FILTER_KEYWORDS = ["פרסומת", "מודעה", "קישור", "לינק", "פרסום", "פרסומות"]

logs = []
sent_titles = set()
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="he" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>לוח מערכת ימות</title>
        <meta http-equiv="refresh" content="10">
        <style>
            body { font-family: sans-serif; background: #f5f5f5; padding: 20px; direction: rtl; }
            pre { background: #fff; padding: 10px; border: 1px solid #ccc; height: 80vh; overflow-y: scroll; }
        </style>
    </head>
    <body>
        <h2>יומן פעילות</h2>
        <pre>{{ log_content }}</pre>
    </body>
    </html>
    """, log_content="\n".join(logs[-200:]))

def log(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    logs.append(f"[{timestamp}] {message}")
    print(f"[{timestamp}] {message}")

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html)

def contains_filtered_word(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in FILTER_KEYWORDS)

def fetch_feed_with_headers(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx) as response:
            return feedparser.parse(response.read())
    except Exception as e:
        log(f"❌ שגיאה בבקשת RSS עם User-Agent: {e}")
        return feedparser.parse("")

def get_last_telegram_message(channel_username):
    url = f"https://t.me/s/{channel_username}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code != 200:
            log(f"❌ שגיאה בגישה לערוץ טלגרם: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        messages = soup.find_all('div', class_='tgme_widget_message_text')
        if not messages:
            log("❌ לא נמצאו הודעות בטלגרם.")
            return None

        last_message = messages[-1].get_text(strip=True)
        return last_message
    except Exception as e:
        log(f"❌ שגיאה בגרידת טלגרם: {e}")
        return None

def fetch_headlines():
    # בדיקת פיד RSS
    for feed_url in RSS_FEEDS:
        log(f"🔍 בודק פיד RSS: {feed_url}")
        feed = fetch_feed_with_headers(feed_url)

        if hasattr(feed, 'status') and feed.status != 200:
            log(f"⚠️ סטטוס HTTP {feed.status}, מדלג...")
            continue

        entries = feed.entries
        if not entries:
            log("ℹ️ הפיד RSS ריק.")
            continue

        for entry in entries:
            title = getattr(entry, 'title', '')
            summary = getattr(entry, 'summary', '')
            content_title = clean_html(title).strip()
            content_summary = clean_html(summary).strip()
            combined_content = f"{content_title} - {content_summary}"

            if contains_filtered_word(combined_content) or combined_content in sent_titles:
                continue
            sent_titles.add(combined_content)
            return "חדשות אמרי משה: " + combined_content

    # בדיקת טלגרם
    log(f"🔍 בודק ערוץ טלגרם: @{TELEGRAM_CHANNEL}")
    telegram_message = get_last_telegram_message(TELEGRAM_CHANNEL)
    if telegram_message:
        cleaned_message = clean_html(telegram_message).strip()
        if not contains_filtered_word(cleaned_message) and cleaned_message not in sent_titles:
            sent_titles.add(cleaned_message)
            return "חדשות אמית סגל: " + cleaned_message

    log("❌ לא נמצאו כותרות או הודעות חדשות.")
    return None

async def tts_edge(text, filename="news.wav"):
    try:
        communicate = edge_tts.Communicate(text, voice="he-IL-AvriNeural")
        await communicate.save(filename)
        return filename
    except Exception as e:
        log(f"❌ שגיאה בהמרה לקול: {e}")
        return None

def upload_to_yemot(file_path):
    try:
        url = "https://call2all.co.il/ym/api/UploadFile"
        token = f"{SYSTEM_NUMBER}:{PASSWORD}"
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'audio/wav')}
            data = {
                'token': token,
                'path': UPLOAD_PATH,
                'autoNumbering': 'true',
                'convertAudio': '1'
            }
            response = requests.post(url, data=data, files=files)
        return response.json()
    except Exception as e:
        log(f"❌ שגיאה בהעלאה לימות: {e}")
        return {"success": False, "message": str(e)}

async def job_loop():
    while True:
        log("⏱️ התחלת תהליך")
        text = fetch_headlines()
        if not text:
            log("❌ אין טקסט לשליחה.")
        else:
            log("🎙️ מייצר קובץ קול...")
            filename = await tts_edge(text)
            if filename:
                log("📤 מעלה לימות...")
                result = upload_to_yemot(filename)
                log("📦 תוצאה: " + str(result))
            else:
                log("❌ כשל ביצירת קול.")
        log("⏳ ממתין לדקה הבאה...\n")
        await asyncio.sleep(CHECK_INTERVAL)

def run_app():
    import threading
    threading.Thread(target=lambda: app.run(port=5000, debug=False, use_reloader=False)).start()
    asyncio.run(job_loop())

if __name__ == "__main__":
    run_app()
