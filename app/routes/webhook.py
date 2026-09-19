from flask import Blueprint, request, jsonify, current_app
import stripe
from app.services.stripe_service import handle_checkout_session_completed

bp = Blueprint('webhook', __name__, url_prefix='/webhook')

@bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """
    Endpoint seguro para recibir notificaciones asíncronas (webhooks) de Stripe.
    Valida la firma criptográfica obligatoriamente.
    """
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    has_real_secret = webhook_secret and webhook_secret != 'whsec_tu_webhook_secret'

    if not has_real_secret and current_app.debug:
        # Modo de desarrollo local sin secreto de webhook configurado todavía.
        # Fuera de debug (producción) esto NUNCA se salta: sin firma válida no se procesa
        # el evento, para que nadie pueda falsificar pagos "completados" con una request falsa.
        event = request.json
    elif not has_real_secret:
        current_app.logger.error(
            "STRIPE_WEBHOOK_SECRET no está configurado en producción; rechazando webhook."
        )
        return jsonify({'error': 'Webhook not configured'}), 500
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            # Payload inválido
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError as e:
            # Firma inválida (intento de suplantación o error)
            return jsonify({'error': 'Invalid signature'}), 400

    # Manejar el evento de pago completado
    event_type = event.get('type')
    
    if event_type == 'checkout.session.completed':
        session = event.get('data', {}).get('object', {})
        try:
            handle_checkout_session_completed(session)
        except Exception as e:
            current_app.logger.error(f"Error procesando checkout session: {e}")
            return jsonify({'error': 'Internal server error'}), 500

    return jsonify({'status': 'success'}), 200
