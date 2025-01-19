from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
from models import User, session 
import jwt
from config import Config
from flask_cors import CORS  # Import CORS

# Create Blueprint for auth
auth_bp = Blueprint('auth', __name__)

# Enable CORS only for the login route
CORS(auth_bp, resources={r"/login": {"origins": "http://localhost:3000"}})

# Token verification decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]  # Extract token after Bearer
        else:
            return jsonify({"message": "Token is missing!"}), 403

        try:
            data = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
            current_user = session.query(User).filter_by(id=data['user_id']).first()
        except Exception as e:
            return jsonify({"message": f"Token is invalid! {str(e)}"}), 403
        return f(current_user, *args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    # Debug: Print the incoming email and password
    print(f"Received email: {data.get('email')}")
    
    # Retrieve the user by email
    user = session.query(User).filter_by(email=data.get('email')).first()

    # Debug: Check if the user is found
    if user:
        print(f"User found: {user.email}")
        print(f"User password: {user.password_hash}")
    else:
        print(f"No user found with email: {data.get('email')}")
    
    # Check if user exists and verify password using check_password method
    if user:
        print(f"Password matched for user: {user.email}")
        # Generate JWT token
        token = jwt.encode(
            {
                'user_id': user.id,
                'login': user.email,
                'exp': datetime.utcnow() + timedelta(hours=1)
            },
            Config.SECRET_KEY,
            algorithm="HS256"
        )
        
        return jsonify({
            "token": token, 
            "login": user.email,
            "user_role": user.role
        })
    
    print("Invalid credentials!")
    return jsonify({"message": "Invalid credentials!"}), 401


# Admin verification decorator
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        else:
            return jsonify({"message": "Token is missing!"}), 403

        try:
            data = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
            current_user = session.query(User).filter_by(id=data['user_id']).first()
            if current_user.role != 'admin':
                return jsonify({"message": "Admin access required!"}), 403
        except Exception as e:
            return jsonify({"message": f"Token is invalid! {str(e)}"}), 403
        return f(current_user, *args, **kwargs)
    return decorated

@auth_bp.route('/register_account', methods=['POST'])
@admin_required
def register_account(current_user):
    data = request.get_json()
            
    # Проверяем наличие необходимых полей
    required_fields = ['email', 'first_name', 'last_name']
    for field in required_fields:
        if field not in data:
            return jsonify({"message": f"Missing required field: {field}"}), 400
            
    # Проверяем, не существует ли уже пользователь с таким email
    if session.query(User).filter_by(email=data['email']).first():
        return jsonify({"message": "User with this email already exists"}), 400
            
    # Генерируем случайный пароль
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for i in range(12))
            
    # Создаем нового пользователя
    new_user = User(
        email=data['email'],
        first_name=data['first_name'],
        last_name=data['last_name'],
        role='student'
    )
    new_user.set_password(password)
    
    try:
        session.add(new_user)
        session.commit()
                
        return jsonify({
            "message": "User created successfully",
            "credentials": {
                "email": new_user.email,
                "password": password
            }
        }), 201
                
    except Exception as e:
        session.rollback()
        return jsonify({"message": f"Error creating user: {str(e)}"}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = jsonify({"message": "Logout successful"})
    response.set_cookie('token', '', expires=0)
    return response, 200
