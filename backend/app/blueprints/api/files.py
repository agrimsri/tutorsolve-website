from flask import request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename
from flask_jwt_extended import get_jwt_identity
from datetime import datetime
import uuid
import os
import io
import time
import mimetypes

from app.blueprints.api import api_bp
from app.extensions import get_db
from app.utils.decorators import expert_required, role_required, student_required
from app.utils.constants import Role
from app.utils.helpers import oid
from app.services.file_service import upload_to_s3, get_signed_url

@api_bp.route("/files/upload", methods=["POST"])
@student_required
def upload_student_file():
    """
    Generic upload for students (e.g. during question posting).
    """
    uid = get_jwt_identity()
    
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "No file provided"}), 400

    filename = secure_filename(uploaded.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_bytes = uploaded.read()
    
    # Pattern: student_attachments/{uid}/{timestamp}_{filename}
    timestamp = int(time.time())
    key = f"student_attachments/{uid}/{timestamp}_{filename}"
    db = get_db()
    content_type = mimetypes.guess_type(uploaded.filename)[0] or "application/octet-stream"
    upload_to_s3(io.BytesIO(file_bytes), key, content_type=content_type)
    result = db.files.insert_one({
        "question_id":       None, # To be linked
        "student_user_id":   oid(uid),
        "uploader_role":     "student",
        "category":          "attachment",
        "original_filename": uploaded.filename,
        "s3_key":            key,
        "file_type":         ext,
        "is_locked":         False, # Student files are never locked
        "uploaded_at":       datetime.utcnow()
    })
    
    return jsonify({"file_id": str(result.inserted_id)}), 201


@api_bp.route("/files/upload/<question_id>", methods=["POST"])
@expert_required
def upload_solution(question_id):
    
    uid    = get_jwt_identity()
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "No file provided"}), 400

    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    if not expert:
        return jsonify({"error": "Expert record not found"}), 404
        
    # Security: allow upload while task is active (including reviewing, for iterative submissions)
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question or question.get("status") not in ("in_progress", "advance_paid", "reviewing"):
        return jsonify({"error": "Cannot upload files to this task at this stage"}), 403
        
    filename = secure_filename(uploaded.filename)
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_bytes = uploaded.read()
    
    timestamp = int(time.time())
    expert_id_str = str(expert["_id"])
    
    # Naming: solutions/{question_id}/{expert_id}/{timestamp}_{filename}
    base_path = f"solutions/{question_id}/{expert_id_str}"
    key       = f"{base_path}/{timestamp}_{filename}"
    content_type = mimetypes.guess_type(uploaded.filename)[0] or "application/octet-stream"
    upload_to_s3(io.BytesIO(file_bytes), key, content_type=content_type)
    
    # Preview Generation using consolidated service
    import tempfile
    import traceback
    preview_key = None
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_original = os.path.join(tmpdir, filename)
            with open(temp_original, "wb") as f:
                f.write(file_bytes)
                
            from app.services.preview_service import generate_preview
            preview_result = generate_preview(temp_original)
            
            current_app.logger.info(f"[Files] preview_result for {filename}: {preview_result}")
            
            if isinstance(preview_result, str) and os.path.exists(preview_result):
                p_ext = os.path.splitext(preview_result)[1].lower().strip(".")
                preview_key = f"{base_path}/preview_{timestamp}_{filename}.{p_ext}"
                with open(preview_result, "rb") as f:
                    preview_ct = mimetypes.guess_type(preview_key)[0] or "image/png"
                    upload_to_s3(f, preview_key, content_type=preview_ct)
                current_app.logger.info(f"[Files] Preview uploaded to S3: {preview_key}")
            elif isinstance(preview_result, dict):
                current_app.logger.info(f"[Files] Preview not possible: {preview_result.get('message')}")
    except Exception as pe:
        current_app.logger.error(f"[Files] Preview generation exception: {str(pe)}")
        current_app.logger.error(traceback.format_exc())
        # We continue even if preview fails, to allow the main upload to succeed
        
    result = db.files.insert_one({
        "question_id":       oid(question_id),
        "expert_id":         expert["_id"],
        "uploader_role":     "expert",
        "category":          "solution",
        "original_filename": uploaded.filename,
        "s3_key":            key,
        "preview_s3_key":    preview_key,
        "file_type":         ext,
        "is_locked":         True,
        "uploaded_at":       datetime.utcnow(),
        "forwarded_at":      None
    })
    
    # Note: Status update and notifications moved to explicit /submit route per user request
    return jsonify({
        "file_id": str(result.inserted_id),
        "has_preview": bool(preview_key)
    }), 201


@api_bp.route("/files/<file_id>/url", methods=["GET"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def get_file_url(file_id):
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    role   = claims.get("role")
    uid    = get_jwt_identity()

    db   = get_db()
    file = db.files.find_one({"_id": oid(file_id)})
    if not file:
        return jsonify({"error": "File record not found"}), 404

    # Enforcement of visibility
    question = db.questions.find_one({"_id": file["question_id"]})
    uploader_role = file.get("uploader_role", "expert")
    is_solution   = uploader_role == "expert"

    if is_solution:
        if role == Role.STUDENT and not file.get("forwarded_at"):
            return jsonify({"error": "Access denied. File not shared with student yet."}), 403
        if role in (Role.EMPLOYEE, Role.SUPER_ADMIN):
            if question and question.get("status") in ("in_progress", "advance_paid", "pending_payment", "awaiting_quote"):
                return jsonify({"error": "Access denied. Expert has not submitted solution yet."}), 403
        if role == Role.EXPERT:
            expert_p = db.experts.find_one({"user_id": oid(uid)})
            if not expert_p or str(file.get("expert_id")) != str(expert_p["_id"]):
                return jsonify({"error": "Access denied. Not your file."}), 403

    is_locked = file.get("is_locked", False)
    if is_locked:
        key = file.get("preview_s3_key")
        if not key:
            return jsonify({"error": "Preview not available for this file type. Pay to unlock full file."}), 404
        current_app.logger.info(
            f"[FileURL] Serving PREVIEW for file {file_id}: key={key}, "
            f"forwarded_at={file.get('forwarded_at')}, role={role}"
        )
    else:
        key = file.get("s3_key")
        current_app.logger.info(
            f"[FileURL] Serving FULL file {file_id}: key={key}, role={role}"
        )

    if not key:
        return jsonify({"error": "File content not found"}), 404

    import mimetypes
    filename = file.get("original_filename", "file")
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    url = get_signed_url(key, filename=filename, content_type=content_type)
    return jsonify({"url": url, "locked": is_locked}), 200


@api_bp.route("/files/<file_id>/unlock", methods=["POST"])
@role_required(Role.STUDENT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def unlock_file(file_id):
    db   = get_db()
    file = db.files.find_one({"_id": oid(file_id)})
    if not file:
        return jsonify({"error": "File not found"}), 404

    from app.services.diamond_engine import unlock_all_solutions
    unlock_all_solutions(str(file["question_id"]))
    return jsonify({"status": "unlocked"}), 200

@api_bp.route("/files/question/<question_id>", methods=["GET"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def get_files_for_question(question_id):
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    role   = claims.get("role")
    uid    = get_jwt_identity()
    
    db    = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404
        
    files = list(db.files.find({"question_id": oid(question_id)}))
    
    filtered_files = []
    for f in files:
        uploader_role = f.get("uploader_role", "student" if f.get("student_user_id") else "expert")
        is_solution   = uploader_role == "expert"
        
        # Visibility Logic
        visible = False
        
        if role in (Role.EMPLOYEE, Role.SUPER_ADMIN):
            # Admin sees all student files
            if not is_solution:
                visible = True
            else:
                # Admin sees expert files only if expert has submitted (status is NOT in_progress/advance_paid)
                if question.get("status") not in ("in_progress", "advance_paid", "pending_payment", "awaiting_quote"):
                    visible = True
                    
        elif role == Role.EXPERT:
            expert_p = db.experts.find_one({"user_id": oid(uid)})
            # Expert sees all student files
            if not is_solution:
                visible = True
            # Expert sees their OWN solution files
            elif expert_p and str(f.get("expert_id")) == str(expert_p["_id"]):
                visible = True
                
        elif role == Role.STUDENT:
            # Student sees their OWN files
            if not is_solution:
                visible = True
            # Student sees expert files ONLY if admin has explicitly forwarded them.
            # Status==completed alone does NOT grant access — admin must forward first.
            elif f.get("forwarded_at") or not f.get("is_locked", True):
                visible = True
        
        if visible:
            filtered_files.append({
                "_id":               str(f["_id"]),
                "original_filename": f["original_filename"],
                "file_type":         f["file_type"],
                "is_locked":         f.get("is_locked", False),
                "has_preview":       bool(f.get("preview_s3_key")),
                "uploader_role":     uploader_role,
                "uploader_type":     uploader_role,
                "category":          f.get("category", "attachment" if not is_solution else "solution"),
                "uploaded_at":       str(f["uploaded_at"]),
                "forwarded_at":      str(f["forwarded_at"]) if f.get("forwarded_at") else None
            })
            
    return jsonify(filtered_files), 200


@api_bp.route("/files/<file_id>", methods=["DELETE"])
@expert_required
def delete_file(file_id):
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    
    file = db.files.find_one({"_id": oid(file_id)})
    if not file:
        return jsonify({"error": "File not found"}), 404
        
    # Security: only the uploader (expert) can delete their own solution files
    if str(file.get("expert_id")) != str(expert["_id"]):
        return jsonify({"error": "Access denied"}), 403
        
    # Only allowed while the task is still active (including reviewing for iterative work)
    question = db.questions.find_one({"_id": file["question_id"]})
    if question and question.get("status") not in ["in_progress", "advance_paid", "reviewing"]:
        return jsonify({"error": "Cannot delete files after completion"}), 400

    db.files.delete_one({"_id": oid(file_id)})
    return jsonify({"status": "deleted"}), 200

@api_bp.route("/files/<file_id>/forward", methods=["POST"])
@role_required(Role.EMPLOYEE, Role.SUPER_ADMIN)
def forward_file(file_id):
    db = get_db()
    file = db.files.find_one({"_id": oid(file_id)})
    if not file:
        return jsonify({"error": "File not found"}), 404
        
    db.files.update_one(
        {"_id": oid(file_id)},
        {"$set": {"forwarded_at": datetime.utcnow()}}
    )
    
    # Notify student
    question = db.questions.find_one({"_id": file["question_id"]})
    if question:
        student = db.students.find_one({"_id": question["student_id"]})
        if student:
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(student["user_id"]),
                notif_type="solution_forwarded",
                title="Expert Solution Shared",
                body=f"Admin has shared a solution for: {question['title']}",
                link=f"/student/order-detail.html?id={file['question_id']}"
            )

    return jsonify({"status": "forwarded"}), 200
