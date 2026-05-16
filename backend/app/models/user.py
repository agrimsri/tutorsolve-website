"""
JWT identity helpers.
The 'identity' payload embedded in every JWT token.
"""


def make_identity(user_doc):
    """Return the user's string ID as the JWT subject (flask-jwt-extended v4 requires a string)."""
    return str(user_doc["_id"])


def make_additional_claims(user_doc):
    """Return extra claims to embed in the JWT (accessible via get_jwt())."""
    return {"role": user_doc["role"]}
