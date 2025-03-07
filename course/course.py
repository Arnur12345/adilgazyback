from flask import Blueprint, request, jsonify, send_file, make_response
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
from models import session, Course, CourseAccess, Video, User, Comment, PdfDocument
from auth import token_required, admin_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from flask_cors import CORS
from sqlalchemy.sql import text

course_bp = Blueprint('course', __name__)
CORS(course_bp)

# Конфигурация для загрузки файлов
UPLOAD_FOLDER = 'uploads'
COURSE_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'courses')
VIDEO_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'videos')
PDF_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'pdfs')

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}

# Создаем необходимые директории если их нет
for folder in [UPLOAD_FOLDER, COURSE_UPLOAD_FOLDER, VIDEO_UPLOAD_FOLDER, PDF_UPLOAD_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_file(file, folder):
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
    unique_filename = timestamp + filename
    file_path = os.path.join(folder, unique_filename)
    file.save(file_path)
    return file_path

def delete_file(file_path):
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

@course_bp.route('/users', methods=['GET'])
@admin_required
def get_users(current_user):
    try:
        # Get all users
        users = session.query(User).all()
        
        users_list = []
        for user in users:
            users_list.append({
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'role': user.role
            })
            
        return jsonify({'users': users_list}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@course_bp.route('/users/<int:user_id>', methods=['GET', 'PUT'])
@admin_required
def edit_user(current_user, user_id):
    if request.method == 'GET':
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404

            return jsonify({
                'user': {
                    'id': user.id,
                    'email': user.email, 
                    'first_name': user.first_name,
                    'role': user.role
                }
            }), 200

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'PUT':
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404

            data = request.get_json()
            
            if 'email' in data:
                user.email = data['email']
            if 'first_name' in data:
                user.first_name = data['first_name']
            if 'role' in data:
                user.role = data['role']
                
            session.commit()
            
            return jsonify({
                'message': 'User updated successfully',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'role': user.role
                }
            }), 200
            
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500

@course_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(current_user, user_id):
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        if user.id == current_user.id:
            return jsonify({'error': 'Cannot delete yourself'}), 400
            
        session.delete(user)
        session.commit()
        
        return jsonify({'message': 'User deleted successfully'}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/<int:course_id>/pdfs', methods=['GET'])
@token_required
def get_course_pdfs(current_user, course_id):
    try:
        # Проверяем существование курса
        course = session.query(Course).filter_by(id=course_id).first()
        if not course:
            return jsonify({'error': 'Course not found'}), 404

        # Проверяем доступ к курсу для студентов
        if current_user.role != 'admin':
            access = session.query(CourseAccess).filter_by(
                user_id=current_user.id,
                course_id=course_id
            ).first()
            
            if not access:
                return jsonify({'error': 'No access to this course'}), 403
                
            if access.end_date < datetime.utcnow():
                return jsonify({'error': 'Access expired'}), 403

        # Получаем PDF документы курса, сортируем по order
        pdfs = session.query(PdfDocument).filter_by(course_id=course_id).order_by(PdfDocument.order).all()
        
        pdfs_data = [{
            'id': pdf.id,
            'title': pdf.title,
            'file_path': pdf.file_path,
            'order': pdf.order,
            'created_at': pdf.created_at.isoformat()
        } for pdf in pdfs]
        
        return jsonify({'pdfs': pdfs_data}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/<int:course_id>/pdf', methods=['POST'])
@admin_required
def add_pdf(current_user, course_id):
    try:
        # Проверяем существование курса
        course = session.query(Course).filter_by(id=course_id).first()
        if not course:
            return jsonify({'error': 'Course not found'}), 404

        # Получаем данные из запроса
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        title = data.get('title')
        pdf_url = data.get('pdf_url')

        if not title or not pdf_url:
            return jsonify({'error': 'Title and PDF URL are required'}), 400

        # Если order не указан, добавляем в конец
        max_order = session.query(func.max(PdfDocument.order)).filter_by(course_id=course_id).scalar()
        order = 1 if max_order is None else max_order + 1

        # Создаем запись в базе данных
        new_pdf = PdfDocument(
            title=title,
            file_path=pdf_url,
            course_id=course_id,
            order=order,
            created_at=datetime.utcnow()
        )
        
        session.add(new_pdf)
        session.commit()
        
        return jsonify({
            'message': 'PDF added successfully',
            'pdf': {
                'id': new_pdf.id,
                'title': new_pdf.title,
                'file_path': new_pdf.file_path,
                'order': new_pdf.order,
                'created_at': new_pdf.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/<int:course_id>/pdf/<int:pdf_id>', methods=['PUT'])
@admin_required
def update_pdf(current_user, course_id, pdf_id):
    old_file_path = None
    new_file_path = None
    try:
        pdf = session.query(PdfDocument).filter_by(id=pdf_id, course_id=course_id).first()
        if not pdf:
            return jsonify({'error': 'PDF not found'}), 404

        # Обновляем название если предоставлено
        if 'title' in request.form:
            pdf.title = request.form['title']

        # Обновляем order если предоставлен
        if 'order' in request.form:
            new_order = int(request.form['order'])
            if new_order != pdf.order:
                # Сдвигаем существующие PDF
                if new_order > pdf.order:
                    session.query(PdfDocument).filter(
                        PdfDocument.course_id == course_id,
                        PdfDocument.order > pdf.order,
                        PdfDocument.order <= new_order
                    ).update({PdfDocument.order: PdfDocument.order - 1})
                else:
                    session.query(PdfDocument).filter(
                        PdfDocument.course_id == course_id,
                        PdfDocument.order >= new_order,
                        PdfDocument.order < pdf.order
                    ).update({PdfDocument.order: PdfDocument.order + 1})
                pdf.order = new_order

        # Обновляем файл если предоставлен
        if 'pdf' in request.files:
            file = request.files['pdf']
            if file.filename != '' and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS):
                old_file_path = pdf.file_path
                new_file_path = save_file(file, PDF_UPLOAD_FOLDER)
                pdf.file_path = new_file_path

        session.commit()
        
        # Удаляем старый файл только после успешного коммита
        if old_file_path:
            delete_file(old_file_path)
        
        return jsonify({
            'message': 'PDF updated successfully',
            'pdf': {
                'id': pdf.id,
                'title': pdf.title,
                'file_path': pdf.file_path,
                'order': pdf.order,
                'created_at': pdf.created_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        session.rollback()
        # В случае ошибки удаляем новый файл если он был создан
        if new_file_path and os.path.exists(new_file_path):
            os.remove(new_file_path)
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/<int:course_id>/pdf/<int:pdf_id>', methods=['DELETE'])
@admin_required
def delete_pdf(current_user, course_id, pdf_id):
    try:
        pdf = session.query(PdfDocument).filter_by(id=pdf_id, course_id=course_id).first()
        if not pdf:
            return jsonify({'error': 'PDF not found'}), 404

        current_order = pdf.order
        file_path = pdf.file_path

        # Удаляем запись из базы данных
        session.delete(pdf)
        
        # Обновляем order для оставшихся PDF
        session.query(PdfDocument).filter(
            PdfDocument.course_id == course_id,
            PdfDocument.order > current_order
        ).update({PdfDocument.order: PdfDocument.order - 1})
        
        session.commit()
        
        # Удаляем файл после успешного коммита
        delete_file(file_path)
        
        return jsonify({'message': 'PDF deleted successfully'}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/<int:course_id>/pdf/<int:pdf_id>', methods=['GET'])
@token_required
def get_pdf(current_user, course_id, pdf_id):
    try:
        pdf = session.query(PdfDocument).filter_by(id=pdf_id, course_id=course_id).first()
        if not pdf:
            return jsonify({'error': 'PDF not found'}), 404
        
        print(f"PDF file path: {pdf.file_path}")

        # Проверяем доступ к курсу для студентов
        if current_user.role != 'admin':
            access = session.query(CourseAccess).filter_by(
                user_id=current_user.id,
                course_id=course_id
            ).first()
            
            if not access:
                return jsonify({'error': 'No access to this PDF'}), 403
                
            if access.end_date < datetime.utcnow():
                return jsonify({'error': 'Access expired'}), 403

        # Проверяем существование файла
        if not os.path.exists(pdf.file_path):
            return jsonify({'error': 'PDF file not found on server'}), 404

        try:
            return send_file(
                pdf.file_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"{pdf.title}.pdf"
            )
        except Exception as e:
            print(f"Error sending file: {str(e)}")
            return jsonify({'error': 'Error sending PDF file'}), 500
        
    except Exception as e:
        print(f"Error in get_pdf: {str(e)}")
        return jsonify({'error': str(e)}), 500

@course_bp.route('/courses', methods=['GET'])
@token_required 
def get_courses(current_user):
    try:
        courses_data = []
        
        if current_user.role == 'admin':
            # Для админа показываем все курсы
            courses = session.query(Course).all()
            for course in courses:
                courses_data.append({
                    'id': course.id,
                    'title': course.title,
                    'description': course.description,
                    'thumbnail_url': course.thumbnail_url
                })
        else:
            # Для студента показываем только курсы с доступом
            course_access = session.query(CourseAccess).filter_by(user_id=current_user.id).all()
            for access in course_access:
                course = session.query(Course).filter_by(id=access.course_id).first()
                if course:
                    courses_data.append({
                        'id': course.id,
                        'title': course.title,
                        'description': course.description,
                        'thumbnail_url': course.thumbnail_url,
                        'access_expires': access.end_date.strftime('%Y-%m-%d %H:%M:%S')
                    })
        
        response = jsonify({'courses': courses_data})
        response.headers.add('Access-Control-Allow-Origin', '*')  # Разрешаем CORS
        return response, 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course', methods=['POST'])
@admin_required
def create_course(current_user):
    try:
        # Проверяем тип контента и получаем данные
        if request.is_json:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid JSON data'}), 400
                
            title = data.get('title')
            description = data.get('description') 
            thumbnail_url = data.get('thumbnail_url')
        else:
            if not request.form:
                return jsonify({'error': 'Invalid form data'}), 400
                
            title = request.form.get('title')
            description = request.form.get('description')
            thumbnail_url = request.form.get('thumbnail')

        # Проверяем наличие всех обязательных полей
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        if not description:
            return jsonify({'error': 'Description is required'}), 400
        if not thumbnail_url:
            return jsonify({'error': 'Thumbnail URL is required'}), 400

        # Создаем новый курс
        try:
            new_course = Course(
                title=title,
                description=description,
                thumbnail_url=thumbnail_url,
                created_by=current_user.id
            )
            
            session.add(new_course)
            session.commit()
            
        except SQLAlchemyError as e:
            session.rollback()
            return jsonify({'error': 'Database error occurred'}), 500

        return jsonify({
            'message': 'Course created successfully',
            'course_id': new_course.id,
            'thumbnail_url': thumbnail_url
        }), 201
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': 'An unexpected error occurred'}), 500

@course_bp.route('/course/<int:course_id>', methods=['GET'])
@token_required
def get_course_detail(current_user, course_id):
    try:
        print(f"Getting course details for course_id: {course_id}, user: {current_user.id}")  # Логирование
        
        # Получаем курс из базы данных
        course = session.query(Course).filter_by(id=course_id).first()
        
        if not course:
            print(f"Course not found: {course_id}")  # Логирование
            return jsonify({'error': 'Course not found'}), 404

        # Проверяем доступ к курсу для студентов
        if current_user.role != 'admin':
            access = session.query(CourseAccess).filter_by(
                user_id=current_user.id,
                course_id=course_id
            ).first()
            
            if not access:
                print(f"No access for user {current_user.id} to course {course_id}")  # Логирование
                return jsonify({'error': 'No access to this course'}), 403
                
            if access.end_date < datetime.utcnow():
                print(f"Access expired for user {current_user.id} to course {course_id}")  # Логирование
                return jsonify({'error': 'Access expired'}), 403

        # Формируем ответ с данными курса
        course_data = {
            'course': {
                'id': course.id,
                'title': course.title,
                'description': course.description,
                'thumbnail_url': course.thumbnail_url,
                'created_by': course.created_by,
                'created_at': course.created_at.isoformat() if course.created_at else None
            }
        }

        print(f"Successfully retrieved course data: {course_data}")  # Логирование
        return jsonify(course_data), 200

    except SQLAlchemyError as e:
        print(f"Database error in get_course_detail: {str(e)}")  # Подробное логирование SQL ошибок
        session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        print(f"Unexpected error in get_course_detail: {str(e)}")  # Подробное логирование общих ошибок
        import traceback
        print(traceback.format_exc())  # Печать полного стека ошибки
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@course_bp.route('/course/<int:course_id>/edit', methods=['PUT'])
@admin_required
def update_course(current_user, course_id):
    try:
        course = session.query(Course).filter_by(id=course_id).first()
        if not course:
            return jsonify({'error': 'Course not found'}), 404
            
        # Обновляем thumbnail если есть
        if 'thumbnail' in request.files:
            file = request.files['thumbnail']
            if file.filename != '' and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                # Удаляем старый файл
                delete_file(course.thumbnail_url)
                    
                file_path = save_file(file, COURSE_UPLOAD_FOLDER)
                course.thumbnail_url = file_path
        
        # Обновляем остальные поля
        if 'title' in request.form:
            course.title = request.form['title']
        if 'description' in request.form:
            course.description = request.form['description']
            
        session.commit()
        return jsonify({'message': 'Course updated successfully'}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/<int:course_id>', methods=['DELETE'])
@admin_required
def delete_course(current_user, course_id):
    try:
        # Проверяем существование курса
        course = session.query(Course).filter_by(id=course_id).first()
        if not course:
            return jsonify({'error': 'Course not found'}), 404

        # Удаляем файл thumbnail если он существует
        if course.thumbnail_url:
            delete_file(course.thumbnail_url)
            
        # Удаляем все видео курса
        videos = session.query(Video).filter_by(course_id=course_id).all()
        for video in videos:
            if video.file_path:
                delete_file(video.file_path)
            if video.thumbnail_url:
                delete_file(video.thumbnail_url)
            session.delete(video)
            
        # Удаляем все PDF документы курса
        pdfs = session.query(PdfDocument).filter_by(course_id=course_id).all()
        for pdf in pdfs:
            if pdf.file_path:
                delete_file(pdf.file_path)
            session.delete(pdf)

        # Удаляем все записи о доступе к курсу
        session.query(CourseAccess).filter_by(course_id=course_id).delete()
        
        # Удаляем сам курс
        session.delete(course)
        session.commit()
        
        return jsonify({'message': 'Course and all related content deleted successfully'}), 200
        
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Database error in delete_course: {str(e)}")
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        session.rollback()
        print(f"Unexpected error in delete_course: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500
    

@course_bp.route('/course/revoke-access', methods=['POST'])
@admin_required
def revoke_course_access(current_user):
    try:
        data = request.get_json()
        
        if not all(k in data for k in ['user_id', 'course_id']):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Проверяем существование записи о доступе
        access = session.query(CourseAccess).filter_by(
            user_id=data['user_id'],
            course_id=data['course_id']
        ).first()
        
        if not access:
            return jsonify({'error': 'Access record not found'}), 404
            
        # Удаляем запись о доступе
        session.delete(access)
        session.commit()
        
        return jsonify({'message': 'Course access revoked successfully'}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/grant-access', methods=['POST'])
@admin_required
def grant_course_access(current_user):
    try:
        data = request.get_json()
        
        if not all(k in data for k in ['user_id', 'course_id', 'duration_days']):
            return jsonify({'error': 'Missing required fields'}), 400
            
        user = session.query(User).filter_by(id=data['user_id']).first()
        course = session.query(Course).filter_by(id=data['course_id']).first()
        
        if not user or not course:
            return jsonify({'error': 'User or course not found'}), 404
            
        end_date = datetime.utcnow() + timedelta(days=int(data['duration_days']))
        
        course_access = CourseAccess(
            user_id=data['user_id'],
            course_id=data['course_id'],
            end_date=end_date
        )
        
        session.add(course_access)
        session.commit()
        
        return jsonify({'message': 'Course access granted successfully'}), 201
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/<int:course_id>/videos', methods=['GET'])
@token_required
def get_course_videos(current_user, course_id):
    try:
        print(f"Getting videos for course_id: {course_id}, user: {current_user.id}")  # Логирование
        
        # Проверяем существование курса
        course = session.query(Course).filter_by(id=course_id).first()
        if not course:
            print(f"Course not found: {course_id}")  # Логирование
            return jsonify({'error': 'Course not found'}), 404

        # Проверяем доступ к курсу для студентов
        if current_user.role != 'admin':
            access = session.query(CourseAccess).filter_by(
                user_id=current_user.id,
                course_id=course_id
            ).first()
            
            if not access:
                print(f"No access for user {current_user.id} to course {course_id}")  # Логирование
                return jsonify({'error': 'No access to this course'}), 403
                
            if access.end_date < datetime.utcnow():
                print(f"Access expired for user {current_user.id} to course {course_id}")  # Логирование
                return jsonify({'error': 'Access expired'}), 403

        # Получаем видео курса
        videos = session.query(Video).filter_by(course_id=course_id).order_by(Video.order).all()
        
        videos_data = [{
            'id': video.id,
            'title': video.title,
            'file_path': video.file_path,
            'thumbnail_url': video.thumbnail_url,
            'order': video.order
        } for video in videos]
        
        print(f"Successfully retrieved {len(videos_data)} videos")  # Логирование
        return jsonify({'videos': videos_data}), 200

    except SQLAlchemyError as e:
        print(f"Database error in get_course_videos: {str(e)}")  # Подробное логирование SQL ошибок
        session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        print(f"Unexpected error in get_course_videos: {str(e)}")  # Подробное логирование общих ошибок
        import traceback
        print(traceback.format_exc())  # Печать полного стека ошибки
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@course_bp.route('/course/<int:course_id>/video', methods=['POST'])
@admin_required
def add_video(current_user, course_id):
    try:
        course = session.query(Course).filter_by(id=course_id).first()
        if not course:
            return jsonify({'error': 'Course not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        title = data.get('title')
        video_url = data.get('video_url')
        video_source = data.get('video_source')
        thumbnail_url = data.get('thumbnail_url', '')

        print(f"Received data: title={title}, video_url={video_url}, source={video_source}")

        if not all([title, video_url, video_source]):
            return jsonify({'error': 'Title, video URL and source are required'}), 400

        # Проверяем и нормализуем video_source
        valid_sources = ['youtube', 'local']
        if video_source not in valid_sources:
            return jsonify({'error': f'Invalid video source. Must be one of: {", ".join(valid_sources)}'}), 400

        try:
            last_video = session.query(Video).filter_by(course_id=course_id).order_by(Video.order.desc()).first()
            next_order = (last_video.order + 1) if last_video else 1

            # Создаем новое видео с явным указанием типа
            new_video = Video(
                title=title,
                file_path=video_url,
                thumbnail_url=thumbnail_url,
                course_id=course_id,
                order=next_order,
                video_source=str(video_source)  # Явно преобразуем в строку
            )
            
            session.add(new_video)
            session.commit()
            
            return jsonify({
                'message': 'Video added successfully',
                'video': {
                    'id': new_video.id,
                    'title': new_video.title,
                    'file_path': new_video.file_path,
                    'thumbnail_url': new_video.thumbnail_url,
                    'order': next_order,
                    'video_source': video_source
                }
            }), 201
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Database error in add_video: {str(e)}")
            return jsonify({'error': f'Database error: {str(e)}'}), 500
            
    except Exception as e:
        session.rollback()
        print(f"Error in add_video: {str(e)}")
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/<int:course_id>/video/<int:video_id>', methods=['DELETE'])
@admin_required
def delete_video(current_user, course_id, video_id):
    try:
        video = session.query(Video).filter_by(id=video_id, course_id=course_id).first()
        if not video:
            return jsonify({'error': 'Video not found'}), 404
            
        # Удаляем комментарии к видео
        session.query(Comment).filter_by(video_id=video_id).delete()
            
        # Удаляем видео из базы данных
        session.delete(video)
        session.commit()
        
        return jsonify({'message': 'Video deleted successfully'}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/<int:course_id>/video/<int:video_id>', methods=['GET'])
@token_required
def video_detail(current_user, course_id, video_id):
    try:
        video = session.query(Video).filter_by(id=video_id).first()
        if not video:
            return jsonify({'error': 'Video not found'}), 404
            
        # Проверяем доступ к курсу
        if current_user.role != 'admin':
            access = session.query(CourseAccess).filter_by(
                user_id=current_user.id,
                course_id=video.course_id
            ).first()
            
            if not access:
                return jsonify({'error': 'No access to this video'}), 403
            
        # Получаем комментарии к видео с информацией о пользователях
        comments = session.query(Comment, User).join(User, Comment.user_id == User.id)\
            .filter(Comment.video_id == video_id)\
            .order_by(Comment.created_at.desc()).all()
            
        comments_data = [{
            'id': comment.id,
            'text': comment.text,
            'user_name': user.first_name,
            'created_at': comment.created_at.isoformat()
        } for comment, user in comments]
            
        video_data = {
            'id': video.id,
            'title': video.title,
            'file_path': video.file_path,
            'thumbnail_url': video.thumbnail_url,
            'order': video.order,
            'course_id': video.course_id,
            'comments': comments_data
        }
        
        return jsonify({'video': video_data}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@course_bp.route('/course/<int:course_id>/video/<int:video_id>/comment', methods=['POST'])
@token_required
def add_comment(current_user, course_id, video_id):
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'Comment text is required'}), 400
            
        video = session.query(Video).filter_by(id=video_id).first()
        if not video:
            return jsonify({'error': 'Video not found'}), 404
            
        # Проверяем доступ к курсу
        if current_user.role != 'admin':
            access = session.query(CourseAccess).filter_by(
                user_id=current_user.id,
                course_id=course_id
            ).first()
            
            if not access:
                return jsonify({'error': 'No access to this video'}), 403
                
        new_comment = Comment(
            text=data['text'],
            user_id=current_user.id,
            video_id=video_id,
            created_at=datetime.utcnow()
        )
        
        session.add(new_comment)
        session.commit()
        
        return jsonify({
            'message': 'Comment added successfully',
            'comment': {
                'id': new_comment.id,
                'text': new_comment.text,
                'user_name': current_user.first_name,
                'created_at': new_comment.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500

@course_bp.route('/uploads/<path:filename>')
@token_required
def serve_file(current_user, filename):
    try:
        return send_file(os.path.join(UPLOAD_FOLDER, filename))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
