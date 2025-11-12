from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
import base64, os, datetime, re, subprocess

# Utility to clean unsafe characters (e.g., from Gemini)
def strip_invalid_chars(value):
    if not isinstance(value, str):
        return value
    return re.sub(r'[{}#]', '', value)

def generate_resume_from_template(resume_data, template_path='templates/docx/Creative.docx', image_b64=None):
    doc = DocxTemplate(template_path)

    # --- Save image if provided ---
    image_path = None
    image_inline = ""
    if image_b64:
        try:
            img_data = base64.b64decode(image_b64.split(",")[-1])  # handle data:image/png;base64,...
            image_path = "temp_image.png"
            with open(image_path, "wb") as f:
                f.write(img_data)
            # Inline image for docxtpl
            image_inline = InlineImage(doc, image_path, width=Mm(40))  # adjust size if needed
        except Exception as e:
            print("⚠ Failed to decode image:", e)

    # Flatten NAME and CONTACT
    name_block = resume_data.get("NAME", {})
    if isinstance(name_block, dict):
        resume_data["FULL_NAME"] = strip_invalid_chars(name_block.get("NAME", ""))
        resume_data["JOB_TITLE"] = strip_invalid_chars(name_block.get("TITLE", ""))
    else:
        resume_data["FULL_NAME"] = strip_invalid_chars(resume_data.get("NAME", ""))
        resume_data["JOB_TITLE"] = strip_invalid_chars(resume_data.get("TITLE", ""))

    contact_block = resume_data.get("CONTACT", {})
    if isinstance(contact_block, dict):
        resume_data["PHONE"] = strip_invalid_chars(contact_block.get("PHONE", ""))
        resume_data["EMAIL"] = strip_invalid_chars(contact_block.get("EMAIL", ""))
        resume_data["WEBSITE"] = strip_invalid_chars(contact_block.get("WEBSITE", ""))
    else:
        resume_data["PHONE"] = strip_invalid_chars(resume_data.get("PHONE", ""))
        resume_data["EMAIL"] = strip_invalid_chars(resume_data.get("EMAIL", ""))
        resume_data["WEBSITE"] = strip_invalid_chars(resume_data.get("WEBSITE", ""))

    address_block = resume_data.get("LOCATION", {})
    if isinstance(address_block, dict):
        resume_data["ADDRESS"] = strip_invalid_chars(address_block.get("ADDRESS", "") or address_block.get("LOCATION", ""))
    else:
        resume_data["ADDRESS"] = strip_invalid_chars(resume_data.get("ADDRESS", ""))

    resume_data["PROFILE"] = strip_invalid_chars(
        resume_data.get("PROFILE", "To work in a challenging environment that allows me to grow and utilize my skills.")
    )

    # Context for template
    context = {
        "FULL_NAME": resume_data.get("FULL_NAME", ""),
        "JOB_TITLE": resume_data.get("JOB_TITLE", ""),
        "PHONE": resume_data.get("PHONE", ""),
        "EMAIL": resume_data.get("EMAIL", ""),
        "WEBSITE": resume_data.get("WEBSITE", ""),
        "ADDRESS": resume_data.get("ADDRESS", ""),
        "PROFILE": resume_data.get("PROFILE", ""),
        "IMAGE": image_inline,

        "EDUCATION": [
            {
                "EDU_YEAR": strip_invalid_chars(edu.get("EDU_YEAR", "")),
                "DEGREE": strip_invalid_chars(edu.get("DEGREE", "")),
                "UNIVERSITY": strip_invalid_chars(edu.get("UNIVERSITY", "")),
                "EDU_DESC": strip_invalid_chars(edu.get("EDU_DESC", ""))
            }
            for edu in resume_data.get("EDUCATION", [])
        ],

        "EXPERIENCE": [
            {
                "EXP_YEAR": strip_invalid_chars(exp.get("EXP_YEAR", "")),
                "EXP_JOB_TITLE": strip_invalid_chars(exp.get("EXP_JOB_TITLE", "")),
                "EXP_COMPANY": strip_invalid_chars(exp.get("EXP_COMPANY", "")),
                "EXP_DESC": strip_invalid_chars(exp.get("EXP_DESC", ""))
            }
            for exp in resume_data.get("EXPERIENCE", [])
        ],

        "AWARDS": [
            {
                "AWARD_TITLE": strip_invalid_chars(award.get("AWARD_TITLE", "")),
                "AWARD_DESC": strip_invalid_chars(award.get("AWARD_DESC", ""))
            }
            for award in resume_data.get("AWARDS", [])
        ],

        "EXPERTISE": [{"SKILL": strip_invalid_chars(skill)} for skill in resume_data.get("SKILLS", [])],
        "INTERESTS": [{"INTEREST": strip_invalid_chars(i)} for i in resume_data.get("INTERESTS", [])]
    }

    # Render the template
    doc.render(context)

    # Save DOCX
    output_folder = "output"
    os.makedirs(output_folder, exist_ok=True)
    filename = f"resume_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    output_path = os.path.join(output_folder, filename)
    doc.save(output_path)

    # Convert to PDF using LibreOffice
    pdf_output_path = os.path.join(output_folder, filename.replace(".docx", ".pdf"))
    try:
        # Cross-platform LibreOffice command
        soffice_cmd = "soffice"
        if os.name == "nt":  # Windows
            soffice_cmd = r"C:\Program Files\LibreOffice\program\soffice.exe"

        subprocess.run([
            soffice_cmd,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", output_folder,
            output_path
        ], check=True)
    except Exception as e:
        print("⚠ LibreOffice PDF conversion failed:", e)

    # Cleanup temporary image
    if image_path and os.path.exists(image_path):
        os.remove(image_path)

    return output_path, pdf_output_path
