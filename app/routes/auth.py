from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required
from authlib.integrations.flask_client import OAuth
from app.models.user import User
from app.extensions import db
from app.services.email_service import send_verification_email

bp = Blueprint('auth', __name__, url_prefix='/auth')
oauth = OAuth()

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Correo o contraseña incorrectos.')
            return render_template('auth/login.html')

        if not user.is_verified:
            flash('Tu cuenta aún no está verificada. Revisa tu correo.')
            return render_template('auth/login.html', unverified_email=user.email)

        user.apply_admin_bootstrap()
        user.last_login = datetime.utcnow()
        db.session.commit()

        login_user(user)
        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('main.index'))

    return render_template('auth/login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Ese correo ya está registrado.')
            return render_template('auth/register.html')

        new_user = User(name=name, email=email, role='Client', is_verified=False)
        new_user.set_password(password)
        new_user.apply_admin_bootstrap()
        db.session.add(new_user)
        db.session.commit()

        send_verification_email(new_user)
        flash('¡Cuenta creada! Te enviamos un correo para verificar tu cuenta antes de iniciar sesión.')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@bp.route('/verify/<token>')
def verify_email(token):
    user = User.verify_token(token)
    if not user:
        flash('El enlace de verificación no es válido o ya expiró.')
        return redirect(url_for('auth.login'))

    if not user.is_verified:
        user.is_verified = True
    user.apply_admin_bootstrap()
    user.last_login = datetime.utcnow()
    db.session.commit()

    login_user(user)
    flash('¡Tu cuenta fue verificada correctamente!')
    return redirect(url_for('main.index'))

@bp.route('/resend-verification/<email>')
def resend_verification(email):
    user = User.query.filter_by(email=email).first()
    if user and not user.is_verified:
        send_verification_email(user)
        flash('Te reenviamos el correo de verificación.')
    return redirect(url_for('auth.login'))

@bp.route('/google-login')
def google_login():
    if not current_app.config.get('GOOGLE_CLIENT_ID') or not current_app.config.get('GOOGLE_CLIENT_SECRET'):
        flash('Credenciales de Google OAuth no configuradas en el entorno.')
        return redirect(url_for('auth.login'))
    
    if not oauth._registry:
        oauth.init_app(current_app)
        oauth.register(
            name='google',
            client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
            client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET'),
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
    
    google = oauth.create_client('google')
    redirect_uri = url_for('auth.google_authorized', _external=True)
    return google.authorize_redirect(redirect_uri)

@bp.route('/google-callback')
def google_authorized():
    if not oauth._registry:
        oauth.init_app(current_app)

    google = oauth.create_client('google')
    try:
        token = google.authorize_access_token()
        resp = google.get('https://www.googleapis.com/oauth2/v3/userinfo')
        user_info = resp.json()
    except Exception as e:
        flash(f'Error en la autenticación con Google: {str(e)}')
        return redirect(url_for('auth.login'))

    email = user_info.get('email')
    name = user_info.get('name', 'Google User')

    if not email:
        flash('No se pudo obtener el correo electrónico de Google.')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            name=name, 
            email=email, 
            role='Client', 
            oauth_provider='google', 
            is_verified=True
        )
        db.session.add(user)
        db.session.commit()
    else:
        if not user.is_verified:
            user.is_verified = True

    user.apply_admin_bootstrap()
    user.last_login = datetime.utcnow()
    db.session.commit()

    login_user(user)
    flash('Successfully logged in with Google!')

    next_url = request.args.get('next')
    if next_url:
        return redirect(next_url)
    return redirect(url_for('main.index'))

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))
