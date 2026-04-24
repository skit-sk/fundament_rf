from flask import Flask
from routes import api, web, graphics

app = Flask(__name__)

app.register_blueprint(api.bp)
app.register_blueprint(web.bp)
app.register_blueprint(graphics.bp)


if __name__ == '__main__':
    app.run(debug=False, host='172.18.0.2', port=5000)
