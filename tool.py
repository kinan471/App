import streamlit as st
import requests
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip,
    concatenate_videoclips, concatenate_audioclips
)
from gtts import gTTS
import os
import uuid
import re
import spacy

# تحميل النموذج اللغوي (إن أمكن)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None
    st.warning("⚠️ نموذج spaCy غير متوفر. سيتم استخدام استخراج كلمات بسيط.")

# 🔑 مفتاح Pexels من الأسرار
try:
    PEXELS_API_KEY = st.secrets["general"]["PEXELS_API_KEY"]
except KeyError:
    st.error("❌ لم يتم العثور على مفتاح Pexels. تأكد من إعداد `secrets.toml`.") 
    st.stop()

# إعدادات
TARGET_DURATION = 60  # ثانية
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
MUSIC_VOLUME = 0.3
MUSIC_URL = "https://cdn.pixabay.com/audio/2021/09/09/audio_22d566ebf6.mp3"

# كلمات بديلة
FALLBACK_KEYWORDS = [
    "motivation", "success", "workout", "inspiration", "hustle", "focus", "energy"
]

def extract_keywords_advanced(text):
    """استخراج كلمات مفتاحية باستخدام NLP أو تعبيرات نمطية"""
    if nlp:
        try:
            doc = nlp(text)
            keywords = [
                token.lemma_.lower() for token in doc
                if token.pos_ in ("NOUN", "ADJ") and len(token.lemma_) > 2
            ]
            return list(set(keywords))
        except:
            pass
    # الاستخراج البديل
    return list(set(re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())))

def search_video_pexels(query):
    """البحث عن فيديو بصيغة عمودية من Pexels"""
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=portrait&size=medium"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            videos = response.json().get("videos", [])
            if videos:
                # اختيار أفضل فيديو بصيغة MP4
                for video in videos[0]["video_files"]:
                    if "video_url" in video and video["width"] <= video["height"]:  # عمودي
                        return video["link"]
    except Exception as e:
        st.write(f"❌ خطأ في البحث عن `{query}`: {e}")
    return None

def download_file(url, filename, timeout=15):
    """تحميل ملف مع التقدم (progress bar)"""
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            return True
    except Exception as e:
        st.error(f"فشل تحميل {filename}: {e}")
        return False

def create_motivational_video(text, video_url):
    """إنشاء فيديو تحفيزي بجودة عالية وخلفية موسيقية مختلطة"""
    # أسماء ملفات مؤقتة
    video_file = f"video_{uuid.uuid4()}.mp4"
    audio_file = f"speech_{uuid.uuid4()}.mp3"
    music_file = f"music_{uuid.uuid4()}.mp3" if MUSIC_URL else None
    output_file = f"shorts_{uuid.uuid4()}.mp4"

    try:
        st.write("⬇️ جاري تحميل الفيديو...")
        if not download_file(video_url, video_file):
            raise Exception("فشل تحميل الفيديو")

        st.write("🔊 توليد الصوت من النص...")
        lang = 'ar' if any(ord(c) > 128 for c in text) else 'en'
        tts = gTTS(text=text.strip(), lang=lang, slow=False)
        tts.save(audio_file)

        # تحميل الموسيقى الخلفية
        music_clip = None
        if MUSIC_URL:
            st.write("🎵 تحميل الموسيقى الخلفية...")
            if download_file(MUSIC_URL, music_file):
                music_raw = AudioFileClip(music_file)
                # تكرار الموسيقى لتغطية 60 ثانية
                music_parts = []
                duration = 0
                while duration < TARGET_DURATION:
                    seg = music_raw.subclip(0, min(music_raw.duration, TARGET_DURATION - duration))
                    music_parts.append(seg)
                    duration += seg.duration
                music_clip = concatenate_audioclips(music_parts).volumex(MUSIC_VOLUME)
                music_raw.close()

        # تحميل الفيديو وتغيير حجمه
        st.write("🎬 معالجة الفيديو...")
        orig_clip = VideoFileClip(video_file)
        target_fps = min(orig_clip.fps, 30)  # تقليل fps لتقليل الحجم

        # تكرار الفيديو لتصل المدة لـ 60 ثانية
        clips = []
        total = 0
        while total < TARGET_DURATION:
            duration = min(orig_clip.duration, TARGET_DURATION - total)
            clips.append(orig_clip.subclip(0, duration))
            total += duration
        video_clip = concatenate_videoclips(clips, method="compose")
        video_clip = video_clip.resize(height=TARGET_HEIGHT)  # المحافظة على النسبة

        # تكرار الصوت
        speech = AudioFileClip(audio_file)
        speech_parts = []
        total_speech = 0
        while total_speech < TARGET_DURATION:
            seg = speech.subclip(0, min(speech.duration, TARGET_DURATION - total_speech))
            speech_parts.append(seg)
            total_speech += seg.duration
        final_speech = concatenate_audioclips(speech_parts)

        # دمج الصوت مع الموسيقى
        audio_tracks = [final_speech]
        if music_clip:
            audio_tracks.append(music_clip)
        final_audio = CompositeAudioClip(audio_tracks)
        video_with_audio = video_clip.set_audio(final_audio)

        # تصدير الفيديو
        st.write("⏳ جاري تصدير الفيديو النهائي...")
        video_with_audio.write_videofile(
            output_file,
            codec="libx264",
            audio_codec="aac",
            fps=target_fps,
            preset="fast",
            threads=4,
            temp_audiofile="temp_audio.m4a",
            remove_temp=True,
            logger=None  # إخفاء التفاصيل
        )

        # تنظيف الملفات
        orig_clip.close()
        video_clip.close()
        final_speech.close()
        if music_clip:
            music_clip.close()
        if os.path.exists(video_file):
            os.remove(video_file)
        if os.path.exists(audio_file):
            os.remove(audio_file)
        if music_file and os.path.exists(music_file):
            os.remove(music_file)

        return output_file

    except Exception as e:
        st.error(f"❌ خطأ أثناء إنشاء الفيديو: {e}")
        # تنظيف الملفات في حالة الفشل
        for f in [video_file, audio_file, music_file, output_file]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        return None

# واجهة المستخدم
st.set_page_config(page_title="منشئ YouTube Shorts", layout="centered")
st.title("🎬 منشئ فيديو YouTube Shorts تحفيزي 🚀")

st.markdown("""
أدخل رسالة تحفيزية، وسأُنتج لك فيديو جاهز لـ **YouTube Shorts**:
- 📱 أبعاد 1080x1920 (9:16)
- ⏱ دقيقة كاملة
- 🔊 صوت + موسيقى خلفية
- 🎵 دمج الصوت والموسيقى معًا
- 🌍 يدعم العربية والإنجليزية
""")

user_input = st.text_area(
    "✍️ اكتب رسالتك التحفيزية:",
    "استيقظ! النسخة الأفضل منك تنتظرك 💥",
    height=150
)

if st.button("🎥 أنشئ فيديو Shorts"):
    if not user_input.strip():
        st.error("❗ يرجى كتابة رسالة تحفيزية.")
    else:
        with st.spinner("جاري إنشاء الفيديو... قد يستغرق 1-3 دقائق"):
            # استخراج الكلمات المفتاحية
            keywords = extract_keywords_advanced(user_input)
            st.write("🔍 **الكلمات المفتاحية:**", ", ".join(keywords) if keywords else "باستخدام النص ككلمة مفتاحية.")

            # البحث عن فيديو
            video_url = None
            search_sources = keywords + FALLBACK_KEYWORDS
            for keyword in search_sources:
                st.write(f"🔎 البحث بـ: `{keyword}`")
                video_url = search_video_pexels(keyword)
                if video_url:
                    st.success(f"✅ وجد فيديو باستخدام: `{keyword}`")
                    break

            if not video_url:
                st.error("❌ لم يتم العثور على فيديو مناسب من Pexels.")
            else:
                output_path = create_motivational_video(user_input, video_url)
                if output_path and os.path.exists(output_path):
                    st.success("🎉 ✅ تم إنشاء الفيديو بنجاح!")
                    st.video(output_path)
                    with open(output_path, "rb") as f:
                        st.download_button(
                            "⬇️ حمل الفيديو",
                            f.read(),
                            file_name="shorts_motivational.mp4",
                            mime="video/mp4"
                        )
                    # تنظيف الفيديو النهائي بعد التحميل
                    st.session_state['cleanup'] = output_path

# تنظيف الملفات المؤقتة عند إعادة التحميل
if 'cleanup' in st.session_state:
    def cleanup():
        if os.path.exists(st.session_state['cleanup']):
            os.remove(st.session_state['cleanup'])
    st.button("🗑️ تنظيف الملفات", on_click=cleanup)
