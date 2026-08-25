// ---- Config ----
const API_BASE = "https://healthloop.onrender.com/api";

// ---- Simple "logged in user" handling (hackathon scope: no real auth) ----
function getUserId() {
  return localStorage.getItem("healthloop_user_id");
}
function getUserLanguage() {
  return localStorage.getItem("healthloop_language") || "English";
}
function setUser(userId, language) {
  localStorage.setItem("healthloop_user_id", userId);
  localStorage.setItem("healthloop_language", language);
}
function logout() {
  localStorage.removeItem("healthloop_user_id");
  localStorage.removeItem("healthloop_language");
  window.location.href = "index.html";
}

// Language code map: display name -> BCP-47 code for browser TTS
const LANG_CODES = {
  English: "en-IN",
  Hindi: "hi-IN",
  Telugu: "te-IN",
  Tamil: "ta-IN",
  Kannada: "kn-IN",
  Bengali: "bn-IN",
};

// ---- Free, zero-cost text-to-speech using the browser's built-in Web Speech API ----
// No API key, no backend cost. Voice availability/quality depends on the user's device/browser.
function speak(text, language) {
  if (!("speechSynthesis" in window)) {
    alert("Voice playback isn't supported in this browser.");
    return;
  }
  window.speechSynthesis.cancel(); // stop any current speech
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = LANG_CODES[language] || "en-IN";
  utterance.rate = 0.95;
  window.speechSynthesis.speak(utterance);
}

// ---- Fetch helper ----
async function apiPost(path, body, isFormData = false) {
  const opts = { method: "POST" };
  if (isFormData) {
    opts.body = body;
  } else {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Something went wrong" }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error("Request failed");
  return res.json();
}
