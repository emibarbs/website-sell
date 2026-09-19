from datetime import datetime
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from app.extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), default='Client')  # 'Admin' o 'Client'
    oauth_provider = db.Column(db.String(50), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    orders = db.relationship('Order', back_populates='customer', lazy=True, foreign_keys='Order.customer_id')
    tickets = db.relationship('Ticket', back_populates='user', lazy=True, foreign_keys='Ticket.user_id')

    ROLE_ADMIN = 'Admin'
    ROLE_CLIENT = 'Client'

    @property
    def is_admin(self):
        return self.role == User.ROLE_ADMIN

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def apply_admin_bootstrap(self):
        """Promueve a Admin si el correo está en ADMIN_EMAILS (config). Devuelve True si cambió el rol."""
        admin_emails = current_app.config.get('ADMIN_EMAILS', set())
        if self.email and self.email.lower() in admin_emails and self.role != User.ROLE_ADMIN:
            self.role = User.ROLE_ADMIN
            return True
        return False

    def get_verification_token(self):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(self.email, salt='email-verify')

    @staticmethod
    def verify_token(token, max_age=86400):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = s.loads(token, salt='email-verify', max_age=max_age)
        except Exception:
            return None
        return User.query.filter_by(email=email).first()

    def __repr__(self):
        return f'<User {self.email} - Role: {self.role}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
