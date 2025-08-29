from openai import OpenAI
from flask import Flask, request, jsonify
import PyPDF2
import os
from dotenv import load_dotenv
from flask_cors import CORS
import logging
import json
import re
import requests
import time

# -------------------- CONFIG --------------------
load_dotenv()  # Load environment variables from .env

# OpenAI client setup
client = OpenAI()

application = Flask(__name__)
CORS(application, origins=["http://localhost:3570"])  # Allow frontend to connect

# Debugging: Print partial OpenAI key for verification
print("OpenAI Key (partial):", os.getenv("OPENAI_API_KEY")[:8])

# Logging configuration: log both to file and console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -------------------- HELPERS --------------------

# Validate if a given URL is reachable
def is_valid_url(url):
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code == 200
    except requests.RequestException:
        return False

# Health check route
@application.route('/')
def index():
    return "Backend is running"

# Extract text from a PDF file
def extract_text_from_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
        logger.info('PDF text extraction successful')
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        raise

# Compare one CV against a JD using GPT
def compare_with_gpt_for_many_cvs(job_description, cv_text, selected_params):
    start_time = time.time()
    try:
        # Structured JSON response format for GPT
        prompt_string = '''
- "match_percentage": Number (e.g., 70)
- "similarities": List of matching skills/qualifications
- "missing": List of skills/requirements missing from the CV
- "course_recommendations": A list of objects. Each object should have:
    - "name": a short course title related to a missing skill
    - "url": a direct link to one relevant course online
    - If no course is available, include a "topics_to_cover" field instead with 2–3 topic suggestions
'''

        # Messages for GPT prompt
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"""
Job Description: {job_description}

CV Content: {cv_text}

Analyze the match between the job description and the CV. Return a JSON object with the following keys:

{prompt_string}

Only respond with the JSON object. If a course URL is not available for a missing skill, suggest relevant 'topics_to_cover' instead.
"""}
        ]

        # Send request to OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini", messages=messages
        )

        # Extract raw response from GPT
        feedback_raw = response.choices[0].message.content.strip()

        # Extract JSON object from GPT response
        match = re.search(r"\{.*\}", feedback_raw, re.DOTALL)
        if not match:
            logger.error("No JSON object found in GPT response.")
            raise ValueError("Invalid response format from GPT")

        feedback_full = json.loads(match.group(0))

        # Map frontend request params to GPT keys
        key_map = {
            "percentage": "match_percentage",
            "similarities": "similarities",
            "missing": "missing",
            "courses": "course_recommendations",
            "all": "all"
        }

        # Filter feedback by requested params
        if "all" in selected_params:
            selected_keys = list(key_map.values())[:-1]  # all except 'all'
        else:
            selected_keys = [key_map[p] for p in selected_params if p in key_map]

        feedback_filtered = {
            key: feedback_full.get(key)
            for key in selected_keys
            if feedback_full.get(key) is not None
        }

        # Validate course URLs before returning
        if "course_recommendations" in feedback_filtered:
            valid_courses = []
            for course in feedback_filtered["course_recommendations"]:
                if is_valid_url(course.get("url", "")):
                    valid_courses.append(course)
            feedback_filtered["course_recommendations"] = valid_courses

        return feedback_filtered

    except Exception as e:
        logger.error(f"Error in GPT-3 API request (many CVs): {e}")
        raise
    finally:
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"Processed one CV in {duration:.2f} seconds")

# -------------------- ROUTES --------------------

@application.route('/analyzeManyCvs', methods=['POST'])
def analyze_many_cvs():
    """
    Compare a single JD against multiple CVs.
    Returns a list of results with feedback for each CV.
    """
    jd_file = request.files.get('job_description')
    selected_params = request.form.get('selectedOptions')
    files = request.files.getlist('cvs')

    if not jd_file or not files:
        logger.error('Missing data: Job description file or CVs not provided')
        return jsonify({'error': 'Missing data'}), 400

    try:
        job_description = extract_text_from_pdf(jd_file)
    except Exception as e:
        logger.error(f"Error processing JD file: {e}")
        return jsonify({'error': f"Error processing JD file: {str(e)}"}), 500

    results = []

    # Process each CV
    for file in files:
        start_time = time.time()
        try:
            cv_text = extract_text_from_pdf(file)
            feedback = compare_with_gpt_for_many_cvs(job_description, cv_text, selected_params)
            results.append({
                'filename': file.filename,
                'feedback': feedback
            })
        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}")
            results.append({
                'filename': file.filename,
                'error': str(e)
            })
        finally:
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"[/analyzeManyCvs] {file.filename} processed in {duration:.2f} seconds")

    return jsonify({'results': results}), 200


@application.route('/analyzeManyCvsTableWithParams', methods=['POST'])
def analyze_many_cvs_table_with_params():
    """
    Compare a JD against multiple CVs and return results in table format.
    Only the selected parameters are included (percentage, similarities, etc.).
    """
    jd_file = request.files.get('job_description')
    selected_params = request.form.get('selectedOptions')
    files = request.files.getlist('cvs')

    if not jd_file or not files:
        logger.error('Missing data: Job description file or CVs not provided')
        return jsonify({'error': 'Missing data'}), 400

    try:
        job_description = extract_text_from_pdf(jd_file)
    except Exception as e:
        logger.error(f"Error processing JD file: {e}")
        return jsonify({'error': f"Error processing JD file: {str(e)}"}), 500

    table_data = []

    # Process each CV
    for file in files:
        start_time = time.time()
        try:
            cv_text = extract_text_from_pdf(file)
            feedback = compare_with_gpt_for_many_cvs(job_description, cv_text, selected_params)

            # Build a row of results for the table
            row = {'cv_name': file.filename}
            for param in selected_params:
                value = feedback.get(param)

                # Format output values
                if param == "percentage":
                    value = f"{value}%" if value is not None else "N/A"
                elif isinstance(value, list):
                    value = ', '.join(map(str, value))
                elif isinstance(value, dict):
                    value = json.dumps(value)
                else:
                    value = str(value) if value is not None else "N/A"

                row[param] = value

            table_data.append(row)

        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}")
            row = {'cv_name': file.filename, 'error': str(e)}
            for param in selected_params:
                row[param] = 'Error'
            table_data.append(row)
        finally:
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"[analyzeManyCvsTableWithParams] {file.filename} processed in {duration:.2f} seconds")

    return jsonify({'table_data': table_data}), 200


# -------------------- MAIN --------------------
if __name__ == '__main__':
    application.run(debug=True, port=4780)
