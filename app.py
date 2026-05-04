import sys
import os
sys.path.insert(0, os.path.expanduser('~/.local/lib/python3.12/site-packages'))

from flask import Flask
from routes import api, web, graphics, processor_1d, dashboard

app = Flask(__name__)

app.jinja_env.cache = None

app.register_blueprint(api.bp)
app.register_blueprint(web.bp)
app.register_blueprint(graphics.bp)
app.register_blueprint(processor_1d.bp)
app.register_blueprint(dashboard.bp)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(debug=False, host="0.0.0.0", port=port)
