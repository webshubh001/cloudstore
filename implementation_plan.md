# Cloud-Based File Storage System

## Overview
A full-featured Django-based cloud file storage system using AWS S3 for storage, MySQL for metadata, and Bootstrap 5 for the UI. Inspired by Google Drive / Dropbox — clean, premium dark/light UI with all requested features.

---

## Tech Stack
| Layer | Technology |
|---|---|
| Backend | Django 4.2, Python 3.11 |
| Database | MySQL 8.0 |
| Cloud Storage | AWS S3 (boto3 + django-storages) |
| Frontend | Bootstrap 5.3, Vanilla JS, Font Awesome 6 |
| File Encryption | Fernet (cryptography library) — server-side before upload |
| Auth | Django built-in Auth + custom profile |
| Search | Django ORM full-text search |

---

## Architecture

```
User Browser (Bootstrap 5 UI)
       │
       ▼
Django Application Server
  ├── Auth Module (login/register/profile)
  ├── Files Module (upload/download/delete/share/search)
  ├── Folders Module (CRUD, hierarchy)
  ├── Versions Module (history per file)
  └── Dashboard Module (storage stats)
       │
       ├──► MySQL (metadata: users, files, folders, versions, shares)
       └──► AWS S3 (actual file blobs, encrypted)
```

---

## Project Structure
```
cloudstore/
├── manage.py
├── requirements.txt
├── .env.example
├── cloudstore/           # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/             # User auth & profile
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   └── urls.py
├── files/                # Core file operations
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── utils.py          # S3 helpers, encryption
│   └── templatetags/
├── templates/
│   ├── base.html
│   ├── accounts/
│   └── files/
└── static/
    ├── css/custom.css
    └── js/main.js
```

---

## Proposed Changes

### Core Django Project

#### [NEW] `cloudstore/settings.py`
- AWS S3 credentials via environment variables
- MySQL database config
- django-storages S3 backend
- Session/auth settings

#### [NEW] `requirements.txt`
- Django, mysqlclient, boto3, django-storages, cryptography, Pillow, python-decouple

---

### Accounts App

#### [NEW] `accounts/models.py`
- `UserProfile` model: avatar, storage_used (bytes), storage_quota, created_at

#### [NEW] `accounts/views.py`
- `register`, `login_view`, `logout_view`, `profile`, `change_password`

#### [NEW] `accounts/forms.py`
- `RegisterForm`, `LoginForm`, `ProfileForm`

---

### Files App (Core)

#### [NEW] `files/models.py`
- **`Folder`**: owner, name, parent (self-FK for nesting), created_at
- **`File`**: owner, folder, original_name, s3_key, size, mime_type, is_encrypted, created_at, updated_at, is_deleted (soft delete)
- **`FileVersion`**: file (FK), version_number, s3_key, size, created_at
- **`FileShare`**: file, shared_by, shared_with (FK or email), token (UUID), can_download, expires_at
- **`Tag`**: many-to-many with File

#### [NEW] `files/utils.py`
- `encrypt_file(bytes) → bytes` using Fernet
- `decrypt_file(bytes) → bytes`
- `upload_to_s3(file_obj, key, encrypted)` 
- `get_presigned_url(key, expires)` for secure download
- `calculate_user_storage(user)` 

#### [NEW] `files/views.py`
- `dashboard` — storage stats, recent files, quick actions
- `folder_list` / `folder_create` / `folder_delete`
- `file_upload` — multipart, encryption, versioning, S3 upload
- `file_download` — decrypt + stream or presigned URL
- `file_delete` — soft delete → move to trash
- `trash_view` / `restore_file` / `empty_trash`
- `file_share` — generate share link with expiry
- `shared_link_download` — token-based public access
- `file_search` — search by name, type, tag
- `version_history` — list versions, restore version
- `storage_dashboard` — chart data for AJAX

---

### Templates (Premium Bootstrap 5 Dark/Light UI)

#### [NEW] `templates/base.html`
- Sidebar nav with collapsible folders
- Top navbar with search bar, storage indicator, profile menu
- Toast notifications, drag-and-drop zone indicator
- Dark/Light mode toggle

#### [NEW] `templates/files/dashboard.html`
- Storage usage donut chart (Chart.js)
- Recent files grid with file-type icons
- Quick upload button, stats cards

#### [NEW] `templates/files/file_list.html`
- Table/Grid toggle view
- Sortable columns, breadcrumb navigation
- Context menu (right-click) for actions

#### [NEW] `templates/accounts/login.html` / `register.html`
- Glassmorphism card, animated background gradient

---

### Static Assets

#### [NEW] `static/css/custom.css`
- CSS variables for dark/light theme
- Glassmorphism effects, smooth transitions
- Custom scrollbar, file card styles

#### [NEW] `static/js/main.js`
- Drag-and-drop upload
- AJAX file operations (delete, rename)
- Dark/light mode persistence

---

## Key Feature Details

### File Encryption
- Server-side Fernet symmetric encryption before S3 upload
- Encryption key stored in environment variable (`.env`)
- Files stored as `.enc` objects in S3, decrypted on download

### Version History
- Every upload/overwrite of same filename creates a new `FileVersion` record
- Old S3 objects preserved with versioned key (`file_id/v2/filename`)
- UI shows version list with restore button

### File Sharing
- Generate UUID token link: `/share/<token>/`
- Options: view-only or allow download, expiry date
- Email-based sharing (user must have account) OR public link

### Search
- Search by filename, folder, file type (MIME), date range
- Django ORM `icontains` across File model fields

### Storage Dashboard
- Donut chart: used vs available (Chart.js)
- Bar chart: file types breakdown
- Storage quota enforced on upload (returns 403 if exceeded)

---

## Verification Plan

### Automated
```bash
python manage.py test accounts files
python manage.py check --deploy
```

### Manual Verification
1. Register/Login → profile shows avatar and storage meter
2. Upload a file → appears in S3, encrypted, listed in dashboard
3. Create folder → upload file into folder → breadcrumb works
4. Share file → open link in incognito → download works
5. Upload same file again → version history shows 2 versions
6. Search → results appear instantly
7. Delete → goes to trash → restore works
8. Storage bar updates after each upload/delete

---

## Open Questions

> [!IMPORTANT]
> **AWS Credentials**: Do you have AWS credentials ready (Access Key ID, Secret Key, S3 bucket name, region)? The app will use `.env` file for these — I'll provide an `.env.example`.

> [!NOTE]
> **MySQL Setup**: I'll assume local MySQL on port 3306 with database name `cloudstore_db`. Let me know if you need a different config.

> [!NOTE]
> **Storage Quota**: Default quota per user will be set to **5 GB**. This can be changed in settings.

> [!NOTE]
> **Email Sharing**: For file-sharing via email notifications, Django's email backend will need SMTP config. I'll add `.env` variables for it. For now, share links will work without email.
