from flask import Flask, render_template, request, jsonify
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
