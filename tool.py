import streamlit as st
import requests
from moviepy.editor import (
    VideoFileClip, AudioFileClip, concatenate_videoclips,
    concatenate_audioclips
)
from gtts import gTTS
import os
import uuid
import re
import spacy

# تحميل النموذج اللغوي للغة الإنجليزية (يمكن استبداله بالعربية إذا توفر)
try:
    nlp = spacy.load("en_core_web_sm")
except:
    nlp = None

# 🔑 استرجاع مفتاح Pexels من الأسرار
try:
    PEXELS_API_KEY = st.secrets["general"]["PEXELS_API_KEY"]
except KeyError:
    st.error("❌ لم يتم العثور على مفتاح Pexels. تأكد من إعداد الأسرار في لوحة التحكم.")
    st.stop()

# كلمات احتياطية
FALLBACK_KEYWORDS = [
    "motivation", "success", "workout", "inspiration", "hustle", "focus"
]

# الإعدادات
TARGET_DURATION = 60  # ثانية
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
MUSIC_VOLUME = 0.3

def extract_keywords_advanced(text):
    """استخدام معالجة اللغة لاستخراج كلمات مفتاحية أعمق"""
    if not nlp:
        return [w.lower() for w in re.findall(r'\w+', text) if len(w) > 2]
    doc = nlp(text)
    keywords = [token.lemma_.lower() for token in doc if token.pos_ in ("NOUN", "ADJ") and len(token.lemma_) > 2]
    # إزالة التكرار
    return list(set(keywords))

def search_video(query):
    """البحث عن فيديو من Pexels"""
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=portrait"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['videos']:
                return data['videos'][0]['video_files'][0]['link']
    except Exception as e:
        st.write(f"❌ خطأ في البحث بـ `{query}`: {e}")
    return None

def create_motivational_video(text, video_url):
    try:
        video_filename = f"{uuid.uuid4()}.mp4"
        audio_filename = f"{uuid.uuid4()}.mp3"
        music_filename = None
        final_filename = f"shorts_{uuid.uuid4()}.mp4"

        # تحميل الفيديو
        with requests.get(video_url, stream=True) as r:
            r.raise_for_status()
            with open(video_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        # توليد الصوت من النص
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(audio_filename)

        # تحميل الفيديو الأصلي
        original_clip = VideoFileClip(video_filename).resize(height=720)

        # بناء فيديو 60 ثانية مع تكرار
        clips = []
        total_duration = 0
        while total_duration < TARGET_DURATION:
            remaining = TARGET_DURATION - total_duration
            duration = min(original_clip.duration, remaining)
            clips.append(original_clip.subclip(0, duration))
            total_duration += duration

        video_clip = concatenate_videoclips(clips, method="compose")
        video_clip = video_clip.resize((TARGET_WIDTH, TARGET_HEIGHT))

        # الصوت من النص
        speech_audio = AudioFileClip(audio_filename)
        speech_clips = []
        total_speech = 0
        while total_speech < TARGET_DURATION:
            remaining = TARGET_DURATION - total_speech
            duration = min(speech_audio.duration, remaining)
            speech_clips.append(speech_audio.subclip(0, duration))
            total_speech += duration
        final_speech = concatenate_audioclips(speech_clips)

        # تحميل موسيقى خلفية
        MUSIC_URL = "https://cdn.pixabay.com/audio/2021/09/09/audio_22d566ebf6.mp3"
        try:
            r = requests.get(MUSIC_URL, stream=True, timeout=10)
            r.raise_for_status()
            music_filename = f"{uuid.uuid4()}.mp3"
            with open(music_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            music_raw = AudioFileClip(music_filename)
            music_parts = []
            total_music = 0
            while total_music < TARGET_DURATION:
                remaining = TARGET_DURATION - total_music
                duration = min(music_raw.duration, remaining)
                music_parts.append(music_raw.subclip(0, duration))
                total_music += duration
            music_audio = concatenate_audioclips(music_parts).volumex(MUSIC_VOLUME)
        except Exception as e:
            st.warning(f"⚠️ تعذر تحميل الموسيقى: {e}")
            music_audio = None

        # دمج الموسيقى مع الصوت
        if music_audio:
            final_audio = concatenate_audioclips([music_audio, final_speech])
        else:
            final_audio = final_speech

        # دمج الصوت مع الفيديو
        final_video = video_clip.set_audio(final_audio)

        # تصدير الفيديو
        final_video.write_videofile(
            final_filename,
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset='fast',
            threads=4,
            temp_audiofile='temp-audio.m4a',
            remove_temp=True
        )

        # التنظيف
        original_clip.close()
        video_clip.close()
        final_audio.close()
        final_video.close()
        os.remove(video_filename)
        os.remove(audio_filename)
        if music_filename and os.path.exists(music_filename):
            os.remove(music_filename)

        return final_filename

    except Exception as e:
        st.error(f"❌ حدث خطأ أثناء إنشاء الفيديو: {e}")
        # محاولة تنظيف الملفات إذا كانت موجودة
        for f in [video_filename, audio_filename, music_filename]:
            if f and os.path.exists(f):
                os.remove(f)
        return None

# واجهة المستخدم
st.set_page_config(page_title="YouTube Shorts تحفيزي", layout="centered")
st.title("🎬 منشئ فيديو YouTube Shorts تحفيزي 🚀")

st.markdown("""
أدخل رسالة تحفيزية، وسأُنتج لك فيديو جاهز لـ **YouTube Shorts**:
- 📱 أبعاد 1080x1920 (9:16)
- ⏱ دقيقة كاملة
- 🔊 صوت + موسيقى خلفية
- 🔍 فيديو مناسب للمحتوى
- ✍️ **بدون نص على الفيديو** (تم إزالته لحل الأخطاء)
""")

user_input = st.text_area(
    "✍️ اكتب رسالتك التحفيزية:",
    "استيقظ! النسخة الأفضل منك تنتظرك 💥",
    height=150
)

if st.button("🎥 أنشئ فيديو Shorts"):
    if not user_input.strip():
        st.error("يرجى كتابة رسالة أولاً!")
    else:
        with st.spinner("جاري إنشاء فيديو Shorts... قد يستغرق 1-3 دقائق"):
            # تحليل النص لاستخراج كلمات مفتاحية أعمق
            keywords = extract_keywords_advanced(user_input)
            st.write("🔍 **الكلمات المفتاحية:**", ", ".join(keywords) if keywords else "لا توجد كلمات مفتاحية مناسبة.")

            # البحث عن فيديو باستخدام الكلمات المفتاحية
            video_url = None
            for keyword in keywords:
                st.write(f"🔎 البحث بـ: `{keyword}`")
                video_url = search_video(keyword)
                if video_url:
                    st.success(f"✅ وجد فيديو باستخدام: `{keyword}`")
                    break

            # إذا لم يُوجد فيديو بالكلمات المفتاحية، جرب كلمات عامة
            if not video_url:
                st.info("جرب كلمات عامة...")
                for fallback in FALLBACK_KEYWORDS:
                    st.write(f"🔎 البحث بـ: `{fallback}`")
                    video_url = search_video(fallback)
                    if video_url:
                        st.success(f"✅ وجد فيديو باستخدام: `{fallback}`")
                        break

            if video_url:
                output = create_motivational_video(user_input, video_url)
                if output:
                    st.success("🎉 ✅ تم إنشاء فيديو YouTube Shorts بنجاح!")
                    st.video(output)
                    with open(output, "rb") as f:
                        st.download_button(
                            "⬇️ حمل الفيديو",
                            f.read(),
                            file_name="shorts_تحفيزي.mp4",
                            mime="video/mp4"
                        )
            else:
                st.error("❌ لم يتم العثور على فيديو مناسب.")
