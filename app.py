from flask import Flask, render_template, request, jsonify
from groq import Groq
import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

TRANSCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcripts")

# Whisper tends to invent these phrases on silent or near-silent audio
WHISPER_HALLUCINATIONS = {
    "thank you.", "thank you", "thanks for watching!", "thanks for watching.",
    "thank you for watching.", "thank you for watching!", "you", "bye.", ".",
    "please subscribe.", "subtitles by the amara.org community",
}

TRANSLATE_PROMPT = """אתה מתורגמן סימולטני מקצועי מאנגלית לעברית.

תקבל קטע קצר מתוך תמלול של דיבור באנגלית, ולפעמים גם הקשר — המשפטים שנאמרו ממש לפניו.
תרגם לעברית רק את הקטע החדש, לא את ההקשר.

חוקים:
- תרגום טבעי וזורם בעברית מדוברת תקנית, לא מילולי
- שמור על שמות פרטיים, מותגים ומונחים טכניים מקובלים (אפשר באנגלית בסוגריים כשזה עוזר)
- אם הקטע נקטע באמצע משפט — תרגם את מה שיש, בלי להשלים
- החזר את התרגום בלבד, בלי הסברים, בלי מרכאות ובלי הקדמות"""

SUMMARY_PROMPT = """אתה עוזר שמסכם הרצאות, פגישות ושיחות בעברית.

תקבל תמלול מלא באנגלית. כתוב סיכום בעברית לפי המבנה הבא:

נושא: משפט אחד שמתאר במה עסק הדיבור

תקציר:
פסקה של 3-5 משפטים עם עיקרי הדברים

נקודות מרכזיות:
- כל נקודה בשורה נפרדת שמתחילה במקף

משימות והחלטות:
- רק אם הוזכרו משימות, החלטות או צעדי המשך. אם לא — השמט את החלק הזה לגמרי

חוקים:
- כתוב בעברית תקנית וברורה
- אל תמציא מידע שלא מופיע בתמלול
- בלי כוכביות, בלי סימני markdown ובלי כותרות נוספות"""

WHATSAPP_PROMPT = """אתה כותב תוכן לוואטסאפ המתמחה בהודעות קצרות ומושכות לאירועים וסדנאות בעברית.

כתוב הודעת וואטסאפ לפי המבנה הבא בדיוק:

שורה 1: אמוג'י מתאים + שם האירוע
שורה 2: ריקה
שורה 3-4: משפט פתיחה רגשי וקצר — פנייה ישירה לקהל, מה הבעיה שהאירוע פותר
שורה ריקה
שורה: תיאור קצר של מה ילמדו/יקבלו — 2-3 שורות עם אמוג'י
שורה ריקה
מתי?
📅 [יום] | [תאריך] | [שעה]
💻 [פורמט - זום/פנים אל פנים/היברידי]
שורה ריקה
🔗 להרשמה >> [אם ניתן קישור, שים אותו. אם לא — כתוב: [קישור להרשמה]]
שורה ריקה
📞 לפרטים — [אם ניתן טלפון/מייל, שים אותו. אם לא — השמט שורה זו]

חוקים:
- הודעה קצרה ומושכת — לא יותר מ-15 שורות סה״כ
- שימוש נכון באמוג'י — לא יותר מ-2-3 לשורה
- טון חם, ישיר, מזמין
- כתוב בעברית תקנית
- אל תוסיף מידע שלא ניתן לך
- אל תוסיף כוכביות, קווים או תגיות"""

FACEBOOK_PROMPT = """אתה כותב פוסטים לפייסבוק המתמחה בתוכן ערכי ומעורר מעורבות לאירועים וסדנאות בעברית.

כתוב פוסט פייסבוק לפי המבנה הבא:

פסקה 1 (2-3 שורות): פתיחה בסיפור אישי או תיאור מצב מוכר — לא מתחילים בשם האירוע, מתחילים בנרטיב שהקהל יזדהה איתו. כאילו אתה מספר לחברים.

שורה ריקה

פסקה 2 (2-3 שורות): התפתחות — מה השתנה, מה הוביל לאירוע, למה הוא נוצר. כולל את האמת מאחוריו.

שורה ריקה

פסקה 3 (1-2 שורות): ערך — מה המשתתפים יקבלו, מה ישתנה עבורם, למה שווה לבוא.

שורה ריקה

הנעה לפעולה: "מוזמנים להירשם בלינק שבתגובה" + קריאה לתייג — "תייגו [תיאור אנשים רלוונטיים] שיכולים להפיק מזה".

חוקים:
- טון אישי, חם, אותנטי — לא שיווקי מדי
- כתוב בגוף ראשון רבים או כאילו הארגון מדבר ישירות
- אל תכתוב את שם האירוע בשורה הראשונה — תן לסיפור להוביל
- אמוג'י — מינימלי, רק אם מתאים לטון
- אל תוסיף תאריך/שעה/מיקום אלא אם נאמר מפורשות שיש לכלול
- אל תוסיף כוכביות, קווים או תגיות
- אורך כולל: 8-12 שורות"""

SYSTEM_PROMPT = """אתה כותב שיווקי מקצועי המתמחה בכתיבת תוכן לאירועים וסדנאות בעברית.

כשתקבל מידע על אירוע, כתוב טקסט שיווקי לפי המבנה הבא בדיוק (ללא כוכביות, ללא תווים מיוחדים, ללא מספור):

שורה 1: שם האירוע/הסדנה בלבד
שורה 2: ריקה
שורה 3-5: פתיחה רגשית ומשכנעת — 2-3 משפטים שמתארים את האתגר או הבעיה שהאירוע פותר. פנייה ישירה לקהל.
שורה ריקה
משפט הצעת ערך: "ב[שם האירוע] תוכלו..." — מה הם יקבלו, מה ישתנה עבורם.
שורה ריקה
תיאור האירוע עצמו: איך הוא מתקיים (פנים אל פנים / אונליין), מה הפורמט.
שורה ריקה
"מה נלמד ב[שם]?"
שורה ריקה
[נושאים — כל נושא בשורה נפרדת, מופרד בפסיק מהבא, ללא נקודות ו-ללא מספור]
שורה ריקה
"מי צריך [שם]?"
שורה ריקה
[תיאור קהל היעד]
שורה ריקה
"מתי?"
[יום + תאריך]
[שעה]
שורה ריקה
"איפה?"
[כתובת]

חוקים:
- כתוב בעברית תקנית
- טון חם, מזמין, שיווקי אך אמיתי
- אל תוסיף כותרות מיותרות, תגיות HTML, כוכביות או קווים
- אל תוסיף מידע שלא ניתן לך
- הטקסט צריך להיות מוכן להעתקה ישירה לאתר"""


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    mode = data.get("mode", "free")

    if mode == "free":
        event_info = data.get("text", "")
    else:
        fields = data.get("fields", {})
        event_info = f"""שם האירוע: {fields.get('name', '')}
סוג האירוע: {fields.get('type', '')}
תחום: {fields.get('domain', '')}
תיאור כללי: {fields.get('description', '')}
מה ילמדו המשתתפים: {fields.get('topics', '')}
קהל יעד: {fields.get('audience', '')}
פורמט: {fields.get('format', 'פנים אל פנים')}
תאריך: {fields.get('date', '')}
שעה: {fields.get('time', '')}
מיקום: {fields.get('location', '')}"""

    if not event_info.strip():
        return jsonify({"error": "לא הוזן מידע"}), 400

    try:
        marketing_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"כתוב טקסט שיווקי לאירוע הבא:\n\n{event_info}"},
            ],
            max_tokens=2048,
        )
        whatsapp_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": WHATSAPP_PROMPT},
                {"role": "user", "content": f"כתוב הודעת וואטסאפ לאירוע הבא:\n\n{event_info}"},
            ],
            max_tokens=1024,
        )
        facebook_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": FACEBOOK_PROMPT},
                {"role": "user", "content": f"כתוב פוסט פייסבוק לאירוע הבא:\n\n{event_info}"},
            ],
            max_tokens=1024,
        )
        return jsonify({
            "result": marketing_response.choices[0].message.content,
            "whatsapp": whatsapp_response.choices[0].message.content,
            "facebook": facebook_response.choices[0].message.content,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/translator")
def translator():
    return render_template("translator.html")


@app.route("/translator/chunk", methods=["POST"])
def translate_chunk():
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "לא התקבל קובץ שמע"}), 400
    context = request.form.get("context", "")[-1000:]

    try:
        transcription = client.audio.transcriptions.create(
            file=(audio.filename or "chunk.webm", audio.read()),
            model="whisper-large-v3-turbo",
            language="en",
            prompt=context[-500:] or None,
            response_format="json",
            temperature=0.0,
        )
        english = (transcription.text or "").strip()
        if not english or english.lower() in WHISPER_HALLUCINATIONS:
            return jsonify({"english": "", "hebrew": ""})

        user_content = f"הקטע לתרגום:\n{english}"
        if context:
            user_content = f"הקשר (לא לתרגם):\n{context}\n\n" + user_content
        translation = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": TRANSLATE_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=512,
            temperature=0.2,
        )
        return jsonify({
            "english": english,
            "hebrew": translation.choices[0].message.content.strip(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/translator/summary", methods=["POST"])
def translator_summary():
    data = request.json or {}
    segments = data.get("segments", [])
    english = " ".join(s.get("english", "") for s in segments).strip()
    if not english:
        return jsonify({"error": "אין תמלול לסכם"}), 400

    try:
        summary_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": f"סכם את התמלול הבא:\n\n{english[-100000:]}"},
            ],
            max_tokens=2048,
            temperature=0.3,
        )
        summary = summary_response.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    title = re.sub(r"[^\w\- ]", "", data.get("title", ""), flags=re.UNICODE).strip()[:60]
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + (f"_{title.replace(' ', '_')}" if title else "") + ".json"
    try:
        os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
        with open(os.path.join(TRANSCRIPTS_DIR, filename), "w", encoding="utf-8") as f:
            json.dump({"title": title, "segments": segments, "summary": summary}, f, ensure_ascii=False, indent=2)
    except OSError:
        filename = None

    return jsonify({"summary": summary, "saved_as": filename})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
