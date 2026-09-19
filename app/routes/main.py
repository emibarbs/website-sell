from datetime import datetime, timezone
from flask import Blueprint, render_template, Response, url_for
from app.models.setting import Setting

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Renderiza la página Home principal de la agencia digital."""
    return render_template('home.html')


@bp.route('/about')
def about():
    """Renderiza la página About Us de la agencia."""
    return render_template('about.html')


@bp.route('/how-it-works')
def how_it_works():
    """Renderiza la página explicativa How It Works."""
    return render_template('how_it_works.html')


@bp.route('/pricing')
def pricing():
    """Renderiza la página de precios leyendo los valores configurados en base de datos."""
    p1 = Setting.query.filter_by(key_name='plan1_price').first()
    p2 = Setting.query.filter_by(key_name='plan2_price').first()

    return render_template(
        'pricing.html',
        plan1_price=p1.key_value if p1 else '620',
        plan2_price=p2.key_value if p2 else '1100'
    )


@bp.route('/robots.txt')
def robots_txt():
    lines = [
        'User-agent: *',
        'Allow: /',
        f"Sitemap: {url_for('main.sitemap_xml', _external=True)}",
    ]
    return Response("\n".join(lines), mimetype='text/plain')


@bp.route('/sitemap.xml')
def sitemap_xml():
    pages = [
        url_for('main.index', _external=True),
        url_for('main.about', _external=True),
        url_for('main.how_it_works', _external=True),
        url_for('main.pricing', _external=True),
        url_for('auth.login', _external=True),
        url_for('auth.register', _external=True),
    ]
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    xml_items = "".join(
        f"<url><loc>{p}</loc><lastmod>{now}</lastmod></url>" for p in pages
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{xml_items}</urlset>'
    return Response(xml, mimetype='application/xml')
