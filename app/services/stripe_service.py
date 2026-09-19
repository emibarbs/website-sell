import stripe
from flask import current_app
from app.extensions import db, socketio
from app.models.order import Order, generate_order_id
from app.models.user import User
from app.models.ticket import Ticket
from app.models.setting import Setting
from app.services.email_service import send_order_confirmation_email


def sync_plan_price(plan_key, plan_display_name, new_price_usd):
    """
    Crea (o reutiliza) el Product de Stripe para el plan, crea un nuevo Price con el
    monto indicado, desactiva el Price anterior y persiste todo en Setting.
    Devuelve el nuevo Stripe Price ID. Lanza excepción si Stripe falla.
    """
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

    product_setting = Setting.query.filter_by(key_name=f'{plan_key}_stripe_product_id').first()
    if product_setting and product_setting.key_value:
        product_id = product_setting.key_value
    else:
        product = stripe.Product.create(name=plan_display_name)
        product_id = product.id
        if product_setting:
            product_setting.key_value = product_id
        else:
            db.session.add(Setting(key_name=f'{plan_key}_stripe_product_id', key_value=product_id))

    new_price = stripe.Price.create(
        product=product_id,
        unit_amount=int(round(float(new_price_usd) * 100)),
        currency='usd',
    )

    price_id_setting = Setting.query.filter_by(key_name=f'{plan_key}_stripe_price_id').first()
    if price_id_setting and price_id_setting.key_value and price_id_setting.key_value != new_price.id:
        try:
            stripe.Price.modify(price_id_setting.key_value, active=False)
        except Exception as e:
            current_app.logger.warning(f"No se pudo desactivar el precio anterior de Stripe: {e}")

    if price_id_setting:
        price_id_setting.key_value = new_price.id
    else:
        db.session.add(Setting(key_name=f'{plan_key}_stripe_price_id', key_value=new_price.id))

    display_setting = Setting.query.filter_by(key_name=f'{plan_key}_price').first()
    if display_setting:
        display_setting.key_value = str(new_price_usd)
    else:
        db.session.add(Setting(key_name=f'{plan_key}_price', key_value=str(new_price_usd)))

    db.session.commit()
    return new_price.id


def handle_checkout_session_completed(session):
    """
    Procesa el evento checkout.session.completed enviado por Stripe de forma segura.
    Registra la orden en la base de datos, crea el ticket inicial, notifica al panel
    de administración en tiempo real y envía el email de confirmación.
    """
    session_id = session.get('id')
    payment_intent_id = session.get('payment_intent')
    customer_details = session.get('customer_details') or {}
    customer_email = customer_details.get('email') or session.get('customer_email')
    customer_name = customer_details.get('name') or 'Cliente'
    amount_total = (session.get('amount_total') or 0) / 100.0
    currency = session.get('currency', 'usd')
    metadata = session.get('metadata') or {}
    plan_name = metadata.get('plan_name') or ('Plan 1' if amount_total < 1000 else 'Plan 2')

    # Verificar si la orden ya existe para evitar duplicados (Stripe puede reenviar webhooks)
    existing_order = Order.query.filter_by(stripe_session_id=session_id).first()
    if existing_order:
        return True

    # Preferir el usuario autenticado que inició el checkout (metadata.user_id); si no, buscar/crear por email
    user = None
    user_id = metadata.get('user_id')
    if user_id:
        user = User.query.get(int(user_id))
    if not user and customer_email:
        user = User.query.filter_by(email=customer_email).first()
    if not user:
        user = User(
            name=customer_name,
            email=customer_email,
            role='Client',
            oauth_provider='stripe',
            is_verified=True,
        )
        db.session.add(user)
        db.session.commit()

    new_order = Order(
        order_id=generate_order_id(),
        stripe_session_id=session_id,
        stripe_payment_intent_id=payment_intent_id,
        customer_id=user.id,
        plan_name=plan_name,
        amount=amount_total,
        currency=currency,
        status='paid',
    )
    db.session.add(new_order)
    db.session.flush()

    # Crear automáticamente un ticket inicial para el cliente tras la compra
    new_ticket = Ticket(
        subject=f"Proyecto Web - {plan_name} ({new_order.order_id})",
        description=(
            f"Gracias por adquirir tu {plan_name}. Orden {new_order.order_id} confirmada "
            f"por ${amount_total:.2f} {currency.upper()}. Por favor detalla aquí tus requisitos, "
            f"diseño y referencias para comenzar tu proyecto."
        ),
        status='Open',
        user_id=user.id,
    )
    db.session.add(new_ticket)
    db.session.commit()

    # Notificar en tiempo real al panel de administración (badge + sonido de nuevo pedido)
    try:
        socketio.emit('new_order', {
            'order_id': new_order.order_id,
            'ticket_id': new_ticket.id,
            'plan_name': plan_name,
            'amount': amount_total,
            'currency': currency,
            'customer_name': user.name,
        }, room='admin_notifications')
    except Exception as e:
        current_app.logger.error(f"Error emitiendo notificación de nuevo pedido: {e}")

    # Enviar correo electrónico de confirmación
    try:
        send_order_confirmation_email(user.email, user.name, new_order.order_id, plan_name, amount_total)
    except Exception as e:
        current_app.logger.error(f"Error al enviar email de confirmación: {e}")

    return True
