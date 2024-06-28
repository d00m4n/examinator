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
from config import THEME
from config import TITLE

app = Flask(__name__)
app.secret_key = 'una_clau_secreta_molt_segura'

ESTIL_PREGUNTA = 'h3'

def load_cfg(filename):
    '''
    load config file
    '''
    with open(filename, 'r', encoding="utf-8") as f:
        cfg = f.read()
    return cfg
header=load_cfg(f"./static/theme/{THEME}/header.cfg")
# load theme
HEADER=f"<head>{header}</head>".replace("@THEME",THEME)
HEADER=HEADER.replace("@TITLE",TITLE)

def get_syllabus(folder):
    '''
        scan folder for exam syllabus
    '''
    return [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]

def obtenir_fitxers_examen(tema):
    ruta_tema = os.path.join(EXAMS_FOLDER, tema)
    return [f for f in os.listdir(ruta_tema) if f.endswith('.md')]

def processar_fitxer(tema, nom_fitxer):
    ruta_completa = os.path.join(EXAMS_FOLDER, tema, nom_fitxer)
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
    html = f'<html>{HEADER}<body>\n'
    html += '<h2>Selecciona un tema:</h2>\n'
    html += '<form method="post" action="/seleccionar_tema">\n'
    for tema in temes:
        html += f'<input type="radio" name="tema" value="{tema}">{tema}<br>\n'
    html += '<br><input type="submit" value="Seleccionar Tema">\n'
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
    html += '<br><input type="submit" value="Començar Examen">\n'
    html += '</form>\n'
    html += '</body></html>'
    return html

def generar_html(preguntes_respostes, estil_pregunta, pagina_actual, total_preguntes, respostes_guardades):
    html = '<html><body>\n'
    html += '<form method="post">\n'
    
    offset = (pagina_actual - 1) * QUESTIONS_PER_PAGE
    
    for i, pregunta in enumerate(preguntes_respostes, offset + 1):
        html += f"<{estil_pregunta}>{i}. {pregunta['pregunta']}</{estil_pregunta}>\n"
        clau = f'pregunta{i}'
        respostes_usuari = respostes_guardades.get(clau, [])
        
        if len(pregunta['correctes']) == 1 and len(pregunta['respostes']) == 1:
            valor = respostes_usuari[0] if respostes_usuari else ""
            html += f'<input type="text" name="{clau}" value="{valor}" />\n'
        elif len(pregunta['correctes']) == 1:
            for resposta in pregunta['respostes']:
                checked = 'checked' if resposta in respostes_usuari else ''
                html += f'<input type="radio" name="{clau}" value="{resposta}" {checked}>{resposta}<br/>\n'
        else:
            for resposta in pregunta['respostes']:
                checked = 'checked' if resposta in respostes_usuari else ''
                html += f'<input type="checkbox" name="{clau}" value="{resposta}" {checked}>{resposta}<br/>\n'
    
    # Afegim controls de paginació
    total_pagines = (total_preguntes + QUESTIONS_PER_PAGE - 1) // QUESTIONS_PER_PAGE
    html += f'<p>Pàgina {pagina_actual} de {total_pagines}</p>\n'
    
    if pagina_actual > 1:
        html += f'<a href="{url_for("quiz", pagina=pagina_actual-1)}">Anterior</a> '
    
    if pagina_actual < total_pagines:
        html += f'<a href="{url_for("quiz", pagina=pagina_actual+1)}">Següent</a> '
    
    html += '<br><br><input type="submit" name="action" value="Finalitzar Examen" />\n'
    html += '</form>\n'
    html += '</body></html>'
    return html

def generar_html_resultats(puntuacio, total_preguntes, resultats_detallats):
    percentatge = (puntuacio / total_preguntes) * 100
    
    html = f'<h1>La teva puntuació és: {puntuacio} de {total_preguntes} ({percentatge:.2f}%)</h1>'
    html += '<h2>Respostes detallades:</h2>'
    for i, resultat in enumerate(resultats_detallats, 1):
        html += f"<{ESTIL_PREGUNTA}>{i}. {resultat['pregunta']}</{ESTIL_PREGUNTA}>"
        
        # Mostrem la resposta de l'usuari
        if isinstance(resultat['resposta_usuari'], list):
            resposta_usuari = ', '.join(resultat['resposta_usuari']) if resultat['resposta_usuari'] else "Cap resposta seleccionada"
        else:
            resposta_usuari = resultat['resposta_usuari'] if resultat['resposta_usuari'] else "Cap resposta introduïda"
        html += f"<p>La teva resposta: {resposta_usuari}</p>"
        
        # Mostrem la resposta correcta
        html += f"<p>Resposta correcta: {', '.join(resultat['respostes_correctes'])}</p>"
        
        # Indiquem si és correcta o incorrecta
        html += f"<p>{'Correcta' if resultat['es_correcta'] else 'Incorrecta'}</p>"
        html += "<hr>"
    
    html += '<form method="get" action="/">'
    html += '<input type="submit" value="Nou Examen" />'
    html += '</form>'
    
    return html
@app.route('/')
def index():
    temes = get_syllabus(EXAMS_FOLDER)
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
        preguntes_respostes = processar_fitxer(tema, examen_seleccionat)
        session['preguntes_respostes'] = preguntes_respostes
        session['respostes_usuari'] = {f'pregunta{i+1}': [] for i in range(len(preguntes_respostes))}
        return redirect(url_for('quiz'))
    return redirect(url_for('index'))

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if 'preguntes_respostes' not in session:
        return redirect(url_for('index'))
    
    preguntes_respostes = session['preguntes_respostes']
    total_preguntes = len(preguntes_respostes)
    
    # Inicialitzem les respostes de l'usuari si no existeixen
    if 'respostes_usuari' not in session:
        session['respostes_usuari'] = {f'pregunta{i+1}': [] for i in range(total_preguntes)}
    
    # Obtenim la pàgina actual
    pagina_actual = request.args.get('pagina', 1, type=int)
    
    # Calculem l'índex d'inici i final per a la pàgina actual
    inici = (pagina_actual - 1) * QUESTIONS_PER_PAGE
    final = min(inici + QUESTIONS_PER_PAGE, total_preguntes)
    
    # Obtenim les preguntes per a la pàgina actual
    preguntes_pagina = preguntes_respostes[inici:final]
    
    if request.method == 'POST':
        # Guardem les respostes de la pàgina actual
        respostes_usuari = session['respostes_usuari']
        for i in range(inici + 1, final + 1):
            clau = f'pregunta{i}'
            if clau in request.form:
                respostes_usuari[clau] = request.form.getlist(clau)
            elif clau not in respostes_usuari:
                respostes_usuari[clau] = []
        
        session['respostes_usuari'] = respostes_usuari
        session.modified = True
        
        if request.form.get('action') == 'Finalitzar Examen':
            # Processem totes les respostes
            puntuacio = 0
            resultats_detallats = []
            
            for i, pregunta in enumerate(preguntes_respostes, 1):
                clau = f'pregunta{i}'
                resposta_usuari = respostes_usuari.get(clau, [])
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
            
            # Netegem les respostes de la sessió
            session.pop('respostes_usuari', None)
            session.pop('preguntes_respostes', None)
            
            # Generem i retornem els resultats
            return generar_html_resultats(puntuacio, total_preguntes, resultats_detallats)
        else:
            # Si no s'ha finalitzat l'examen, redirigim a la següent pàgina
            return redirect(url_for('quiz', pagina=pagina_actual+1))
    
    # Recuperem les respostes guardades per a aquesta pàgina
    respostes_guardades = {k: v for k, v in session['respostes_usuari'].items() if int(k[8:]) > inici and int(k[8:]) <= final}
    
    html = generar_html(preguntes_pagina, ESTIL_PREGUNTA, pagina_actual, total_preguntes, respostes_guardades)
    return render_template_string(html)

if __name__ == '__main__':
    app.run(debug=True)