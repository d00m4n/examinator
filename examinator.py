# Base imports
import random
import re
import os
from typing import List, Dict, Any
from time import sleep
from io import BytesIO
from datetime import datetime
import io
import importlib
import ast

# external imports
from flask import Flask, render_template_string, request, session, redirect, url_for,flash
from flask import send_file,render_template
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from PyPDF2 import PdfReader, PdfWriter
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend

# custom imports
from config import EXAMS_FOLDER
from config import EXAM_QUESTIONS
from config import QUESTIONS_PER_PAGE
from config import THEME
from config import TITLE
from appsecrets import PRIVATE_KEY_PATH
from appsecrets import PRIVATE_KEY_PASSWORD
import config


app = Flask(__name__)
app.secret_key = 'una_clau_secreta_molt_segura'
QUESTION_STYLE = 'h3'

def load_private_key():
    if not os.path.exists(PRIVATE_KEY_PATH):
        return None
    try:
        with open(PRIVATE_KEY_PATH, 'rb') as key_file:
            private_key = load_pem_private_key(
                key_file.read(),
                password=PRIVATE_KEY_PASSWORD if PRIVATE_KEY_PASSWORD else None,
                backend=default_backend()
            )
            return private_key
    except Exception as e:
        print(f"Error loading private key: {str(e)}")
        return None

def sign_pdf(pdf_content):
    private_key = load_private_key()
    if private_key is None:
        return pdf_content  # Return unsigned PDF if no valid key is found

    # Assegurem-nos que pdf_content és bytes
    if isinstance(pdf_content, io.BytesIO):
        pdf_content = pdf_content.getvalue()

    # Rest of the signing process...
    reader = PdfReader(io.BytesIO(pdf_content))
    writer = PdfWriter()

    # Copiem totes les pàgines al nou writer
    for page in reader.pages:
        writer.add_page(page)

    # Creem la signatura
    hash_object = hashes.Hash(hashes.SHA256())
    hash_object.update(pdf_content)
    digest = hash_object.finalize()

    signature = private_key.sign(
        digest,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )

    # Afegim la signatura al PDF
    writer.add_metadata({
        '/Signature': signature.hex(),
        '/SignatureMethod': 'RSA-SHA256'
    })

    # Escrivim el PDF signat
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output.getvalue()  # Return bytes instead of BytesIO

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
                # Només barregem i afegim la pregunta si té respostes
                if current_question['answers']:
                    answers = current_question['answers']
                    correct_answers = current_question['correct']
                    zipped_answers = list(zip(answers, [answer in correct_answers for answer in answers]))
                    random.shuffle(zipped_answers)
                    current_question['answers'], is_correct = zip(*zipped_answers)
                    current_question['correct'] = [answer for answer, correct in zip(current_question['answers'], is_correct) if correct]
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

    # Processar l'última pregunta
    if current_question['question'] and current_question['answers']:
        answers = current_question['answers']
        correct_answers = current_question['correct']
        zipped_answers = list(zip(answers, [answer in correct_answers for answer in answers]))
        random.shuffle(zipped_answers)
        current_question['answers'], is_correct = zip(*zipped_answers)
        current_question['correct'] = [answer for answer, correct in zip(current_question['answers'], is_correct) if correct]
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

def add_redirect(BASE_HTML, redirect_url, delay=5):
    # Creem la metaetiqueta de redirecció
    redirect_meta = f'<meta http-equiv="refresh" content="{delay}; URL=\'{redirect_url}\'" />'
    
    # Afegim la metaetiqueta al <head> de BASE_HTML
    head_end_index = BASE_HTML.find('</head>')
    if head_end_index == -1:
        return BASE_HTML  # Si no hi ha </head>, retornem BASE_HTML sense canvis
    
    # Inserim la metaetiqueta just abans de </head>
    return BASE_HTML[:head_end_index] + redirect_meta + BASE_HTML[head_end_index:]

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
        # Afegim l'estil CSS per al div flotant
    # Afegim la referència al fitxer CSS
    html += f'<link rel="stylesheet" type="text/css" href="/static/theme/{THEME}/css/confirm.css">'
        
    # Afegim el div flotant al HTML
    html += '''
    <div id="confirmOverlay">
        <div id="confirmBox">
            <p>Estàs segur que vols finalitzar l'examen?</p>
            <button onclick="submitExam()">Sí</button>
            <button onclick="hideConfirm()">No</button>
        </div>
    </div>
    '''
    
    # Afegim la referència al fitxer JavaScript
    html += f'<script src="/static/js/confirm.js"></script>'    
    html += '<form id="quizForm" method="post">\n'
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
    html += f'<input type="hidden" name="current_page" value="{current_page}">'
    html += f'<p>Page {current_page} of {total_pages}</p>\n'
    
    if current_page > 1:
        html += f'<a href="{url_for("quiz", page=current_page-1)}">Previous</a> '
    
    if current_page < total_pages:
        html += f'<a href="{url_for("quiz", page=current_page+1)}">Next</a> '
    
    html += '<br><br><input type="button" onclick="showConfirm()" value="Finish Exam" />\n'
    html += '<input type="hidden" name="action" value="Finish Exam" />\n'
    html += '</form>\n'
    html += '</body></html>'
    return html

# ---------------------| Variables |------------------

header = load_cfg(f"static/theme/default/header.cfg")
# load theme
HEADER = f"<head>{header}</head>".replace("@THEME", THEME)
HEADER = HEADER.replace("@TITLE", TITLE)
BASE_HTML = f'<html>{HEADER}<body>\n'

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
    course = request.form.get('course')
    selected_exams = request.form.getlist('exam')
    if course and selected_exams:
        session['course'] = course
        session['selected_exams'] = selected_exams
        questions_answers = process_files(course, selected_exams)
        
        # Comprova si hi ha preguntes vàlides
        if not questions_answers:
            flash("No s'han trobat preguntes vàlides en els exàmens seleccionats.", "error")
            return redirect(url_for('index'))
        
        # Barreja les preguntes si és necessari
        random.shuffle(questions_answers)
        
        # Limita a EXAM_QUESTIONS si és necessari
        questions_answers = questions_answers[:EXAM_QUESTIONS]
        
        session['questions_answers'] = questions_answers
        session['user_answers'] = {f'question{i+1}': [] for i in range(len(questions_answers))}
        return redirect(url_for('quiz'))
    return redirect(url_for('index'))
@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if 'questions_answers' not in session:
        return redirect(url_for('index'))
    
    questions_answers = session['questions_answers']
    total_questions = len(questions_answers)
    
    if 'user_answers' not in session:
        session['user_answers'] = {}
    
    user_answers = session['user_answers']
    
    if request.method == 'POST':
        for key, value in request.form.items():
            if key.startswith('question'):
                question_number = int(key[8:])  # Extract the question number from the key
                if isinstance(value, list):
                    user_answers[question_number] = value
                else:
                    user_answers[question_number] = [value]
        
        session['user_answers'] = to_string_keys(session['user_answers'])
        session.modified = True
        
        if request.form.get('action') == 'Finish Exam':
            # Process all answers
            score = 0
            detailed_results = []
            
            for i, question in enumerate(questions_answers, 1):
                user_answer = user_answers.get(i, [])
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
            # Redirect to the next page
            current_page = int(request.form.get('current_page', 1))
            return redirect(url_for('quiz', page=current_page+1))
    
    current_page = request.args.get('page', 1, type=int)
    start = (current_page - 1) * QUESTIONS_PER_PAGE
    end = min(start + QUESTIONS_PER_PAGE, total_questions)
    page_questions = questions_answers[start:end]
    
    saved_answers = {i: user_answers.get(i, []) for i in range(start + 1, end + 1)}
    
    html = generate_quiz_html(page_questions, QUESTION_STYLE, current_page, total_questions, saved_answers)
    return render_template_string(html)

@app.route('/certificate_error')
def certificate_error():
    html=BASE_HTML
    html+="<p>La contrasenya proporcionada per al certificat és incorrecta.</p>"
    return render_template_string(html)

@app.route('/download_results')
def download_results():
    score = session.get('score')
    total_questions = session.get('total_questions')
    detailed_results = session.get('detailed_results')

    if not all([score, total_questions, detailed_results]):
        return redirect(url_for('pdfnotfound'))

    try:
        pdf_buffer = generate_pdf(score, total_questions, detailed_results)
        pdf_content = pdf_buffer.getvalue()
        
        # Try to sign, but use unsigned if no valid certificate
        signed_pdf = sign_pdf(pdf_content)
        
        filename = "exam_results_{}.pdf".format(datetime.now().strftime('%Y%m%d_%H%M%S'))
        if signed_pdf == pdf_content:
            filename = "unsigned_" + filename
        
        return send_file(
            io.BytesIO(signed_pdf),
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error generating or signing PDF: {str(e)}")
        return redirect(url_for('pdfnotfound'))
        
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        # Llegeix el contingut del fitxer config.py
        with open('config.py', 'r') as f:
            config_content = f.read()
        
        # Analitza el contingut com un arbre de sintaxi abstracta (AST)
        config_ast = ast.parse(config_content)
        
        # Recorre l'AST i actualitza els valors de les variables
        for node in ast.walk(config_ast):
            if isinstance(node, ast.Assign):
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id in request.form:
                    value = request.form[target.id]
                    if isinstance(node.value, ast.Num):
                        node.value.n = int(value)
                    elif isinstance(node.value, ast.Str):
                        node.value.s = value
        
        # Genera el codi font modificat a partir de l'AST
        modified_config = ast.unparse(config_ast)
        
        # Escriu el codi font modificat al fitxer config.py
        with open('config.py', 'w') as f:
            f.write(modified_config)
        
        # Recarrega el mòdul config
        importlib.reload(config)
        
        return redirect(url_for('admin'))

    # Obté totes les variables de configuració
    config_vars = {key: value for key, value in config.__dict__.items() if not key.startswith('__')}
    
    return render_template('admin.html', config_vars=config_vars)


@app.route('/pdfnotfound')
def pdfnotfound():
    html=add_redirect(BASE_HTML, '/', 2)
    html+="No exam results available"
      
    return render_template_string(html), 400

@app.route('/review', methods=['GET', 'POST'])
def review():
    if 'questions_answers' not in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Actualitzem les respostes si l'usuari les ha modificat
        for key, value in request.form.items():
            if key.startswith('question'):
                session['user_answers'][str(key)] = value if isinstance(value, list) else [value]
    
    questions_answers = session['questions_answers']
    user_answers = {str(k): v for k, v in session.get('user_answers', {}).items()}
    
    return render_template('review.html', 
                           questions=questions_answers, 
                           user_answers=user_answers)

@app.route('/submit')
def submit():
    if 'questions_answers' not in session or 'user_answers' not in session:
        return redirect(url_for('index'))
    
    questions_answers = session['questions_answers']
    user_answers = session['user_answers']
    
    score = 0
    total_questions = len(questions_answers)
    detailed_results = []
    
    for i, question in enumerate(questions_answers, 1):
        user_answer = set(user_answers.get(f'question{i}', []))
        correct_answers = set(question['correct'])
        is_correct = user_answer == correct_answers
        
        if is_correct:
            score += 1
        
        detailed_results.append({
            'question': question['question'],
            'user_answer': user_answer,
            'correct_answers': correct_answers,
            'is_correct': is_correct
        })
    
    session['score'] = score
    session['total_questions'] = total_questions
    session['detailed_results'] = detailed_results
    
    return redirect(url_for('results'))

@app.route('/results')
def results():
    if 'score' not in session or 'total_questions' not in session or 'detailed_results' not in session:
        return redirect(url_for('index'))
    
    score = session['score']
    total_questions = session['total_questions']
    detailed_results = session['detailed_results']
    
    # Netegem la sessió
    session.pop('questions_answers', None)
    session.pop('user_answers', None)
    session.pop('score', None)
    session.pop('total_questions', None)
    session.pop('detailed_results', None)
    
    return render_template('results.html', 
                           score=score, 
                           total_questions=total_questions, 
                           detailed_results=detailed_results)
def to_string_keys(d):
    if isinstance(d, dict):
        return {str(k): to_string_keys(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [to_string_keys(v) for v in d]
    else:
        return d    
if __name__ == '__main__':
    app.run(debug=True,port=5005)