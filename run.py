import os
from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == '__main__':
    # Ejecutar la aplicación usando SocketIO para soportar tiempo real
    # PORT es opcional (usado por algunos hosts/herramientas); por defecto usa 5000.
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, debug=True, host='127.0.0.1', port=port, allow_unsafe_werkzeug=True)
