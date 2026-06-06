from flask import request, jsonify, current_app
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from bson import ObjectId
from urllib.parse import quote_plus
import hashlib
import hmac
import secrets
import os, time

from app.blueprints.auth import auth_bp
from app.extensions import get_db
from app.models.user import make_identity, make_additional_claims
from app.services.geo_service import is_blocked_country, get_real_ip
from app.utils.constants import Role, KYCStatus, BLOCKED_COUNTRIES, DOMAINS
from app.utils.helpers import oid


def _canonical_role(raw_role):
    role = (raw_role or "").strip().lower()
    if role in {"superadmin", "super-admin", "super admin", "super_admin"}:
        return Role.SUPER_ADMIN
    return role


def _resolve_user_name(db, user_doc):
    role = _canonical_role(user_doc.get("role"))
    user_id = user_doc["_id"]

    if role == Role.STUDENT:
        student = db.students.find_one({"user_id": user_id}, {"name": 1})
        if student and student.get("name"):
            return student["name"]
    elif role == Role.EXPERT:
        expert = db.experts.find_one({"user_id": user_id}, {"name": 1})
        if expert and expert.get("name"):
            return expert["name"]
    elif role == Role.EMPLOYEE:
        employee = db.employees.find_one({"user_id": user_id}, {"name": 1})
        if employee and employee.get("name"):
            return employee["name"]
    elif role == Role.SUPER_ADMIN:
        super_admin = db.super_admins.find_one({"user_id": user_id}, {"name": 1})
        if super_admin and super_admin.get("name"):
            return super_admin["name"]

    email = user_doc.get("email", "")
    return email.split("@")[0] if "@" in email else "User"


def _hash_reset_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _validate_phone_number(phone):
    """Validate phone number - must contain 10-15 digits and only phone formatting chars"""
    if not phone:
        return True  # Optional field
    import re
    phone = phone.strip()
    if not re.match(r'^[+0-9\s().-]+$', phone):
        return False
    phone_digits = re.sub(r'\D', '', phone)
    return 10 <= len(phone_digits) <= 15


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
    domains = list(db.domains.find({"is_active": {"$ne": False}}))
    domains_by_name = {d["name"]: d for d in domains}
    ordered_domains = [
        {"id": str(domains_by_name[name]["_id"]), "name": name}
        for name in DOMAINS
        if name in domains_by_name
    ]
    return jsonify(ordered_domains), 200

@auth_bp.route("/expert-apply", methods=["POST"])
def expert_apply():
    # Expert apply accepts multipart/form-data for file uploads
    email    = (request.form.get("email") or "").strip().lower()
    name     = (request.form.get("name") or "").strip()
    phone    = (request.form.get("phone") or "").strip()
    whatsapp_number = (request.form.get("whatsapp_number") or "").strip()
    domain_id = (request.form.get("domain") or "").strip()
    password = request.form.get("password") or ""

    if not all([email, name, domain_id, password]):
        return jsonify({"error": "All fields are required"}), 400

    if phone and not _validate_phone_number(phone):
        return jsonify({"error": "Phone number must contain 10-15 digits"}), 400

    if whatsapp_number and not _validate_phone_number(whatsapp_number):
        return jsonify({"error": "WhatsApp number must contain 10-15 digits"}), 400

    cv_file = request.files.get("cv")
    if not cv_file or not cv_file.filename:
        return jsonify({"error": "Resume/CV is required"}), 400

    id_proof_file = request.files.get("id_proof")
    if not id_proof_file or not id_proof_file.filename:
        return jsonify({"error": "ID Proof is required"}), 400

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

    from app.services.file_service import upload_to_s3, delete_from_s3
    import mimetypes

    cv_url = None
    id_proof_url = None
    uploaded_keys = []

    try:
        cv_file = request.files.get("cv")
        if cv_file and cv_file.filename:
            filename = secure_filename(cv_file.filename)
            key = f"kyc/experts/{user_id}/cv_{int(time.time())}_{filename}"
            cv_ct = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            upload_to_s3(cv_file, key, content_type=cv_ct)
            uploaded_keys.append(key)
            cv_url = key

        id_proof_file = request.files.get("id_proof")
        if id_proof_file and id_proof_file.filename:
            filename = secure_filename(id_proof_file.filename)
            key = f"kyc/experts/{user_id}/id_proof_{int(time.time())}_{filename}"
            id_ct = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            upload_to_s3(id_proof_file, key, content_type=id_ct)
            uploaded_keys.append(key)
            id_proof_url = key

        db.experts.insert_one({
            "user_id":        user_id,
            "name":           name,
            "phone":          phone or None,
            "whatsapp_number": whatsapp_number or None,
            "domain_id":      domain_doc["_id"],
            "domain":         domain_doc["name"],

            "kyc_status":     KYCStatus.PENDING,
            "cv_url":         cv_url,
            "id_proof_url":   id_proof_url,
            "display_name":   name,              # Show full name as provided
            "about_me":       "",
            "qualifications": "",
            "average_rating": 0.0,
            "review_count":   0,
            "total_earnings": 0.0,
            "quality_score":  0.0,
            "on_time_rate":   0.0,
            "tasks_completed": 0
        })
    except Exception as e:
        # Roll back user + best-effort storage cleanup to avoid partial expert accounts.
        db.users.delete_one({"_id": user_id})
        for k in uploaded_keys:
            try:
                delete_from_s3(k)
            except Exception:
                pass
        current_app.logger.exception("expert_apply failed during file upload/profile creation")
        return jsonify({"error": f"Expert application failed: {str(e)}"}), 500

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

    # Normalize legacy super-admin role spellings to canonical constants.py value.
    canonical_role = _canonical_role(user_doc.get("role"))
    if canonical_role != user_doc.get("role"):
        db.users.update_one({"_id": user_doc["_id"]}, {"$set": {"role": canonical_role}})
        user_doc["role"] = canonical_role

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

    canonical_role = _canonical_role(user.get("role"))
    if canonical_role != user.get("role"):
        db.users.update_one({"_id": user["_id"]}, {"$set": {"role": canonical_role}})
        user["role"] = canonical_role

    return jsonify({
        "id":    str(user["_id"]),
        "email": user["email"],
        "role":  canonical_role
    }), 200


@auth_bp.route("/profile", methods=["GET"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def get_profile():
    uid   = get_jwt_identity()
    role  = _canonical_role(get_jwt().get("role"))
    db    = get_db()
    
    user = db.users.find_one({"_id": ObjectId(uid)}, {"password_hash": 0})
    if not user:
        return jsonify({"error": "User not found"}), 404

    canonical_role = _canonical_role(user.get("role"))
    if canonical_role != user.get("role"):
        db.users.update_one({"_id": user["_id"]}, {"$set": {"role": canonical_role}})
        user["role"] = canonical_role

    profile_data = {
        "id":    str(user["_id"]),
        "email": user["email"],
        "role":  canonical_role,
        "name":  _resolve_user_name(db, user),
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
            domain_name = p.get("domain")
            if p.get("domain_id"):
                domain_doc = db.domains.find_one({"_id": oid(p["domain_id"])})
                if domain_doc:
                    domain_name = domain_doc["name"]
            profile_data.update({
                "name":    p.get("name"),
                "phone":   p.get("phone"),
                "domain":  domain_name,
                "domain_id": str(p.get("domain_id")) if p.get("domain_id") else None,
                "bio":     p.get("bio", ""),
                "about_me": p.get("about_me") or p.get("bio", ""),
                "qualifications": p.get("qualifications", ""),
                "kyc":     p.get("kyc_status")
            })
    elif role == Role.EMPLOYEE:
        p = db.employees.find_one({"user_id": ObjectId(uid)})
        if p:
            profile_data.update({
                "name": p.get("name")
            })
    elif role == Role.SUPER_ADMIN:
        p = db.super_admins.find_one({"user_id": ObjectId(uid)})
        if p:
            profile_data.update({
                "name": p.get("name")
            })
    
    return jsonify(profile_data), 200


@auth_bp.route("/profile", methods=["PUT"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def update_profile():
    uid   = get_jwt_identity()
    role  = _canonical_role(get_jwt().get("role"))
    data  = request.get_json() or {}
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
        if "phone" in data:
            phone = data["phone"].strip()
            if phone and not _validate_phone_number(phone):
                return jsonify({"error": "Phone number must contain 10-15 digits"}), 400
            update_fields["phone"] = phone
        if "whatsapp_number" in data:
            whatsapp_number = data["whatsapp_number"].strip()
            if whatsapp_number and not _validate_phone_number(whatsapp_number):
                return jsonify({"error": "WhatsApp number must contain 10-15 digits"}), 400
            update_fields["whatsapp_number"] = whatsapp_number
        if "bio" in data:   update_fields["bio"]   = data["bio"].strip()
        if "about_me" in data:
            about_me = data["about_me"].strip()
            update_fields["about_me"] = about_me
            update_fields["bio"] = about_me
        if "qualifications" in data:
            update_fields["qualifications"] = data["qualifications"].strip()

        # Domain update: accepts domain_id (preferred) or domain (fallback string)
        if "domain_id" in data and data["domain_id"]:
            try:
                domain_doc = db.domains.find_one({"_id": oid(data["domain_id"])})
                if domain_doc:
                    update_fields["domain_id"] = domain_doc["_id"]
                    update_fields["domain"] = domain_doc["name"]
            except Exception:
                return jsonify({"error": "Invalid domain selected"}), 400
        elif "domain" in data and data["domain"]:
            domain_name = data["domain"].strip()
            import re
            domain_doc = db.domains.find_one({"name": {"$regex": f"^{re.escape(domain_name)}$", "$options": "i"}})
            if domain_doc:
                update_fields["domain_id"] = domain_doc["_id"]
                update_fields["domain"] = domain_doc["name"]
            else:
                update_fields["domain"] = domain_name

        if update_fields:
            db.experts.update_one({"user_id": ObjectId(uid)}, {"$set": update_fields})
    elif role == Role.EMPLOYEE:
        name = (data.get("name") or "").strip()
        if name:
            db.employees.update_one({"user_id": ObjectId(uid)}, {"$set": {"name": name}})
    elif role == Role.SUPER_ADMIN:
        name = (data.get("name") or "").strip()
        if name:
            db.super_admins.update_one(
                {"user_id": ObjectId(uid)},
                {"$set": {"name": name}, "$setOnInsert": {"user_id": ObjectId(uid)}},
                upsert=True,
            )

    return jsonify({"message": "Profile updated successfully"}), 200


@auth_bp.route("/change-password", methods=["POST"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def change_password():
    uid = get_jwt_identity()
    data = request.get_json() or {}

    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not all([current_password, new_password, confirm_password]):
        return jsonify({"error": "Current password, new password, and confirm password are required"}), 400
    if new_password != confirm_password:
        return jsonify({"error": "New password and confirm password do not match"}), 400
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400
    if new_password == current_password:
        return jsonify({"error": "New password must be different from current password"}), 400

    db = get_db()
    user = db.users.find_one({"_id": ObjectId(uid)})
    if not user:
        return jsonify({"error": "User not found"}), 404
    if not check_password_hash(user.get("password_hash", ""), current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    db.users.update_one(
        {"_id": ObjectId(uid)},
        {
            "$set": {
                "password_hash": generate_password_hash(new_password),
                "password_changed_at": datetime.utcnow(),
            },
            "$unset": {
                "password_reset_token_hash": "",
                "password_reset_expires_at": "",
                "password_reset": "",
            },
        },
    )

    # Best-effort email notification; password is updated regardless of email provider state.
    try:
        from app.services.email_service import send_password_changed_email

        send_password_changed_email(
            user_email=user["email"],
            user_name=_resolve_user_name(db, user),
            role=_canonical_role(user.get("role")),
        )
    except Exception:
        pass

    return jsonify({"message": "Password changed successfully"}), 200


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    generic_msg = {"message": "If this email exists, a reset link was sent."}

    # Always return a generic success message to prevent email enumeration.
    if not email:
        return jsonify(generic_msg), 200

    db = get_db()
    user = db.users.find_one({"email": email})
    if not user:
        return jsonify(generic_msg), 200

    raw_token = secrets.token_urlsafe(32)
    hashed_token = _hash_reset_token(raw_token)
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_reset": {
                    "token": hashed_token,
                    "expires_at": expires_at,
                    "requested_at": datetime.utcnow(),
                }
            }
        },
    )

    frontend_base = (
        current_app.config.get("FRONTEND_URL")
        or os.environ.get("FRONTEND_URL")
        or request.headers.get("Origin")
        or ""
    ).rstrip("/")
    if not frontend_base:
        # Final local fallback for dev if neither config/env nor Origin is available.
        frontend_base = "http://localhost:5001"
    reset_link = f"{frontend_base}/auth/reset-password.html?token={raw_token}&email={quote_plus(email)}"

    try:
        from app.services.email_service import send_password_reset_email

        send_password_reset_email(
            user_email=email,
            user_name=_resolve_user_name(db, user),
            reset_link=reset_link,
            minutes_valid=15,
        )
    except Exception:
        pass

    return jsonify(generic_msg), 200


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}

    email = (data.get("email") or "").strip().lower()
    raw_token = (data.get("token") or "").strip()
    new_password = data.get("new_password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not all([email, raw_token, new_password, confirm_password]):
        return jsonify({"error": "Invalid request"}), 400
    if new_password != confirm_password:
        return jsonify({"error": "New password and confirm password do not match"}), 400
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    db = get_db()
    user = db.users.find_one({"email": email})
    if not user:
        return jsonify({"error": "Invalid or expired token"}), 400

    reset_data = user.get("password_reset") or {}
    stored_hashed_token = reset_data.get("token")
    expires_at = reset_data.get("expires_at")

    if not stored_hashed_token or not expires_at:
        return jsonify({"error": "Invalid or expired token"}), 400

    if datetime.utcnow() > expires_at:
        db.users.update_one({"_id": user["_id"]}, {"$unset": {"password_reset": ""}})
        return jsonify({"error": "Invalid or expired token"}), 400

    hashed_input = _hash_reset_token(raw_token)
    if not hmac.compare_digest(hashed_input, stored_hashed_token):
        return jsonify({"error": "Invalid or expired token"}), 400

    if check_password_hash(user.get("password_hash", ""), new_password):
        return jsonify({"error": "New password must be different from current password"}), 400

    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": generate_password_hash(new_password),
                "password_changed_at": datetime.utcnow(),
            },
            "$unset": {"password_reset": ""},
        },
    )

    try:
        from app.services.email_service import send_password_changed_email

        send_password_changed_email(
            user_email=user["email"],
            user_name=_resolve_user_name(db, user),
            role=_canonical_role(user.get("role")),
        )
    except Exception:
        pass

    return jsonify({"message": "Password reset successfully"}), 200


@auth_bp.route("/geo-check", methods=["GET"])
def geo_check():
    """Called by the signup page to check if the user's region is blocked."""
    blocked = is_blocked_country(get_real_ip())
    return jsonify({"blocked": blocked}), 200
