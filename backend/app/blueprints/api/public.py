from flask import jsonify, request
from app.blueprints.api import api_bp
from app.extensions import get_db
from app.utils.constants import KYCStatus
from app.utils.helpers import oid


@api_bp.route("/public/experts", methods=["GET"])
def public_experts():
    """
    Public endpoint — no auth required.
    Returns approved experts with anonymized display info.
    """
    db      = get_db()
    domain  = request.args.get("domain")  # Optional domain filter

    query = {"kyc_status": KYCStatus.APPROVED}
    if domain:
        query["domain"] = {"$regex": f"^{domain}$", "$options": "i"}

    experts = list(
        db.experts.find(query)
        .sort("average_rating", -1)  # Highest rated first
        .limit(50)
    )

    result = []
    for e in experts:
        result.append({
            "_id":            str(e["_id"]),
            "display_name":   e.get("display_name", "Expert"),
            "domain":         e["domain"],
            "average_rating": e.get("average_rating", 0.0),
            "review_count":   e.get("review_count", 0),
            "tasks_completed": e.get("tasks_completed", 0),
            "quality_score":  e.get("quality_score", 0.0),
            # Never expose: name, email, phone, user_id, cv_url, id_proof_url
        })

    return jsonify(result), 200


@api_bp.route("/public/experts/<expert_id>/reviews", methods=["GET"])
def expert_reviews(expert_id):
    """
    Public endpoint — no auth required.
    Returns all visible reviews for an expert.
    """
    db      = get_db()
    page    = int(request.args.get("page", 1))
    per_page = 10
    skip    = (page - 1) * per_page

    reviews = list(
        db.reviews.find({
            "expert_id":  oid(expert_id),
            "$or": [{"is_visible": True}, {"is_visible": {"$exists": False}}]
        })
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
    )

    total = db.reviews.count_documents({
        "expert_id":  oid(expert_id),
        "$or": [{"is_visible": True}, {"is_visible": {"$exists": False}}]
    })

    result = []
    for r in reviews:
        # Get question title for context
        question = db.questions.find_one({"_id": r["question_id"]})
        result.append({
            "_id":         str(r["_id"]),
            "rating":      r["rating"],
            "review_text": r.get("review_text"),
            "domain":      question["domain"] if question else "—",
            "created_at":  str(r["created_at"]),
            # Never expose: student_id, question_id, expert_id
        })

    return jsonify({
        "reviews":      result,
        "total":        total,
        "page":         page,
        "has_more":     (skip + per_page) < total
    }), 200

@api_bp.route("/public/reviews", methods=["GET"])
def recent_reviews():
    """
    Public endpoint — no auth required.
    Returns recent visible reviews across all experts.
    """
    db      = get_db()
    limit   = int(request.args.get("limit", 3))

    reviews = list(
        db.reviews.find({"is_visible": True})
        .sort("created_at", -1)
        .limit(limit)
    )

    result = []
    for r in reviews:
        # Get expert info
        expert = db.experts.find_one({"_id": r["expert_id"]})
        
        # Get question info
        question = db.questions.find_one({"_id": r["question_id"]})
        
        # Get student info
        student = db.students.find_one({"_id": r["student_id"]}) if "student_id" in r else None
        
        result.append({
            "_id":         str(r["_id"]),
            "rating":      r["rating"],
            "review_text": r.get("review_text"),
            "domain":      question["domain"] if question else "—",
            "expert_name": expert.get("display_name", "Expert") if expert else "Expert",
            "student_name": student.get("name") if student else "Student",
            "created_at":  str(r["created_at"]),
        })

    return jsonify(result), 200

@api_bp.route("/public/stats", methods=["GET"])
def public_stats():
    """
    Public endpoint to get high-level platform statistics for the landing page.
    """
    db = get_db()
    # Active experts count
    active_experts = db.experts.count_documents({"kyc_status": KYCStatus.APPROVED})
    
    # Questions solved
    total_solved = db.questions.count_documents({"status": "completed"})
    
    return jsonify({
        "active_experts": active_experts,
        "total_solved": total_solved
    }), 200

