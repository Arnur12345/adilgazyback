from datetime import datetime

from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, Enum as DbEnum, LargeBinary, Integer  # noqa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func #noqa
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash

# Create engine and Base for standalone use
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
Base = declarative_base()
# Session factory for standalone scripts (outside of Flask)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    role = Column(DbEnum('admin', 'student', name='user_roles'), nullable=False, default='student')
    created_at = Column(DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Course(Base):
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000))
    thumbnail_url = Column(String(500))  # URL or path to course thumbnail image
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Video(Base):
    __tablename__ = 'videos'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500))  # URL or path to video thumbnail image
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    order = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class PdfDocument(Base):
    __tablename__ = 'pdf_documents'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)  # URL or path to PDF file
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    order = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class CourseAccess(Base):
    __tablename__ = 'course_access'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', name='fk_student_user'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)
    

class Comment(Base):
    __tablename__ = 'comments'
    
    id = Column(Integer, primary_key=True)
    text = Column(String(1000), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Создание таблиц (перемещено в конец файла)
Base.metadata.create_all(bind=engine)