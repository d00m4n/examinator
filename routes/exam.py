import os
import random

from flask import Blueprint, request, redirect, url_for, render_template
# import globals from main app
from flask import g , session,flash
from typing import List, Dict, Any

from config import EXAMS_FOLDER
# from config import TITLE
# from config import THEME
from datetime import datetime
current_year = datetime.now().year

selexam_bp = Blueprint('select_exam', __name__)
@selexam_bp.route('/select_exam', methods=['GET', 'POST'])
def select_topic():
    if request.method == 'POST':
        selected_topic = request.form.get('course')
        if selected_topic:
            files = get_exam_files(selected_topic)
            return render_template('select_exam.html',files=files)        
    return redirect(url_for('index.index'))

def get_exam_files(course):
    """
    Returns a list of exam files for a specific course.
    """
    
    syllabus_path = os.path.join(g.EXAMS, course)
    print("Course path: " + syllabus_path)
    return [f for f in os.listdir(syllabus_path) if f.endswith('.md')]

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
