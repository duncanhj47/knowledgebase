from werkzeug.middleware.proxy_fix import ProxyFix
from webapp import create_app

app = create_app()
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

if __name__ == '__main__':
    app.run(debug=True)
