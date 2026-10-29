import os, uuid
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="BoloPay Voice Assistant", page_icon="🎙️", layout="centered")
ROOT = Path(__file__).parent
voice_ui = components.declare_component("bolopay_livekit_voice", path=str(ROOT / "livekit_component"))

def cfg(name, default=""):
    value = os.getenv(name)
    if value: return value
    try:
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return default

LANGUAGES = {
    "English": "en-IN", "Hindi": "hi-IN", "Telugu": "te-IN", "Tamil": "ta-IN",
    "Kannada": "kn-IN", "Malayalam": "ml-IN", "Bengali": "bn-IN", "Marathi": "mr-IN",
    "Gujarati": "gu-IN", "Punjabi": "pa-IN",
}
for k, v in {"screen":"home", "history":[], "last_voice_id":None, "payee":"", "amount":0.0, "notice":""}.items():
    if k not in st.session_state: st.session_state[k] = v

st.markdown("""
<style>
.stApp{background:#f4f7ff}.block-container{max-width:900px;padding-top:1.4rem}
.hero{padding:1.3rem 1.5rem;border-radius:22px;color:#fff;background:linear-gradient(125deg,#123b83,#1769e8);margin-bottom:1rem}
.hero h1{color:white;margin:0}.hero p{color:#e7f0ff;margin:.4rem 0 0}
.warning{border:1px solid #e7c66e;background:#fff8e6;color:#6b4d00;padding:.85rem 1rem;border-radius:12px;margin:.7rem 0}
</style>
<div class="hero"><h1>🎙️ BoloPay</h1><p>Speak naturally. BoloPay can navigate the demo for you.</p></div>
<div class="warning"><b>Demo only:</b> no real money moves. Do not speak or enter PINs, OTPs, passwords, or bank credentials.</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Voice settings")
    language_name = st.selectbox("Spoken language", list(LANGUAGES.keys()), index=0)
    language = LANGUAGES[language_name]
    st.caption("Gnani's documented LiveKit plugin supports these 10 language options. Language support and voice quality vary by account/model.")
    st.divider()
    token_url = cfg("BOLOPAY_TOKEN_URL", "http://localhost:8001/token").rstrip("/")
    if token_url:
        st.caption("The token service must be deployed and reachable over HTTPS.")

nav = st.columns(5)
for col, (emoji, label, screen) in zip(nav, [("🏠","Home","home"),("📜","History","history"),("💰","Balance","balance"),("🔎","Scan","scan"),("❓","Help","help")]):
    if col.button(f"{emoji} {label}", use_container_width=True, key=f"nav_{screen}"):
        st.session_state.screen = screen
        st.rerun()

st.subheader("Voice assistant")
st.caption("Tap once to start. Speak a command. After a short pause, BoloPay sends the turn and stops the microphone. Tap again to speak again.")
livekit_url = cfg("LIVEKIT_URL", "")
if not livekit_url:
    st.error("Set LIVEKIT_URL in Streamlit Secrets (your LiveKit Cloud WebSocket URL).")
elif not token_url or token_url.startswith("http://localhost"):
    st.warning("Set BOLOPAY_TOKEN_URL to the public HTTPS URL of your deployed token service.")

result = voice_ui(token_url=token_url, livekit_url=livekit_url, language=language, screen=st.session_state.screen, key="bolopay_livekit_voice")
if isinstance(result, dict) and result.get("id") != st.session_state.last_voice_id:
    st.session_state.last_voice_id = result.get("id")
    transcript = str(result.get("transcript", ""))
    reply = str(result.get("reply", ""))
    if transcript or reply:
        st.session_state.history.append({"transcript": transcript, "reply": reply})
        st.session_state.history = st.session_state.history[-50:]
    for action in result.get("actions", []):
        if not isinstance(action, dict): continue
        tool = action.get("tool")
        if tool == "open_screen" and action.get("screen") in {"home","history","balance","scan","help","pay"}:
            st.session_state.screen = action["screen"]
        elif tool == "prepare_payment":
            st.session_state.payee = str(action.get("payee", ""))[:100]
            try: st.session_state.amount = max(0.0, float(action.get("amount", 0)))
            except (TypeError, ValueError): st.session_state.amount = 0.0
            st.session_state.screen = "pay"
        elif tool == "cancel":
            st.session_state.screen = "home"; st.session_state.payee = ""; st.session_state.amount = 0.0
            st.session_state.notice = "Demo request cancelled."
    st.rerun()

if st.session_state.notice:
    st.info(st.session_state.notice)

screen = st.session_state.screen
st.divider()
if screen == "home":
    st.subheader("Welcome")
    st.write("Try saying: ‘Open history’, ‘Show balance’, ‘Open scan’, ‘Help’, or ‘Pay 500 rupees to Rahul’. Payment is only simulated.")
    a,b=st.columns(2); a.metric("Demo balance", "₹12,450.00"); b.metric("Voice interactions", len(st.session_state.history))
    st.caption("The balance is illustrative and is not connected to a bank account.")
elif screen == "history":
    st.subheader("Conversation history")
    if not st.session_state.history: st.info("No conversations yet.")
    for i,item in enumerate(reversed(st.session_state.history),1):
        with st.container(border=True):
            st.markdown(f"**Conversation {i}**")
            st.write("You:",item.get("transcript", "")); st.write("BoloPay:",item.get("reply", ""))
elif screen == "balance":
    st.subheader("Demo balance"); st.metric("Illustrative balance", "₹12,450.00")
    st.info("This is sample data only. No financial account is connected.")
elif screen == "scan":
    st.subheader("QR scan")
    st.info("The Scan screen is a placeholder. Camera-based QR parsing and verified payment processing are not connected yet.")
elif screen == "help":
    st.subheader("Help")
    st.markdown("- Tap the microphone to start speaking.\n- A short pause ends the utterance automatically.\n- Tap again to interrupt/stop or start a new turn, depending on the current state.\n- Ask to open Home, History, Balance, Scan, or Help.\n- Never speak a PIN, OTP, password, or banking credential.")
elif screen == "pay":
    st.subheader("Payment preparation — simulation only")
    st.write("Payee:", st.session_state.payee or "Not specified")
    st.write("Amount:", f"₹{st.session_state.amount:,.2f}")
    st.warning("No payment will be sent. Real payments require a regulated payment provider, authentication, and explicit confirmation.")
    if st.button("Cancel demo payment"):
        st.session_state.screen="home"; st.session_state.payee=""; st.session_state.amount=0.0; st.rerun()
