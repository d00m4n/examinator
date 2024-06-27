# Base imports
import random
import re
import os

# external imports
from flask import Flask, render_template_string, request, session, redirect, url_for

# custom imports
from config import EXAMS_FOLDER
from config import EXAM_QUESTIONS
from config import QUESTIONS_PER_PAGE

app = Flask(__name__)
app.secret_key = 'una_clau_secreta_molt_segura'

ESTIL_PREGUNTA = 'h3'


def get_syllabus(folder):
    '''
        scan folder for exam syllabus
    '''
    return [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]

def obtenir_fitxers_examen(tema):
    ruta_tema = os.path.join(CARPETA_EXAMS, tema)
    return [f for f in os.listdir(ruta_tema) if f.endswith('.md')]

def processar_fitxer(tema, nom_fitxer):
    ruta_completa = os.path.join(CARPETA_EXAMS, tema, nom_fitxer)
    with open(ruta_completa, 'r', encoding='utf-8') as fitxer:
        linies = fitxer.readlines()

    preguntes_respostes = []
    pregunta_actual = {'pregunta': '', 'respostes': [], 'correctes': []}
    for linia in linies:
        linia = linia.strip()
        linia = re.sub(r'\[\[(.*?)\]\]', r'\1', linia)
        linia = re.sub(r'`(.*?)`', r'<code>\1</code>', linia)
        if linia.startswith('####'):
            if pregunta_actual['pregunta']:
                preguntes_respostes.append(pregunta_actual)
                pregunta_actual = {'pregunta': '', 'respostes': [], 'correctes': []}
            pregunta_actual['pregunta'] += linia[4:] + ' '
        elif linia.startswith('+'):
            resposta = linia[1:].strip()
            es_correcta = '**' in resposta
            resposta = resposta.replace('**', '')
            pregunta_actual['respostes'].append(resposta)
            if es_correcta:
                pregunta_actual['correctes'].append(resposta)

    if pregunta_actual['pregunta']:
        preguntes_respostes.append(pregunta_actual)
    
    random.shuffle(preguntes_respostes)
    return preguntes_respostes[:EXAM_QUESTIONS]

def generar_html_seleccio_tema(temes):
    html = '<html><body>\n'
    html += '<h2>Selecciona un tema:</h2>\n'
    html += '<form method="post" action="/seleccionar_tema">\n'
    for tema in temes:
        html += f'<input type="radio" name="tema" value="{tema}">{tema}<br>\n'
    html += '<input type="submit" value="Seleccionar Tema">\n'
    html += '</form>\n'
    html += '</body></html>'
    return html

def generar_html_seleccio_examen(tema, fitxers):
    html = '<html><body>\n'
    html += f'<h2>Tema: {tema}</h2>\n'
    html += '<h3>Selecciona un examen:</h3>\n'
    html += '<form method="post" action="/seleccionar_examen">\n'
    for fitxer in fitxers:
        html += f'<input type="radio" name="examen" value="{fitxer}">{fitxer}<br>\n'
    html += f'<input type="hidden" name="tema" value="{tema}">\n'
    html += '<input type="submit" value="Començar Examen">\n'
    html += '</form>\n'
    html += '</body></html>'
    return html

def generar_html(preguntes_respostes, estil_pregunta):
    html = '<html><body>\n'
    html += '<form method="post">\n'
    for i, pregunta in enumerate(preguntes_respostes, 1):
        html += f"<{estil_pregunta}>{i}. {pregunta['pregunta']}</{estil_pregunta}>\n"
        if len(pregunta['correctes']) == 1 and len(pregunta['respostes']) == 1:
            html += f'<input type="text" name="pregunta{i}" />\n'
        elif len(pregunta['correctes']) == 1:
            for resposta in pregunta['respostes']:
                html += f'<input type="radio" name="pregunta{i}" value="{resposta}">{resposta}<br/>\n'
        else:
            for resposta in pregunta['respostes']:
                html += f'<input type="checkbox" name="pregunta{i}" value="{resposta}">{resposta}<br/>\n'
    html += '<input type="submit" name="action" value="Finalitzar Examen" />\n'
    html += '</form>\n'
    html += '</body></html>'
    return html

@app.route('/')
def index():
    temes = get_syllabus(CARPETA_EXAMS)
    return render_template_string(generar_html_seleccio_tema(temes))

@app.route('/seleccionar_tema', methods=['POST'])
def seleccionar_tema():
    tema_seleccionat = request.form.get('tema')
    if tema_seleccionat:
        fitxers = obtenir_fitxers_examen(tema_seleccionat)
        return render_template_string(generar_html_seleccio_examen(tema_seleccionat, fitxers))
    return redirect(url_for('index'))

@app.route('/seleccionar_examen', methods=['POST'])
def seleccionar_examen():
    tema = request.form.get('tema')
    examen_seleccionat = request.form.get('examen')
    if tema and examen_seleccionat:
        session['tema'] = tema
        session['examen_seleccionat'] = examen_seleccionat
        session['preguntes_respostes'] = processar_fitxer(tema, examen_seleccionat)
        return redirect(url_for('quiz'))
    return redirect(url_for('index'))

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if 'preguntes_respostes' not in session:
        return redirect(url_for('index'))
    
    preguntes_respostes = session['preguntes_respostes']
    
    if request.method == 'POST' and request.form.get('action') == 'Finalitzar Examen':
        respostes_usuari = request.form
        puntuacio = 0
        resultats_detallats = []
        
        for i, pregunta in enumerate(preguntes_respostes, 1):
            clau = f'pregunta{i}'
            resposta_usuari = respostes_usuari.getlist(clau)
            respostes_correctes = set(pregunta['correctes'])
            es_correcta = False
            
            if len(pregunta['correctes']) == 1 and len(pregunta['respostes']) == 1:
                resposta_usuari = resposta_usuari[0] if resposta_usuari else ""
                es_correcta = resposta_usuari.lower() == pregunta['correctes'][0].lower()
            elif len(pregunta['correctes']) == 1:
                resposta_usuari = resposta_usuari[0] if resposta_usuari else ""
                es_correcta = resposta_usuari in respostes_correctes
            else:
                es_correcta = set(resposta_usuari) == respostes_correctes
            
            if es_correcta:
                puntuacio += 1
            
            resultats_detallats.append({
                'pregunta': pregunta['pregunta'],
                'resposta_usuari': resposta_usuari,
                'respostes_correctes': pregunta['correctes'],
                'es_correcta': es_correcta
            })
        
        total_preguntes = len(preguntes_respostes)
        percentatge = (puntuacio / total_preguntes) * 100
        
        html_resultats = f'<h1>La teva puntuació és: {puntuacio} de {total_preguntes} ({percentatge:.2f}%)</h1>'
        html_resultats += '<h2>Respostes detallades:</h2>'
        for i, resultat in enumerate(resultats_detallats, 1):
            html_resultats += f"<{ESTIL_PREGUNTA}>{i}. {resultat['pregunta']}</{ESTIL_PREGUNTA}>"
            html_resultats += f"<p>La teva resposta: {', '.join(resultat['resposta_usuari']) if isinstance(resultat['resposta_usuari'], list) else resultat['resposta_usuari']}</p>"
            html_resultats += f"<p>Resposta correcta: {', '.join(resultat['respostes_correctes'])}</p>"
            html_resultats += f"<p>{'Correcta' if resultat['es_correcta'] else 'Incorrecta'}</p>"
            html_resultats += "<hr>"
        
        html_resultats += '<form method="get" action="/">'
        html_resultats += '<input type="submit" value="Nou Examen" />'
        html_resultats += '</form>'
        
        return html_resultats
    else:
        html = generar_html(preguntes_respostes, ESTIL_PREGUNTA)
        return render_template_string(html)

if __name__ == '__main__':
    app.run(debug=True)