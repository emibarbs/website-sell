import uuid
from app.extensions import db
from datetime import datetime


def generate_order_id():
    return f"ORD-{uuid.uuid4().hex[:8].upper()}"


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(100), unique=True, nullable=False, default=generate_order_id)
    stripe_session_id = db.Column(db.String(255), unique=True, nullable=True)
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='usd')
    status = db.Column(db.String(50), default='paid')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('User', back_populates='orders')

    def __repr__(self):
        return f'<Order {self.order_id} - {self.plan_name} - ${self.amount}>'
