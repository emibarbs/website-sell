import stripe
from flask import Blueprint, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.setting import Setting

bp = Blueprint('payments', __name__, url_prefix='/checkout')

PLAN_NAMES = {
    'plan1': 'Plan 1',
    'plan2': 'Plan 2',
}


@bp.route('/<plan_key>')
@login_required
def checkout(plan_key):
    if plan_key not in PLAN_NAMES:
        flash('Plan desconocido.')
        return redirect(url_for('main.pricing'))

    price_setting = Setting.query.filter_by(key_name=f'{plan_key}_stripe_price_id').first()
    if not price_setting or not price_setting.key_value:
        flash('Este plan aún no está disponible para pago directo. Por favor contáctanos por chat.')
        return redirect(url_for('main.pricing'))

    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

    try:
        session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[{'price': price_setting.key_value, 'quantity': 1}],
            customer_email=current_user.email,
            metadata={'plan_name': PLAN_NAMES[plan_key], 'user_id': str(current_user.id)},
            success_url=url_for('client.dashboard', checkout='success', _external=True),
            cancel_url=url_for('main.pricing', checkout='cancelled', _external=True),
        )
    except Exception as e:
        current_app.logger.error(f"Error creando sesión de Stripe Checkout: {e}")
        flash('No se pudo iniciar el pago en este momento. Intenta de nuevo o contáctanos por chat.')
        return redirect(url_for('main.pricing'))

    return redirect(session.url, code=303)
