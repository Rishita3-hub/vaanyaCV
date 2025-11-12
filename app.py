from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import os
import json
import base64
import requests
import re
import datetime
from generate_resume import generate_resume_from_template
from bhashini_pipeline import stt_translate

app = Flask(__name__, static_url_path="/output", static_folder="output")
CORS(app)

# ----------------- AUDIO TO TEXT ---------------------
@app.route("/audio_to_text", methods=["POST"])
def audio_to_text():
    temp_path = "temp_audio.wav"
    try:
        data = request.json
        audio_base64 = data["audio"]
        lang = data.get("lang", "hi")

        with open(temp_path, "wb") as f:
            f.write(base64.b64decode(audio_base64))

        translated_text = stt_translate(temp_path, lang)
        return jsonify({"translated_text": translated_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# ----------------- GEMINI ---------------------
GEMINI_API_KEY = "AIzaSyDQq1B4ZAsHIwVvK49Sl99up4H4JA0GxGQ"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

def clean_json_string(text):
    return re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()

def gemini_prompt(prompt, text):
    full_prompt = f"{prompt.strip()}\n\nInput:\n{text.strip()}\n\nOutput JSON only."
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
    response = requests.post(GEMINI_URL, headers=headers, json=payload)
    if response.status_code == 200:
        try:
            raw = response.json()['candidates'][0]['content']['parts'][0]['text']
            return clean_json_string(raw)
        except:
            return "{}"
    else:
        return "{}"

# ----------------- HOME ---------------------
@app.route('/')
def home():
    return '✅ Flask backend running'

# ----------------- PARSE RESUME ---------------------
@app.route('/parse_resume', methods=['POST'])
def parse_resume():
    data = request.json
    answers = data.get("answers", {})
    print("Received data from Flutter:", request.json)
    selected_template = data.get("template", "Creative.docx")
    parsed_resume = {}

    prompts = {
        "education": """
You are a professional resume assistant. Extract and rewrite the education details from the input in a polished, formal tone.
Return a JSON array of objects in this format:
[ { "EDU_YEAR": "2021–2025", "DEGREE": "Bachelor of Technology in Computer Science", "UNIVERSITY": "IIT Bombay", "EDU_DESC": "Graduated with distinction, specialized in Artificial Intelligence, CGPA: 8.9" } ]
Only return clean JSON output. No explanations.
""",
        "experience": """
You are a professional resume assistant. Extract and polish professional experience from the text. Convert responsibilities into bullet-style descriptions (use '\\n' to separate lines).
Return a JSON array like:
[ { "EXP_YEAR": "2023–2024", "EXP_JOB_TITLE": "Machine Learning Intern", "EXP_COMPANY": "Microsoft", "EXP_DESC": "- Developed ML models for classification\\n- Integrated models into production with Flask\\n- Collaborated with senior engineers" } ]
Only return clean JSON output. No explanations.
""",
        "awards": """
You are a resume assistant. Extract achievements/awards and rewrite them in professional format.
Return a JSON array like:
[ { "AWARD_TITLE": "Winner – Smart India Hackathon", "AWARD_DESC": "Achieved 1st place nationwide for designing an AI solution for agriculture" } ]
Only return clean JSON. No markdown or explanations.
""",
        "skills": """
Extract a clean list of professional skills (technical + soft skills) from the input. Avoid duplicates.
Return ONLY a JSON array like:
["Python", "Machine Learning", "Communication", "Problem Solving"]
""",
        "name": """
Extract the full name and the professional title from the input.
Return ONLY this JSON:
{ "NAME": "Rishita Sharma", "TITLE": "AI & Data Science Student" }
""",
        "contact": """
Extract contact details. Ensure phone number is valid (Indian format if applicable). Format as JSON:
{ "PHONE": "9876543210", "EMAIL": "rishitasharma@example.com", "WEBSITE": "https://linkedin.com/in/rishita" }
Return only JSON. No explanation.
""",
        "location": """
Extract current location of the candidate.
Return JSON in this format:
{ "ADDRESS": "New Delhi, India" }
"""
    }

    for key, text in answers.items():
        prompt = prompts.get(key)
        if prompt:
            try:
                response_text = gemini_prompt(prompt, text)
                print(f"📦 Gemini Output for '{key}':\n{response_text}")
                parsed_resume[key.upper()] = json.loads(response_text)
            except Exception as e:
                parsed_resume[key.upper()] = {"error": str(e), "raw": response_text if 'response_text' in locals() else ''}

    return jsonify({"parsed_resume": parsed_resume, "template": selected_template})

# Ensure the output directory exists (for Render and local)
OUTPUT_DIR = os.path.join(os.getcwd(), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ----------------- GENERATE RESUME (Word + PDF) ---------------------
@app.route('/generate_resume', methods=['POST'])
def generate_resume():
    data = request.json
    resume_data = data.get("resume_data", {})
    selected_template = data.get("template", "Creative.docx")
    image_b64 = data.get("image_b64")

    try:
        # Generate both DOCX and PDF
        docx_path, pdf_path = generate_resume_from_template(
            resume_data,
            template_path=f"templates/docx/{selected_template}",
            image_b64=image_b64
        )

        base_url = request.host_url.rstrip('/')
        docx_url = f"{base_url}/download/docx/{os.path.basename(docx_path)}"
        pdf_url = f"{base_url}/download/pdf/{os.path.basename(pdf_path)}"

        print("✅ DOCX URL:", docx_url)
        print("✅ PDF URL:", pdf_url)

        return jsonify({
            "docx_url": docx_url,
            "pdf_url": pdf_url,
            "error": None
        })

    except Exception as e:
        print("❌ Resume generation failed:", e)
        return jsonify({
            "docx_url": "",
            "pdf_url": "",
            "error": str(e)
        }), 500

# ----------------- Serve Files as Attachments ---------------------
@app.route('/download/docx/<filename>')
def download_docx(filename):
    return send_file(
        os.path.join("output", filename),
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

@app.route('/download/pdf/<filename>')
def download_pdf(filename):
    return send_file(
        os.path.join("output", filename),
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )

# ----------------- START ---------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
