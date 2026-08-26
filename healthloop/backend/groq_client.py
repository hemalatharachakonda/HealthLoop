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
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def analyze_report(raw_text: str, language: str = "English"):
    """
    Takes OCR'd report text -> returns structured analysis:
    primary finding, other findings, diet/lifestyle tips - all in the target language.
    """
    system_prompt = f"""You are a careful medical-report explainer for a health app used in India.
Respond ONLY in {language}. Respond ONLY with valid JSON, no markdown, no preamble.

Given raw OCR text from a lab report, produce JSON with this exact shape:
{{
  "primary_finding": {{
     "summary": "plain-language explanation of the main abnormal value, 2-3 short sentences, no jargon",
     "diet_tips": ["short tip 1", "short tip 2", "short tip 3"]
  }},
  "other_findings": [
     {{
       "value_name": "e.g. Iron / Hemoglobin",
       "summary": "one short plain-language sentence about this finding",
       "food_suggestions": ["food 1", "food 2"]
     }}
  ],
  "disclaimer": "a short one-line reminder to consult a doctor"
}}

Rules:
- Never invent numbers not present in the text.
- Keep language extremely simple, as if explaining to someone with no medical background.
- Do not suggest medicine dosages or treatment changes - only diet/lifestyle/food suggestions.
- If you cannot find clear abnormal values, say so honestly in primary_finding.summary.
- "other_findings" can be an empty list if nothing else stands out.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Report text:\n\n{raw_text}"},
    ]
    content = _call_groq(messages, temperature=0.3, force_json=True)
    return json.loads(content)


def extract_medicines(raw_text: str):
    """Extracts structured medicine info from prescription text."""
    system_prompt = """Extract medicines from this prescription text.
Respond ONLY with valid JSON: a list of objects like
[{"medicine_name": "...", "dosage": "...", "frequency": "..."}]
If no medicines are found, return an empty list. No markdown, no preamble."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": raw_text},
    ]
    content = _call_groq(messages, temperature=0.1, force_json=False)
    try:
        # model may wrap in an object; handle both list and {"medicines": [...]}
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v
            return []
        return parsed
    except json.JSONDecodeError:
        return []


def symptom_triage_question(conversation_history: list, language: str = "English"):
    """
    Adaptive interview: given the conversation so far, ask the next best question,
    OR if enough info is gathered, return a specialty recommendation.
    conversation_history: list of {"role": "assistant"/"user", "content": "..."}
    """
    system_prompt = f"""You are a friendly, careful symptom-triage assistant (NOT a diagnostic tool).
Respond ONLY in {language}. Respond ONLY with valid JSON, no markdown.

Ask short, simple follow-up questions one at a time to understand the person's symptom or injury.
Once you have enough information (usually after 3-5 questions), stop asking and instead recommend
a medical specialty to see.

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
