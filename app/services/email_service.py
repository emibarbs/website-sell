from flask import current_app
from flask_mail import Message
from app.extensions import mail


def send_order_confirmation_email(to_email, customer_name, order_id, plan_name, amount):
    """
    Envía un correo electrónico de confirmación de pago al cliente.
    """
    subject = f"¡Pago Confirmado! Orden {order_id} - Digital Agency"
    sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    html_body = f"""
    <div style="font-family: Arial, sans-serif; background-color: #0A0A0C; color: #F3F4F6; padding: 20px; border-radius: 8px;">
        <h2 style="color: #10B981;">¡Gracias por tu compra, {customer_name}!</h2>
        <p>Hemos recibido exitosamente tu pago para el <strong>{plan_name}</strong>.</p>
        <div style="background-color: #121216; padding: 15px; border: 1px solid #27272A; border-radius: 6px; margin: 20px 0;">
            <p style="margin: 5px 0;"><strong>Order ID:</strong> {order_id}</p>
            <p style="margin: 5px 0;"><strong>Plan:</strong> {plan_name}</p>
            <p style="margin: 5px 0;"><strong>Monto Pagado:</strong> ${amount} USD</p>
            <p style="margin: 5px 0;"><strong>Estado:</strong> Pagado y Verificado</p>
        </div>
        <p>Próximos pasos: Ya hemos creado un ticket inicial en tu panel de cliente. Accede a tu cuenta para explicarnos los detalles, diseño y referencias de tu proyecto.</p>
        <p style="color: #9CA3AF; font-size: 12px; margin-top: 30px;">Digital Agency Solutions — Alcance Global</p>
    </div>
    """

    msg = Message(subject=subject, recipients=[to_email], sender=sender, html=html_body)

    try:
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"Error enviando correo: {e}")
        raise e


def send_verification_email(user):
    """
    Envía el correo de verificación de cuenta con un enlace único (válido 24 horas).
    """
    from flask import url_for

    token = user.get_verification_token()
    verify_url = url_for('auth.verify_email', token=token, _external=True)

    subject = "Verifica tu cuenta - Digital Agency"
    sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    html_body = f"""
    <div style="font-family: Arial, sans-serif; background-color: #0A0A0C; color: #F3F4F6; padding: 20px; border-radius: 8px;">
        <h2 style="color: #38BDF8;">¡Hola, {user.name}!</h2>
        <p>Gracias por registrarte en Digital Agency. Confirma tu cuenta haciendo clic aquí:</p>
        <p style="margin: 25px 0;">
            <a href="{verify_url}" style="background-color: #0066FF; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold;">Verificar mi cuenta</a>
        </p>
        <p style="color: #9CA3AF; font-size: 0.85rem;">Este enlace es válido por 24 horas. Si no creaste esta cuenta, ignora este correo.</p>
    </div>
    """

    msg = Message(subject=subject, recipients=[user.email], sender=sender, html=html_body)

    try:
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"Error enviando correo de verificacion: {e}")
        # Sin credenciales SMTP reales configuradas, imprime el enlace para poder
        # verificar la cuenta manualmente durante el desarrollo (no depende de app.debug,
        # que socketio.run() no siempre propaga a current_app.debug).
        print(f"\n[DEV] Enlace de verificacion para {user.email}: {verify_url}\n", flush=True)
