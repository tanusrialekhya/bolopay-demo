"""BoloPay backend:  uvicorn backend:app --port 8000
audio -> Gnani STT + Whisper (both forced to the app language) -> gpt-oss LLM -> live TTS in the SAME language
The language never changes unless the user picks it (dropdown) or clearly says "change language to ...".
.env: GROQ_API_KEY, GNANI_STT_API_KEY, GNANI_TTS_API_KEY   Optional: LLM_MODEL, GROQ_STT_MODEL, GNANI_VOICE, LIVE_TTS=0
This server never moves money and never accepts a PIN."""


import os, json, base64, asyncio, logging, tempfile, threading
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
from pathlib import Path

import re
import unicodedata

BALANCE_PATTERNS = {
    "en-IN": [
        r"\bwhat is my balance\b",
        r"\bmy balance\b",
        r"\bcheck my balance\b",
        r"\bhow much money do i have\b",
        r"\bhow much balance\b",
    ],
    "hi-IN": [
        "मेरा बैलेंस",
        "मेरा बैलेंस कितना है",
        "मेरे खाते में कितने पैसे",
        "बैलेंस चेक करो",
    ],
    "te-IN": [
        "నా బ్యాలెన్స్",
        "నా బ్యాలెన్స్ ఎంత",
        "నా అకౌంట్ లో ఎంత",
        "బ్యాలెన్స్ ఎంత",
    ],
    "ta-IN": [
        "என் பேலன்ஸ்",
        "என் கணக்கில் எவ்வளவு பணம்",
        "என் பேலன்ஸ் எவ்வளவு",
    ],
    "kn-IN": [
        "ನನ್ನ ಬ್ಯಾಲೆನ್ಸ್",
        "ನನ್ನ ಖಾತೆಯಲ್ಲಿ ಎಷ್ಟು ಹಣ",
        "ಬ್ಯಾಲೆನ್ಸ್ ಎಷ್ಟು",
    ],
    "ml-IN": [
        "എന്റെ ബാലൻസ്",
        "എന്റെ അക്കൗണ്ടിൽ എത്ര പണം",
        "ബാലൻസ് എത്ര",
    ],
    "bn-IN": [
        "আমার ব্যালেন্স",
        "আমার অ্যাকাউন্টে কত টাকা",
        "ব্যালেন্স কত",
    ],
    "mr-IN": [
        "माझा बॅलन्स",
        "माझ्या खात्यात किती पैसे",
        "बॅलन्स किती",
    ],
    "gu-IN": [
        "મારું બેલેન્સ",
        "મારા ખાતામાં કેટલા પૈસા",
        "બેલેન્સ કેટલું",
    ],
    "pa-IN": [
        "ਮੇਰਾ ਬੈਲੰਸ",
        "ਮੇਰੇ ਖਾਤੇ ਵਿੱਚ ਕਿੰਨੇ ਪੈਸੇ",
        "ਬੈਲੰਸ ਕਿੰਨਾ",
    ],
}

BALANCE_UNAVAILABLE = {
    "en-IN": "Sorry, I can't retrieve your balance right now.",
    "te-IN": "క్షమించండి, ప్రస్తుతం మీ బ్యాలెన్స్ తెలుసుకోలేకపోతున్నాను.",
    "hi-IN": "क्षमा करें, अभी आपका बैलेंस नहीं मिल पा रहा है।",
    # Add translations for the remaining supported languages.
}

BALANCE_REPLY = {
    "en-IN": "Your current balance is ₹{amount:,.2f}.",
    "te-IN": "మీ ప్రస్తుత బ్యాలెన్స్ ₹{amount:,.2f}.",
    # Add translations for the remaining supported languages.
}


def make_balance_reply(lang, balance):
    if balance is None:
        return BALANCE_UNAVAILABLE.get(
            lang, BALANCE_UNAVAILABLE["en-IN"]
        )

    try:
        amount = float(balance)
        if not (0 <= amount < float("inf")):
            raise ValueError("Invalid balance")
    except (TypeError, ValueError):
        return BALANCE_UNAVAILABLE.get(
            lang, BALANCE_UNAVAILABLE["en-IN"]
        )

    template = BALANCE_REPLY.get(lang)
    if not template:
        return BALANCE_UNAVAILABLE.get(
            lang, BALANCE_UNAVAILABLE["en-IN"]
        )

    return template.format(amount=amount)
def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    return re.sub(r"\s+", " ", text.strip().lower())

def is_balance_question(text: str, lang: str) -> bool:
    text = normalize_text(text)
    patterns = BALANCE_PATTERNS.get(lang, [])

    return any(
        re.search(pattern, text) if lang == "en-IN"
        else pattern in text
        for pattern in patterns
    )



LOG_FILE = Path(__file__).resolve().parent / "conversation_logs.jsonl"


def save_interaction(record):
    record["timestamp"] = datetime.now(timezone.utc).isoformat()

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.write("\n")

load_dotenv()
log = logging.getLogger("bolopay")
logging.basicConfig(level=logging.INFO)

GNANI_STT_KEY = os.getenv("GNANI_STT_API_KEY", "")
GNANI_TTS_KEY = os.getenv("GNANI_TTS_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
ok_key = lambda k: bool(k) and "paste_your" not in k
HAVE_GNANI, HAVE_GROQ, HAVE_TTS = ok_key(GNANI_STT_KEY), ok_key(GROQ_KEY), ok_key(GNANI_TTS_KEY)

LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
WHISPER_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
GNANI_TTS_MODEL = os.getenv("GNANI_TTS_MODEL", "timbre-v2.5")
LIVE_TTS = os.getenv("LIVE_TTS", "1") != "0"
STREAM_RATE = 16000
_env_voice = os.getenv("GNANI_VOICE", "").strip()
VOICE_CANDIDATES = ([_env_voice] if _env_voice else []) + [None, "Nalini", "Kaveri", "Shubhra"]

app = FastAPI()
CONTACTS = ["Amma", "Dad", "Rahul", "Priya", "Shopkeeper"]
LANGS = ["en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "ml-IN", "bn-IN", "mr-IN", "gu-IN", "pa-IN"]
SCREENS = ["home", "history", "balance", "scan", "help", "pay"]
FONTS = ["Small", "Medium", "Large"]

CANNED = {
    "en-IN": "Sorry, I didn't catch that. Please tap and say it again.",
    "hi-IN": "माफ़ कीजिए, सुनाई नहीं दिया। कृपया फिर से बोलें।",
    "te-IN": "క్షమించండి, వినిపించలేదు. దయచేసి మళ్లీ చెప్పండి.",
    "ta-IN": "மன்னிக்கவும், கேட்கவில்லை. மீண்டும் சொல்லுங்கள்.",
    "kn-IN": "ಕ್ಷಮಿಸಿ, ಕೇಳಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ.",
    "ml-IN": "ക്ഷമിക്കണം, കേട്ടില്ല. ദയവായി വീണ്ടും പറയൂ.",
    "bn-IN": "দুঃখিত, শুনতে পাইনি। অনুগ্রহ করে আবার বলুন।",
    "mr-IN": "माफ करा, ऐकू आले नाही. कृपया पुन्हा बोला.",
    "gu-IN": "માફ કરશો, સંભળાયું નહીં. કૃપા કરીને ફરી બોલો.",
    "pa-IN": "ਮਾਫ਼ ਕਰਨਾ, ਸੁਣਾਈ ਨਹੀਂ ਦਿੱਤਾ। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਬੋਲੋ।",
}
PAY_READY = {
    "en-IN": "Payment is ready. Please enter your PIN on the screen.",
    "hi-IN": "भुगतान तैयार है। कृपया स्क्रीन पर अपना पिन डालें।",
    "te-IN": "చెల్లింపు సిద్ధంగా ఉంది. దయచేసి స్క్రీన్‌పై మీ పిన్ నమోదు చేయండి.",
    "ta-IN": "பணம் செலுத்த தயார். திரையில் உங்கள் பின்னை உள்ளிடவும்.",
    "kn-IN": "ಪಾವತಿ ಸಿದ್ಧವಾಗಿದೆ. ದಯವಿಟ್ಟು ಪರದೆಯಲ್ಲಿ ನಿಮ್ಮ ಪಿನ್ ನಮೂದಿಸಿ.",
    "ml-IN": "പേയ്‌മെന്റ് തയ്യാറാണ്. സ്ക്രീനിൽ നിങ്ങളുടെ പിൻ നൽകുക.",
    "bn-IN": "পেমেন্ট প্রস্তুত। অনুগ্রহ করে স্ক্রিনে আপনার পিন দিন।",
    "mr-IN": "पेमेंट तयार आहे. कृपया स्क्रीनवर तुमचा पिन टाका.",
    "gu-IN": "ચુકવણી તૈયાર છે. કૃપા કરીને સ્ક્રીન પર તમારો પિન દાખલ કરો.",
    "pa-IN": "ਭੁਗਤਾਨ ਤਿਆਰ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਸਕ੍ਰੀਨ 'ਤੇ ਆਪਣਾ ਪਿੰਨ ਦਰਜ ਕਰੋ।",
}
HELLO = {
    "en-IN": "Hello! How can I help you?",
    "hi-IN": "नमस्ते! मैं आपकी कैसे मदद करूँ?",
    "te-IN": "నమస్కారం! నేను మీకు ఎలా సహాయం చేయగలను?",
    "ta-IN": "வணக்கம்! நான் எப்படி உதவலாம்?",
    "kn-IN": "ನಮಸ್ಕಾರ! ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
    "ml-IN": "നമസ്കാരം! ഞാൻ എങ്ങനെ സഹായിക്കണം?",
    "bn-IN": "নমস্কার! আমি কীভাবে সাহায্য করতে পারি?",
    "mr-IN": "नमस्कार! मी तुम्हाला कशी मदत करू?",
    "gu-IN": "નમસ્તે! હું તમને કેવી રીતે મદદ કરી શકું?",
    "pa-IN": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡੀ ਕਿਵੇਂ ਮਦਦ ਕਰਾਂ?",
}
# words that must appear in what the user said before a language change is accepted
LANG_WORDS = ["language", "भाषा", "భాష", "மொழி", "ಭಾಷೆ", "ഭാഷ", "ভাষা", "ભાષા", "ਭਾਸ਼ਾ",
              "english", "hindi", "telugu", "tamil", "kannada", "malayalam", "bengali", "marathi", "gujarati", "punjabi",
              "हिंदी", "हिन्दी", "తెలుగు", "தமிழ்", "ಕನ್ನಡ", "മലയാളം", "বাংলা", "मराठी", "ગુજરાતી", "ਪੰਜਾਬੀ", "अंग्रेज़ी", "अंग्रेजी"]

try:
    with open(os.path.join("knowledge", "bolopay_knowledge.txt"), encoding="utf-8") as f:
        KNOWLEDGE = f.read()
except Exception:
    KNOWLEDGE = ""

SYSTEM = f"""You are BoloPay, a friendly voice payment assistant (DEMO: no real money moves).
Reply with ONLY one JSON object:
{{
    "category": "PAYMENT_QA | NAVIGATION | OUT_OF_SCOPE | UNCLEAR",
    "supported": true,
    "said": "...",
    "reply": "...",
    "actions": []
}}

INPUT: app_state.heard_options = the SAME audio transcribed by 1-2 speech engines. They can contain mistakes
(wrong words, numbers, names). Combine them and use common sense. Fix mis-heard contact names, numbers and amounts.
"said" = the sentence the user most likely said, corrected, in the same language and native script.

The user speaks the language app_state.language. "reply" is ONE short sentence (max 12 words), written ONLY in that
language's native script. NEVER answer in any other language.
TOOLS (zero or more in "actions"):
 {{"tool":"open_screen","screen":"home|history|balance|scan|help","mode":"camera|gallery"}}   (mode only for scan)
 {{"tool":"prepare_payment","payee":"<contact in English OR 10-digit mobile>","amount":<number>}}
 {{"tool":"set_language","lang":"<code from {LANGS}>"}}   ONLY if the user clearly asked to change the language
 {{"tool":"set_font","size":"Small|Medium|Large"}}
 {{"tool":"cancel"}}
 OUTPUT FORMAT:
Return ONLY one valid JSON object with these fields:
{{
    "category": "PAYMENT_QA",
    "supported": true,
    "said": "User's recognized question",
    "reply": "Assistant response in the user's language",
    "actions": []
}}

Allowed categories:
- PAYMENT_QA: Questions about BoloPay payment information.
- NAVIGATION: Requests to open or navigate website features.
- OUT_OF_SCOPE: Questions unrelated to BoloPay.
- UNCLEAR: Questions whose intent cannot be determined.

For unsupported information, set supported to false.
Never answer unrelated general-knowledge questions.
Preserve the user's language in every response.
CONTACTS: {", ".join(CONTACTS)}. Amma=mother/mummy/maa/అమ్మ/अम्मा/அம்மா/ಅಮ್ಮ/അമ്മ, Dad=father/papa/నాన్న/पापा/அப்பா/ಅಪ್ಪ/അച്ഛൻ,
Shopkeeper=dukaan/dukandar. Convert spoken numbers to digits ("five hundred"/"ఐదు వందలు"/"पाँच सौ" -> 500).
RULES: "Pay 500 to Rahul" -> prepare_payment (the app then opens the PIN step). "Open camera / scan" -> open_screen scan camera.
Balance, history, help, home and font requests are normal: do them. If amount or payee is missing, no action, say which is
missing. If the audio is meaningless, no action and ask them to repeat. Never ask for, repeat or accept a PIN.
Never say money was sent. No chit-chat, no questions.
{("HELP INFO:" + chr(10) + KNOWLEDGE) if KNOWLEDGE else ""}"""

# ---------------------------------------------------------------- helpers
def norm_phone(s):
    d = re.sub(r"\D", "", str(s))
    if len(d) == 12 and d.startswith("91"):
        d = d[2:]
    elif len(d) == 11 and d.startswith("0"):
        d = d[1:]
    return d if re.fullmatch(r"[6-9]\d{9}", d) else None


def canned(lang):
    return CANNED.get(lang, CANNED["en-IN"])


def clean_actions(raw, heard_text):
    out, bad_pay = [], False
    if not isinstance(raw, list):
        return out, bad_pay
    asked_lang = any(w in heard_text.lower() for w in LANG_WORDS)
    for a in raw[:4]:
        if not isinstance(a, dict):
            continue
        t = a.get("tool")
        if t == "open_screen" and a.get("screen") in SCREENS:
            o = {"tool": t, "screen": a["screen"]}
            if a["screen"] == "scan" and a.get("mode") in ("camera", "gallery"):
                o["mode"] = a["mode"]
            out.append(o)
        elif t == "prepare_payment":
            payee = str(a.get("payee", "")).strip()
            phone = norm_phone(payee)
            contact = next((c for c in CONTACTS if c.lower() == payee.lower()), None)
            try:
                amount = round(float(a.get("amount")), 2)
            except (TypeError, ValueError):
                amount = 0
            if (phone or contact) and 0 < amount <= 100000:
                return [{"tool": "prepare_payment", "payee": phone or contact, "amount": amount}], False
            bad_pay = True
        elif t == "set_language" and a.get("lang") in LANGS and asked_lang:      # never on its own
            out.append({"tool": t, "lang": a["lang"]})
        elif t == "set_font" and a.get("size") in FONTS:
            out.append({"tool": t, "size": a["size"]})
        elif t == "cancel":
            out.append({"tool": t})
    return out, bad_pay


_RANGES = {"hi-IN": [(0x0900, 0x097F)], "mr-IN": [(0x0900, 0x097F)], "bn-IN": [(0x0980, 0x09FF)],
           "pa-IN": [(0x0A00, 0x0A7F)], "gu-IN": [(0x0A80, 0x0AFF)], "ta-IN": [(0x0B80, 0x0BFF)],
           "te-IN": [(0x0C00, 0x0C7F)], "kn-IN": [(0x0C80, 0x0CFF)], "ml-IN": [(0x0D00, 0x0D7F)]}


def script_ok(text, lang):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    if lang == "en-IN":
        return sum(1 for c in letters if c.isascii()) / len(letters) >= 0.8
    rng = _RANGES.get(lang)
    if not rng:
        return True
    return sum(1 for c in letters if any(lo <= ord(c) <= hi for lo, hi in rng)) / len(letters) >= 0.6


PAY_RE = re.compile(r"(?:pay|send)\s*(?:rs\.?|₹)?\s*(\d[\d,]*)\s*(?:rupees|rs)?\s*to\s+([\w\s+\-]+)", re.I)


def rule_based(text):
    """Offline English fallback if the LLM is unreachable."""
    m = PAY_RE.search(text)
    if m:
        return {"reply": PAY_READY["en-IN"],
                "actions": [{"tool": "prepare_payment", "payee": m.group(2).strip(),
                             "amount": float(m.group(1).replace(",", ""))}]}
    t = text.lower()
    if "cancel" in t:
        return {"reply": "Cancelled.", "actions": [{"tool": "cancel"}]}
    if "camera" in t:
        return {"reply": "Opening camera.", "actions": [{"tool": "open_screen", "screen": "scan", "mode": "camera"}]}
    for word, screen in (("balance", "balance"), ("history", "history"), ("transaction", "history"),
                         ("scan", "scan"), ("help", "help"), ("home", "home")):
        if word in t:
            return {"reply": f"Opening {screen}.", "actions": [{"tool": "open_screen", "screen": screen}]}
    return None

# ---------------------------------------------------------------- STT (both engines forced to the app language)
EN_PROMPT = ("BoloPay voice payment. Pay 500 rupees to Amma. Send 200 to Dad, Rahul, Priya or Shopkeeper. "
             "Show balance, history, scan QR, open camera.")
_GROQ_S = None


def groq_sync():
    global _GROQ_S
    if _GROQ_S is None:
        from groq import Groq
        _GROQ_S = Groq(api_key=GROQ_KEY)
    return _GROQ_S


def _extract(r):
    if r is None:
        return ""
    if isinstance(r, str):
        return r.strip()
    get = (lambda k: r.get(k)) if isinstance(r, dict) else (lambda k: getattr(r, k, None))
    for k in ("transcript", "full_transcript", "text"):
        v = get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            t = _extract(v)
            if t:
                return t
    files = get("files")
    if files:
        return _extract(files[0] if not isinstance(files, dict) else list(files.values())[0])
    return ""


def _gnani_stt(wav, lang):
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="bolopay_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(wav)
        try:
            from gnani.stt import GnaniSTTClient
            r = GnaniSTTClient(api_key=GNANI_STT_KEY).transcribe(path, language_code=lang)
        except ImportError:
            from gnani.stt import GnaniSTTBatchClient
            r = GnaniSTTBatchClient(api_key=GNANI_STT_KEY).transcribe(files=path, language_code=lang)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return _extract(r)


def _whisper(wav, lang):
    kw = dict(file=("audio.wav", wav), model=WHISPER_MODEL, response_format="json", temperature=0,
              language=lang.split("-")[0])
    if lang == "en-IN":
        kw["prompt"] = EN_PROMPT
    r = groq_sync().audio.transcriptions.create(**kw)
    return (getattr(r, "text", "") or "").strip()


async def hear(wav, lang):
    """Returns a list of candidate sentences, all in `lang`. The language is never guessed."""
    if not (HAVE_GNANI or HAVE_GROQ):
        raise RuntimeError("Set GNANI_STT_API_KEY or GROQ_API_KEY in .env")
    g_t = asyncio.to_thread(_gnani_stt, wav, lang) if HAVE_GNANI else asyncio.sleep(0, result="")
    w_t = asyncio.to_thread(_whisper, wav, lang) if HAVE_GROQ else asyncio.sleep(0, result="")
    g, w = await asyncio.wait_for(asyncio.gather(g_t, w_t, return_exceptions=True), 25)
    g = g if isinstance(g, str) else ""
    w = w if isinstance(w, str) else ""
    log.info("STT (%s) gnani=%r | whisper=%r", lang, g, w)
    cands = []
    for t in ([w, g] if lang == "en-IN" else [g, w]):          # Gnani first for Indian languages, Whisper first for English
        t = t.strip()
        if t and t not in cands and script_ok(t, lang):
            cands.append(t)
    return cands

# ---------------------------------------------------------------- LLM (gpt-oss on Groq)
_GROQ_A = None
_LLM_VARIANTS = [{"extra_body": {"reasoning_effort": "low"}, "response_format": {"type": "json_object"}},
                 {"extra_body": {"reasoning_effort": "low"}}, {}]
_LLM_OK = {"i": 0}


def groq_async():
    global _GROQ_A
    if _GROQ_A is None:
        from groq import AsyncGroq
        _GROQ_A = AsyncGroq(api_key=GROQ_KEY)
    return _GROQ_A


async def llm(ctx):
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps({"app_state": ctx}, ensure_ascii=False)}]
    last = None
    for i in range(_LLM_OK["i"], len(_LLM_VARIANTS)):
        try:
            r = await asyncio.wait_for(groq_async().chat.completions.create(
                model=LLM_MODEL, messages=msgs, temperature=0, max_tokens=1200, **_LLM_VARIANTS[i]), 20)
            out = json.loads(re.search(r"\{.*\}", r.choices[0].message.content or "", re.S).group(0))
            _LLM_OK["i"] = i
            return out
        except Exception as e:
            last = e
            log.warning("LLM failed (model=%s variant=%d): %s", LLM_MODEL, i, e)
    raise last or RuntimeError("LLM unavailable")


async def understand(cands, lang, msg):
    heard_text = " ".join(cands)
    ctx = {"language": lang, "heard_options": cands, "screen": msg.get("screen"),
           "last_payee": msg.get("payee"), "last_amount": msg.get("amount"),
           "recent": (msg.get("history") or [])[-3:]}
    try:
        data = await llm(ctx)
    except Exception as e:
        log.error("LLM unavailable: %s", e)
        data = None
        if lang == "en-IN":
            for c in cands:
                data = rule_based(c)
                if data:
                    break
        data = data or {"reply": canned(lang), "actions": []}
    actions, bad_pay = clean_actions(data.get("actions"), heard_text)
    out_lang, switched = lang, False
    for a in actions:
        if a["tool"] == "set_language":
            out_lang, switched = a["lang"], True
    said = str(data.get("said") or "").strip()
    if not said or not script_ok(said, lang):
        said = cands[0]
    reply = str(data.get("reply") or "").strip()
    if actions and actions[0]["tool"] == "prepare_payment":
        reply = PAY_READY.get(out_lang, PAY_READY["en-IN"])
    elif switched:
        reply = HELLO.get(out_lang, HELLO["en-IN"])
    elif bad_pay or not reply or not script_ok(reply, out_lang):
        reply = canned(out_lang)
    return said, reply, out_lang, actions

# ---------------------------------------------------------------- TTS
_TTS_LOCK = asyncio.Lock()
_VOICE_OK = {}
_AUDIO = {}
_GTTS = {"en-IN": ("en", "co.in"), "hi-IN": ("hi", "com"), "te-IN": ("te", "com"), "ta-IN": ("ta", "com"),
         "kn-IN": ("kn", "com"), "ml-IN": ("ml", "com"), "bn-IN": ("bn", "com"), "mr-IN": ("mr", "com"),
         "gu-IN": ("gu", "com"), "pa-IN": ("pa", "com")}


def _voices(lang):
    v = VOICE_CANDIDATES[:]
    if lang in _VOICE_OK and _VOICE_OK[lang] in v:
        v.remove(_VOICE_OK[lang])
        v.insert(0, _VOICE_OK[lang])
    return v


def _stream_worker(text, lang, voice, loop, q):
    try:
        from gnani.tts import GnaniTTSStreamClient, AudioConfig
        kw = dict(model=GNANI_TTS_MODEL, language=lang,
                  audio_config=AudioConfig(sample_rate=STREAM_RATE, encoding="linear_pcm", container="raw"))
        if voice:
            kw["voice"] = voice
        first = True
        for chunk in GnaniTTSStreamClient(api_key=GNANI_TTS_KEY).synthesize_stream(text, **kw):
            if not chunk:
                continue
            if first and chunk[:4] == b"RIFF":
                chunk = chunk[44:]
            first = False
            if chunk:
                loop.call_soon_threadsafe(q.put_nowait, chunk)
        loop.call_soon_threadsafe(q.put_nowait, None)
    except Exception as e:
        loop.call_soon_threadsafe(q.put_nowait, e)


async def stream_audio(ws, text, lang):
    if not (LIVE_TTS and text and HAVE_TTS):
        return False
    key = (text, lang)
    if key in _AUDIO:
        await ws.send_json({"type": "audio_start", "format": "pcm16", "rate": STREAM_RATE})
        for c in _AUDIO[key]:
            await ws.send_bytes(c)
        return True
    loop = asyncio.get_running_loop()
    async with _TTS_LOCK:
        for voice in _voices(lang):
            q, buf = asyncio.Queue(), []
            threading.Thread(target=_stream_worker, args=(text, lang, voice, loop, q), daemon=True).start()
            while True:
                item = await q.get()
                if item is None:
                    if buf:
                        _VOICE_OK[lang] = voice
                        if len(_AUDIO) < 80:
                            _AUDIO[key] = buf
                        log.info("LIVE TTS ok voice=%s lang=%s chunks=%d", voice, lang, len(buf))
                        return True
                    break
                if isinstance(item, Exception):
                    log.warning("LIVE TTS failed (voice=%s lang=%s): %r", voice, lang, item)
                    if buf:
                        return True
                    break
                if not buf:
                    await ws.send_json({"type": "audio_start", "format": "pcm16", "rate": STREAM_RATE})
                buf.append(item)
                await ws.send_bytes(item)
    return False


def _tts_sync(text, lang, voice):
    from gnani.tts import GnaniTTSClient, AudioConfig
    kw = dict(model=GNANI_TTS_MODEL, language=lang,
              audio_config=AudioConfig(sample_rate=16000, encoding="linear_pcm", container="wav"))
    if voice:
        kw["voice"] = voice
    r = GnaniTTSClient(api_key=GNANI_TTS_KEY).synthesize(text, **kw)
    if isinstance(r, (bytes, bytearray)):
        return bytes(r)
    for k in ("audio", "audio_content", "content", "data"):
        v = r.get(k) if isinstance(r, dict) else getattr(r, k, None)
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
    raise RuntimeError("Gnani TTS returned no audio bytes")


def _gtts_sync(text, lang):
    import io
    from gtts import gTTS
    code, tld = _GTTS.get(lang, _GTTS["en-IN"])
    fp = io.BytesIO()
    gTTS(text, lang=code, tld=tld).write_to_fp(fp)
    return fp.getvalue()


async def clip_audio(text, lang):
    if HAVE_TTS:
        async with _TTS_LOCK:
            for voice in _voices(lang):
                try:
                    a = await asyncio.to_thread(_tts_sync, text, lang, voice)
                    _VOICE_OK[lang] = voice
                    return a
                except Exception as e:
                    log.warning("Gnani TTS clip (voice=%s lang=%s): %s", voice, lang, e)
    try:
        log.info("TTS: Google voice (%s)", lang)
        return await asyncio.to_thread(_gtts_sync, text, lang)
    except Exception as e:
        log.warning("Google TTS failed (browser voice will be used): %r", e)
        return None


async def speak_out(ws, text, lang):
    lang = lang if lang in LANGS else "en-IN"
    if not await stream_audio(ws, text, lang):
        audio = await clip_audio(text, lang)
        if audio:
            await ws.send_bytes(audio)
    await ws.send_json({"type": "done"})

# ---------------------------------------------------------------- one request
async def handle(ws, msg):
    lang = msg.get("language") if msg.get("language") in LANGS else "en-IN"
    if msg.get("type") == "speak":
        await speak_out(ws, str(msg.get("text", ""))[:300], lang)
        return
    if msg.get("stage") == "pin" or msg.get("muted"):
        await ws.send_json({"type": "warn", "reason": "muted"})
        return
    try:
        wav = base64.b64decode(msg.get("audio", ""))
    except Exception:
        wav = b""
    if len(wav) < 4000:
        await ws.send_json({"type": "warn", "reason": "too_short"})
        return
    try:
        cands = await hear(wav, lang)
    except Exception as e:
        log.exception("STT failed")
        await ws.send_json({"type": "error", "message": f"STT failed: {e!r}"})
        return
    log.info("HEARD (%s): %r", lang, cands)

    if not cands:                                                   # say so out loud, in the app language
        await ws.send_json({"type": "transcript", "text": "", "lang": lang})
        await ws.send_json({"type": "action", "reply": canned(lang), "lang": lang, "actions": []})
        await speak_out(ws, canned(lang), lang)
        return
    if any(re.fullmatch(r"[\d\s,.\-]{4,}", c) for c in cands):      # a spoken PIN is never accepted
        await ws.send_json({"type": "transcript", "text": "••••", "lang": lang})
        await ws.send_json({"type": "action", "reply": canned(lang), "lang": lang, "actions": []})
        await speak_out(ws, canned(lang), lang)
        return

    await ws.send_json({"type": "transcript", "text": cands[0], "lang": lang})
    said, reply, out_lang, actions = await understand(cands, lang, msg)
    log.info("SAID: %r | REPLY (%s): %r | actions=%s", said, out_lang, reply, actions)
    save_interaction({
    "language": lang,
    "transcript_candidates": cands,
    "user_text": said,
    "assistant_language": out_lang,
    "assistant_reply": reply,
    "actions": actions,
    "screen": msg.get("screen"),
    "llm_model": LLM_MODEL
})
    await ws.send_json({"type": "action", "said": said, "reply": reply, "lang": out_lang, "actions": actions})
    await speak_out(ws, reply, out_lang)


@app.on_event("startup")
async def warm():
    if HAVE_GROQ:
        groq_sync()
        groq_async()
    log.info("BoloPay backend ready | LLM=%s | whisper=%s | gnani_stt=%s gnani_tts=%s groq=%s",
             LLM_MODEL, WHISPER_MODEL, HAVE_GNANI, HAVE_TTS, HAVE_GROQ)


@app.get("/health")
async def health():
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            try:
                await handle(ws, msg)
            except WebSocketDisconnect:
                raise
            except Exception as e:
                log.exception("request failed")
                await ws.send_json({"type": "error", "message": str(e)})
    except WebSocketDisconnect:
        pass