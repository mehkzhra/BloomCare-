"Local educational fallback; never substitutes a PE prediction or prescription."

from app.bp_guidance import blood_pressure_guidance

MODEL = "local-basic-guide-v1"
SOURCE = "https://www.nice.org.uk/guidance/ng133/chapter/recommendations"


def basic_care_guide(context, language):
    observations = context.get("observations") or {}
    guidance = blood_pressure_guidance(observations)
    action = guidance["action"] if guidance else None
    if language == "ur":
        parts = [
            "بنیادی نگہداشت کی رہنمائی — خودکار AI منصوبہ دستیاب نہیں",
            "یہ محفوظ ریکارڈ پر مبنی عمومی معلومات ہیں، تشخیص یا نسخہ نہیں۔",
        ]
        actions = {
            "IMMEDIATE_MATERNITY_REVIEW": (
                "محفوظ بلڈ پریشر شدید حد میں تھا۔ اگر یہ موجودہ ریڈنگ ہے یا اس کا "
                "طبی جائزہ نہیں ہوا تو فوراً زچگی کی ٹیم یا ایمرجنسی سے رابطہ "
                "کریں۔ معمول کی ملاقات یا آن لائن جواب کا انتظار نہ کریں۔"
            ),
            "SAME_DAY_MATERNITY_CONTACT": (
                "محفوظ بلڈ پریشر بلند تھا۔ اگر یہ موجودہ ریڈنگ ہے یا اس کا طبی "
                "جائزہ نہیں ہوا تو آج ہی زچگی کی ٹیم سے رابطہ کریں۔"
            ),
        }
        parts.append(
            actions.get(
                action,
                (
                    "بلڈ پریشر کا انتباہ نہ ہونا پری ایکلیمپسیا کو خارج نہیں کرتا۔ "
                    "اپنی مقررہ طبی ملاقاتیں جاری رکھیں۔"
                ),
            )
        )
        parts.extend(
            [
                (
                    "شدید سر درد، نظر میں خرابی، پسلیوں کے نیچے شدید درد، قے یا چہرے، "
                    "ہاتھوں یا پاؤں کی اچانک سوجن ہو تو فوراً طبی مدد لیں، چاہے "
                    "اسکریننگ کا نتیجہ کم خطرہ ہو۔"
                ),
                (
                    "اپنی اصل ریڈنگز، ان کے اوقات، علامات، رپورٹس اور استعمال ہونے "
                    "والی دواؤں کی فہرست ڈاکٹر کو دکھائیں۔ پوچھیں کہ دوبارہ معائنہ کب "
                    "ضروری ہے۔ دوا یا خوراک خود تبدیل نہ کریں۔"
                ),
                (
                    "نامکمل یا غیر دستیاب PE نتیجہ منفی نتیجہ نہیں۔ یہ رہنمائی کوئی "
                    "نیا PE نتیجہ پیدا نہیں کرتی۔"
                ),
            ]
        )
    else:
        parts = [
            "Basic care guide — AI personalization unavailable",
            ("General information based on your saved record, not a diagnosis or prescription."),
        ]
        actions = {
            "IMMEDIATE_MATERNITY_REVIEW": (
                "Your saved blood pressure was in the severe range. If this is "
                "current or has not been medically reviewed, contact "
                "maternity/emergency care immediately. Do not wait for a routine "
                "appointment or an online reply."
            ),
            "SAME_DAY_MATERNITY_CONTACT": (
                "Your saved blood pressure was elevated. If this is current or has"
                " not been medically reviewed, contact your maternity team today."
            ),
        }
        parts.append(
            actions.get(
                action,
                (
                    "No blood-pressure alert does not rule out pre-eclampsia. Keep "
                    "your scheduled antenatal appointments."
                ),
            )
        )
        parts.extend(
            [
                (
                    "Seek medical help immediately for a severe headache, visual "
                    "disturbance, severe pain beneath the ribs, vomiting, or sudden "
                    "swelling of the face, hands or feet, even with a LOW screening "
                    "result."
                ),
                (
                    "Bring your actual readings and their dates, symptoms, reports and"
                    " medication list to your care team. Ask when you need another "
                    "assessment. Do not change medicines or doses yourself."
                ),
                (
                    "An incomplete or unavailable PE result is not a negative result. "
                    "This guide does not generate a new PE prediction."
                ),
            ]
        )
    parts.append("NICE NG133: " + SOURCE)
    return "\n\n".join(parts)
