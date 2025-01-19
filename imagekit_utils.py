from imagekitio import ImageKit
from config import Config
import base64

imagekit = ImageKit(
    public_key=Config.IMAGEKIT_PUBLIC_KEY,
    private_key=Config.IMAGEKIT_PRIVATE_KEY,
    url_endpoint=Config.IMAGEKIT_URL_ENDPOINT
)

def upload_image(file, folder_path):
    try:
        # Читаем файл и кодируем в base64
        file_content = file.read()
        encoded_file = base64.b64encode(file_content).decode('utf-8')
        
        # Получаем оригинальное имя файла
        filename = file.filename
        
        # Загружаем в ImageKit
        upload = imagekit.upload(
            file=encoded_file,
            file_name=filename,
            options={
                "folder": folder_path,
                "is_private_file": False,
                "use_unique_file_name": True
            }
        )
        
        return {
            'url': upload.get('url', ''),
            'file_id': upload.get('file_id', ''),
            'thumbnail_url': upload.get('thumbnail_url', '')
        }
        
    except Exception as e:
        print(f"ImageKit upload error: {str(e)}")  # Для отладки
        raise Exception(f"ImageKit upload failed: {str(e)}")