# BoloPay — LiveKit voice assistant starter

This version uses a real LiveKit room for browser audio, the LiveKit Agents framework, Gnani STT/TTS, and Groq as the LLM. The Streamlit UI stays as the website and changes screens when the agent calls a UI tool.

## Important limitations

- This is a working starter architecture, not a production payment app. Balance/history are demo-only; QR scanning and real payments are not connected.
- Gnani's documented LiveKit integration lists English, Hindi, Telugu, Tamil, Kannada, Malayalam, Bengali, Marathi, Gujarati, and Punjabi. Do not assume Kashmiri or Urdu is supported by the selected STT/TTS models; test with your Gnani account. The selected language is fixed for each room/voice session.
- The Gnani LiveKit plugin expects a key per service. This project uses `GNANI_STT_API_KEY` for STT and `GNANI_TTS_API_KEY` for TTS, falling back to `GNANI_API_KEY` if either separate key is absent.
- LiveKit's room token is generated server-side. Never put `LIVEKIT_API_SECRET` in Streamlit secrets used by browser code or in the component HTML.
- A continuously running LiveKit agent worker may require a paid always-on worker host. Free web hosting often sleeps and is not reliable for realtime voice.

## Files

- `app.py` — Streamlit website/screens and voice component integration.
- `livekit_component/index.html` — tap-to-talk browser component; joins a LiveKit room and stops publishing the mic after about 1.3 seconds of silence.
- `token_server.py` — issues short-lived room tokens.
- `agent.py` — LiveKit Agents worker: Gnani STT + Groq LLM + Gnani TTS; includes navigation/payment-demo tools.
- `render.yaml` — example token service and agent worker deployment.

## 1. Add secrets

Create a `.env` locally from `.env.example`, and add your actual values privately. Do not commit `.env`.

Required values:

```dotenv
GNANI_STT_API_KEY=your_gnani_stt_key
GNANI_TTS_API_KEY=your_gnani_tts_key
GNANI_API_KEY=your_shared_gnani_key_if_you_have_one
GROQ_API_KEY=your_groq_key
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
```

You can leave `GNANI_API_KEY` unset if your STT and TTS keys are separate. Set `GROQ_MODEL` to a model available to your Groq account if the default is unavailable.

## 2. Local run

Use Python 3.11 or 3.12.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open three terminals from this folder:

```bash
uvicorn token_server:app --host 0.0.0.0 --port 8001
```

```bash
python agent.py dev
```

```bash
streamlit run app.py
```

For local use, the defaults point to `http://localhost:8001/token`; make sure `LIVEKIT_URL` is your LiveKit Cloud URL. Browser microphone access requires localhost or HTTPS.

## 3. Deploy

1. Push this folder to a GitHub repository. Make sure `.env` is excluded.
2. Create a Render Blueprint using `render.yaml`.
3. In the token service, set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`.
4. In the agent worker, set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `GROQ_API_KEY`, `GNANI_STT_API_KEY`, and `GNANI_TTS_API_KEY`. Set `GNANI_API_KEY` too if you have a shared key.
5. Deploy the token service and agent worker. The agent worker must stay running and connect to LiveKit.
6. Deploy `app.py` to Streamlit Community Cloud.
7. In Streamlit app Secrets, set:

```toml
LIVEKIT_URL = "wss://your-project.livekit.cloud"
BOLOPAY_TOKEN_URL = "https://your-token-service.onrender.com/token"
```

The public URL for the token service must use HTTPS. Do not add the LiveKit API secret to Streamlit Secrets unless absolutely necessary; it belongs only on the token server/worker.

## Voice and actions

- Tap the mic to start listening.
- After speech followed by ~1.3 seconds of silence, the browser stops the mic track and the agent handles the turn.
- Tap again to speak another request.
- Commands like “open history”, “show balance”, “open scan”, and “help” can trigger screen-opening tools.
- “Pay 500 rupees to Rahul” should only open the simulated payment screen; no money moves.

## Troubleshooting

- **Token service error:** check `/health`, `LIVEKIT_URL`, API key, and API secret.
- **Agent not responding:** inspect worker logs; confirm the worker is running and the LiveKit URL/key/secret match the project.
- **Speech recognition/TTS fails:** verify the separate Gnani STT and TTS keys and that the selected language is supported by your account.
- **No mic access:** use HTTPS/localhost and allow microphone permission.
- **Screen doesn't open:** inspect worker logs for tool calls and browser console for LiveKit data events.
