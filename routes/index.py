from flask import Blueprint, render_template, session,g
from config import EXAMS_FOLDER
from config import THEME
from config import APP_NAME
# from config import TITLE

import os
index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    # Obtenim la llista de cursos disponibles
    courses = get_available_courses()
    
    # Netegem la sessió per si hi hagués dades d'exàmens anteriors
    session.clear()
    options={
        "courses": courses,
        # "year": g.YEAR,
        "theme": THEME,
        "app_name": APP_NAME,
        # "title": TITLE        
        }
    return render_template('index.html',**options)

def get_available_courses():
    """
    Obté la llista de cursos disponibles basant-se en els directoris dins de EXAMS_FOLDER
    """
    try:
        return [d for d in os.listdir(EXAMS_FOLDER) if os.path.isdir(os.path.join(EXAMS_FOLDER, d))]
    except FileNotFoundError:
        print(f"Error: El directori {EXAMS_FOLDER} no existeix.")
        return []
    except PermissionError:
        print(f"Error: No tens permís per accedir al directori {EXAMS_FOLDER}.")
        return []