import requests
from bs4 import BeautifulSoup
import time
import os
import datetime
import subprocess
import urllib.request
import tarfile
import asyncio
from edge_tts import Communicate
from requests_toolbelt.multipart.encoder import MultipartEncoder

# הגדרות ימות המשיח
USERNAME = os.getenv("YEMOT_USERNAME", "0747097784")
PASSWORD = os.getenv("YEMOT_PASSWORD", "595944")
TOKEN = f"{USERNAME}:{PASSWORD}"
UPLOAD_PATH = "ivr2:/3/001.wav"

# קבצים
MP3_FILE = "amitsegal.mp3"
WAV_FILE = "amitsegal.wav"
FFMPEG_PATH = "./bin/ffmpeg"

def get_last_telegram_message(channel_username):
    url = f"https://t.me/s/{channel_username}"
    response = requests.get(url, verify=False)
    if response.status_code != 200:
        print("❌ שגיאה בגישה לערוץ.")
        return None
    soup = BeautifulSoup(response.text, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_text')
    if not messages:
        print("❌ לא נמצאו הודעות.")
        return None
    return messages[-1].get_text(strip=True)

async def create_mp3(text, filename=MP3_FILE):
    tts = Communicate(text, voice="he-IL-AvriNeural")
    await tts.save(filename)

def ensure_ffmpeg():
    if os.path.exists(FFMPEG_PATH):
        return
    print("⬇️ מוריד ffmpeg...")
    os.makedirs("bin", exist_ok=True)
    url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    archive_path = "bin/ffmpeg.tar.xz"
    urllib.request.urlretrieve(url, archive_path)
    with tarfile.open(archive_path) as tar:
        for member in tar.getmembers():
            if "/ffmpeg" in member.name and not member.isdir():
                member.name = os.path.basename(member.name)
                tar.extract(member, path="bin")
                os.rename(os.path.join("bin", member.name), FFMPEG_PATH)
                os.chmod(FFMPEG_PATH, 0o755)
                break

def convert_to_wav():
    ensure_ffmpeg()
    subprocess.run([FFMPEG_PATH, "-y", "-i", MP3_FILE, WAV_FILE])

def upload_to_yemot():
    with open(WAV_FILE, 'rb') as f:
        m = MultipartEncoder(
            fields={
                'token': TOKEN,
                'path': UPLOAD_PATH,
                'autoNumbering': 'false',
                'file': ('amitsegal.wav', f, 'audio/wav')
            }
        )
        r = requests.post("https://www.call2all.co.il/ym/api/UploadFile", data=m, headers={'Content-Type': m.content_type})
        return r.json()

async def loop():
    last_seen = None
    while True:
        try:
            print(f"\n🕒 {datetime.datetime.now().strftime('%H:%M:%S')} בודק הודעות חדשות...")
            message = get_last_telegram_message("amitsegal")
            if message and message != last_seen:
                print("🆕 הודעה חדשה נמצאה!")
                await create_mp3("עמית סגל: " + message)
                convert_to_wav()
                result = upload_to_yemot()
                print("📤 הועלה לימות המשיח:", result)
                last_seen = message
            else:
                print("ℹ️ אין הודעה חדשה.")
        except Exception as e:
            print("❌ שגיאה:", e)

        await asyncio.sleep(300)  # כל 5 דקות

if __name__ == "__main__":
    asyncio.run(loop())
