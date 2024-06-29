# Base imports
import random
import re
import os
from typing import List, Dict, Any

# external imports
from flask import Flask, render_template_string, request, session, redirect, url_for
from flask import send_file
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from datetime import datetime
import io
from PyPDF2 import PdfReader, PdfWriter
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# custom imports
from config import EXAMS_FOLDER
from config import EXAM_QUESTIONS
from config import QUESTIONS_PER_PAGE
from config import THEME
from config import TITLE

app = Flask(__name__)
app.secret_key = 'una_clau_secreta_molt_segura'

QUESTION_STYLE = 'h3'
def generate_pdf(score: int, total_questions: int, detailed_results: List[Dict[str, Any]]) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    # Add title
    story.append(Paragraph(f"Exam Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Title']))
    story.append(Spacer(1, 12))

    # Add score
    percentage = (score / total_questions) * 100
    story.append(Paragraph(f"Score: {score} out of {total_questions} ({percentage:.2f}%)", styles['Heading2']))
    story.append(Spacer(1, 12))

    # Add detailed results
    for i, result in enumerate(detailed_results, 1):
        story.append(Paragraph(f"{i}. {result['question']}", styles['Heading3']))
        
        if result['is_correct']:
            story.append(Paragraph(f"Correct answer: {', '.join(result['correct_answers'])}", styles['BodyText']))
        else:
            if isinstance(result['user_answer'], list):
                user_answer = ', '.join(result['user_answer']) if result['user_answer'] else "No answer selected"
            else:
                user_answer = result['user_answer'] if result['user_answer'] else "No answer provided"
            
            story.append(Paragraph(f"Your answer: {user_answer}", styles['BodyText']))
            story.append(Paragraph(f"Correct answer: {', '.join(result['correct_answers'])}", styles['BodyText']))
        
        story.append(Spacer(1, 12))

    doc.build(story)
    buffer.seek(0)
    return buffer

def load_cfg(filename: str) -> str:
    '''
    Load config file
    '''
    with open(filename, 'r', encoding="utf-8") as f:
        cfg = f.read()
    return cfg

def get_syllabus(folder: str) -> List[str]:
    '''
    Scan folder for exam course
    '''
    return [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]

def get_exam_files(course: str) -> List[str]:
    """
    Returns a list of exam files for a specific course.
    
    Args:
    course -- The course for which to get the exam files
    
    Returns:
    A list of filenames ending with '.md'
    """
    exams_folder = EXAMS_FOLDER  # Define this variable according to your configuration
    syllabus_path = os.path.join(exams_folder, course)
    return [f for f in os.listdir(syllabus_path) if f.endswith('.md')]

def process_files(course: str, file_names: List[str]) -> List[Dict[str, Any]]:
    """
    Process multiple exam files and return a list of unique questions and answers.

    Args:
    course -- The course name
    file_names -- List of file names to process

    Returns:
    A list of dictionaries containing unique questions, answers, and correct answers
    """
    all_questions = []
    
    for file_name in file_names:
        questions = process_single_file(course, file_name)
        print(f"Loaded {len(questions)} questions from {file_name}")
        all_questions.extend(questions)
    
    # Remove duplicates
    unique_questions = remove_duplicates(all_questions)
    
    print(f"Total unique questions after removing duplicates: {len(unique_questions)}")
    
    return unique_questions

def process_single_file(course: str, file_name: str) -> List[Dict[str, Any]]:
    """
    Process a single exam file and return a list of questions and answers.

    Args:
    course -- The course name
    file_name -- The name of the file to process

    Returns:
    A list of dictionaries containing questions, answers, and correct answers
    """
    full_path = os.path.join(EXAMS_FOLDER, course, file_name)
    with open(full_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    questions_answers = []
    current_question = {'question': '', 'answers': [], 'correct': []}
    for line in lines:
        line = line.strip()
        line = re.sub(r'\[\[(.*?)\]\]', r'\1', line)
        line = re.sub(r'`(.*?)`', r'<code>\1</code>', line)
        if line.startswith('####'):
            if current_question['question']:
                questions_answers.append(current_question)
                current_question = {'question': '', 'answers': [], 'correct': []}
            current_question['question'] += line[4:] + ' '
        elif line.startswith('+'):
            answer = line[1:].strip()
            is_correct = '**' in answer
            answer = answer.replace('**', '')
            current_question['answers'].append(answer)
            if is_correct:
                current_question['correct'].append(answer)

    if current_question['question']:
        questions_answers.append(current_question)
    
    return questions_answers

def remove_duplicates(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate questions from the list.

    Args:
    questions -- List of question dictionaries

    Returns:
    A list of unique question dictionaries
    """
    unique_questions = []
    seen_questions = set()
    
    for question in questions:
        # Create a tuple of the question and its answers for comparison
        question_tuple = (question['question'], tuple(sorted(question['answers'])))
        
        if question_tuple not in seen_questions:
            seen_questions.add(question_tuple)
            unique_questions.append(question)
    
    return unique_questions


def generate_topic_selection_html(topics: List[str]) -> str:
    """
    Generate HTML for topic selection page.

    Args:
    topics -- List of available topics

    Returns:
    HTML string for topic selection page
    """
    html = BASE_HTML
    html += '<h2>Select a course:</h2>\n'
    html += '<form method="post" action="/select_topic">\n'
    for course in topics:
        html += f'<input type="radio" name="course" value="{course}">{course}<br>\n'
    html += '<br><input type="submit" value="Select course">\n'
    html += '</form>\n'
    html += '</body></html>'
    return html

def generate_exam_selection_html(course: str, files: List[str]) -> str:
    """
    Generate HTML for exam selection page.

    Args:
    course -- Selected course
    files -- List of available exam files

    Returns:
    HTML string for exam selection page
    """
    html = BASE_HTML
    html += f'<h2>Course: {course}</h2>\n'
    html += '<h3>Select an exam:</h3>\n'
    html += '<form method="post" action="/select_exam">\n'
    for file in files:
        html += f'<input type="checkbox" name="exam" value="{file}">{file}<br>\n'
    html += f'<input type="hidden" name="course" value="{course}">\n'
    html += '<br><input type="submit" value="Start Exam">\n'
    html += '</form>\n'
    html += '</body></html>'
    return html

def generate_quiz_html(questions_answers: List[Dict[str, Any]], question_style: str, 
                       current_page: int, total_questions: int, saved_answers: Dict[str, List[str]]) -> str:
    """
    Generate HTML for the quiz page.

    Args:
    questions_answers -- List of questions and answers
    question_style -- HTML style for questions
    current_page -- Current page number
    total_questions -- Total number of questions
    saved_answers -- Dictionary of saved user answers

    Returns:
    HTML string for the quiz page
    """
    html = BASE_HTML
    html += '<form method="post">\n'
    
    offset = (current_page - 1) * QUESTIONS_PER_PAGE
    
    for i, question in enumerate(questions_answers, offset + 1):
        html += f"<{question_style}>{i}. {question['question']}</{question_style}>\n"
        key = f'question{i}'
        user_answers = saved_answers.get(key, [])
        
        if len(question['correct']) == 1 and len(question['answers']) == 1:
            value = user_answers[0] if user_answers else ""
            html += f'<input type="text" name="{key}" value="{value}" />\n'
        elif len(question['correct']) == 1:
            for answer in question['answers']:
                checked = 'checked' if answer in user_answers else ''
                html += f'<input type="radio" name="{key}" value="{answer}" {checked}>{answer}<br/>\n'
        else:
            for answer in question['answers']:
                checked = 'checked' if answer in user_answers else ''
                html += f'<input type="checkbox" name="{key}" value="{answer}" {checked}>{answer}<br/>\n'
    
    # Add pagination controls
    total_pages = (total_questions + QUESTIONS_PER_PAGE - 1) // QUESTIONS_PER_PAGE
    html += f'<p>Page {current_page} of {total_pages}</p>\n'
    
    if current_page > 1:
        html += f'<a href="{url_for("quiz", page=current_page-1)}">Previous</a> '
    
    if current_page < total_pages:
        html += f'<a href="{url_for("quiz", page=current_page+1)}">Next</a> '
    
    html += '<br><br><input type="submit" name="action" value="Finish Exam" />\n'
    html += '</form>\n'
    html += '</body></html>'
    return html

def generate_results_html(score: int, total_questions: int, detailed_results: List[Dict[str, Any]]) -> str:
    """
    Generate HTML for the results page with colored answers and improved display logic.

    Args:
    score -- User's score
    total_questions -- Total number of questions
    detailed_results -- List of detailed results for each question

    Returns:
    HTML string for the results page
    """
    percentage = (score / total_questions) * 100  
    html= BASE_HTML  
    html += f'<h1>Your score is: {score} out of {total_questions} ({percentage:.2f}%)</h1>'
    html += '<h2>Detailed answers:</h2>'
    
    for i, result in enumerate(detailed_results, 1):
        html += f"<{QUESTION_STYLE}>{i}. {result['question']}</{QUESTION_STYLE}>"
        
        if result['is_correct']:
            # If the answer is correct, show only the correct answer in green
            html += '<p><span style="color: black;">Correct answer: </span>'
            html += f'<span style="color: green;">{", ".join(result["correct_answers"])}</span></p>'
        else:
            # If the answer is incorrect, show both user's answer (in red) and correct answer (in green)
            if isinstance(result['user_answer'], list):
                user_answer = ', '.join(result['user_answer']) if result['user_answer'] else "No answer selected"
            else:
                user_answer = result['user_answer'] if result['user_answer'] else "No answer provided"
            
            html += '<p><span style="color: black;">Your answer: </span>'
            html += f'<span style="color: red;">{user_answer}</span></p>'
            html += '<p><span style="color: black;">Correct answer: </span>'
            html += f'<span style="color: green;">{", ".join(result["correct_answers"])}</span></p>'
        
        html += "<hr>"
     
        html += '<form method="get" action="/download_results">'
    html += '<input type="submit" value="Download Exam Results" />'
    html += '</form>'
    html += '<form method="get" action="/">'
    html += '<input type="submit" value="New Exam" />'
    html += '</form>'
    
    return html


# ---------------------| Variables |------------------

header = load_cfg(f"./static/theme/{THEME}/header.cfg")
# load theme
HEADER = f"<head>{header}</head>".replace("@THEME", THEME)
HEADER = HEADER.replace("@TITLE", TITLE)
BASE_HTML = f'<html>{HEADER}<body>\n'
# Assumim que tens una clau privada en format PEM
PRIVATE_KEY_PATH = 'path/to/your/private_key.pem'
PRIVATE_KEY_PASSWORD = b'your_password_if_any'  # Deixa-ho com a None si no hi ha contrasenya
# --------------------------- Main app ------------------
@app.route('/')
def index():
    """
    Route for the index page.
    """
    topics = get_syllabus(EXAMS_FOLDER)
    return render_template_string(generate_topic_selection_html(topics))

@app.route('/select_topic', methods=['POST'])
def select_topic():
    """
    Route for topic selection.
    """
    selected_topic = request.form.get('course')
    if selected_topic:
        files = get_exam_files(selected_topic)
        return render_template_string(generate_exam_selection_html(selected_topic, files))
    return redirect(url_for('index'))

# Modify the select_exam route to use the new process_files function
@app.route('/select_exam', methods=['POST'])
def select_exam():
    """
    Route for exam selection.
    """
    course = request.form.get('course')
    selected_exams = request.form.getlist('exam')  # This will get multiple selected exams
    if course and selected_exams:
        session['course'] = course
        session['selected_exams'] = selected_exams
        questions_answers = process_files(course, selected_exams)
        
        # Shuffle the questions if needed
        random.shuffle(questions_answers)
        
        # Limit to EXAM_QUESTIONS if needed
        questions_answers = questions_answers[:EXAM_QUESTIONS]
        
        session['questions_answers'] = questions_answers
        session['user_answers'] = {f'question{i+1}': [] for i in range(len(questions_answers))}
        return redirect(url_for('quiz'))
    return redirect(url_for('index'))
@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    """
    Route for the quiz page.
    """
    if 'questions_answers' not in session:
        return redirect(url_for('index'))
    
    questions_answers = session['questions_answers']
    total_questions = len(questions_answers)
    
    # Initialize user answers if they don't exist
    if 'user_answers' not in session:
        session['user_answers'] = {f'question{i+1}': [] for i in range(total_questions)}
    
    # Get current page
    current_page = request.args.get('page', 1, type=int)
    
    # Calculate start and end index for current page
    start = (current_page - 1) * QUESTIONS_PER_PAGE
    end = min(start + QUESTIONS_PER_PAGE, total_questions)
    
    # Get questions for current page
    page_questions = questions_answers[start:end]
    
    if request.method == 'POST':
        # Save answers for current page
        user_answers = session['user_answers']
        for i in range(start + 1, end + 1):
            key = f'question{i}'
            if key in request.form:
                user_answers[key] = request.form.getlist(key)
            elif key not in user_answers:
                user_answers[key] = []
        
        session['user_answers'] = user_answers
        session.modified = True
        
        if request.form.get('action') == 'Finish Exam':
            # Process all answers
            score = 0
            detailed_results = []
            
            for i, question in enumerate(questions_answers, 1):
                key = f'question{i}'
                user_answer = user_answers.get(key, [])
                correct_answers = set(question['correct'])
                is_correct = False
                
                if len(question['correct']) == 1 and len(question['answers']) == 1:
                    user_answer = user_answer[0] if user_answer else ""
                    is_correct = user_answer.lower() == question['correct'][0].lower()
                elif len(question['correct']) == 1:
                    user_answer = user_answer[0] if user_answer else ""
                    is_correct = user_answer in correct_answers
                else:
                    is_correct = set(user_answer) == correct_answers
                
                if is_correct:
                    score += 1
                
                detailed_results.append({
                    'question': question['question'],
                    'user_answer': user_answer,
                    'correct_answers': question['correct'],
                    'is_correct': is_correct
                })
            
            # Save results to session
            session['score'] = score
            session['total_questions'] = total_questions
            session['detailed_results'] = detailed_results
            
            # Clear answers from session
            session.pop('user_answers', None)
            session.pop('questions_answers', None)
            
            # Generate and return results
            return generate_results_html(score, total_questions, detailed_results)
        else:
            # If exam not finished, redirect to next page
            return redirect(url_for('quiz', page=current_page+1))
    
    # Retrieve saved answers for this page
    saved_answers = {k: v for k, v in session['user_answers'].items() if int(k[8:]) > start and int(k[8:]) <= end}
    
    html = generate_quiz_html(page_questions, QUESTION_STYLE, current_page, total_questions, saved_answers)
    return render_template_string(html)

@app.route('/download_results')
def download_results():
    score = session.get('score')
    total_questions = session.get('total_questions')
    detailed_results = session.get('detailed_results')

    if not all([score, total_questions, detailed_results]):
        return "No exam results available", 400

    pdf_buffer = generate_pdf(score, total_questions, detailed_results)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"exam_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mimetype='application/pdf'
    )
if __name__ == '__main__':
    app.run(debug=True)