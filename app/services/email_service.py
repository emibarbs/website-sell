import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app, url_for

def send_order_confirmation_email(to_email, customer_name, order_id, plan_name, amount):
    """
    Envía un correo electrónico de confirmación de pago al cliente mediante socket directo.
    """
    subject = f"¡Pago Confirmado! Orden {order_id} - Digital Agency"
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME')

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
    _send_via_socket(to_email, subject, html_body, sender)


def send_verification_email(user):
    """
    Envía el correo de verificación de cuenta de forma segura y evita bloqueos de red.
    """
    token = user.get_verification_token()
    verify_url = url_for('auth.verify_email', token=token, _external=True)

    subject = "Verifica tu cuenta - Digital Agency"
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME')

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
        _send_via_socket(user.email, subject, html_body, sender)
    except Exception as e:
        current_app.logger.error(f"Fallo envío de correo de verificación: {e}")
        print(f"\n[DEV] Enlace de verificación para {user.email}: {verify_url}\n", flush=True)
        raise e


def _send_via_socket(to_email, subject, html_body, sender):
    """
    Función interna que maneja la conexión SMTP nativa con timeout para evitar cuelgues en Railway.
    """
    server_host = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    server_port = int(current_app.config.get('MAIL_PORT', 587))
    username = current_app.config.get('MAIL_USERNAME')
    password = current_app.config.get('MAIL_PASSWORD')
    use_tls = current_app.config.get('MAIL_USE_TLS', True)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to_email
    msg.attach(MIMEText(html_body, 'html'))

    try:
        # Timeout estricto de 10s para liberar la app si la red de Railway rechaza el paquete
        if server_port == 465:
            smtp_server = smtplib.SMTP_SSL(server_host, server_port, timeout=10)
        else:
            smtp_server = smtplib.SMTP(server_host, server_port, timeout=10)
            if use_tls:
                smtp_server.starttls()

        smtp_server.login(username, password)
        smtp_server.sendmail(sender, [to_email], msg.as_string())
        smtp_server.quit()
    except Exception as ex:
        current_app.logger.error(f"Error crítico en socket SMTP hacia {to_email}: {str(ex)}")
        raise ex
