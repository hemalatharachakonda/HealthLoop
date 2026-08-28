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


def _call_groq(messages, temperature=0.4, force_json=False):
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
summary generator. Respond ONLY in {language} (except JSON keys, which stay in English). Respond ONLY
with valid JSON, no markdown, no preamble.

Given raw OCR text from a lab report or prescription, produce JSON with this exact shape:
{{
  "primary_finding": {{
     "summary": "plain-language explanation of the main abnormal value. 4-6 sentences: state the actual number and its normal/reference range from the report, name the condition/stage in plain words, explain what it means for the person day-to-day, and why it matters if left unaddressed. No jargon - explain any medical term you must use.",
     "diet_tips": ["short tip 1", "short tip 2", "short tip 3", "short tip 4"]
  }},
  "other_findings": [
     {{
       "value_name": "e.g. Vitamin B12",
       "summary": "2-3 plain-language sentences: the actual value and reference range from the report, what it means, and why it's worth attention (e.g. 'this is important for your nerves and blood cells').",
       "food_suggestions": ["food 1", "food 2", "food 3"]
     }}
  ],
  "normal_findings": [
     "short reassuring line naming a value/test that came back fine, e.g. 'Kidney function (creatinine) - normal'"
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
- Keep language warm and simple, as if explaining to someone with no medical background, but do NOT be terse - a person reading this should feel like it was explained to them properly, not given a one-line label.
- Do not suggest medicine dosages or treatment changes - only diet/lifestyle/food suggestions.
- If you cannot find clear abnormal values, say so honestly in primary_finding.summary.
- "other_findings" can be an empty list if nothing else stands out. Include every clearly abnormal value found, not just one or two.
- "normal_findings" can be an empty list, but include it whenever the report has values that were checked and came back fine - this reassures the person that not everything is a problem.
- "medicines" can be an empty list if no prescription/medicine info is present in the text.
- Keep diet_plan entries SHORT (5-8 words each) - this keeps the response small and fast.
- Build diet_plan around what was actually found in the report (e.g. iron-rich meals if iron is low).
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Report text:\n\n{raw_text}"},
    ]
    content = _call_groq(messages, temperature=0.3, force_json=True)
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
    system_prompt = f"""You are a warm, supportive listener for a student mental health check-in feature.
Respond ONLY in {language}. You are NOT a therapist and must not diagnose.
Be gentle, non-judgmental, and validating. Ask at most one gentle follow-up question at a time.
Keep replies short (2-4 sentences).

Respond ONLY with valid JSON:
{{
  "reply": "your supportive response",
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
