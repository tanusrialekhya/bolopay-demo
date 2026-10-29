import os, re, json
from dotenv import load_dotenv

load_dotenv()
FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations.json")
MODEL = os.getenv("TRANSLATE_MODEL", os.getenv("LLM_MODEL", "openai/gpt-oss-20b"))

NAMES = {"हिंदी": "Hindi", "తెలుగు": "Telugu", "தமிழ்": "Tamil", "ಕನ್ನಡ": "Kannada",
         "മലയാളം": "Malayalam", "বাংলা": "Bengali", "मराठी": "Marathi",
         "ગુજરાતી": "Gujarati", "ਪੰਜਾਬੀ": "Punjabi"}

EN_TEXT = """
brand|BoloPay
nav_home|Home
nav_scan|Scan & Pay
nav_tx|Transactions
nav_help|Help
signin|Sign in
h1a|Speak. Pay.
h1b|Simplify.
sub|Your voice-powered payment assistant
start|Get Started
hello|Hello
how|How can I help you today?
tap|Tap and speak
tile_scan|Scan QR
tile_pay|Pay
tile_hist|History
tile_bal|Balance
say_like|Say things like
ex1|Pay ₹500 to Amma
ex2|Show my balance
ex3|Open history
ex4|Scan QR code
bub_home|Hi! Tap the mic and tell me what you need.
bub_welcome|Nice to meet you! What should I call you?
bub_scan|Show me a QR code and I will read it for you.
bub_pay|Just say the amount and the name. I will take care of the rest!
bub_pin|Type your PIN on the screen. I cannot listen to PINs.
bub_hist|Here are your recent payments.
bub_bal|Enter your PIN to see your balance.
bub_help|Try saying one of these. I am here to help!
bub_ok|Yay! Your payment went through!
bub_bad|Oh no! Something went wrong.
name_q|What should we call you?
name|Your name
cont|Continue
scan_title|Scan QR
scan_hint|Point the camera at a QR code
cam|Camera
gallery|Gallery
take_photo|Take photo
upload|Upload QR image
qr_ok|QR code detected
qr_fail|Could not read this QR code. Try again.
qr_pay|Pay this person
qr_check|Check the recipient details before paying.
qr_text|QR text
pay_title|Pay
pay_to|Pay to
amount|Amount (₹)
note|Add a note (optional)
pay_now|Pay Now
step1|Details
step2|PIN
step3|Done
pin_label|Enter your 4-digit PIN
confirm_pay|Confirm payment
cancel|Cancel
bad_pin|Wrong PIN
tries_left|tries left
too_many|Too many wrong attempts. Payment cancelled.
no_funds|Not enough balance for this payment.
success|Payment successful
paid_to|Paid to
new_bal|New balance
sim|This is a demo. No real money moved.
retry|Try again
done|Done
view_hist|View history
back|Back to Home
hist_title|Transaction history
empty|No transactions yet
received|Received
completed|Completed
bal_title|Account balance
holder|Account holder
acc|Account number
avail|Available balance
hide|Hide balance
unlock|Unlock
pin_bal|Enter your PIN
st_listen|Listening…
st_proc|Thinking…
st_speak|Speaking…
st_pin|Microphone is off
mic_denied|Please allow the microphone
st_err|Cannot reach the voice server
help_title|Help
try|Try saying
font|Font size
small|Small
medium|Medium
large|Large
lang_tip|Say: "Change language to Hindi"
say_hello|Hello! How can I help you?
say_ok|Payment successful. {amt} rupees sent to {name}.
say_bad|Wrong PIN. Please try again.
say_cancel|Too many wrong attempts. Payment cancelled.
say_nofunds|Sorry, your balance is not enough.
c_Amma|Amma
c_Dad|Dad
c_Rahul|Rahul
c_Priya|Priya
c_Shopkeeper|Shopkeeper
"""
EN = dict(l.split("|", 1) for l in EN_TEXT.strip().splitlines() if "|" in l)

_mem = {}


def _read():
    try:
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def ready(name):
    if name == "English" or name in _mem:
        return True
    have = _read().get(name, {})
    return all(k in have for k in EN)


def _chat(prompt):
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    last = None
    for kw in ({"extra_body": {"reasoning_effort": "low"}}, {}):
        try:
            r = client.chat.completions.create(
                model=MODEL, temperature=0, max_tokens=8000,
                messages=[{"role": "user", "content": prompt}], **kw)
            return r.choices[0].message.content or ""
        except Exception as e:
            last = e
    raise last


def _translate(name, keys):
    lang = NAMES[name]
    out, last = {}, None
    for i in range(0, len(keys), 34):
        part = {k: EN[k] for k in keys[i:i + 34]}
        prompt = (
            f"Translate these mobile payment app strings from English to {lang}. "
            f"Use short, natural, everyday spoken {lang}. Write ONLY in {lang} script, no English letters. "
            f"Write the brand BoloPay and the names Amma, Dad, Rahul, Priya in {lang} script. "
            f"Keep ₹, digits, the trailing … and placeholders like {{amt}} and {{name}} exactly as they are. "
            f"Return ONLY one JSON object with the SAME keys.\n" + json.dumps(part, ensure_ascii=False))
        got = {}
        for _ in range(3):
            try:
                d = json.loads(re.search(r"\{.*\}", _chat(prompt), re.S).group(0))
                for k, v in d.items():
                    v = str(v).strip()
                    if k in part and v and all(p in v for p in re.findall(r"\{\w+\}", part[k])):
                        got[k] = v
                if len(got) >= len(part) * 0.9:
                    break
            except Exception as e:
                last = e
        out.update(got)
    if len(out) < len(keys) * 0.5:
        raise RuntimeError(f"translation failed: {last!r}")
    return out


def get(name):
    if name == "English":
        return EN
    if name in _mem:
        return _mem[name]
    data = _read()
    have = data.get(name, {})
    missing = [k for k in EN if k not in have]
    if missing:
        try:
            have = {**have, **_translate(name, missing)}
            data[name] = have
            with open(FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print("[i18n]", e)
            return {**EN, **have}
    _mem[name] = {**EN, **have}
    return _mem[name]


if __name__ == "__main__":
    for n in NAMES:
        get(n)
        print(n, "ok" if ready(n) else "INCOMPLETE")