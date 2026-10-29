import os
import copy
import time
import html
import base64
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

import i18n

load_dotenv()
st.set_page_config(page_title="BoloPay", page_icon="💙", layout="wide", initial_sidebar_state="collapsed")

APP_PIN = "7777"                                              # demo only
MAX_PIN_TRIES = 3
VOICE_WS_URL = os.getenv("VOICE_WS_URL", "ws://localhost:8000/ws")
HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "screen": "home", "user_name": "", "language": "English", "lang_sel": "English", "pending_lang": "",
    "font_size": "Medium", "balance": 5000.0,
    "history": [
        {"name": "Priya", "amount": 200.0, "type": "received", "note": "", "time": "28/10 10:20"},
        {"name": "Rahul", "amount": 500.0, "type": "paid", "note": "", "time": "28/10 14:30"},
    ],
    "bubble": "", "heard": "", "say": None, "last_voice_id": "",
    "pin_verified": False, "pending_payment": None, "pin_tries": 0, "bal_tries": 0,
    "payee": "Amma", "amount": 500.0, "scan_mode": "camera",
    "result_kind": "", "result_msg": "", "result_data": {},
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = copy.deepcopy(v)
ss = st.session_state

CONTACTS = ["Amma", "Dad", "Rahul", "Priya", "Shopkeeper"]
LANGUAGES = {"English": "en-IN", "हिंदी": "hi-IN", "తెలుగు": "te-IN", "தமிழ்": "ta-IN", "ಕನ್ನಡ": "kn-IN",
             "മലയാളം": "ml-IN", "বাংলা": "bn-IN", "मराठी": "mr-IN", "ગુજરાતી": "gu-IN", "ਪੰਜਾਬੀ": "pa-IN"}
FONT_OF = {"English": "Inter", "हिंदी": "Noto Sans Devanagari", "मराठी": "Noto Sans Devanagari",
           "తెలుగు": "Noto Sans Telugu", "தமிழ்": "Noto Sans Tamil", "ಕನ್ನಡ": "Noto Sans Kannada",
           "മലയാളം": "Noto Sans Malayalam", "বাংলা": "Noto Sans Bengali", "ગુજરાતી": "Noto Sans Gujarati",
           "ਪੰਜਾਬੀ": "Noto Sans Gurmukhi"}


def uid():
    return str(time.time_ns())


def say_now(text, lang_name=None):
    ss.say = {"id": uid(), "text": text, "lang": LANGUAGES[lang_name or ss.language]}


if ss.pending_lang:                                           # language changed by voice
    ss.language = ss.lang_sel = ss.pending_lang
    ss.pending_lang = ""
    say_now(i18n.get(ss.language)["say_hello"])


def _lang_changed():                                          # language changed from the dropdown
    ss.language = ss.lang_sel
    ss.bubble = ""
    say_now(i18n.get(ss.language)["say_hello"])


if i18n.ready(ss.language):
    TX = i18n.get(ss.language)
else:
    with st.spinner("⏳"):
        TX = i18n.get(ss.language)

FONT = FONT_OF.get(ss.language, "Inter")
FS = {"Small": "14px", "Medium": "16px", "Large": "19px"}[ss.font_size]


def dn(p):
    return TX.get("c_" + str(p), str(p))


def nav(screen):
    if screen != "pay":
        ss.pending_payment = None
        ss.pin_tries = 0
    if screen != "balance":
        ss.pin_verified = False
        ss.bal_tries = 0
    ss.screen = screen
    ss.bubble = ""
    ss.heard = ""


def go(screen):
    nav(screen)
    st.rerun()


def result(kind, msg, speak=None, data=None):
    ss.result_kind, ss.result_msg, ss.result_data = kind, msg, data or {}
    if kind in ("ok", "bad"):
        ss.pending_payment = None
        ss.pin_verified = False
    ss.screen, ss.bubble, ss.heard = "result", "", ""
    if speak:
        say_now(speak)
    st.rerun()


# ---------------- DESIGN ----------------
mood = ""
if ss.screen == "result":
    mood = "ok" if ss.result_kind == "ok" else "bad"
BGS = {
    "": "radial-gradient(circle at 88% 6%,#cfe3ff 0,transparent 42%),radial-gradient(circle at 4% 94%,#d6e7ff 0,transparent 38%),linear-gradient(180deg,#f7fbff,#e8f1ff)",
    "ok": "radial-gradient(circle at 88% 6%,#bff3d4 0,transparent 45%),radial-gradient(circle at 4% 94%,#d2f7e1 0,transparent 40%),linear-gradient(180deg,#f3fff8,#dff8ea)",
    "bad": "radial-gradient(circle at 88% 6%,#ffc9c9 0,transparent 45%),radial-gradient(circle at 4% 94%,#ffd9d9 0,transparent 40%),linear-gradient(180deg,#fff5f5,#ffe3e3)",
}
fam = "family=Inter:wght@400;600;700;800" + ("" if FONT == "Inter" else "&family=" + FONT.replace(" ", "+") + ":wght@400;600;700;800")
ACTIVE = {"home": "home", "scan": "scan", "pay": "scan", "result": "scan", "history": "history", "help": "help"}.get(ss.screen, "none")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?__FAM__&display=swap');
:root{color-scheme:light}
body *:not([data-testid="stIconMaterial"]):not(.material-icons){font-family:"__FONT__","Inter","Noto Sans",sans-serif!important}
.stApp{background:__BG__;font-size:__FS__;color:#122b52;line-height:1.55}
header[data-testid="stHeader"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"],
[data-testid="stToolbar"],[data-testid="stStatusWidget"],#MainMenu,footer,[data-testid="InputInstructions"]{display:none!important}
.block-container{max-width:1300px!important;padding:14px 28px 30px!important}
.stApp p,.stApp label,.stApp li,.stApp h1,.stApp h2,.stApp h3{color:#122b52!important}
.stApp .blue,.stApp .blue *{color:#1265f1!important}
.stApp [data-testid="stCaptionContainer"] p,.muted{color:#6f84a3!important}.muted{font-size:.85em}

.st-key-hdr{background:rgba(255,255,255,.95);border-radius:22px;padding:8px 18px;box-shadow:0 8px 28px #1265f11f;margin-bottom:22px}
.brand{display:flex;align-items:center;gap:10px}
.logo{width:46px;height:46px;border-radius:14px;display:flex;align-items:center;justify-content:center;color:#fff!important;
 font-size:26px;font-weight:800;background:linear-gradient(140deg,#10a5ff,#174cf2)}
.brand-t{font-size:1.5em;font-weight:800;color:#1265f1!important}
[class*="st-key-nav_"] button{background:transparent!important;border:0!important;box-shadow:none!important;min-height:42px;border-radius:0!important}
[class*="st-key-nav_"] button p{color:#35507a!important;font-weight:600}
.st-key-nav___ACTIVE__ button{border-bottom:3px solid #1265f1!important}
.st-key-nav___ACTIVE__ button p{color:#1265f1!important;font-weight:800}

[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondaryFormSubmit"]{background:#fff!important;
 border:1px solid #d6e4fa!important;border-radius:16px!important;min-height:48px;box-shadow:0 3px 10px #1265f10f}
[data-testid="stBaseButton-secondary"] p,[data-testid="stBaseButton-secondaryFormSubmit"] p{color:#1265f1!important;font-weight:700}
[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]{background:linear-gradient(135deg,#10a5ff,#1648f4)!important;
 border:none!important;border-radius:16px!important;min-height:52px;box-shadow:0 10px 22px #1265f14d}
[data-testid="stBaseButton-primary"] p,[data-testid="stBaseButton-primaryFormSubmit"] p{color:#fff!important;font-weight:700}
.st-key-signin button p{font-size:1.15em!important;font-weight:800!important}

[class*="st-key-tile_"] button{min-height:132px!important;border-radius:24px!important;background:#fff!important;
 border:1px solid #dbe8fb!important;box-shadow:0 10px 26px #1265f120!important;flex-direction:column;justify-content:center}
[class*="st-key-tile_"] button:hover{transform:translateY(-3px);border-color:#1265f1!important}
[class*="st-key-tile_"] button p{margin:0!important;font-size:1em!important;font-weight:800!important;color:#1265f1!important;line-height:1.5}
[class*="st-key-tile_"] button p:first-child{font-size:2.2em!important;line-height:1.3}

.stApp [data-baseweb="input"],.stApp [data-baseweb="base-input"],.stApp [data-baseweb="select"]>div{background:#fff!important;
 border:1.5px solid #cfe0fb!important;border-radius:14px!important}
.stApp [data-baseweb="input"]:focus-within{border-color:#1265f1!important;box-shadow:0 0 0 3px #1265f124!important}
.stApp input{color:#0b1f44!important;-webkit-text-fill-color:#0b1f44!important;font-weight:600!important;background:#fff!important;caret-color:#1265f1!important}
.stApp [data-baseweb="select"] div,.stApp [data-baseweb="select"] span{color:#0b1f44!important;-webkit-text-fill-color:#0b1f44!important}
[data-baseweb="popover"] li,[data-baseweb="popover"] li *{color:#122b52!important}
[data-testid="stNumberInput"] button{background:#eaf2ff!important;color:#1265f1!important}
div[data-testid="stForm"]{border-radius:22px;padding:16px;background:#fff;border:1px solid #e4edfa;box-shadow:0 8px 22px #1265f112}
[data-testid="stFileUploaderDropzoneInstructions"]{display:none}
[data-testid="stFileUploaderDropzone"] button{font-size:0!important}
[data-testid="stFileUploaderDropzone"] button::after{content:"__UP__";font-size:16px;color:#1265f1;font-weight:700}
[data-testid="stCameraInputButton"]{font-size:0!important}
[data-testid="stCameraInputButton"]::after{content:"📸  __SNAP__";font-size:16px;color:#1265f1;font-weight:700}

.hero-h{font-size:clamp(2.2rem,4.2vw,3.8rem);line-height:1.12;font-weight:800;margin:6px 0 12px;color:#0e1b36!important}
.hero-p{font-size:1.2em;color:#4d6285!important;margin-bottom:20px}
.greet{font-size:clamp(2rem,3.6vw,3.2rem);font-weight:800;margin-bottom:8px;line-height:1.2}
.greet .blue{font-size:1.1em}
.title{font-size:1.7em;font-weight:800;margin:2px 0 14px}
.card{background:#fff;border:1px solid #e4edfa;border-radius:20px;padding:14px 16px;margin:10px 0;box-shadow:0 6px 18px #1265f10f}
.pay-card{text-align:center}
.avatar{width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;color:#1265f1;background:#e3eeff;flex:none}
.tx-row{display:flex;align-items:center;gap:12px}
.tx-name{font-weight:700}.tx-amt{margin-left:auto;text-align:right;font-weight:800}
.ok-c{color:#1aa35a!important}.bad-c{color:#e0263d!important}
.big{text-align:center;font-size:2.8em;font-weight:800;margin:4px 0}
.pills{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.pill{padding:7px 14px;border-radius:99px;background:#fff;border:1px solid #d6e4fa;color:#1265f1;font-weight:700;font-size:.85em}
.steps{display:flex;align-items:center;gap:8px;margin:0 0 14px}
.st{display:flex;align-items:center;gap:6px;font-weight:700;color:#9db0cc}
.st b{width:26px;height:26px;border-radius:50%;background:#e3eeff;display:flex;align-items:center;justify-content:center;font-size:.8em}
.st.on{color:#1265f1}.st.on b{background:#1265f1;color:#fff}
.st.dn{color:#1aa35a}.st.dn b{background:#1aa35a;color:#fff}
.ln{flex:1;height:2px;background:#d6e4fa}
.vf{width:230px;height:230px;margin:16px auto;position:relative;display:flex;align-items:center;justify-content:center;font-size:4.5rem;color:#1265f1}
.vf i{position:absolute;width:46px;height:46px;border:5px solid #1265f1}
.vf i:nth-child(1){top:0;left:0;border-right:0;border-bottom:0;border-radius:16px 0 0 0}
.vf i:nth-child(2){top:0;right:0;border-left:0;border-bottom:0;border-radius:0 16px 0 0}
.vf i:nth-child(3){bottom:0;left:0;border-right:0;border-top:0;border-radius:0 0 0 16px}
.vf i:nth-child(4){bottom:0;right:0;border-left:0;border-top:0;border-radius:0 0 16px 0}
.vf:after{content:"";position:absolute;left:12%;right:12%;height:3px;background:#10a5ff;box-shadow:0 0 12px #10a5ff;animation:scan 2s ease-in-out infinite}
@keyframes scan{0%,100%{top:12%}50%{top:88%}}

.stage{position:relative;height:420px}
.halo{position:absolute;left:50%;top:52px;width:360px;height:360px;transform:translateX(-50%);border-radius:50%;
 background:radial-gradient(circle,#fff 0,#dbe9ff 52%,transparent 70%)}
.mc{position:absolute;left:50%;transform:translateX(-50%);top:56px}
.bubble{position:absolute;left:0;top:0;max-width:240px;background:#fff;border-radius:20px;padding:12px 16px;font-weight:700;
 box-shadow:0 10px 28px #1265f12b;z-index:3;line-height:1.4}
.bubble:after{content:"";position:absolute;right:26px;bottom:-9px;width:18px;height:18px;background:#fff;transform:rotate(45deg);border-radius:3px}
.heard{position:absolute;left:0;bottom:66px;background:#ffffffdd;border-radius:14px;padding:6px 12px;font-size:.85em;color:#4d6285!important;z-index:3;max-width:70%}
.wave-in{animation:pop .7s ease both}
.cf{position:absolute;top:-10px;width:9px;height:14px;border-radius:2px;animation:fall 2.8s linear infinite;z-index:4}
@keyframes fall{to{transform:translateY(470px) rotate(720deg)}}
@keyframes pop{0%{transform:scale(.6);opacity:0}70%{transform:scale(1.06)}100%{transform:scale(1);opacity:1}}
@keyframes shake{0%,100%{transform:translateX(0)}20%,60%{transform:translateX(-9px)}40%,80%{transform:translateX(9px)}}
@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-9px)}}
.mood-happy{animation:pop .6s ease both,bounce 1.2s ease-in-out .6s infinite}
.mood-sad{animation:shake .5s ease both}
.st-key-mic_box{margin-top:-62px;position:relative;z-index:5}

.banner{position:fixed;top:16px;left:50%;z-index:9999;padding:14px 28px;border-radius:18px;font-weight:800;color:#fff!important;
 font-size:1.05em;box-shadow:0 14px 40px rgba(0,0,0,.22);animation:drop .6s cubic-bezier(.2,1.4,.4,1) both,away .5s ease 5s forwards}
.banner.ok{background:linear-gradient(135deg,#22c55e,#0f9d58)}.banner.bad{background:linear-gradient(135deg,#ef4444,#b91c1c)}
@keyframes drop{from{transform:translate(-50%,-160%)}to{transform:translate(-50%,0)}}
@keyframes away{to{opacity:0;transform:translate(-50%,-160%)}}
@media(max-width:900px){.hero-h{font-size:2.3rem}.stage{height:380px}}
</style>
"""
st.markdown(CSS.replace("__FAM__", fam).replace("__FONT__", FONT).replace("__FS__", FS).replace("__BG__", BGS[mood])
            .replace("__ACTIVE__", ACTIVE).replace("__UP__", TX["upload"].replace('"', "'"))
            .replace("__SNAP__", TX["take_photo"].replace('"', "'")), unsafe_allow_html=True)

# ---------------- ASSISTANT GIRL ----------------
GIRL_SVG = """
<svg viewBox="0 0 240 255" width="__W__" xmlns="http://www.w3.org/2000/svg">
  <ellipse cx="120" cy="244" rx="82" ry="9" fill="#cfe1ff" opacity=".7"/>
  <path d="M164 52 Q224 62 214 128 Q208 170 182 196 Q200 140 172 104Z" fill="#241529"/>
  <circle cx="166" cy="56" r="8" fill="#1265f1"/>
  <path d="M50 246 Q46 172 84 152 L156 152 Q194 172 190 246Z" fill="#1d63ea"/>
  <path d="M62 178 Q46 204 66 226" stroke="#1d63ea" stroke-width="17" fill="none" stroke-linecap="round"/>
  <circle cx="66" cy="230" r="9" fill="#f0b48a"/>
  <path d="M180 176 Q216 156 214 116" stroke="#1d63ea" stroke-width="17" fill="none" stroke-linecap="round"/>
  <circle cx="214" cy="108" r="10" fill="#f0b48a"/>
  <rect x="107" y="124" width="26" height="32" rx="11" fill="#e8a678"/>
  <path d="M100 152 Q120 172 140 152Z" fill="#e8a678"/>
  <text x="120" y="224" font-size="44" font-weight="800" text-anchor="middle" fill="#ffffff">__B__</text>
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


def _png(name):
    p = os.path.join(HERE, "assets", name)
    if os.path.isfile(p):
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def girl(kind="", width=300):
    """kind: '' (waving), 'ok' (laughing + thumbs up), 'bad' (sad + thumbs down). Uses assets/*.png if present."""
    png = _png({"": "girl.png", "ok": "girl_happy.png", "bad": "girl_sad.png"}[kind]) or (_png("girl.png") if kind else None)
    if png:
        return f'<img src="data:image/png;base64,{png}" width="{width}" style="display:block"/>'
    s = GIRL_SVG.replace("__W__", str(width)).replace("__B__", html.escape(TX["brand"][:1])).replace("\n", "")
    if not kind:
        return s
    eye_l = '<ellipse cx="103" cy="86" rx="4.5" ry="6.5" fill="#241529"/>'
    eye_r = '<ellipse cx="137" cy="86" rx="4.5" ry="6.5" fill="#241529"/>'
    hl_l = '<circle cx="104.5" cy="84" r="1.5" fill="#fff"/>'
    hl_r = '<circle cx="138.5" cy="84" r="1.5" fill="#fff"/>'
    mouth = '<path d="M108 104 Q120 117 133 104" stroke="#b5434b" stroke-width="3" fill="none" stroke-linecap="round"/>'
    hand = '<rect x="202" y="100" width="24" height="20" rx="6" fill="#f0b48a"/>'
    if kind == "ok":
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


def bubble_text():
    if ss.bubble:
        return ss.bubble
    s = ss.screen
    if s == "pay":
        return TX["bub_pin"] if ss.pending_payment else TX["bub_pay"]
    if s == "result":
        return TX["bub_ok"] if ss.result_kind == "ok" else TX["bub_bad"]
    if s == "welcome":
        return TX["bub_welcome"]
    key = {"home": "bub_home", "scan": "bub_scan", "history": "bub_hist", "balance": "bub_bal", "help": "bub_help"}.get(s, "bub_home")
    return TX[key]


def stage_html():
    kind = ""
    conf = ""
    if ss.screen == "result":
        kind = "ok" if ss.result_kind == "ok" else "bad"
        if kind == "ok":
            cols = ["#ff7a59", "#10a5ff", "#ffd24d", "#2ecf7a", "#a066ff"]
            conf = "".join(f'<i class="cf" style="left:{(i * 37) % 100}%;background:{cols[i % 5]};animation-delay:{(i % 7) * .38}s"></i>'
                           for i in range(28))
    cls = {"ok": "mood-happy", "bad": "mood-sad"}.get(kind, "wave-in")
    heard = f'<div class="heard">🗣 {html.escape(ss.heard)}</div>' if ss.heard else ""
    return (f'<div class="stage">{conf}<div class="bubble">{html.escape(bubble_text())}</div><div class="halo"></div>'
            f'<div class="mc"><div class="{cls}">{girl(kind, 300)}</div></div>{heard}</div>')


def title(text):
    st.markdown(f'<div class="title">{text}</div>', unsafe_allow_html=True)


# ---------------- HEADER ----------------
with st.container(key="hdr"):
    h1, h2, h3, h4 = st.columns([1.5, 4.2, 1.7, 1.6], vertical_alignment="center")
    with h1:
        st.markdown(f'<div class="brand"><div class="logo">{html.escape(TX["brand"][:1])}</div>'
                    f'<div class="brand-t">{html.escape(TX["brand"])}</div></div>', unsafe_allow_html=True)
    with h2:
        n1, n2, n3, n4 = st.columns(4)
        if n1.button(TX["nav_home"], key="nav_home", use_container_width=True):
            go("home")
        if n2.button(TX["nav_scan"], key="nav_scan", use_container_width=True):
            go("scan")
        if n3.button(TX["nav_tx"], key="nav_history", use_container_width=True):
            go("history")
        if n4.button(TX["nav_help"], key="nav_help", use_container_width=True):
            go("help")
    with h3:
        st.selectbox("lang", list(LANGUAGES), key="lang_sel", label_visibility="collapsed", on_change=_lang_changed)
    with h4:
        if st.button(("👤 " + ss.user_name) if ss.user_name else TX["signin"], type="primary",
                     use_container_width=True, key="signin"):
            go("welcome")

if ss.screen == "result":                                     # pop-out banner
    if ss.result_kind == "ok":
        st.markdown(f'<div class="banner ok">✅ {TX["success"]} · ₹{ss.result_data.get("amount", 0):,.0f}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="banner bad">⚠️ {html.escape(ss.result_msg)}</div>', unsafe_allow_html=True)


# ---------------- VOICE ACTIONS ----------------
def apply_voice_action(v):
    ss.last_voice_id = v["id"]
    for a in v.get("actions") or []:
        t = a.get("tool")
        if t == "open_screen":
            nav(a.get("screen", "home"))
            if a.get("screen") == "scan":
                ss.scan_mode = a.get("mode") or "camera"
        elif t == "prepare_payment":
            try:
                amt = max(1.0, float(a.get("amount")))
            except (TypeError, ValueError):
                continue
            ss.payee, ss.amount = str(a.get("payee", "")), amt
            nav("pay")
            ss.pending_payment = {"name": ss.payee, "amount": amt, "note": ""}      # straight to the PIN step
            ss.pin_tries = 0
        elif t == "cancel":
            nav("home")
        elif t == "set_language":
            name = next((n for n, c in LANGUAGES.items() if c == a.get("lang")), None)
            if name:
                ss.pending_lang = name
        elif t == "set_font" and a.get("size") in ("Small", "Medium", "Large"):
            ss.font_size = a["size"]
    ss.heard = v.get("transcript", "")
    ss.bubble = v.get("reply", "")
    st.rerun()


# ---------------- QR ----------------
def decode_qr(data):
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return ""
    det = cv2.QRCodeDetector()
    txt, _, _ = det.detectAndDecode(img)
    if txt:
        return txt
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    for scale in (1.5, 0.6, 2.0):
        txt, _, _ = det.detectAndDecode(cv2.resize(gray, None, fx=scale, fy=scale))
        if txt:
            return txt
    return ""


def parse_upi(txt):
    if txt.lower().startswith("upi://"):
        q = {k: v[0] for k, v in parse_qs(urlparse(txt).query).items()}
        try:
            amt = float(q.get("am")) if q.get("am") else None
        except ValueError:
            amt = None
        name = unquote(q.get("pn") or q.get("pa") or "").strip()
        if name:
            return {"upi": True, "name": name, "amount": amt}
    return {"upi": False, "text": txt}


# ---------------- PAGE ----------------
left, right = st.columns([1.1, 1], gap="large")
s = ss.screen

with left:
    if s == "home":
        if ss.user_name:
            st.markdown(f'<div class="greet">{TX["hello"]}, <span class="blue">{html.escape(ss.user_name)}</span> 👋</div>',
                        unsafe_allow_html=True)
        st.markdown(f'<h1 class="hero-h">{TX["h1a"]}<br><span class="blue">{TX["h1b"]}</span></h1>'
                    f'<p class="hero-p">{TX["sub"]}</p>', unsafe_allow_html=True)
        tc = st.columns(4)
        tiles = [("📷", "tile_scan", "scan"), ("💸", "tile_pay", "pay"), ("🕒", "tile_hist", "history"), ("🔒", "tile_bal", "balance")]
        for col, (ic, key, target) in zip(tc, tiles):
            if col.button(f"{ic}\n\n{TX[key]}", key=f"tile_{target}", use_container_width=True):
                go(target)
        st.markdown(f'<div class="muted" style="margin-top:16px">{TX["say_like"]}</div><div class="pills">'
                    + "".join(f'<span class="pill">🎙 {TX[k]}</span>' for k in ("ex1", "ex2", "ex3", "ex4")) + '</div>',
                    unsafe_allow_html=True)
        if not ss.user_name:
            st.write("")
            if st.button(TX["start"] + "  →", type="primary", use_container_width=True, key="hb_start"):
                go("welcome")

    elif s == "welcome":
        title("👋 " + TX["name_q"])
        with st.form("name_form"):
            name = st.text_input(TX["name"], value=ss.user_name)
            ok = st.form_submit_button(TX["cont"] + "  →", type="primary", use_container_width=True)
        if ok:
            if name.strip():
                ss.user_name = name.strip()
                nav("home")
                ss.bubble = f'{TX["hello"]}, {ss.user_name}!'
                say_now(f'{TX["hello"]} {ss.user_name}! {TX["say_hello"]}')
                st.rerun()
            else:
                st.warning(TX["name"])

    elif s == "scan":
        title("📷 " + TX["scan_title"])
        m1, m2 = st.columns(2)
        if m1.button("📷  " + TX["cam"], type="primary" if ss.scan_mode == "camera" else "secondary",
                     use_container_width=True, key="m_cam"):
            ss.scan_mode = "camera"
            st.rerun()
        if m2.button("🖼  " + TX["gallery"], type="primary" if ss.scan_mode == "gallery" else "secondary",
                     use_container_width=True, key="m_gal"):
            ss.scan_mode = "gallery"
            st.rerun()
        pic = (st.camera_input(TX["take_photo"], key="cam_in", label_visibility="collapsed")
               if ss.scan_mode == "camera"
               else st.file_uploader(TX["upload"], type=["png", "jpg", "jpeg"], key="up_in", label_visibility="collapsed"))
        if not pic:
            st.markdown(f'<div class="vf"><i></i><i></i><i></i><i></i>▦</div>'
                        f'<div class="muted" style="text-align:center">{TX["scan_hint"]}</div>', unsafe_allow_html=True)
        else:
            try:
                txt = decode_qr(pic.getvalue())
            except Exception as exc:
                txt = ""
                st.error(str(exc))
            if not txt:
                st.error(TX["qr_fail"])
            else:
                info = parse_upi(txt)
                st.success(TX["qr_ok"])
                if info["upi"]:
                    amt = f' · ₹{info["amount"]:,.0f}' if info["amount"] else ""
                    st.markdown(f'<div class="card tx-row"><div class="avatar">{html.escape(info["name"][:1].upper())}</div>'
                                f'<div><div class="tx-name">{html.escape(info["name"])}</div>'
                                f'<div class="muted">{TX["qr_check"]}</div></div><div class="tx-amt">{amt}</div></div>',
                                unsafe_allow_html=True)
                    if st.button("💸  " + TX["qr_pay"], type="primary", use_container_width=True, key="qr_pay"):
                        ss.payee = info["name"]
                        if info["amount"]:
                            ss.amount = info["amount"]
                        go("pay")
                else:
                    st.markdown(f'<div class="card"><div class="muted">{TX["qr_text"]}</div>{html.escape(info["text"][:300])}</div>',
                                unsafe_allow_html=True)
                    st.warning(TX["qr_check"])
        if st.button("←  " + TX["back"], use_container_width=True, key="scan_back"):
            go("home")

    elif s == "pay":
        title("💸 " + TX["pay_title"])
        p = ss.pending_payment
        st.markdown(f'<div class="steps"><div class="st {"dn" if p else "on"}"><b>{"✓" if p else "1"}</b>{TX["step1"]}</div><div class="ln"></div>'
                    f'<div class="st {"on" if p else ""}"><b>2</b>{TX["step2"]}</div><div class="ln"></div>'
                    f'<div class="st"><b>3</b>{TX["step3"]}</div></div>', unsafe_allow_html=True)
        if p:                                                  # step 2: PIN (typed only)
            st.markdown(f'<div class="card pay-card"><div class="avatar" style="margin:0 auto 4px">{html.escape(dn(p["name"])[:1])}</div>'
                        f'<div class="tx-name">{html.escape(dn(p["name"]))}</div>'
                        f'<div class="big">₹{p["amount"]:,.0f}</div>'
                        f'<div class="muted">{html.escape(p["note"])}</div></div>', unsafe_allow_html=True)
            with st.form("pay_pin_form"):
                pin = st.text_input(TX["pin_label"], type="password", max_chars=4)
                go_btn = st.form_submit_button("🔒  " + TX["confirm_pay"], type="primary", use_container_width=True)
            if go_btn:
                if pin == APP_PIN:
                    amt = p["amount"]
                    if amt > ss.balance:
                        ss.pin_tries = 0
                        result("bad", TX["no_funds"], TX["say_nofunds"])
                    ss.balance -= amt                           # bank balance updated
                    ss.history.append({"name": p["name"], "amount": amt, "type": "paid", "note": p["note"],
                                       "time": datetime.now().strftime("%d/%m %H:%M")})
                    ss.pin_tries = 0
                    result("ok", "", TX["say_ok"].replace("{amt}", f"{amt:,.0f}").replace("{name}", dn(p["name"])),
                           {"name": dn(p["name"]), "amount": amt, "balance": ss.balance})
                ss.pin_tries += 1
                if ss.pin_tries >= MAX_PIN_TRIES:
                    ss.pin_tries = 0
                    result("bad", TX["too_many"], TX["say_cancel"])
                result("retry", f'{TX["bad_pin"]} · {MAX_PIN_TRIES - ss.pin_tries} {TX["tries_left"]}', TX["say_bad"])
            if st.button("✖  " + TX["cancel"], use_container_width=True, key="pay_cancel"):
                go("home")
        else:                                                   # step 1: details
            st.markdown(f'<div class="card pay-card"><div class="avatar" style="margin:0 auto 4px">{html.escape(dn(ss.payee)[:1])}</div>'
                        f'<div class="tx-name">{html.escape(dn(ss.payee))}</div>'
                        f'<div class="big">₹{ss.amount:,.0f}</div></div>', unsafe_allow_html=True)
            options = CONTACTS + ([ss.payee] if ss.payee not in CONTACTS else [])
            with st.form("payment_form"):
                recipient = st.selectbox(TX["pay_to"], options, index=options.index(ss.payee), format_func=dn)
                amount = st.number_input(TX["amount"], min_value=1.0, value=max(1.0, float(ss.amount)), step=50.0)
                note = st.text_input(TX["note"])
                submit = st.form_submit_button(TX["pay_now"], type="primary", use_container_width=True)
            if submit:
                ss.payee, ss.amount = recipient, amount
                ss.pending_payment = {"name": recipient, "amount": amount, "note": note}
                ss.pin_tries = 0
                ss.bubble = ""
                st.rerun()
        if st.button("←  " + TX["back"], use_container_width=True, key="pay_back"):
            go("home")

    elif s == "result":
        ok = ss.result_kind == "ok"
        if ok:
            d = ss.result_data
            title("✅ " + TX["success"])
            st.markdown(f'<div class="card"><div class="muted" style="text-align:center">{TX["paid_to"]} {html.escape(str(d.get("name", "")))}</div>'
                        f'<div class="big ok-c">₹{d.get("amount", 0):,.0f}</div>'
                        f'<hr><div class="tx-row"><span class="muted">{TX["new_bal"]}</span>'
                        f'<span class="tx-amt blue">₹{d.get("balance", 0):,.2f}</span></div>'
                        f'<div class="muted" style="text-align:center;margin-top:8px">{TX["sim"]}</div></div>', unsafe_allow_html=True)
            r1, r2 = st.columns(2)
            if r1.button(TX["done"], type="primary", use_container_width=True, key="res_done"):
                go("home")
            if r2.button("🕒  " + TX["view_hist"], use_container_width=True, key="res_hist"):
                go("history")
        else:
            title("❌ " + html.escape(ss.result_msg))
            if ss.result_kind in ("retry", "retry_bal"):
                if st.button("🔁  " + TX["retry"], type="primary", use_container_width=True, key="res_retry"):
                    ss.screen = "pay" if ss.result_kind == "retry" else "balance"
                    ss.bubble = ""
                    st.rerun()
            if st.button("←  " + TX["back"], use_container_width=True, key="res_back"):
                go("home")

    elif s == "balance":
        title("🔒 " + TX["bal_title"])
        if not ss.pin_verified:
            with st.form("balance_pin_form"):
                pin = st.text_input(TX["pin_bal"], type="password", max_chars=4)
                unlock = st.form_submit_button(TX["unlock"], type="primary", use_container_width=True)
            if unlock:
                if pin == APP_PIN:
                    ss.pin_verified, ss.bal_tries = True, 0
                    ss.bubble = ""
                    st.rerun()
                ss.bal_tries += 1
                if ss.bal_tries >= MAX_PIN_TRIES:
                    ss.bal_tries = 0
                    result("bad", TX["too_many"], TX["say_cancel"])
                result("retry_bal", f'{TX["bad_pin"]} · {MAX_PIN_TRIES - ss.bal_tries} {TX["tries_left"]}', TX["say_bad"])
        else:
            st.markdown(f'<div class="card"><b>{TX["holder"]}</b><br>{html.escape(ss.user_name or "—")}<hr>'
                        f'<b>{TX["acc"]}</b><br>XXXX XXXX 1234<hr><b>{TX["avail"]}</b><br>'
                        f'<span class="blue" style="font-size:2em;font-weight:800">₹{ss.balance:,.2f}</span></div>', unsafe_allow_html=True)
            if st.button("🙈  " + TX["hide"], use_container_width=True, key="hide_bal"):
                go("home")
        if st.button("←  " + TX["back"], use_container_width=True, key="bal_back"):
            go("home")

    elif s == "history":
        title("🕒 " + TX["hist_title"])
        if not ss.history:
            st.info(TX["empty"])
        for item in reversed(ss.history):
            rec = item.get("type") == "received"
            note = f' · {html.escape(item["note"])}' if item.get("note") else ""
            st.markdown(f'<div class="card tx-row"><div class="avatar">{html.escape(dn(item["name"])[:1])}</div>'
                        f'<div><div class="tx-name">{html.escape(dn(item["name"]))}</div><div class="muted">{item["time"]}{note}</div></div>'
                        f'<div class="tx-amt {"ok-c" if rec else ""}">{"+" if rec else "-"}₹{item["amount"]:,.0f}<br>'
                        f'<span class="ok-c" style="font-size:.8em">{TX["received"] if rec else TX["completed"]}</span></div></div>',
                        unsafe_allow_html=True)
        if st.button("←  " + TX["back"], use_container_width=True, key="hist_back"):
            go("home")

    elif s == "help":
        title("❓ " + TX["help_title"])
        st.markdown(f'<div class="card"><b>{TX["try"]}:</b><br><br>' + "<br><br>".join(f'🎙 “{TX[k]}”' for k in ("ex1", "ex2", "ex3", "ex4"))
                    + f'<br><br>🌐 {TX["lang_tip"]}</div>', unsafe_allow_html=True)
        sizes = ["Small", "Medium", "Large"]
        sel = st.radio(TX["font"], sizes, index=sizes.index(ss.font_size), horizontal=True, format_func=lambda x: TX[x.lower()])
        if sel != ss.font_size:
            ss.font_size = sel
            st.rerun()
        if st.button("←  " + TX["back"], use_container_width=True, key="help_back"):
            go("home")

# ---------------- ASSISTANT (right column; same place on every screen so the mic never remounts) ----------------
_voice = components.declare_component("bolopay_voice", path=os.path.join(HERE, "voice_component"))

with right:
    st.markdown(stage_html(), unsafe_allow_html=True)
    muted = bool(ss.pending_payment) or (ss.screen == "balance" and not ss.pin_verified)
    labels = {"tap": TX["tap"], "st_listen": TX["st_listen"], "st_proc": TX["st_proc"], "st_speak": TX["st_speak"],
              "st_pin": TX["st_pin"], "mic_denied": TX["mic_denied"], "st_err": TX["st_err"]}
    say, ss.say = ss.say, None
    with st.container(key="mic_box"):
        _v = _voice(ws_url=VOICE_WS_URL, language=LANGUAGES[ss.language], screen=ss.screen, payee=ss.payee,
                    amount=float(ss.amount), stage="pin" if muted else "idle", muted=muted, labels=labels, say=say,
                    font=FONT, font_px={"Small": 16, "Medium": 18, "Large": 21}[ss.font_size],
                    history=[f'{h["time"]}: ₹{h["amount"]:,.0f} {h["name"]}' for h in ss.history[-5:]],
                    key="bolopay_voice", default=None)
    if _v and _v.get("id") != ss.last_voice_id:
        apply_voice_action(_v)