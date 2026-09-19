import os
import random
from datetime import datetime, timezone
from flask import Flask, request, redirect, make_response, url_for
from config import Config
from app.extensions import db, migrate, login_manager, mail, socketio

MAX_AGENTS_ONLINE = 7


def agents_online_count():
    """Número de agentes 'en línea' determinístico por hora (cambia cada hora, a veces sube, a veces baja)."""
    now = datetime.now(timezone.utc)
    seed = now.year * 100000 + now.timetuple().tm_yday * 100 + now.hour
    return random.Random(seed).randint(1, MAX_AGENTS_ONLINE)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    socketio.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    # Importar todos los modelos para que SQLAlchemy los reconozca al crear las tablas
    from app.models import user, order, ticket, message, setting

    # Crear automáticamente las tablas si no existen (red de seguridad para primer arranque;
    # el esquema autoritativo vive en migrations/ vía `flask db upgrade`)
    with app.app_context():
        db.create_all()

    # Registrar los manejadores de eventos Socket.IO (chat en tiempo real + notificaciones admin)
    from app import sockets

    # Vigilante de tickets inactivos (cierra y borra chats sin respuesta del cliente tras 5 min).
    # Se evita duplicar el hilo cuando el reloader de Flask lanza el proceso monitor + el worker.
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        sockets.start_stale_ticket_watcher(app)

    # Diccionario global absoluto con todas las traducciones del sitio
    translations = {
        'en': {
            'home': 'Home', 'about': 'About Us', 'how': 'How It Works', 'pricing': 'Pricing',
            'login': 'Login', 'logout': 'Logout', 'admin': 'Admin Dashboard', 'client': 'Client Dashboard',
            'hero_title': 'The Web, Built for the Present',
            'hero_desc': 'We build websites, AI chatbots & apps that attract, engage, and convert.',
            'cta_pricing': 'View Pricing', 'cta_how': 'How It Works',
            'google_login': 'Continue with Google',
            'chat_welcome': "In a moment we'll be with you — we're finding an agent to help you.",
            'chat_login_req': 'Please Login to start messaging our team.',
            'chat_placeholder': 'Type a message...',
            'chat_disabled': 'Login required to chat...',
            'agents_online_label': 'agents online',
            # Pricing page
            'pricing_title': 'PRICING',
            'pricing_desc': 'Choose the ultimate web architecture or AI integration package for your business.',
            'plan_starter_title': 'Starter Web', 'plan_starter_desc': 'Perfect for professional portfolios and small business landing pages.',
            'plan_pro_title': 'Pro Agency AI', 'plan_pro_desc': 'Advanced web platforms with custom AI chatbot integration and high performance.',
            'plan_enterprise_title': 'Enterprise Suite', 'plan_enterprise_desc': 'Tailor-made scalable software architectures with dedicated 24/7 engineering.',
            'buy_now': 'Buy Now',
            'popular': 'Popular',
            'no_refund': 'No refund',
            'custom_quote_badge': 'Custom Quote',
            'custom_quote_title': 'Custom Quote',
            'talk_direct_chat': 'Talk with us (Direct Chat)',
            'purchase_warning_text': "Don't you want to talk with us first to make sure you are getting the exact plan you need?",
            'talk_first_btn': 'Talk with us first',
            'proceed_checkout_btn': 'Proceed to Direct Checkout',
            'cancel': 'Cancel',
            'support_plan_help': 'Hello! I want to make sure I am choosing the right plan for my project. Can you help me?',
            'support_plan3_help': "Hello! I want to hire Plan 3 (Custom Enterprise). Let's discuss a custom quote!",
            'orders_and_tickets': 'Orders & Tickets',
            'admin_panel': 'Admin Panel',
            'log_out': 'Log Out',
            # Plan 1 & 2 features
            'plan1_features': [
                '4 pages max',
                'We can add videos that you need',
                'Log in interactive buttons, dashboard, logo creation, colors',
                'Mail page where clients can send info to your email',
                '1 week and a half of work',
                'Good SEO',
                'Fully responsive (adjustable for mobile, PC, or any device)'
            ],
            'plan2_features': [
                'Everything in Plan 1',
                'Animations included',
                '7 pages max',
                'Payment method integration (or talk about other methods)',
                '1 on 1 chat with you + Admin page to check notifications',
                '1 week and a half of work',
                'Better SEO'
            ],
            'plan3_features': [
                'Anything you need',
                'Custom Apps',
                'AI Chatbots & self-learning Artificial Intelligence',
                'AI-powered websites that assist your clients',
                'Advanced system integrations',
                'And much more...'
            ],
            # How it works page
            'how_title': 'Our Working Process',
            'how_desc': 'Follow our 3 simple steps to get your high-end digital solution online.',
            # About us page
            'about_title': 'About Our Global Agency',
            'about_desc': 'We are a premier international software development agency delivering high-end digital solutions, custom AI systems, and scalable web architectures for clients worldwide.',
            'global_reach': 'Global Reach', 'global_reach_desc': 'We operate seamlessly across time zones, providing robust cloud infrastructure and remote development support to international markets.',
            'ai_apps': 'AI Chatbots & Apps', 'ai_apps_desc': 'We integrate intelligent conversational agents and high-performance web applications designed to attract, engage, and convert visitors.',
            'custom_arch': 'Custom Architecture', 'custom_arch_desc': 'From secure backend APIs in Python to interactive 3D interfaces with Three.js, we build tailor-made digital ecosystems.'
        },
        'es': {
            'home': 'Inicio', 'about': 'Sobre Nosotros', 'how': 'Cómo Funciona', 'pricing': 'Precios',
            'login': 'Iniciar Sesión', 'logout': 'Cerrar Sesión', 'admin': 'Panel Admin', 'client': 'Panel de Cliente',
            'hero_title': 'La Web, Construida para el Presente',
            'hero_desc': 'Construimos sitios web, chatbots de IA y aplicaciones que atraen, cautivan y convierten.',
            'cta_pricing': 'Ver Planes', 'cta_how': 'Cómo Funciona',
            'google_login': 'Continuar con Google',
            'chat_welcome': 'En un momento te atendemos, estamos buscando un agente para ayudarte.',
            'chat_login_req': 'Por favor inicia sesión para comenzar a chatear.',
            'chat_placeholder': 'Escribe un mensaje...',
            'chat_disabled': 'Se requiere iniciar sesión...',
            'agents_online_label': 'agentes en línea',
            # Pricing page
            'pricing_title': 'PRECIOS',
            'pricing_desc': 'Elige la arquitectura web o el paquete de integración de IA definitivo para tu negocio.',
            'plan_starter_title': 'Web Inicial', 'plan_starter_desc': 'Perfecto para portafolios profesionales y páginas de aterrizaje para pequeños negocios.',
            'plan_pro_title': 'Pro Agencia IA', 'plan_pro_desc': 'Plataformas web avanzadas con integración de chatbots de IA personalizados y alto rendimiento.',
            'plan_enterprise_title': 'Suite Empresarial', 'plan_enterprise_desc': 'Arquitecturas de software escalables a la medida con ingeniería dedicada 24/7.',
            'buy_now': 'Comprar Ahora',
            'popular': 'Popular',
            'no_refund': 'Sin reembolso',
            'custom_quote_badge': 'Cotización Personalizada',
            'custom_quote_title': 'Cotización Personalizada',
            'talk_direct_chat': 'Hablar con nosotros (Chat Directo)',
            'purchase_warning_text': '¿No quieres hablar con nosotros primero para saber si estás comprando el plan que necesitas?',
            'talk_first_btn': 'Hablar con nosotros primero',
            'proceed_checkout_btn': 'Continuar con la Compra Directa',
            'cancel': 'Cancelar',
            'support_plan_help': '¡Hola! Quiero asegurarme de elegir el plan correcto para mi proyecto. ¿Me ayudan?',
            'support_plan3_help': '¡Hola! Quiero contratar el Plan 3 (Cotización Personalizada). ¡Hablemos de los detalles!',
            'orders_and_tickets': 'Pedidos y Tickets',
            'admin_panel': 'Panel de Administración',
            'log_out': 'Cerrar Sesión',
            # Plan 1 & 2 features in Spanish
            'plan1_features': [
                'Máximo 4 páginas',
                'Podemos agregar los videos que necesites',
                'Botones interactivos de inicio de sesión, panel, creación de logotipos, colores',
                'Página de correo donde los clientes pueden enviar información a tu correo',
                '1 semana y media de trabajo',
                'Buen SEO',
                'Totalmente responsivo (ajustable para móvil, PC o cualquier dispositivo)'
            ],
            'plan2_features': [
                'Todo lo del Plan 1',
                'Animaciones incluidas',
                'Máximo 7 páginas',
                'Integración de métodos de pago (o consulta otros métodos)',
                'Chat 1 a 1 contigo + Página de administrador para revisar notificaciones',
                '1 semana y media de trabajo',
                'Mejor SEO'
            ],
            'plan3_features': [
                'Todo lo que necesites',
                'Aplicaciones Personalizadas',
                'Chatbots de IA e Inteligencia Artificial de autoaprendizaje',
                'Sitios web impulsados por IA que asisten a tus clientes',
                'Integraciones de sistemas avanzados',
                'Y mucho más...'
            ],
            # How it works page
            'how_title': 'Nuestro Proceso de Trabajo',
            'how_desc': 'Sigue nuestros 3 simples pasos para poner en marcha tu solución digital de alta gama.',
            # About us page
            'about_title': 'Sobre Nuestra Agencia Global',
            'about_desc': 'Somos una agencia internacional premier de desarrollo de software que ofrece soluciones digitales de alta gama, sistemas de IA personalizados y arquitecturas web escalables para clientes en todo el mundo.',
            'global_reach': 'Alcance Global', 'global_reach_desc': 'Operamos sin problemas a través de zonas horarias, proporcionando infraestructura en la nube robusta y soporte de desarrollo remoto a mercados internacionales.',
            'ai_apps': 'Chatbots y Apps de IA', 'ai_apps_desc': 'Integramos agentes conversacionales inteligentes y aplicaciones web de alto rendimiento diseñadas para atraer, cautivar y convertir visitantes.',
            'custom_arch': 'Arquitectura a la Medida', 'custom_arch_desc': 'Desde APIs seguras en Python hasta interfaces 3D interactivas con Three.js, construimos ecosistemas digitales hechos a la medida.'
        }
    }

    @app.context_processor
    def inject_lang_and_texts():
        lang = request.cookies.get('lang', 'en')
        if lang not in translations:
            lang = 'en'
        t = translations[lang]
        return dict(current_lang=lang, t=t, agents_online=agents_online_count())

    @app.route('/set-language/<lang>')
    def set_language(lang):
        if lang not in ['en', 'es']:
            lang = 'en'
        response = make_response(redirect(request.referrer or url_for('main.index')))
        response.set_cookie('lang', lang, max_age=60*60*24*365, path='/')
        return response

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    from app.routes.webhook import bp as webhook_bp
    app.register_blueprint(webhook_bp)
    from app.routes.client import bp as client_bp
    app.register_blueprint(client_bp)
    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp)
    from app.routes.payments import bp as payments_bp
    app.register_blueprint(payments_bp)

    return app
