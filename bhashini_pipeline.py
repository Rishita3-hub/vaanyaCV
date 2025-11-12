import requests
import json
import base64
import io
import copy
import librosa
import soundfile as sf

# --- API Keys & Endpoints ---
BHASHINI_AUTH_TOKEN = "ujzb4jidEwJo1U-IDxGr2iMkRChAw8qrKcKUQsCA1RSOC2rt6ITU3TihElxkmoHA"
BHASHINI_ENDPOINT = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
HEADERS_BHASHINI = {"Authorization": BHASHINI_AUTH_TOKEN}

# --- Payload Templates ---
asr_trans_payload = {
    "pipelineTasks": [
        {
            "taskType": "asr",
            "config": {
                "language": {"sourceLanguage": None},
                "serviceId": None,
                "audioFormat": "wav",  # ✅ Important fix
                "samplingRate": 16000,
                "preProcessors": ["vad", "denoiser"],
                "postprocessors": ["itn", "punctuation"]
            }
        },
        {
            "taskType": "translation",
            "config": {
                "language": {"sourceLanguage": None, "targetLanguage": "en"},
                "serviceId": "ai4bharat/indictrans-v2-all-gpu--t4"
            }
        }
    ],
    "inputData": {"audio": [{"audioContent": None}]}
}

lang_detect_payload = {
    "pipelineTasks": [
        {
            "taskType": "audio-lang-detection",
            "config": {
                "serviceId": "bhashini/iitmandi/audio-lang-detection/gpu"
            }
        }
    ],
    "inputData": {"audio": [{"audioContent": None}]}
}

# --- Helpers ---
def safe_json(response):
    try:
        return response.json()
    except json.JSONDecodeError:
        print("❌ JSON decode failed:", response.text)
        return {}

def load_and_resample_audio(file_path, target_sr=16000):
    y, sr = librosa.load(file_path, sr=None)
    y_resampled = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
    return y_resampled, target_sr

def audio_to_base64(y, sr):
    buffer = io.BytesIO()
    sf.write(buffer, y, sr, format='wav')
    return base64.b64encode(buffer.getvalue()).decode()

# --- Final Fixed Function ---
def stt_translate(audio_path, override_lang=None):
    try:
        # 🔤 Step 1: Language Detection
        with open(audio_path, 'rb') as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        lang_payload = copy.deepcopy(lang_detect_payload)
        lang_payload["inputData"]["audio"][0]["audioContent"] = audio_b64
        lang_res = requests.post(BHASHINI_ENDPOINT, headers=HEADERS_BHASHINI, json=lang_payload)
        lang_data = safe_json(lang_res)

        lang_full = override_lang or lang_data.get("pipelineResponse", [{}])[0].get("output", [{}])[0].get("langPrediction", [{}])[0].get("langCode", "hi")
        lang = str(lang_full).split("-")[0]  # Converts 'en-US' → 'en'
        print("🔤 Detected Language:", lang)


    except Exception as e:
        print(f"⚠ Language detection failed: {e}")
        lang = override_lang or "hi"

    try:
        # 🎙 Step 2: Resample Audio
        y, sr = load_and_resample_audio(audio_path)
        audio_b64 = audio_to_base64(y, sr)
    except Exception as e:
        print(f"⚠ Audio processing failed: {e}")
        return "❌ Audio processing failed."

    try:
        # 🧠 Step 3: ASR + Translation Pipeline
        # payload = copy.deepcopy(asr_trans_payload)
        # payload["inputData"]["audio"][0]["audioContent"] = audio_b64
        # payload["pipelineTasks"][0]["config"]["language"]["sourceLanguage"] = lang
        # payload["pipelineTasks"][1]["config"]["language"]["sourceLanguage"] = lang
        # payload["pipelineTasks"][0]["config"]["serviceId"] = (
        #     "ai4bharat/conformer-hi-gpu--t4" if lang == "hi"
        #     else "ai4bharat/conformer-multilingual-dravidian-gpu--t4"
        # )

        payload = {
            "pipelineTasks": [
        {
            "taskType": "asr",
            "config": {
                "language": {
                    "sourceLanguage": lang
                },
                #"pipelineId": "64392f96daac500b55c543cd",
                "serviceId": "bhashini/ai4bharat/conformer-multilingual-asr",
                "audioFormat": "wav",
                "samplingRate": 16000,
                "postprocessors": [
                    "itn"
                ]
            }
        },
        {
            "taskType": "translation",
            "config": {
                "language": {
                    "sourceLanguage": lang,
                    "targetLanguage": "en"
                },
                "serviceId": "ai4bharat/indictrans-v2-all-gpu--t4"
            }
        }
    ],
    "inputData": {
        "audio": [
            {
                "audioContent": audio_b64
            }
        ]
    }
    }

        trans_res = requests.post(BHASHINI_ENDPOINT, headers=HEADERS_BHASHINI, json=payload)
        trans_data = safe_json(trans_res)

        # 🔍 Log full response (optional)
        print("🧾 Bhashini ASR+Translation Response:")
        print(json.dumps(trans_data, indent=2))

        # ✅ Final Transcription Output
        outputs = trans_data.get("pipelineResponse", [])
        if len(outputs) < 2:
            print("❌ Bhashini response missing expected output[1]")
            return "⚠ No transcription found"

        print("Transcription:", trans_res.json()['pipelineResponse'][0]['output'][0]['source'])
        print("Translation:", trans_res.json()['pipelineResponse'][1]['output'][0]['target'])
        translated_text = outputs[1].get("output", [{}])[0].get("target", "⚠ No transcription found")
        return translated_text

    except Exception as e:
        print(f"❌ Error extracting transcription: {e}")
        return "⚠ No transcription found"