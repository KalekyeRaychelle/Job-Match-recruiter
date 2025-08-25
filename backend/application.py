import openai
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

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

application = Flask(__name__)
CORS(application, origins=["http://localhost:3570"])



print("OpenAI Key (partial):", os.getenv("OPENAI_API_KEY")[:8])

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# URL validation function
def is_valid_url(url):
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code == 200
    except requests.RequestException:
        return False
    
@application.route('/')
def index():
    return "Backend is running"

@application.route('/get-questions', methods=['POST'])
def generate_questions():
    data = request.json
    job_description = data.get('job_description')

    if not job_description:
        return jsonify({'error': 'Missing job description'}), 400

    prompt = f"Based on the following job description, generate 10 common interview questions and their answers in the format Q: ... A: ...\n\n{job_description}"

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    answer_text = response.choices[0].message.content

    qa_pairs = []
    lines = answer_text.split('\n')
    current_q = ''
    current_a = ''
    for line in lines:
        if line.strip().startswith("Q:"):
            if current_q and current_a:
                qa_pairs.append({'question': current_q, 'answer': current_a})
            current_q = line.strip()[2:].strip()
            current_a = ''
        elif line.strip().startswith("A:"):
            current_a = line.strip()[2:].strip()
        else:
            current_a += ' ' + line.strip()

    if current_q and current_a:
        qa_pairs.append({'question': current_q, 'answer': current_a})

    return jsonify({'questions': qa_pairs})

@application.route('/Ask', methods=['POST'])
def Ask():
    try:
        data = request.get_json()
        question = data.get('question')

        if not question:
            return jsonify({"error": "No question provided"}), 400

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ]
        )

        answer = response.choices[0].message.content.strip()
        logger.debug(f"Received question: {question}")
        logger.debug(f"OpenAI response: {answer}")

        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

def compare_with_gpt_for_non_immediate_interview(job_description, cv_text):
    try:
        prompt = f"""
Job Description: {job_description}

CV Content: {cv_text}

Analyze the match between the job description and the CV. Return a JSON object with the following keys:
- "match_percentage": Number (e.g., 70)
- "similarities": List of matching skills/qualifications
- "missing": List of skills/requirements missing from the CV
- "course_recommendations": A list of objects. Each object should have:
    - "name": a short course title related to a missing skill
    - "url": a direct link to one relevant course online 
"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )

        feedback_raw = response.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", feedback_raw, re.DOTALL)
        if not match:
            logger.error("No JSON object found in GPT response.")
            raise ValueError("Invalid response format from GPT")

        feedback = json.loads(match.group(0))

        feedback['course_recommendations'] = [
            course for course in feedback.get('course_recommendations', [])
            if is_valid_url(course['url'])
        ]

        return feedback
    except Exception as e:
        logger.error(f"Error in GPT-3 API request: {e}")
        raise

@application.route('/analyze', methods=['POST'])
def analyze():
    jd_file = request.files.get('job_description')
    cv_file = request.files.get('cv')

    if not jd_file or not cv_file:
        logger.error('Missing data: Job description file or CV not provided')
        return jsonify({'error': 'Missing data'}), 400

    try:
        job_description = extract_text_from_pdf(jd_file)   # extract JD text
        cv_text = extract_text_from_pdf(cv_file)
    except Exception as e:
        logger.error(f"Error processing files: {e}")
        return jsonify({'error': f"Error processing files: {str(e)}"}), 500

    try:
        feedback = compare_with_gpt_for_non_immediate_interview(job_description, cv_text)

        return jsonify({'feedback': feedback}), 200
    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        return jsonify({'error': f"Error during analysis: {str(e)}"}), 500

def compare_with_gpt_for_many_cvs(job_description, cv_text, selected_params):
    start_time = time.time()
    try:
        prompt_string = '''
- "match_percentage": Number (e.g., 70)
- "similarities": List of matching skills/qualifications
- "missing": List of skills/requirements missing from the CV
- "course_recommendations": A list of objects. Each object should have:
    - "name": a short course title related to a missing skill
    - "url": a direct link to one relevant course online
    - If no course is available, include a "topics_to_cover" field instead with 2–3 topic suggestions
'''

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

        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=600,
            temperature=0.7
        )

        feedback_raw = response.choices[0].message.content.strip()

        match = re.search(r"\{.*\}", feedback_raw, re.DOTALL)
        if not match:
            logger.error("No JSON object found in GPT response.")
            raise ValueError("Invalid response format from GPT")

        feedback_full = json.loads(match.group(0))

        key_map = {
            "percentage": "match_percentage",
            "similarities": "similarities",
            "missing": "missing",
            "courses": "course_recommendations",
            "all": "all"
        }

        if "all" in selected_params:
            selected_keys = list(key_map.values())[:-1]  # all except 'all'
        else:
            selected_keys = [key_map[p] for p in selected_params if p in key_map]

        feedback_filtered = {
            key: feedback_full.get(key)
            for key in selected_keys
            if feedback_full.get(key) is not None
        }

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


@application.route('/analyzeManyCvs', methods=['POST'])
def analyze_many_cvs():
    jd_file = request.files.get('job_description')
    selected_params = request.form.get('selectedOptions')
    files = request.files.getlist('cvs')

    if not jd_file or not files:
        logger.error('Missing data: Job description file or CVs not provided')
        return jsonify({'error': 'Missing data'}), 400

    try:
        job_description = extract_text_from_pdf(jd_file)   # JD as file
    except Exception as e:
        logger.error(f"Error processing JD file: {e}")
        return jsonify({'error': f"Error processing JD file: {str(e)}"}), 500

    results = []

    for file in files:
        start_time=time.time()
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
    jd_file = request.files.get('job_description')
    selected_params = request.form.get('selectedOptions')
    files = request.files.getlist('cvs')

    if not jd_file or not files:
        logger.error('Missing data: Job description file or CVs not provided')
        return jsonify({'error': 'Missing data'}), 400

    try:
        job_description = extract_text_from_pdf(jd_file)   # JD as file
    except Exception as e:
        logger.error(f"Error processing JD file: {e}")
        return jsonify({'error': f"Error processing JD file: {str(e)}"}), 500

    table_data = []

    for file in files:
        start_time=time.time()
        try:
            cv_text = extract_text_from_pdf(file)
            feedback = compare_with_gpt_for_many_cvs(job_description, cv_text, selected_params)

            
            row = {'cv_name': file.filename}
            for param in selected_params:
                value = feedback.get(param)

                
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


if __name__ == '__main__':
    application.run(debug=True, port=4780)
