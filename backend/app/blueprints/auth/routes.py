from flask import request, jsonify
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from bson import ObjectId
import os, time

from app.blueprints.auth import auth_bp
from app.extensions import get_db
from app.models.user import make_identity, make_additional_claims
from app.services.geo_service import is_blocked_country, get_real_ip
from app.utils.constants import Role, KYCStatus, BLOCKED_COUNTRIES


# Remote local storage folder - everything should go to S3
# UPLOAD_FOLDER = os.path.join("app", "static", "uploads", "kyc")
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@auth_bp.route("/signup", methods=["POST"])
def signup():
    # Geo-fencing — block IN/PK from student signup (IP-based, proxy-aware)
    if is_blocked_country(get_real_ip()):
        return jsonify({"error": "BLOCKED_REGION", "redirect": "/auth/expert-apply.html"}), 403

    data     = request.get_json()
    email    = (data.get("email") or "").strip().lower()
    name     = (data.get("name") or "").strip()
    country  = (data.get("country") or "").strip()
    password = data.get("password") or ""
    degree   = (data.get("degree") or "").strip()

    if not all([email, name, country, password]):
        return jsonify({"error": "All fields are required"}), 400

    if country in BLOCKED_COUNTRIES:
        return jsonify({"error": "BLOCKED_REGION", "redirect": "/auth/expert-apply.html"}), 403

    db = get_db()
    if db.users.count_documents({"email": email}, limit=1):
        return jsonify({"error": "Email already exists"}), 409

    user_doc = {
        "email":         email,
        "password_hash": generate_password_hash(password),
        "role":          Role.STUDENT,
        "is_active":     True,
        "is_banned":     False,
        "created_at":    datetime.utcnow()
    }
    result  = db.users.insert_one(user_doc)
    user_id = result.inserted_id

    db.students.insert_one({
        "user_id":        user_id,
        "name":           name,
        "degree":         degree or None,
        "country":        country,    # LOCKED — never update after signup
        "wallet_balance": 0.0,
        "total_orders":   0,
        "total_spent":    0.0
    })

    user_doc["_id"] = user_id
    token = create_access_token(
        identity=make_identity(user_doc),
        additional_claims=make_additional_claims(user_doc)
    )
    return jsonify({"token": token, "role": Role.STUDENT}), 201


@auth_bp.route("/domains", methods=["GET"])
def get_domains():
    db = get_db()
    domains = list(db.domains.find({}))
    return jsonify([{"id": str(d["_id"]), "name": d["name"]} for d in domains]), 200

@auth_bp.route("/expert-apply", methods=["POST"])
def expert_apply():
    # Expert apply accepts multipart/form-data for file uploads
    email    = (request.form.get("email") or "").strip().lower()
    name     = (request.form.get("name") or "").strip()
    phone    = (request.form.get("phone") or "").strip()
    domain_id = (request.form.get("domain") or "").strip()
    password = request.form.get("password") or ""

    if not all([email, name, domain_id, password]):
        return jsonify({"error": "All fields are required"}), 400

    from bson import ObjectId
    db = get_db()
    try:
        domain_doc = db.domains.find_one({"_id": ObjectId(domain_id)})
        if not domain_doc:
            raise ValueError()
    except Exception:
        return jsonify({"error": "Invalid or missing domain"}), 400

    if db.users.count_documents({"email": email}, limit=1):
        return jsonify({"error": "Email already exists"}), 409

    user_doc = {
        "email":         email,
        "password_hash": generate_password_hash(password),
        "role":          Role.EXPERT,
        "is_active":     True,
        "is_banned":     False,
        "created_at":    datetime.utcnow()
    }
    result  = db.users.insert_one(user_doc)
    user_id = result.inserted_id

    from app.services.file_service import upload_to_s3
    import mimetypes

    cv_url = None
    id_proof_url = None

    cv_file = request.files.get("cv")
    if cv_file and cv_file.filename:
        filename = secure_filename(cv_file.filename)
        key = f"kyc/experts/{user_id}/cv_{int(time.time())}_{filename}"
        cv_ct = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        upload_to_s3(cv_file, key, content_type=cv_ct)
        cv_url = key # Store key or signed URL generator? Usually key is better for flexibility

    id_proof_file = request.files.get("id_proof")
    if id_proof_file and id_proof_file.filename:
        filename = secure_filename(id_proof_file.filename)
        key = f"kyc/experts/{user_id}/id_proof_{int(time.time())}_{filename}"
        id_ct = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        upload_to_s3(id_proof_file, key, content_type=id_ct)
        id_proof_url = key

    db.experts.insert_one({
        "user_id":        user_id,
        "name":           name,
        "phone":          phone or None,
        "domain_id":      domain_doc["_id"],
        "domain":         domain_doc["name"],

        "kyc_status":     KYCStatus.PENDING,
        "cv_url":         cv_url,
        "id_proof_url":   id_proof_url,
        "display_name":   name,              # Show full name as provided
        "average_rating": 0.0,
        "review_count":   0,
        "total_earnings": 0.0,
        "quality_score":  0.0,
        "on_time_rate":   0.0,
        "tasks_completed": 0
    })

    # Expert is NOT logged in — must wait for KYC approval
    return jsonify({"message": "Application submitted. You will be notified once approved."}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.get_json()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    db       = get_db()
    user_doc = db.users.find_one({"email": email})

    if (not user_doc
            or not check_password_hash(user_doc["password_hash"], password)
            or user_doc.get("is_banned", False)):
        return jsonify({"error": "Invalid credentials"}), 401

    # Geo-fencing for students: block IN/PK by IP and by stored country
    if user_doc.get("role") == Role.STUDENT:
        # 1. IP-based check (works in production with real IPs)
        if is_blocked_country(get_real_ip()):
            return jsonify({"error": "BLOCKED_REGION"}), 403
        # 2. Country-based check (works locally & catches country field tampering)
        student = db.students.find_one({"user_id": user_doc["_id"]})
        if student and student.get("country") in BLOCKED_COUNTRIES:
            return jsonify({"error": "BLOCKED_REGION"}), 403

    token = create_access_token(
        identity=make_identity(user_doc),
        additional_claims=make_additional_claims(user_doc)
    )
    return jsonify({"token": token, "role": user_doc["role"]}), 200


from app.utils.decorators import role_required

@auth_bp.route("/me", methods=["GET"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def me():
    """Returns current user info from JWT. Used by frontend on page load."""
    uid  = get_jwt_identity()
    db   = get_db()
    user = db.users.find_one({"_id": ObjectId(uid)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id":    str(user["_id"]),
        "email": user["email"],
        "role":  user["role"]
    }), 200


@auth_bp.route("/profile", methods=["GET"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def get_profile():
    uid   = get_jwt_identity()
    role  = get_jwt().get("role")
    db    = get_db()
    
    user = db.users.find_one({"_id": ObjectId(uid)}, {"password_hash": 0})
    if not user:
        return jsonify({"error": "User not found"}), 404

    profile_data = {
        "id":    str(user["_id"]),
        "email": user["email"],
        "role":  user["role"]
    }

    if role == Role.STUDENT:
        p = db.students.find_one({"user_id": ObjectId(uid)})
        if p:
            profile_data.update({
                "name":    p.get("name"),
                "degree":  p.get("degree"),
                "country": p.get("country")
            })
    elif role == Role.EXPERT:
        p = db.experts.find_one({"user_id": ObjectId(uid)})
        if p:
            profile_data.update({
                "name":    p.get("name"),
                "phone":   p.get("phone"),
                "domain":  p.get("domain"),
                "bio":     p.get("bio", ""),
                "kyc":     p.get("kyc_status")
            })
    
    return jsonify(profile_data), 200


@auth_bp.route("/profile", methods=["PUT"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def update_profile():
    uid   = get_jwt_identity()
    role  = get_jwt().get("role")
    data  = request.get_json()
    db    = get_db()

    if role == Role.STUDENT:
        update_fields = {}
        if "name" in data:   update_fields["name"]   = data["name"].strip()
        if "degree" in data: update_fields["degree"] = data["degree"].strip()
        
        if update_fields:
            db.students.update_one({"user_id": ObjectId(uid)}, {"$set": update_fields})

    elif role == Role.EXPERT:
        update_fields = {}
        if "name" in data:
            name = data["name"].strip()
            update_fields["name"] = name
            update_fields["display_name"] = name  # Update display name too
        if "phone" in data: update_fields["phone"] = data["phone"].strip()
        if "bio" in data:   update_fields["bio"]   = data["bio"].strip()
        
        # Domain might be sensitive if they are already approved for a domain
        # But for now let's allow it
        if "domain" in data: update_fields["domain"] = data["domain"].strip()

        if update_fields:
            db.experts.update_one({"user_id": ObjectId(uid)}, {"$set": update_fields})

    return jsonify({"message": "Profile updated successfully"}), 200


@auth_bp.route("/geo-check", methods=["GET"])
def geo_check():
    """Called by the signup page to check if the user's region is blocked."""
    blocked = is_blocked_country(get_real_ip())
    return jsonify({"blocked": blocked}), 200
