from flask import Flask
from flask_cors import CORS
from auth.auth import auth_bp
from course.course import course_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(course_bp, url_prefix='/api')

if __name__ == '__main__':
    app.run(debug=True)
