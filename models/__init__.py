from .models import Base, Course, CourseAccess, Video , User, Comment, PdfDocument #noqa
from .models import engine, SessionLocal  # Импорт движка и сессии #noqa

# Создаем сессию для работы с БД
session = SessionLocal()