import os
import time
import requests
import re
import subprocess
import urllib.request
import tarfile
import asyncio
from bs4 import BeautifulSoup
from edge_tts import Communicate
from requests_toolbelt.multipart.encoder import MultipartEncoder

# ⚙️ פרטי התחברות למערכת ימות המשיח
USERNAME = "0747097784"
PASSWORD = "595944"
TOKEN = f"{USERNAME}:{PASSWORD}"
UPLOAD_PATH_PREFIX = "ivr2:/3/"

# 🧾 שמות קבצים
MP3_FILE = "amitsegal.mp3"
WAV_FILE_TEMPLATE = "amitsegal_{:03}.wav"
FFMPEG_PATH = "./bin/ffmpeg"

# ✅ הורדת ffmpeg אם לא קיים
def ensure_ffmpeg():
    if not os.path.exists(FFMPEG_PATH):
        print("⬇️ מוריד ffmpeg...")
        os.makedirs("bin", exist_ok=True)
        url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
        archive_path = "bin/ffmpeg.tar.xz"
        urllib.request.urlretrieve(url, archive_path)
        with tarfile.open(archive_path) as tar:
            for member in tar.getmembers():
                if os.path.basename(member.name) == "ffmpeg":
                    member.name = "ffmpeg"
                    tar.extract(member, path="bin")
        os.chmod(FFMPEG_PATH, 0o755)

# 🌐 שליפת ההודעה האחרונה מטלגרם
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

# 🎙️ יצירת קול בקובץ MP3
async def create_voice(text):
    communicate = Communicate(text=text, voice="he-IL-AvriNeural")
    await communicate.save(MP3_FILE)

# 🔄 המרת MP3 ל-WAV לפי הדרישות של ימות
def convert_to_wav(wav_filename):
    subprocess.run([
        FFMPEG_PATH,
        "-y",  # overwrite
        "-i", MP3_FILE,
        "-ar", "24000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        wav_filename
    ], check=True)

# ⬆️ העלאה לימות
def upload_to_yemot(wav_filename):
    with open(wav_filename, 'rb') as f:
        m = MultipartEncoder(
            fields={
                'token': TOKEN,
                'path': UPLOAD_PATH_PREFIX + os.path.basename(wav_filename),
                'message': 'uploading',
                'file': (os.path.basename(wav_filename), f, 'audio/wav')
            }
        )
        response = requests.post('https://www.call2all.co.il/ym/api/UploadFile', data=m, headers={'Content-Type': m.content_type})
        print("📤 הועלה לימות המשיח:", response.json())

# 🧮 מספר קובץ פנוי
def get_next_filename():
    existing = [f for f in os.listdir() if re.fullmatch(r"amitsegal_\d{3}\.wav", f)]
    nums = [int(re.search(r"(\d{3})", f).group(1)) for f in existing]
    next_num = max(nums) + 1 if nums else 1
    return WAV_FILE_TEMPLATE.format(next_num)

# 🔁 לולאה ראשית
def main_loop():
    ensure_ffmpeg()
    last_seen = ""
    print("🎧 מאזין לערוץ @amitsegal כל 5 דקות...")
    while True:
        print("\n🕒 בודק הודעות חדשות...")
        try:
            current = get_last_telegram_message("amitsegal")
            if current and current != last_seen:
                print("🆕 הודעה חדשה נמצאה!")
                print("📄 תוכן:", current)
                last_seen = current

                asyncio.run(create_voice(current))

                wav_file = get_next_filename()
                convert_to_wav(wav_file)
                upload_to_yemot(wav_file)
            else:
                print("ℹ️ אין הודעות חדשות.")
        except Exception as e:
            print("❌ שגיאה:", e)
        time.sleep(300)

if __name__ == "__main__":
    main_loop()
