# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django-based file management application called "Abnormal File Vault" designed for efficient file handling and storage. It provides a REST API for file upload, download, listing, and deletion operations.

## Technology Stack

- **Backend**: Django 5.x with Django REST Framework
- **Database**: SQLite (local file at `backend/data/db.sqlite3`)
- **Deployment**: Docker + Docker Compose with Gunicorn
- **Static Files**: WhiteNoise for serving static files
- **Storage**: Local file storage in `backend/media/uploads/` with UUID-based filenames

## Development Commands

### Local Development (without Docker)

```bash
# Navigate to backend directory
cd backend

# Activate virtual environment (create if doesn't exist)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p media staticfiles data

# Run database migrations
python manage.py migrate

# Start development server
python manage.py runserver

# Run tests
python manage.py test

# Run specific test app
python manage.py test files
```

### Docker Development

```bash
# Build and start all services
docker-compose up --build

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Database Management

```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser

# Reset database (delete and recreate)
rm backend/data/db.sqlite3
python manage.py migrate
```

## Architecture Overview

### Application Structure

The project follows Django's app-based architecture:

- **`backend/core/`**: Project configuration and settings
  - `settings.py`: Django settings, database config, middleware, installed apps
  - `urls.py`: Root URL routing (maps `/api/` to files app, `/admin/` to Django admin)
  - `wsgi.py`: WSGI application entry point for production servers

- **`backend/files/`**: Main file management application
  - `models.py`: File model with UUID primary key, stores file metadata
  - `views.py`: FileViewSet provides CRUD operations via REST API
  - `serializers.py`: FileSerializer handles data transformation
  - `urls.py`: API routing using DRF's DefaultRouter

### File Storage Architecture

1. **File Upload Flow**:
   - Client POSTs multipart/form-data to `/api/files/`
   - `FileViewSet.create()` extracts file from request
   - Django saves file to `media/uploads/{uuid}.{ext}` (path determined by `file_upload_path()`)
   - File model stores: UUID, original filename, file type, size, upload timestamp
   - Returns file metadata including URL

2. **File Identification**:
   - Files use UUID primary keys (not sequential IDs)
   - Physical files stored with UUID-based names to prevent collisions
   - Original filenames preserved in database for display

3. **File Access**:
   - Files served through Django's static file serving (WhiteNoise in production)
   - URLs accessible via `/media/uploads/{uuid}.{ext}`

### Database Schema

**File Model** (`backend/files/models.py:11`)
- `id`: UUIDField (primary key)
- `file`: FileField (physical file reference)
- `original_filename`: CharField(255)
- `file_type`: CharField(100) - MIME type
- `size`: BigIntegerField - bytes
- `uploaded_at`: DateTimeField - auto-set on creation

### API Endpoints

Base URL: `http://localhost:8000/api/`

- `GET /api/files/` - List all files
- `POST /api/files/` - Upload new file (multipart/form-data with 'file' field)
- `GET /api/files/{uuid}/` - Get file details
- `DELETE /api/files/{uuid}/` - Delete file
- `GET /admin/` - Django admin interface

### Settings Configuration

Important settings in `backend/core/settings.py`:

- **Database**: SQLite at `backend/data/db.sqlite3` (line 83)
- **Media files**: `MEDIA_ROOT = backend/media/`, `MEDIA_URL = /media/` (lines 127-128)
- **Static files**: Served via WhiteNoise with compression (line 124)
- **REST Framework**: AllowAny permissions, supports JSON and MultiPart parsers (lines 136-145)
- **Environment variables**:
  - `DJANGO_SECRET_KEY`: Secret key (defaults to insecure dev key)
  - `DJANGO_DEBUG`: Debug mode (defaults to True)

### Docker Configuration

- **docker-compose.yml**: Single backend service
- **Volumes**:
  - `backend_storage` → `/app/media` (uploaded files)
  - `backend_data` → `/app/data` (SQLite database)
  - `backend_static` → `/app/staticfiles` (static assets)
- **Port mapping**: 8000:8000
- **Startup**: Runs `start.sh` which performs migrations then starts Gunicorn

## Project Submission

The project includes a submission script for creating properly filtered zip files:

```bash
# Activate backend venv first
cd backend && source venv/bin/activate && cd ..

# Create submission zip
python create_submission_zip.py
```

Creates: `{username}_YYYYMMDD.zip` (respects .gitignore patterns)

## Important Notes

1. **No frontend**: This is backend-only. Previously had frontend components that were removed.

2. **Test coverage**: No test files currently exist in `backend/files/`. Tests should be created in `backend/files/tests.py` when adding functionality.

3. **File size limits**: No explicit limit configured. To add limits, modify `FILE_UPLOAD_MAX_MEMORY_SIZE` in settings.py.

4. **Security**: Current configuration uses `ALLOWED_HOSTS = ['*']` and `AllowAny` permissions - should be restricted for production.

5. **Database location**: SQLite DB is in `backend/data/` directory (not default location) to facilitate Docker volume mounting.

6. **Static files**: Must run `python manage.py collectstatic` before production deployment or after adding static files.

7. **Migrations**: The `start.sh` script runs `makemigrations` and `migrate` on container startup, so model changes are automatically applied in Docker environments.
