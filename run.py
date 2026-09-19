import os
from app import create_app
from app.extensions import socketio, db

app = create_app()

# Crear tablas en la base de datos automáticamente si no existen
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # PORT es asignado dinámicamente por Railway en producción
    port = int(os.environ.get('PORT', 5000))
    # Para producción, escucha en 0.0.0.0
    host = os.environ.get('HOST', '0.0.0.0')
    socketio.run(app, debug=False, host=host, port=port, allow_unsafe_werkzeug=True)
