import requests
from flask import current_app, url_for

def send_order_confirmation_email(to_email, customer_name, order_id, plan_name, amount):
    """
    Envía un correo de confirmación de pago mediante la API HTTP de Resend.
    """
    subject = f"¡Pago Confirmado! Orden {order_id} - Digital Agency"

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
    _send_via_resend(to_email, subject, html_body)


def send_verification_email(user):
    """
    Envía el correo de verificación de cuenta mediante la API HTTP de Resend.
    """
    token = user.get_verification_token()
    verify_url = url_for('auth.verify_email', token=token, _external=True)

    subject = "Verifica tu cuenta - Digital Agency"

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

    try:
        _send_via_resend(user.email, subject, html_body)
    except Exception as e:
        current_app.logger.error(f"Fallo envío de correo mediante Resend: {e}")
        print(f"\n[DEV] Enlace de verificación para {user.email}: {verify_url}\n", flush=True)
        raise e


def _send_via_resend(to_email, subject, html_body):
    """
    Función interna que realiza la petición HTTP POST hacia la API de Resend.
    """
    api_key = current_app.config.get('RESEND_API_KEY')
    
    if not api_key:
        raise Exception("Falta configurar la variable RESEND_API_KEY en el entorno de Railway.")

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Digital Agency <noreply@sitelanza.com>",
            "to": [to_email],
            "subject": subject,
            "html": html_body
        },
        timeout=15
    )

    if response.status_code != 200:
        error_msg = response.text
        current_app.logger.error(f"Resend API Error: {error_msg}")
        raise Exception(f"Error enviando correo con Resend: {error_msg}")
