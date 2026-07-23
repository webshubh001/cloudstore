# ☁️ CloudStore — Setup & Run Guide

## Tech Stack
| Component | Technology |
|---|---|
| Backend | Django 4.2, Python 3.11 |
| Database | MySQL 8.0 |
| Cloud Storage | AWS S3 (boto3) |
| Frontend | Bootstrap 5.3, Font Awesome 6, Chart.js |
| File Encryption | Fernet (AES-128-CBC + HMAC-SHA256) |

---

## ✅ Prerequisites

- Python 3.9+
- MySQL 8.0+ (running locally or remote)
- AWS Account with S3 bucket created
- pip (Python package manager)

---

## 🚀 Quick Start

### 1. Create a Virtual Environment
```bash
cd "Cloud Computing Project"
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

> **Note for Windows users**: `mysqlclient` may require MySQL C connector.  
> Alternative: replace `mysqlclient` in requirements with `PyMySQL` and add this to `cloudstore/__init__.py`:
> ```python
> import pymysql
> pymysql.install_as_MySQLdb()
> ```

### 3. Create MySQL Database
```sql
CREATE DATABASE cloudstore_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 4. Configure Environment Variables
```bash
# Copy the example env file
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

Edit `.env` with your values:
```env
SECRET_KEY=your-random-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=cloudstore_db
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306

AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1

ENCRYPTION_KEY=<generate below>
```

### 5. Generate Encryption Key
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Copy the output into `.env` as `ENCRYPTION_KEY`.

### 6. Run Migrations
```bash
python manage.py makemigrations accounts
python manage.py makemigrations files
python manage.py migrate
```

### 7. Create Admin User
```bash
python manage.py createsuperuser
```

### 8. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 9. Run the Server
```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

---

## 🗂️ Project Structure

```
Cloud Computing Project/
├── manage.py
├── requirements.txt
├── .env.example          ← Copy to .env with your credentials
├── cloudstore/           ← Django project settings
│   ├── settings.py
│   └── urls.py
├── accounts/             ← User auth & profiles
│   ├── models.py         ← UserProfile (storage quota/used)
│   ├── views.py          ← register, login, logout, profile
│   └── signals.py        ← Auto-create UserProfile on register
├── files/                ← Core file storage app
│   ├── models.py         ← File, Folder, FileVersion, FileShare
│   ├── views.py          ← All file operations
│   ├── utils.py          ← S3 + Fernet encryption helpers
│   └── urls.py
├── templates/            ← HTML templates
│   ├── base.html         ← Sidebar layout
│   ├── accounts/
│   └── files/
└── static/
    ├── css/custom.css    ← Premium dark/light theme
    └── js/main.js        ← Drag & drop, theme toggle, etc.
```

---

## 🔒 AWS S3 Setup

1. **Create S3 Bucket**: Go to AWS S3 console → Create bucket
2. **Block Public Access**: Keep all "Block Public Access" settings **ON** (files are served via Django, not directly)
3. **Create IAM User**: IAM → Users → Add User → Attach `AmazonS3FullAccess` policy
4. **Copy credentials**: Access Key ID + Secret into `.env`

---

## 🔑 Features

| Feature | Description |
|---|---|
| User Auth | Register, login, logout, profile, change password |
| File Upload | Drag & drop or browse, multiple files at once |
| File Encryption | AES-128 Fernet encryption before S3 upload |
| File Download | Decrypt and stream to browser |
| Folder Management | Create, delete, navigate nested folders |
| File Versioning | Upload same name → auto-archives old version |
| File Sharing | UUID share links with expiry and access control |
| Search | Full-text search by name, type, date range |
| Storage Dashboard | Donut + bar chart, storage meter in sidebar |
| Trash | Soft delete, restore, empty trash |
| Dark/Light Mode | Toggle with localStorage persistence |

---

## 🛡️ Admin Panel

Access at **http://127.0.0.1:8000/admin/** with your superuser credentials.  
Manage: Users, Profiles, Files, Folders, Versions, Shares.

---

## 🐛 Troubleshooting

**mysqlclient install error on Windows:**
```
pip install pymysql
```
Then add to `cloudstore/__init__.py`:
```python
import pymysql; pymysql.install_as_MySQLdb()
```

**AWS credentials error:**
- Check `.env` file has correct `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
- Ensure IAM user has `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on your bucket

**Encryption key error:**
- Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Paste the full key (44 chars) into `ENCRYPTION_KEY` in `.env`
