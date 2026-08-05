import filetype
from django.core.exceptions import ValidationError

def validate_secure_image(file):
    max_size = 10 * 1024 * 1024  # 10MB
    if file.size > max_size:
        raise ValidationError("File size must be under 10MB.")
    
    # Read first 2048 bytes to guess type
    kind = filetype.guess(file.read(2048))
    file.seek(0) # Reset file pointer
    
    if kind is None or not kind.mime.startswith('image/'):
        raise ValidationError("Invalid file content. Only real images are allowed.")
