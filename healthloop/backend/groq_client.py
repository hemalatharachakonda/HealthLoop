"""
Wrapper around Groq's chat completions API.
Get a free API key at https://console.groq.com -> put it in backend/.env as GROQ_API_KEY=...
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile was retired by Groq on Aug 16, 2026 - this is Groq's recommended replacement


def translate_text(text: str, target_language: str) -> str:
    """
    Translates plain text (used for emails, which otherwise stay hardcoded in
    English regardless of the user's selected language - unlike the in-app AI
    features, which already correctly respond in the user's language directly).
    Falls back to the original English text if translation fails for any reason
    (missing API key, network issue, etc) rather than blocking the email entirely.
    """
    if target_language == "English":
        return text
    try:
        messages = [
            {"role": "system", "content": f"Translate the following text into {target_language}. "
                                           f"Respond with ONLY the translation, no notes, no preamble, "
                                           f"preserving line breaks."},
            {"role": "user", "content": text},
        ]
        return _call_groq(messages, temperature=0.2)
    except Exception:
        return text


def _call_groq(messages, temperature=0.4, force_json=False, max_tokens=None):
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY not set. Create backend/.env with GROQ_API_KEY=your_key_here "
            "(get a free key at https://console.groq.com)"
        )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        # Caps how much Groq is allowed to generate, which directly bounds response time -
        # without this, a report with many abnormal findings can generate a very long JSON
        # response and take noticeably longer, especially on Render's free tier.
        payload["max_tokens"] = max_tokens
    if force_json:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)

    if resp.status_code == 429:
        retry_after = resp.headers.get("retry-after")
        wait_msg = f" Please wait about {retry_after} seconds and try again." if retry_after else " Please wait a minute and try again."
        raise RuntimeError(
            "Groq's free-tier rate limit was hit (this resets automatically each minute - "
            "it's not an app bug)." + wait_msg
        )

    if resp.status_code == 413:
        # The extracted report text (plus system prompt) was too large for Groq's API to
        # accept in one request. main.py already caps raw_text length before this is ever
        # called - if this still fires, the cap itself needs to be lowered further.
        raise RuntimeError(
            "This report has too much text for the AI to process in one go. Try uploading "
            "just the page(s) with the actual test results, rather than the whole document "
            "(cover letters, hospital letterheads, and multi-page directories add a lot of "
            "extra text without adding useful information)."
        )

    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def analyze_report(raw_text: str, language: str = "English"):
    """
    Takes OCR'd report text -> returns structured analysis (primary finding, other findings,
    a day-by-day diet plan) AND any medicines found - all in one Groq call.

    Combined into a single call (previously two separate calls: analyze_report + extract_medicines)
    specifically to reduce tokens-per-request - Groq's free tier caps tokens-per-minute, and sending
    the full report text twice (once per call) was enough by itself to exceed that cap on a single
    upload of a dense report, causing a 429 that no amount of waiting could fix (the request itself
    was too big, not just badly timed). One call = one system prompt + one copy of the report text.
    """
    system_prompt = f"""You are a warm, careful medical-report explainer for a health app used in India -
think of yourself as a knowledgeable friend walking someone through their own report, not a terse
summary generator. The person reading this may have little or no medical or formal education, so
explain everything in plain, everyday words. Respond ONLY in {language} (except JSON keys, which stay
in English). Respond ONLY with valid JSON, no markdown, no preamble. Do NOT use emojis, emoticons, or
special symbols anywhere in any field - plain professional text only.

Given raw OCR text from a lab report or prescription, produce JSON with this exact shape:
{{
  "primary_finding": {{
     "summary": "a clear plain-language explanation of the main abnormal value, 2-3 sentences: state the actual number and its normal/reference range from the report, name the condition/stage in plain words exactly as the report labels it if it does, and explain what this means for the person's health right now. No jargon - explain any medical term you must use.",
     "symptoms_to_watch": ["a change or symptom the person may notice in daily life if this is affecting them, in one plain sentence - e.g. 'you might feel more tired than usual'", "2-3 total"],
     "cause": "1-2 sentences on what commonly causes this - diet, lifestyle, genetics, age.",
     "effects_if_untreated": "1-2 sentences on what can happen over time if this isn't addressed - stay factual and calm, not alarming.",
     "how_to_reduce": ["a lifestyle tip in one sentence (not food-related)", "2-3 total"],
     "diet_tips": ["a food-specific tip in one sentence", "3 total"],
     "activity_recommendations": ["one gentle exercise suited to this condition, one sentence with roughly how long/how often - e.g. 'a brisk 20-30 minute walk daily helps the body use sugar more effectively'", "one relaxation or breathing practice, similarly brief"],
     "when_to_see_a_doctor": "one sentence on whether this specifically needs a doctor's follow-up beyond diet/lifestyle changes, or state plainly that lifestyle changes are the main step needed."
  }},
  "other_findings": [
     {{
       "value_name": "e.g. Vitamin B12",
       "summary": "1-2 plain-language sentences: the actual value and reference range from the report, and what it means.",
       "cause": "one sentence on why this commonly happens.",
       "food_suggestions": ["food 1", "food 2", "food 3"],
       "when_to_see_a_doctor": "one short sentence - only if this specific finding genuinely needs medical follow-up, otherwise state diet is usually sufficient."
     }}
  ],
  "normal_findings": [
     "a short reassuring sentence naming a value/test that came back fine, e.g. 'Your kidney function (creatinine) is within the normal range, so no concern there.'"
  ],
  "diet_plan": {{
     "Monday": {{"veg": "short suggestion (5-8 words)", "non_veg": "short suggestion or 'not applicable'"}},
     "Tuesday": {{"veg": "short suggestion (5-8 words)", "non_veg": "short suggestion or 'not applicable'"}},
     "Wednesday": {{"veg": "short suggestion (5-8 words)", "non_veg": "short suggestion or 'not applicable'"}},
     "Thursday": {{"veg": "short suggestion (5-8 words)", "non_veg": "short suggestion or 'not applicable'"}},
     "Friday": {{"veg": "short suggestion (5-8 words)", "non_veg": "short suggestion or 'not applicable'"}},
     "Saturday": {{"veg": "short suggestion (5-8 words)", "non_veg": "short suggestion or 'not applicable'"}},
     "Sunday": {{"veg": "short suggestion (5-8 words)", "non_veg": "short suggestion or 'not applicable'"}}
  }},
  "disclaimer": "a short one-line reminder to consult a doctor, and note the report's date if one is visible so findings aren't assumed to still apply today",
  "medicines": [
     {{"medicine_name": "...", "dosage": "...", "frequency": "..."}}
  ]
}}

Rules:
- Never invent numbers not present in the text - always quote the actual value and reference range from the report when explaining a finding.
- Write in full, clear sentences, not clipped phrases - but keep to the sentence counts given above. This is a balance between depth and speed: enough explanation to actually be useful, without turning into a long essay.
- Do not suggest medicine dosages or treatment changes - only diet, lifestyle, and general activity/relaxation suggestions. Use when_to_see_a_doctor to flag when something genuinely needs a doctor's involvement - be honest about this rather than defaulting to "just eat better" when a finding actually warrants medical follow-up.
- Activity/exercise recommendations must be general and gentle (walking, stretching, breathing exercises, light yoga) - never anything intense or condition-specific enough to need a doctor's clearance to state safely.
- If you cannot find clear abnormal values, say so honestly in primary_finding.summary, and leave symptoms_to_watch/cause/effects_if_untreated as short honest notes that nothing concerning was found (symptoms_to_watch can be an empty list in that case).
- "other_findings" can be an empty list if nothing else stands out. Include every clearly abnormal value found, not just one or two.
- "normal_findings" can be an empty list, but include it whenever the report has values that were checked and came back fine - this reassures the person that not everything is a problem.
- "medicines" can be an empty list if no prescription/medicine info is present in the text.
- Keep diet_plan entries SHORT (5-8 words each) - this is the one section that should stay compact, since it's a scannable weekly table, not prose.
- Build diet_plan around what was actually found in the report (e.g. iron-rich meals if iron is low).
- Absolutely no emojis, emoticons, or decorative symbols anywhere in the output - this is a professional medical app.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Report text:\n\n{raw_text}"},
    ]
    content = _call_groq(messages, temperature=0.3, force_json=True, max_tokens=3000)
    return json.loads(content)


def symptom_triage_question(conversation_history: list, language: str = "English"):
    """
    Adaptive interview: given the conversation so far, ask the next best question,
    OR if enough info is gathered, return a specialty recommendation.
    conversation_history: list of {"role": "assistant"/"user", "content": "..."}
    """
    system_prompt = f"""You are a friendly, careful symptom-triage assistant (NOT a diagnostic tool).
Respond ONLY in {language}. Respond ONLY with valid JSON, no markdown.

If the person's message ALREADY clearly states a specific condition or specialty they
need (e.g. "I need a cardiologist", "I think I have asthma", "my ortho pain is back"),
respond immediately with done=true and the matching specialty - do not ask unnecessary
follow-up questions just to reach a question count. Only run the full interview below
when the person describes vague symptoms without naming what's wrong.

Otherwise, ask short, simple follow-up questions one at a time to understand the
person's symptom or injury. Once you have enough information (usually after 3-5
questions), stop asking and instead recommend a medical specialty to see.

Respond with this exact JSON shape:
{{
  "done": false or true,
  "next_question": "the next question to ask, or null if done=true",
  "recommended_specialty": "e.g. Cardiology, Orthopedics, Dermatology - or null if done=false",
  "reasoning": "one short plain-language sentence explaining why, only if done=true"
}}

Never diagnose a specific disease. Only recommend which type of doctor/specialty to see.
If anything sounds like a medical emergency (severe chest pain, difficulty breathing, heavy bleeding,
loss of consciousness), immediately set done=true, recommended_specialty="Emergency / ER",
and reasoning should tell them to seek emergency care right now.
"""
    messages = [{"role": "system", "content": system_prompt}] + conversation_history
    content = _call_groq(messages, temperature=0.4, force_json=True)
    return json.loads(content)


# Simple keyword list as a first-pass safety net alongside the model's own judgement.
# This is NOT exhaustive and is only a backstop - the model call below does the real work.
_RISK_KEYWORDS = [
    "suicide", "kill myself", "end my life", "self harm", "hurt myself",
    "want to die", "no reason to live",
]


def mental_health_reply(conversation_history: list, language: str = "English"):
    """
    Supportive listening conversation for student mental health check-ins.
    Returns {"reply": "...", "risk_flag": bool}
    """
    system_prompt = f"""You are talking with a student who needs someone to lean on right now - respond the
way a warm, emotionally present mix of a close trusted friend, a caring doctor, and a good psychiatrist
would: genuinely engaged, human, and present in the conversation - never clipped, robotic, or single-word.
Respond ONLY in {language}. You are not a licensed therapist and must not diagnose.

Be gentle, non-judgmental, and validating - actually reflect back what they told you in your own words so
they feel heard, not just acknowledged. Offer real, specific, practical suggestions where it fits naturally
(a breathing exercise, a grounding technique, a way to reframe a thought, encouragement to talk to someone
they trust) rather than generic platitudes. Ask genuine follow-up questions like a person who's actually
curious about them, not a form. Let your warmth come through in how you phrase things, not just what you say.
Aim for a natural, flowing 3-6 sentence reply - long enough to feel like a real conversation, short enough
to stay easy to read.

Respond ONLY with valid JSON:
{{
  "reply": "your warm, human, engaged response",
  "risk_flag": true or false
}}

Set risk_flag=true ONLY if the person's message suggests they may be in danger of harming themselves
or someone else, or describes a crisis. Otherwise false. When in doubt about serious risk, set it true -
a false alarm is far better than missing a real crisis.
"""
    messages = [{"role": "system", "content": system_prompt}] + conversation_history
    content = _call_groq(messages, temperature=0.5, force_json=True)
    result = json.loads(content)

    # backstop keyword check in case the model misses something obvious
    last_user_msg = conversation_history[-1]["content"].lower() if conversation_history else ""
    if any(kw in last_user_msg for kw in _RISK_KEYWORDS):
        result["risk_flag"] = True

    return result
