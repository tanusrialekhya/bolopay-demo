import os
import html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="BoloPay", page_icon="💙", layout="centered",
                   initial_sidebar_state="collapsed")

APP_PIN = "7777"                           # demo only; move to .env for anything real
MAX_PIN_TRIES = 3
VOICE_WS_URL = "ws://localhost:8000/ws"    # must match the uvicorn port

DEFAULTS = {
    "screen": "splash", "user_name": "", "language": "English", "font_size": "Medium",
    "history": [], "last_transcript": "", "last_answer": "",
    "pin_verified": False, "pending_payment": None, "pin_tries": 0, "bal_tries": 0,
    "payee": "Amma", "amount": 500.0, "last_voice_id": "",
    "voice_confirm": False, "result_kind": "", "result_msg": "",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v
ss = st.session_state

CONTACTS = ["Amma", "Dad", "Rahul", "Priya", "Shopkeeper"]
LANGUAGES = {
    "English": "en-IN", "हिंदी": "hi-IN", "తెలుగు": "te-IN", "தமிழ்": "ta-IN",
    "ಕನ್ನಡ": "kn-IN", "മലയാളം": "ml-IN", "বাংলা": "bn-IN", "मराठी": "mr-IN",
    "ગુજરાતી": "gu-IN", "ਪੰਜਾਬੀ": "pa-IN",
}

# ---------------- TRANSLATIONS ----------------
def parse(block):
    return dict(l.split("|", 1) for l in block.strip().splitlines() if "|" in l)

EN = parse("""
hello|Hello
scan|Scan
pay|Pay
history|History
hint|How can I help you today?
tap|Just talk
any|Speak in any language
welcome|Welcome to
tagline|Your voice-powered payment assistant
choose|Choose your language
name_q|What should we call you?
name|Your name
cont|Continue
language|Language
font|Font size
home|Home
help|Help
login|Login
prefs|Preferences
account|Account access
pin|Enter app PIN
unlock|Unlock account
holder|Account holder
number|Account number
balance|Available balance
hide|Hide account information
recipient|Pay to
amount|Amount (₹)
note|Add a note
confirm|I checked the recipient and amount
pay_now|Pay Now
back|Back to Home
recent|Transaction history
empty|No transactions yet
qr|Scan QR
upload|Upload QR image
read_qr|Read QR code
small|Small
medium|Medium
large|Large
last|Last conversation
you|You
bot|BoloPay
done|Paid
bad_pin|Incorrect PIN. Try again.
qr_ok|QR code detected
qr_fail|Could not read this QR code.
check|Check recipient details before paying.
sim|This is a simulated payment; no real funds moved.
opt_upload|Upload image
opt_camera|Use camera
take|Take a picture
try|Try saying
ex1|Pay ₹500 to Amma
ex2|Show my transactions
ex3|Scan a QR code
check_bal|Check balance
cancel|Cancel
pay_pin|Enter PIN to confirm payment
confirm_pay|Confirm payment
too_many|Too many wrong attempts. Payment cancelled.
success|Payment successful
retry|Try again
say_yes|Say “yes” to continue or “cancel” to stop
""")

try:                                   # optional: translations.py with EXTRA = {"हिंदी": {...}, ...}
    from translations import EXTRA
except Exception:
    EXTRA = {}

def get_tx():
    return {**EN, **EXTRA.get(ss.language, {})}

TX = get_tx()

def go(screen):
    if screen != "pay":
        ss.pending_payment = None
        ss.pin_tries = 0
        ss.voice_confirm = False
    if screen != "balance":
        ss.pin_verified = False
        ss.bal_tries = 0
    ss.screen = screen
    st.rerun()

# ---------------- DESIGN ----------------
font_size = {"Small": "14px", "Medium": "16px", "Large": "18px"}[ss.font_size]
FONT = ("'Inter','Noto Sans','Noto Sans Devanagari','Noto Sans Telugu','Noto Sans Tamil',"
        "'Noto Sans Kannada','Noto Sans Malayalam','Noto Sans Bengali','Noto Sans Gujarati',"
        "'Noto Sans Gurmukhi',sans-serif")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=Noto+Sans:wght@400;700&family=Noto+Sans+Devanagari:wght@400;700&family=Noto+Sans+Telugu:wght@400;700&family=Noto+Sans+Tamil:wght@400;700&family=Noto+Sans+Kannada:wght@400;700&family=Noto+Sans+Malayalam:wght@400;700&family=Noto+Sans+Bengali:wght@400;700&family=Noto+Sans+Gujarati:wght@400;700&family=Noto+Sans+Gurmukhi:wght@400;700&display=swap');
:root{color-scheme:light}
html,body,.stApp,.stApp p,.stApp label,.stApp button,.stApp input,.stApp li,.stApp h1,.stApp h2,.stApp h3{font-family:__FONT__}
.stApp{background:#d9e6f8;font-size:__FS__;color:#122b52}
header[data-testid="stHeader"]{background:transparent}
header[data-testid="stHeader"] *{color:#122b52!important}
#MainMenu,footer{visibility:hidden}
.block-container{box-sizing:border-box!important;height:calc(100vh - 24px)!important;
 width:calc((100vh - 24px)*.5625)!important;max-width:calc(100vw - 16px)!important;
 margin:12px auto!important;padding:16px 16px 24px!important;overflow-y:auto;overflow-x:hidden;
 border-radius:38px;border:8px solid #0e1b36;
 background:linear-gradient(180deg,#fff 0%,#f1f6ff 55%,#e2edff 100%);
 box-shadow:0 24px 64px #0e1b3655;scrollbar-width:none}
.block-container::-webkit-scrollbar{display:none}
@media (max-width:600px){.block-container{width:100vw!important;max-width:100vw!important;height:100vh!important;
 margin:0!important;border:0;border-radius:0}}
.stApp [data-testid="stMarkdownContainer"] p,.stApp label,.stApp label p,.stApp li,
.stApp h1,.stApp h2,.stApp h3{color:#122b52!important}
.stApp [data-testid="stCaptionContainer"] p{color:#788ba6!important}
[data-testid="stSidebar"]{background:#fff!important}
[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondaryFormSubmit"]{
 background:#fff!important;border:1px solid #d6e4fa!important;border-radius:16px!important;min-height:46px}
[data-testid="stBaseButton-secondary"] p,[data-testid="stBaseButton-secondaryFormSubmit"] p{color:#1265f1!important;font-weight:700}
[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]{
 background:linear-gradient(135deg,#10a5ff,#1648f4)!important;border:none!important;border-radius:16px!important;min-height:48px}
[data-testid="stBaseButton-primary"] p,[data-testid="stBaseButton-primaryFormSubmit"] p{color:#fff!important;font-weight:700}
[class*="st-key-n_"] button{min-height:92px!important;border-radius:20px!important}
[class*="st-key-n_"] button p{margin:0!important;font-size:.9em!important;line-height:1.4!important}
[class*="st-key-lang_"] button{min-height:54px!important}
.stApp [data-baseweb="input"],.stApp [data-baseweb="base-input"],.stApp [data-baseweb="select"]>div{
 background:#fff!important;border:1.5px solid #cfe0fb!important;border-radius:14px!important}
.stApp input{color:#0b1f44!important;-webkit-text-fill-color:#0b1f44!important;font-weight:600!important;background:#fff!important}
div[data-testid="stForm"]{border-radius:22px;padding:14px;background:#fff;border:1px solid #e4edfa}
.hero-card{display:flex;align-items:center;justify-content:space-between;gap:6px;padding:16px 12px 0 18px;
 margin-bottom:14px;overflow:hidden;border-radius:26px;color:#fff;
 background:linear-gradient(140deg,#19b0ff,#1265f1 60%,#1648f4);box-shadow:0 14px 30px #1265f14a}
.hc-small,.hc-sub{font-size:.85em;color:#fff;opacity:.92}.hc-title{font-size:1.55em;font-weight:800;color:#fff;margin:2px 0 6px}
.logo{width:46px;height:46px;border-radius:14px;display:flex;align-items:center;justify-content:center;
 color:#fff;font-size:28px;font-weight:800;background:linear-gradient(140deg,#10a5ff,#174cf2)}
.brand{display:flex;align-items:center;gap:12px;padding:6px 0 16px}.brand-title{font-size:22px;font-weight:800}
.muted{color:#788ba6;font-size:.82em}.blue{color:#1265f1}
.splash{text-align:center;padding:26px 0 0}
.splash-logo{width:104px;height:104px;margin:auto;border-radius:30px;display:flex;align-items:center;
 justify-content:center;font-size:68px;font-weight:800;color:#fff;background:linear-gradient(145deg,#10a5ff,#1648f4);
 animation:float 2.4s ease-in-out infinite}
.splash-title{color:#1265f1;font-size:36px;font-weight:800;margin-top:14px}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
.hero{text-align:center;padding:6px 4px 8px}.hero-title{font-size:1.5em;font-weight:800}
.greet{font-size:1.55em;font-weight:800;line-height:1.25}
.mic-ring{margin:10px auto 6px;width:150px;height:150px;border-radius:50%;display:flex;align-items:center;
 justify-content:center;background:radial-gradient(circle,#fff 39%,#e2edff 40%,#eff5ff 58%,#d5e6ff 59%,#f8fbff 74%);
 animation:pulse 2.2s ease-in-out infinite}
.mic-core{width:96px;height:96px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 color:#fff;font-size:40px;background:linear-gradient(145deg,#10a5ff,#174cf2)}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.04)}}
.tap-title{text-align:center;font-weight:800}.tap-sub{text-align:center;color:#788ba6;font-size:.82em;margin-bottom:8px}
.chat-card,.panel,.pay-card,.tx-row{background:#fff;border:1px solid #e4edfa;border-radius:18px;
 padding:12px 14px;margin:10px 0;box-shadow:0 4px 14px #1265f10d}
.chat-card .cap{color:#788ba6;font-size:.75em;margin-bottom:4px}
.pay-card{text-align:center;border-radius:22px}
.tx-row{display:flex;align-items:center;gap:12px}
.avatar{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 font-weight:800;color:#1265f1;background:#e3eeff}
.tx-name{font-weight:700}.tx-amt{margin-left:auto;text-align:right;font-weight:800}.tx-ok{color:#1aa35a;font-size:.75em}
.big-amount{text-align:center;font-size:2.8em;font-weight:800;margin:4px 0 8px}
.lock-badge{width:64px;height:64px;margin:4px auto 6px;border-radius:50%;display:flex;align-items:center;
 justify-content:center;font-size:30px;background:#e3eeff;border:1px solid #d6e4fa}
.say{background:#fff7e6;border:1px solid #ffd9a0;border-radius:14px;padding:10px 12px;text-align:center;font-weight:700;color:#8a4b00}
@keyframes pop{0%{transform:scale(.6);opacity:0}70%{transform:scale(1.08)}100%{transform:scale(1);opacity:1}}
@keyframes shake{0%,100%{transform:translateX(0)}20%,60%{transform:translateX(-8px)}40%,80%{transform:translateX(8px)}}
@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}
.mood-happy{animation:pop .6s ease both,bounce 1.2s ease-in-out .6s infinite}
.mood-sad{animation:shake .5s ease both}
</style>
"""
st.markdown(CSS.replace("__FONT__", FONT).replace("__FS__", font_size), unsafe_allow_html=True)

def show_brand():
    st.markdown('<div class="brand"><div class="logo">B</div><div><div class="brand-title">BoloPay</div>'
                '<div class="muted">Speak · Pay · Simplify</div></div></div>', unsafe_allow_html=True)

# ---------------- MASCOT ----------------
GIRL_SVG = """
<svg viewBox="0 0 240 255" width="__W__" xmlns="http://www.w3.org/2000/svg">
  <ellipse cx="120" cy="244" rx="82" ry="9" fill="#cfe1ff" opacity=".7"/>
  <path d="M164 52 Q224 62 214 128 Q208 170 182 196 Q200 140 172 104Z" fill="#241529"/>
  <circle cx="166" cy="56" r="8" fill="#ff7a59"/>
  <path d="M50 246 Q46 172 84 152 L156 152 Q194 172 190 246Z" fill="#ff7a59"/>
  <path d="M96 152 L120 188 L144 152Z" fill="#ffffff"/>
  <rect x="107" y="124" width="26" height="32" rx="11" fill="#e8a678"/>
  <path d="M180 176 Q216 156 214 116" stroke="#ff7a59" stroke-width="17" fill="none" stroke-linecap="round"/>
  <circle cx="214" cy="108" r="10" fill="#f0b48a"/>
  <path d="M62 178 Q46 204 74 218" stroke="#ff7a59" stroke-width="17" fill="none" stroke-linecap="round"/>
  <rect x="62" y="190" width="24" height="38" rx="6" fill="#122b52"/>
  <rect x="65" y="194" width="18" height="28" rx="4" fill="#4cc3ff"/>
  <circle cx="74" cy="226" r="9" fill="#f0b48a"/>
  <circle cx="126" cy="216" r="19" fill="#ffffff"/>
  <text x="126" y="225" font-size="25" font-weight="800" text-anchor="middle" fill="#1265f1" font-family="Arial">B</text>
  <ellipse cx="120" cy="86" rx="44" ry="49" fill="#f0b48a"/>
  <path d="M74 86 Q66 24 122 26 Q178 26 166 86 Q152 50 120 54 Q92 50 74 86Z" fill="#241529"/>
  <path d="M76 80 Q68 112 80 130 Q88 108 86 82Z" fill="#241529"/>
  <path d="M164 80 Q172 112 160 130 Q152 108 154 82Z" fill="#241529"/>
  <path d="M72 92 Q66 28 120 28 Q174 28 168 92" stroke="#1265f1" stroke-width="6" fill="none" stroke-linecap="round"/>
  <rect x="62" y="84" width="15" height="28" rx="7" fill="#1265f1"/>
  <rect x="163" y="84" width="15" height="28" rx="7" fill="#1265f1"/>
  <path d="M68 110 Q70 134 100 128" stroke="#1265f1" stroke-width="4" fill="none" stroke-linecap="round"/>
  <circle cx="102" cy="128" r="5.5" fill="#122b52"/>
  <circle cx="120" cy="64" r="2.8" fill="#e53950"/>
  <ellipse cx="103" cy="86" rx="4.5" ry="6.5" fill="#241529"/>
  <ellipse cx="137" cy="86" rx="4.5" ry="6.5" fill="#241529"/>
  <circle cx="104.5" cy="84" r="1.5" fill="#fff"/>
  <circle cx="138.5" cy="84" r="1.5" fill="#fff"/>
  <path d="M95 74 Q103 69 111 74" stroke="#241529" stroke-width="2.4" fill="none" stroke-linecap="round"/>
  <path d="M129 74 Q137 69 145 74" stroke="#241529" stroke-width="2.4" fill="none" stroke-linecap="round"/>
  <path d="M108 104 Q120 117 133 104" stroke="#b5434b" stroke-width="3" fill="none" stroke-linecap="round"/>
  <circle cx="92" cy="99" r="7" fill="#ef8f86" opacity=".55"/>
  <circle cx="148" cy="99" r="7" fill="#ef8f86" opacity=".55"/>
</svg>
"""

def svg(width):
    return GIRL_SVG.replace("__W__", str(width)).replace("\n", "")

def mascot(width=200):
    st.markdown(f'<div style="text-align:center">{svg(width)}</div>', unsafe_allow_html=True)

def mood_svg(mood, width=220):
    """happy = laughing + thumbs up, sad = crying + thumbs down."""
    s = svg(width)
    eye_l = '<ellipse cx="103" cy="86" rx="4.5" ry="6.5" fill="#241529"/>'
    eye_r = '<ellipse cx="137" cy="86" rx="4.5" ry="6.5" fill="#241529"/>'
    hl_l = '<circle cx="104.5" cy="84" r="1.5" fill="#fff"/>'
    hl_r = '<circle cx="138.5" cy="84" r="1.5" fill="#fff"/>'
    mouth = '<path d="M108 104 Q120 117 133 104" stroke="#b5434b" stroke-width="3" fill="none" stroke-linecap="round"/>'
    hand = '<rect x="202" y="100" width="24" height="20" rx="6" fill="#f0b48a"/>'
    if mood == "happy":
        s = s.replace(eye_l, '<path d="M95 88 Q103 78 111 88" stroke="#241529" stroke-width="3" fill="none" stroke-linecap="round"/>')
        s = s.replace(eye_r, '<path d="M129 88 Q137 78 145 88" stroke="#241529" stroke-width="3" fill="none" stroke-linecap="round"/>')
        s = s.replace(hl_l, "").replace(hl_r, "")
        s = s.replace(mouth, '<path d="M103 99 Q120 128 137 99Z" fill="#b5434b"/><path d="M110 112 Q120 120 130 112 Q120 116 110 112Z" fill="#ef8f86"/>')
        thumb = hand + '<path d="M206 101 L210 82 Q219 82 217 101Z" fill="#f0b48a"/>'
    else:
        s = s.replace(mouth, '<path d="M107 114 Q120 100 133 114" stroke="#b5434b" stroke-width="3" fill="none" stroke-linecap="round"/>')
        s = s.replace(hl_l, hl_l + '<path d="M99 94 Q96 106 101 108 Q106 106 103 94Z" fill="#6ec3ff"/>')
        thumb = hand + '<path d="M206 119 L210 138 Q219 138 217 119Z" fill="#f0b48a"/>'
    return s.replace("</svg>", thumb + "</svg>")

def hero_card(small, title, sub, width=118):
    st.markdown(f'<div class="hero-card"><div><div class="hc-small">{small}</div>'
                f'<div class="hc-title">{title}</div><div class="hc-sub">{sub}</div></div>'
                f'<div style="margin-bottom:-4px">{svg(width)}</div></div>', unsafe_allow_html=True)

def title(text):
    st.markdown(f'<div class="hero"><div class="hero-title">{text}</div></div>', unsafe_allow_html=True)

def result(kind, msg):
    ss.result_kind, ss.result_msg = kind, msg
    ss.pending_payment = None
    ss.voice_confirm = False
    ss.screen = "result"
    st.rerun()

# ---------------- SIDEBAR ----------------
with st.sidebar:
    show_brand()
    if ss.user_name:
        st.markdown(f"**{TX['hello']}, {html.escape(ss.user_name)}**")
    st.markdown("### " + TX["prefs"])
    if st.button("🌐  " + TX["language"], use_container_width=True, key="sb_lang"):
        go("language")
    sizes = ["Small", "Medium", "Large"]
    sel = st.radio(TX["font"], sizes, index=sizes.index(ss.font_size),
                   format_func=lambda x: TX[x.lower()], horizontal=True)
    if sel != ss.font_size:
        ss.font_size = sel
        st.rerun()
    st.divider()
    if st.button("🏠  " + TX["home"], use_container_width=True, key="sb_home"):
        go("home" if ss.user_name else "language")
    if st.button("❓  " + TX["help"], use_container_width=True, key="sb_help"):
        go("help")
    if st.button("👤  " + TX["login"], use_container_width=True, key="sb_login"):
        go("login")

TX = get_tx()

# ---------------- LIVE VOICE AGENT ----------------
# Needs the backend:  uvicorn backend:app --port 8000
_voice = components.declare_component(
    "bolopay_voice",
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_component"),
)

def current_stage():
    if ss.pending_payment:
        return "pin"
    if ss.screen == "pay" and ss.voice_confirm:
        return "confirm"
    return "idle"

def nav(screen):
    if screen != "pay":
        ss.pending_payment = None
        ss.pin_tries = 0
        ss.voice_confirm = False
    if screen != "balance":
        ss.pin_verified = False
        ss.bal_tries = 0
    ss.screen = screen

def apply_voice_action(v):
    """Run the agent's tool calls in order, then rerun once."""
    ss.last_transcript = v.get("transcript", "")
    ss.last_answer = v.get("reply", "")
    for a in v.get("actions") or []:
        t = a.get("tool")
        if t == "open_screen":
            nav(a.get("screen", "home"))
        elif t == "prepare_payment" and a.get("contact") in CONTACTS:
            ss.payee = a["contact"]
            try:
                ss.amount = max(1.0, float(a.get("amount") or ss.amount))
            except (TypeError, ValueError):
                pass
            nav("pay")
            ss.pending_payment = None
            ss.voice_confirm = True                      # waits for "yes"; PIN still required
        elif t == "confirm_payment" and ss.screen == "pay" and ss.voice_confirm:
            ss.pending_payment = {"name": ss.payee, "amount": ss.amount, "note": ""}
            ss.voice_confirm = False
            ss.pin_tries = 0
        elif t == "cancel":
            nav("home")
        elif t == "set_language":
            name = next((n for n, c in LANGUAGES.items() if c == a.get("lang")), None)
            if name:
                ss.language = name
        elif t == "set_font" and a.get("size") in ("Small", "Medium", "Large"):
            ss.font_size = a["size"]
    st.rerun()

if ss.screen not in ("splash", "language", "welcome"):
    stage = current_stage()
    muted = stage == "pin" or (ss.screen == "balance" and not ss.pin_verified)
    _v = _voice(
        ws_url=VOICE_WS_URL, language=LANGUAGES.get(ss.language, "en-IN"),
        screen=ss.screen, payee=ss.payee, amount=float(ss.amount),
        stage=stage, muted=muted, key="bolopay_voice", default=None,
        history=[f'{h["time"]}: ₹{h["amount"]:,.0f} to {h["name"]}' for h in ss.history[-5:]],
    )
    if _v and _v.get("id") != ss.last_voice_id:
        ss.last_voice_id = _v["id"]
        apply_voice_action(_v)

# ---------------- SCREENS ----------------
if ss.screen == "splash":
    st.markdown('<div class="splash"><div class="splash-logo">B</div><div class="splash-title">BoloPay</div>'
                '<div class="muted">Speak · Pay · Simplify</div></div>', unsafe_allow_html=True)
    mascot(220)
    if st.button("Get Started  →", type="primary", use_container_width=True):
        go("language")

elif ss.screen == "language":
    hero_card("🌐", TX["choose"], TX["tagline"])
    names = list(LANGUAGES.keys())
    for i in range(0, len(names), 2):
        cols = st.columns(2)
        for j, n in enumerate(names[i:i + 2]):
            with cols[j]:
                selected = n == ss.language
                if st.button(("✓  " if selected else "") + n, key=f"lang_{n}",
                             type="primary" if selected else "secondary", use_container_width=True):
                    ss.language = n
                    go("home" if ss.user_name else "welcome")

elif ss.screen == "welcome":
    hero_card(TX["welcome"], "BoloPay", TX["tagline"], width=128)
    st.markdown(f'<div class="hero-title" style="font-size:1.15em">👋 {TX["name_q"]}</div>', unsafe_allow_html=True)
    with st.form("name_form"):
        name = st.text_input(TX["name"], value=ss.user_name)
        ok = st.form_submit_button(TX["cont"] + "  →", type="primary", use_container_width=True)
    if ok:
        if name.strip():
            ss.user_name = name.strip()
            go("home")
        else:
            st.warning(TX["name"])
    if st.button("🌐  " + TX["language"], use_container_width=True, key="w_lang"):
        go("language")

elif ss.screen == "home":
    st.markdown(f'<div class="greet">{TX["hello"]}, <span class="blue">{html.escape(ss.user_name)}</span> 👋</div>'
                f'<div class="muted" style="margin-bottom:12px">{TX["hint"]}</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("📷\n\n" + TX["scan"], use_container_width=True, key="n_scan"):
            go("scan")
    with c2:
        if st.button("💸\n\n" + TX["pay"], use_container_width=True, key="n_pay"):
            go("pay")
    with c3:
        if st.button("🕒\n\n" + TX["history"], use_container_width=True, key="n_hist"):
            go("history")
    if st.button("🔒  " + TX["check_bal"], use_container_width=True, key="bal_btn"):
        go("balance")
    st.markdown('<div class="mic-ring"><div class="mic-core">🎙</div></div>'
                f'<div class="tap-title">{TX["tap"]}</div><div class="tap-sub">{TX["any"]}</div>',
                unsafe_allow_html=True)
    if ss.last_answer:
        st.markdown(f'<div class="chat-card"><div class="cap">{TX["last"]}</div>'
                    f'<div><b>{TX["you"]}:</b> {html.escape(ss.last_transcript)}</div>'
                    f'<div><b>{TX["bot"]}:</b> {html.escape(ss.last_answer)}</div></div>',
                    unsafe_allow_html=True)

elif ss.screen == "balance":
    title("🔒 " + TX["account"])
    if not ss.pin_verified:
        st.markdown('<div class="lock-badge">🔐</div>', unsafe_allow_html=True)
        with st.form("balance_pin_form"):
            pin = st.text_input(TX["pin"], type="password", max_chars=4)
            unlock = st.form_submit_button(TX["unlock"], type="primary", use_container_width=True)
        if unlock:
            if pin == APP_PIN:
                ss.pin_verified = True
                ss.bal_tries = 0
                st.rerun()
            else:
                ss.bal_tries += 1
                if ss.bal_tries >= MAX_PIN_TRIES:
                    ss.bal_tries = 0
                    result("bad", TX["too_many"])
                result("retry_bal", f'{TX["bad_pin"]} ({MAX_PIN_TRIES - ss.bal_tries})')
    else:
        st.markdown(f'<div class="panel"><b>{TX["holder"]}</b><br>{html.escape(ss.user_name)}<hr>'
                    f'<b>{TX["number"]}</b><br>XXXX XXXX 1234<hr><b>{TX["balance"]}</b><br>'
                    '<span style="font-size:1.8em;font-weight:800;color:#1265f1">₹12,450.00</span></div>',
                    unsafe_allow_html=True)
        if st.button("🙈  " + TX["hide"], use_container_width=True, key="hide_bal"):
            go("home")
    if st.button("←  " + TX["back"], use_container_width=True, key="bal_back"):
        go("home")

elif ss.screen == "scan":
    title("📷 " + TX["qr"])
    source = st.radio("QR", ["u", "c"], horizontal=True, label_visibility="collapsed",
                      format_func=lambda x: TX["opt_upload"] if x == "u" else TX["opt_camera"])
    uploaded = (st.file_uploader(TX["upload"], type=["png", "jpg", "jpeg"]) if source == "u"
                else st.camera_input(TX["take"]))
    if uploaded:
        st.image(uploaded, use_container_width=True)
        if st.button(TX["read_qr"], type="primary", use_container_width=True):
            try:
                import cv2
                import numpy as np
                img = cv2.imdecode(np.frombuffer(uploaded.getvalue(), dtype=np.uint8), cv2.IMREAD_COLOR)
                qr_text, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
                if qr_text:
                    st.success(TX["qr_ok"])
                    st.code(qr_text)
                    st.warning(TX["check"])
                else:
                    st.error(TX["qr_fail"])
            except Exception as exc:
                st.error(str(exc))
    if st.button("←  " + TX["back"], use_container_width=True):
        go("home")

elif ss.screen == "pay":
    title("💸 " + TX["pay"])
    pending = ss.pending_payment

    if pending:                                              # slide 2: PIN (typed, never spoken)
        st.markdown(f'<div class="pay-card"><div class="avatar" style="margin:0 auto 4px">{html.escape(pending["name"][0])}</div>'
                    f'<div class="tx-name">{html.escape(pending["name"])}</div>'
                    f'<div class="big-amount">₹{pending["amount"]:,.0f}</div>'
                    f'<div class="muted">{html.escape(pending["note"])}</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="lock-badge">🔐</div>', unsafe_allow_html=True)
        with st.form("pay_pin_form"):
            pin = st.text_input(TX["pay_pin"], type="password", max_chars=4)
            go_btn = st.form_submit_button("🔒  " + TX["confirm_pay"], type="primary", use_container_width=True)
        if go_btn:
            if pin == APP_PIN:
                ss.history.append({"name": pending["name"], "amount": pending["amount"],
                                   "note": pending["note"], "status": TX["done"],
                                   "time": datetime.now().strftime("%d %b, %I:%M %p")})
                ss.pin_tries = 0
                result("ok", f'₹{pending["amount"]:,.0f} · {pending["name"]}')
            else:
                ss.pin_tries += 1
                if ss.pin_tries >= MAX_PIN_TRIES:
                    ss.pin_tries = 0
                    result("bad", TX["too_many"])
                else:
                    ss.screen = "result"
                    ss.result_kind = "retry"
                    ss.result_msg = f'{TX["bad_pin"]} ({MAX_PIN_TRIES - ss.pin_tries})'
                    st.rerun()
        if st.button("✖  " + TX["cancel"], use_container_width=True, key="pay_cancel"):
            go("home")
    else:                                                    # slide 1: details
        st.markdown(f'<div class="pay-card"><div class="avatar" style="margin:0 auto 4px">{html.escape(ss.payee[0])}</div>'
                    f'<div class="tx-name">{html.escape(ss.payee)}</div>'
                    f'<div class="big-amount">₹{ss.amount:,.0f}</div></div>', unsafe_allow_html=True)
        if ss.voice_confirm:
            st.markdown(f'<div class="say">🎙 {TX["say_yes"]}</div>', unsafe_allow_html=True)
        with st.form("payment_form"):
            idx = CONTACTS.index(ss.payee) if ss.payee in CONTACTS else 0
            recipient = st.selectbox(TX["recipient"], CONTACTS, index=idx)
            amount = st.number_input(TX["amount"], min_value=1.0, value=max(1.0, float(ss.amount)), step=50.0)
            note = st.text_input(TX["note"])
            confirmed = st.checkbox(TX["confirm"])
            submit = st.form_submit_button(TX["pay_now"], type="primary", use_container_width=True)
        if submit:
            if not confirmed:
                st.warning(TX["confirm"])
            else:
                ss.payee, ss.amount = recipient, amount
                ss.pending_payment = {"name": recipient, "amount": amount, "note": note}
                ss.voice_confirm = False
                ss.pin_tries = 0
                st.rerun()
    if st.button("←  " + TX["back"], use_container_width=True, key="pay_back"):
        go("home")

elif ss.screen == "result":
    kind = ss.result_kind
    ok = kind == "ok"
    st.markdown(f'<div class="mood-{"happy" if ok else "sad"}" style="text-align:center">'
                f'{mood_svg("happy" if ok else "sad", 220)}</div>', unsafe_allow_html=True)
    title(("✅ " + TX["success"]) if ok else ("❌ " + html.escape(ss.result_msg)))
    if ok:
        st.markdown(f'<div class="chat-card"><div>{html.escape(ss.result_msg)}</div>'
                    f'<div class="cap">{TX["sim"]}</div></div>', unsafe_allow_html=True)
    if kind in ("retry", "retry_bal"):
        if st.button("🔁  " + TX["retry"], type="primary", use_container_width=True, key="res_retry"):
            ss.screen = "pay" if kind == "retry" else "balance"
            st.rerun()
    if st.button("←  " + TX["back"], use_container_width=True, key="res_back"):
        go("home")

elif ss.screen == "history":
    title("🕒 " + TX["recent"])
    if not ss.history:
        st.info(TX["empty"])
    for item in reversed(ss.history):
        note = f' · {html.escape(item["note"])}' if item["note"] else ""
        st.markdown(f'<div class="tx-row"><div class="avatar">{html.escape(item["name"][0])}</div>'
                    f'<div><div class="tx-name">{html.escape(item["name"])}</div>'
                    f'<div class="muted">{item["time"]}{note}</div></div>'
                    f'<div class="tx-amt">₹{item["amount"]:,.0f}<br><span class="tx-ok">{item["status"]}</span></div></div>',
                    unsafe_allow_html=True)
    if st.button("←  " + TX["back"], use_container_width=True):
        go("home")

elif ss.screen == "help":
    hero_card("❓", TX["help"], TX["hint"])
    st.markdown(f'<div class="panel"><b>{TX["try"]}:</b><br><br>🎙 “{TX["ex1"]}”<br><br>'
                f'🎙 “{TX["ex2"]}”<br><br>🎙 “{TX["ex3"]}”</div>', unsafe_allow_html=True)
    if st.button("←  " + TX["back"], use_container_width=True):
        go("home")

elif ss.screen == "login":
    title("👤 " + TX["login"])
    mascot(150)
    with st.form("login_form"):
        new_name = st.text_input(TX["name"], value=ss.user_name)
        ok = st.form_submit_button(TX["cont"] + "  →", type="primary", use_container_width=True)
    if ok and new_name.strip():
        ss.user_name = new_name.strip()
        go("home")
    if st.button("←  " + TX["back"], use_container_width=True):
        go("home")