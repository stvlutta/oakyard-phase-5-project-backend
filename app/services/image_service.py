import os
import boto3
from PIL import Image, ImageOps
from flask import current_app
from werkzeug.utils import secure_filename
import uuid
from io import BytesIO

class ImageService:
    def __init__(self):
        self.s3_client = None
        self.bucket_name = current_app.config.get('AWS_S3_BUCKET')
        self.use_s3 = bool(self.bucket_name and current_app.config.get('AWS_ACCESS_KEY_ID'))
        
        if self.use_s3:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY'),
                region_name=current_app.config.get('AWS_S3_REGION', 'us-east-1')
            )
    
    def process_image(self, image_file, max_size=(1200, 800), quality=85):
        """Process and optimize image"""
        try:
            # Open image
            image = Image.open(image_file)
            
            # Auto-orient image based on EXIF data
            image = ImageOps.exif_transpose(image)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize image if it's too large
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save to BytesIO
            img_buffer = BytesIO()
            image.save(img_buffer, format='JPEG', quality=quality, optimize=True)
            img_buffer.seek(0)
            
            return img_buffer, image.size
        except Exception as e:
            current_app.logger.error(f"Image processing failed: {e}")
            raise Exception(f"Image processing failed: {e}")
    
    def generate_filename(self, original_filename):
        """Generate unique filename"""
        # Get file extension
        ext = os.path.splitext(secure_filename(original_filename))[1].lower()
        if not ext:
            ext = '.jpg'
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{ext}"
    
    def upload_to_s3(self, file_buffer, filename, folder='images'):
        """Upload file to S3"""
        if not self.use_s3:
            raise Exception("S3 not configured")
        
        try:
            key = f"{folder}/{filename}"
            
            self.s3_client.upload_fileobj(
                file_buffer,
                self.bucket_name,
                key,
                ExtraArgs={
                    'ContentType': 'image/jpeg',
                    'ACL': 'public-read'
                }
            )
            
            # Return public URL
            return f"https://{self.bucket_name}.s3.amazonaws.com/{key}"
        except Exception as e:
            current_app.logger.error(f"S3 upload failed: {e}")
            raise Exception(f"S3 upload failed: {e}")
    
    def save_to_local(self, file_buffer, filename, folder='images'):
        """Save file to local storage"""
        try:
            # Create directory if it doesn't exist
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(file_buffer.getvalue())
            
            # Return local URL
            base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
            return f"{base_url}/uploads/{folder}/{filename}"
        except Exception as e:
            current_app.logger.error(f"Local save failed: {e}")
            raise Exception(f"Local save failed: {e}")
    
    def upload_image(self, image_file, folder='images', max_size=(1200, 800)):
        """Upload and process image"""
        try:
            # Generate filename
            filename = self.generate_filename(image_file.filename)
            
            # Process image
            img_buffer, dimensions = self.process_image(image_file, max_size)
            
            # Upload to storage
            if self.use_s3:
                url = self.upload_to_s3(img_buffer, filename, folder)
            else:
                url = self.save_to_local(img_buffer, filename, folder)
            
            return {
                'url': url,
                'filename': filename,
                'dimensions': dimensions
            }
        except Exception as e:
            current_app.logger.error(f"Image upload failed: {e}")
            raise Exception(f"Image upload failed: {e}")
    
    def delete_from_s3(self, filename, folder='images'):
        """Delete file from S3"""
        if not self.use_s3:
            return False
        
        try:
            key = f"{folder}/{filename}"
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except Exception as e:
            current_app.logger.error(f"S3 deletion failed: {e}")
            return False
    
    def delete_from_local(self, filename, folder='images'):
        """Delete file from local storage"""
        try:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            current_app.logger.error(f"Local deletion failed: {e}")
            return False
    
    def delete_image(self, filename, folder='images'):
        """Delete image from storage"""
        if self.use_s3:
            return self.delete_from_s3(filename, folder)
        else:
            return self.delete_from_local(filename, folder)
    
    def create_thumbnail(self, image_file, size=(300, 200)):
        """Create thumbnail from image"""
        try:
            # Process image as thumbnail
            img_buffer, dimensions = self.process_image(image_file, max_size=size)
            
            # Generate thumbnail filename
            original_filename = self.generate_filename(image_file.filename)
            thumbnail_filename = f"thumb_{original_filename}"
            
            # Upload thumbnail
            if self.use_s3:
                url = self.upload_to_s3(img_buffer, thumbnail_filename, 'thumbnails')
            else:
                url = self.save_to_local(img_buffer, thumbnail_filename, 'thumbnails')
            
            return {
                'url': url,
                'filename': thumbnail_filename,
                'dimensions': dimensions
            }
        except Exception as e:
            current_app.logger.error(f"Thumbnail creation failed: {e}")
            raise Exception(f"Thumbnail creation failed: {e}")
    
    def upload_multiple_images(self, image_files, folder='images', max_size=(1200, 800)):
        """Upload multiple images"""
        results = []
        
        for image_file in image_files:
            try:
                result = self.upload_image(image_file, folder, max_size)
                results.append(result)
            except Exception as e:
                current_app.logger.error(f"Failed to upload image {image_file.filename}: {e}")
                results.append({
                    'error': str(e),
                    'filename': image_file.filename
                })
        
        return results
    
    def validate_image(self, image_file):
        """Validate image file"""
        try:
            # Check file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if hasattr(image_file, 'content_length') and image_file.content_length > max_size:
                return False, "File too large (max 10MB)"
            
            # Check file type
            allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
            if image_file.content_type not in allowed_types:
                return False, "Invalid file type"
            
            # Try to open image
            image = Image.open(image_file)
            image.verify()
            
            # Reset file pointer
            image_file.seek(0)
            
            return True, "Valid image"
        except Exception as e:
            return False, f"Invalid image: {e}"
    
    def get_image_metadata(self, image_file):
        """Get image metadata"""
        try:
            image = Image.open(image_file)
            
            metadata = {
                'format': image.format,
                'mode': image.mode,
                'size': image.size,
                'has_transparency': image.mode in ('RGBA', 'LA') or 'transparency' in image.info
            }
            
            # Get EXIF data if available
            if hasattr(image, '_getexif'):
                exif_data = image._getexif()
                if exif_data:
                    metadata['exif'] = exif_data
            
            # Reset file pointer
            image_file.seek(0)
            
            return metadata
        except Exception as e:
            current_app.logger.error(f"Failed to get image metadata: {e}")
            return {}
    
    def create_image_variants(self, image_file, variants=None):
        """Create multiple image variants"""
        if variants is None:
            variants = {
                'original': (1200, 800),
                'large': (800, 600),
                'medium': (400, 300),
                'small': (200, 150),
                'thumbnail': (100, 100)
            }
        
        results = {}
        
        for variant_name, size in variants.items():
            try:
                # Reset file pointer
                image_file.seek(0)
                
                # Generate filename for variant
                original_filename = self.generate_filename(image_file.filename)
                variant_filename = f"{variant_name}_{original_filename}"
                
                # Process image
                img_buffer, dimensions = self.process_image(image_file, max_size=size)
                
                # Upload variant
                if self.use_s3:
                    url = self.upload_to_s3(img_buffer, variant_filename, 'variants')
                else:
                    url = self.save_to_local(img_buffer, variant_filename, 'variants')
                
                results[variant_name] = {
                    'url': url,
                    'filename': variant_filename,
                    'dimensions': dimensions
                }
            except Exception as e:
                current_app.logger.error(f"Failed to create {variant_name} variant: {e}")
                results[variant_name] = {'error': str(e)}
        
        return results

# Initialize service will be done in app context
image_service = None

def init_image_service():
    global image_service
    if image_service is None:
        image_service = ImageService()
    return image_service