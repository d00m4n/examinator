from flask import Flask, render_template, redirect, url_for, request
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user

app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin):
    pass

# Aquesta funció verifica si l'usuari és un administrador
def is_admin(username):
    # Aquí pots comprovar si l'usuari és un administrador
    # Per exemple, pots tenir una llista d'usuaris administradors
    admin_users = ['admin1', 'admin2']
    return username in admin_users

@login_manager.user_loader
def user_loader(username):
    if not is_admin(username):
        return
    user = User()
    user.id = username
    return user

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    username = request.form['username']
    if is_admin(username):
        user = User()
        user.id = username
        login_user(user)
        return redirect(url_for('admin'))

    return 'Usuari no vàlid'

@app.route('/admin')
@login_required
def admin():
    return 'Pàgina d\'administració'

@app.route('/logout')
def logout():
    logout_user()
    return 'Has tancat la sessió'
