"""LiveKit voice agent: Gnani STT/TTS + Groq LLM, with safe UI navigation tools."""
import json, os, re
from pathlib import Path
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, RunContext, function_tool, room_io
from livekit.plugins import gnani, groq, silero

load_dotenv()

LANG_NAMES = {"en-IN":"English", "hi-IN":"Hindi", "te-IN":"Telugu", "ta-IN":"Tamil", "kn-IN":"Kannada", "ml-IN":"Malayalam", "bn-IN":"Bengali", "mr-IN":"Marathi", "gu-IN":"Gujarati", "pa-IN":"Punjabi"}
ALLOWED_SCREENS = {"home", "history", "balance", "scan", "help", "pay"}
DEMO_BALANCE = "₹12,450.00"


def load_knowledge():
    """Load the project's plain-text knowledge file as grounded context."""
    path = Path(__file__).parent / "knowledge" / "bolopay_knowledge.txt"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return "Demo balance is ₹12,450.00. Balance and history are illustrative demo data only."

def gnani_key():
    # The LiveKit Gnani plugin expects one key. Prefer the dedicated shared key, then existing keys.
    return os.getenv("GNANI_API_KEY") or os.getenv("GNANI_STT_API_KEY") or os.getenv("GNANI_TTS_API_KEY") or ""

class BoloPayAgent(Agent):
    def __init__(self, room, language):
        self.room = room
        self.language = language if language in LANG_NAMES else "en-IN"
        knowledge = load_knowledge()
        super().__init__(instructions=f"""
You are BoloPay, a helpful voice assistant for a demo financial interface.
LANGUAGE RULE: The selected language is {LANG_NAMES[self.language]} ({self.language}). Always answer in that language, using natural, simple wording. If the transcript is in another language you understand, reply in that same language. Never answer 'I don't know' merely because the question is not in English.
KNOWLEDGE RULE: Use the KNOWLEDGE BASE below for BoloPay facts. If the user asks their balance in any supported phrasing, tell them the demo balance is {DEMO_BALANCE}; do not say the balance is unknown. Clearly describe it as demo-only, not a real bank balance.
ACTION RULE: When asked to open/show/check Balance, History, Scan, Home, or Help, call open_screen for the relevant screen instead of merely giving steps. For balance questions, open the balance screen as well as answering.
Keep replies short and suitable for text-to-speech. Understand the meaning of the entire utterance, not just an isolated word; pay attention to negation such as 'don't show'.
If the user asks to pay/send money, only prepare a simulated payment screen and say that no money is sent. Never request or collect PINs, OTPs, passwords, card numbers, or bank credentials.
Balance and history are demo data only. Never claim a real payment occurred.

KNOWLEDGE BASE:
{knowledge}
""")

    async def send_action(self, action):
        payload = json.dumps({"type":"bolopay_action", **action}, ensure_ascii=False).encode("utf-8")
        await self.room.local_participant.publish_data(payload, reliable=True, topic="bolopay")

    @function_tool()
    async def open_screen(self, context: RunContext, screen: str) -> str:
        """Open a screen in the BoloPay website. screen must be home, history, balance, scan, or help."""
        screen = screen.strip().lower()
        if screen not in {"home", "history", "balance", "scan", "help"}:
            return "That screen is not available."
        await self.send_action({"tool":"open_screen", "screen":screen})
        return f"Opening {screen}."

    @function_tool()
    async def answer_balance(self, context: RunContext) -> str:
        """Use whenever the user asks how much their balance is, including questions phrased in Hindi, Telugu, Tamil, Kannada, Malayalam, Bengali, Marathi, Gujarati, or Punjabi. Opens the demo Balance screen and gives the known demo balance; never say it is unknown."""
        await self.send_action({"tool":"open_screen", "screen":"balance"})
        answers = {
            "en-IN": f"Your demo balance is {DEMO_BALANCE}. This is not a real bank balance.",
            "hi-IN": f"आपका डेमो बैलेंस {DEMO_BALANCE} है। यह असली बैंक बैलेंस नहीं है।",
            "te-IN": f"మీ డెమో బ్యాలెన్స్ {DEMO_BALANCE}. ఇది నిజమైన బ్యాంక్ బ్యాలెన్స్ కాదు.",
            "ta-IN": f"உங்கள் டெமோ இருப்பு {DEMO_BALANCE}. இது உண்மையான வங்கி இருப்பு அல்ல.",
            "kn-IN": f"ನಿಮ್ಮ ಡೆಮೊ ಬ್ಯಾಲೆನ್ಸ್ {DEMO_BALANCE}. ಇದು ನಿಜವಾದ ಬ್ಯಾಂಕ್ ಬ್ಯಾಲೆನ್ಸ್ ಅಲ್ಲ.",
            "ml-IN": f"നിങ്ങളുടെ ഡെമോ ബാലൻസ് {DEMO_BALANCE}. ഇത് യഥാർത്ഥ ബാങ്ക് ബാലൻസ് അല്ല.",
            "bn-IN": f"আপনার ডেমো ব্যালেন্স {DEMO_BALANCE}। এটি আসল ব্যাঙ্ক ব্যালেন্স নয়।",
            "mr-IN": f"तुमची डेमो शिल्लक {DEMO_BALANCE} आहे. ही खरी बँक शिल्लक नाही.",
            "gu-IN": f"તમારું ડેમો બેલેન્સ {DEMO_BALANCE} છે. આ વાસ્તવિક બેંક બેલેન્સ નથી.",
            "pa-IN": f"ਤੁਹਾਡਾ ਡੈਮੋ ਬੈਲੈਂਸ {DEMO_BALANCE} ਹੈ। ਇਹ ਅਸਲ ਬੈਂਕ ਬੈਲੈਂਸ ਨਹੀਂ ਹੈ।",
        }
        return answers.get(self.language, answers["en-IN"])

    @function_tool()
    async def prepare_payment(self, context: RunContext, payee: str, amount: float) -> str:
        """Open the simulated payment screen with a recipient and amount. This never transfers money."""
        payee = re.sub(r"[^\w .'-]", "", str(payee))[:80].strip()
        try: amount = float(amount)
        except (TypeError, ValueError): amount = 0
        if not payee or amount <= 0 or amount > 10000000:
            return "Please tell me a recipient and a positive amount. This is only a demo."
        await self.send_action({"tool":"prepare_payment", "payee":payee, "amount":amount})
        return f"I opened a simulated payment for {payee}, amount {amount:.2f} rupees. No money has been sent."

    @function_tool()
    async def cancel_request(self, context: RunContext) -> str:
        """Cancel the current demo payment/request and return to Home."""
        await self.send_action({"tool":"cancel"})
        return "Cancelled."

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    # Room format is bolopay_<locale>_<random suffix>, e.g. bolopay_hi-IN_ab12cd.
    bits = ctx.room.name.split("_")
    language = bits[1] if len(bits) >= 3 and bits[0] == "bolopay" else os.getenv("BOLOPAY_LANGUAGE", "en-IN")
    if language not in LANG_NAMES: language = "en-IN"
    key = gnani_key()
    if not key:
        raise RuntimeError("Set GNANI_API_KEY or GNANI_STT_API_KEY/GNANI_TTS_API_KEY")

    stt_key = os.getenv("GNANI_STT_API_KEY") or os.getenv("GNANI_API_KEY") or key
    tts_key = os.getenv("GNANI_TTS_API_KEY") or os.getenv("GNANI_API_KEY") or key
    session = AgentSession(
        stt=gnani.STT(api_key=stt_key, language=language, use_streaming=True, sample_rate=16000),
        llm=groq.LLM(model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), api_key=os.getenv("GROQ_API_KEY", ""), temperature=0.2),
        tts=gnani.TTS(api_key=tts_key, voice=os.getenv("GNANI_VOICE", "Nalini"), model=os.getenv("GNANI_TTS_MODEL", "timbre-v2.5"), language=language, synthesize_method="websocket", sample_rate=16000),
        vad=silero.VAD.load(),
    )

    async def send_transcript(event):
        try:
            packet = {"type": "bolopay_transcript", "text": str(getattr(event, "transcript", "")), "final": bool(getattr(event, "is_final", False))}
            await ctx.room.local_participant.publish_data(json.dumps(packet, ensure_ascii=False).encode("utf-8"), reliable=True, topic="bolopay")
        except Exception as exc:
            print("Transcript event warning:", exc)

    async def send_assistant_text(event):
        try:
            item = getattr(event, "item", None)
            role = getattr(item, "role", "")
            if str(role).lower() not in {"assistant", "chatrole.assistant"}:
                return
            content = getattr(item, "text_content", "")
            if callable(content): content = content()
            if not content:
                content = getattr(item, "text", "")
            if content:
                packet = {"type": "bolopay_reply", "text": str(content)}
                await ctx.room.local_participant.publish_data(json.dumps(packet, ensure_ascii=False).encode("utf-8"), reliable=True, topic="bolopay")
        except Exception as exc:
            print("Assistant text event warning:", exc)

    await session.start(
        agent=BoloPayAgent(ctx.room, language),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(sample_rate=16000),
            audio_output=room_io.AudioOutputOptions(sample_rate=16000),
        ),
    )
    session.on("user_input_transcribed", send_transcript)
    session.on("conversation_item_added", send_assistant_text)
    await session.generate_reply(instructions=f"Greet the user briefly in {LANG_NAMES[language]} and tell them they can ask you to open a feature.")

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
