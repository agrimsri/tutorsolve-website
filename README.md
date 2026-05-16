# TutorSolve

## Architecture
- `backend/` — Flask JSON API (deploys to AWS Elastic Beanstalk)
- `frontend/` — Static HTML/CSS/JS (deploys to AWS S3 + CloudFront)

## Local Development

### Backend
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate      # Windows
source .venv/bin/activate    # Mac/Linux
pip install -r requirements.txt
python run.py
```
API runs at: http://localhost:5000

### Frontend
```bash
cd frontend
python -m http.server 3000
```
Frontend runs at: http://localhost:3000

## Seeded Administrative Accounts
| Role | Email | Password |
| :--- | :--- | :--- |
| **Super Admin** | `admin@tutorsolve.com` | `Admin@123` |
| **Employee** | `staff@tutorsolve.com` | `Staff@123` |

## Environment
Copy `backend/.env.example` to `backend/.env` and fill in your values. Ensure `MONGO_URI` is present.
