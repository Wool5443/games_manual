from authlib.integrations.flask_client import OAuth
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DISCOVERY_URL


oauth = OAuth()


def init_extensions(app: Flask) -> None:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    oauth.init_app(app)

    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
        oauth.register(
            name="google",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            server_metadata_url=GOOGLE_DISCOVERY_URL,
            client_kwargs={"scope": "openid email profile"},
        )
