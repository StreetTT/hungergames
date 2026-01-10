from flask import Flask, render_template, request
from .utils import *

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')

    # Register Blueprints
    from .routes import root
    from .api import api_bp
    
    app.register_blueprint(root)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Handle Error Automatically
    def handle_error(error):
        """
        Universal error handler.
        Returns JSON for API requests, HTML for browser requests.
        """
        # Determine status code
        code = getattr(error, 'code', 500)
        
        # Check if request wants JSON (API) or HTML (Browser)
        if request.path.startswith('/api/') or request.headers.get('Accept') == 'application/json':
            return error_response(str(error), code)
        
        # Default to HTML error page
        return render_template('error.html', error=error, code=code), code

    # Register for common HTTP errors
    for code in [400, 404, 405, 500]:
        app.register_error_handler(code, handle_error)
        
    # Catch-all for generic exceptions
    app.register_error_handler(Exception, handle_error)

    return app