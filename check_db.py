from sqlalchemy import text
from models import engine, session

def fix_video_sources():
    try:
        with engine.connect() as conn:
            # Сначала сохраняем существующие данные
            conn.execute(text("""
                ALTER TABLE videos 
                ADD COLUMN temp_source text;
                
                UPDATE videos 
                SET temp_source = video_source::text;
            """))
            
            # Удаляем существующий enum тип
            conn.execute(text("""
                ALTER TABLE videos 
                DROP COLUMN video_source;
                
                DROP TYPE IF EXISTS video_sources;
            """))
            
            # Создаем новый enum тип
            conn.execute(text("""
                CREATE TYPE video_sources AS ENUM ('youtube', 'local');
                
                ALTER TABLE videos 
                ADD COLUMN video_source video_sources;
                
                UPDATE videos 
                SET video_source = 'youtube' 
                WHERE temp_source = 'youtube';
                
                UPDATE videos 
                SET video_source = 'local' 
                WHERE temp_source = 'local';
                
                ALTER TABLE videos 
                DROP COLUMN temp_source;
            """))
            
            conn.commit()
            print("Successfully fixed video_sources enum")
            
    except Exception as e:
        print(f"Error fixing video_sources: {str(e)}")
        raise e

if __name__ == "__main__":
    fix_video_sources() 