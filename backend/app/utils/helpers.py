from bson import ObjectId
import re


def to_str_id(doc):
    """Recursively convert all ObjectId values to strings in a document. Mutates in place."""
    if isinstance(doc, list):
        for i in range(len(doc)):
            doc[i] = to_str_id(doc[i])
    elif isinstance(doc, dict):
        for key, val in doc.items():
            if isinstance(val, ObjectId):
                doc[key] = str(val)
            elif isinstance(val, (dict, list)):
                doc[key] = to_str_id(val)
    elif isinstance(doc, ObjectId):
        return str(doc)
    return doc


def oid(id_str):
    """Safely convert a string to ObjectId. Returns None on failure."""
    try:
        return ObjectId(id_str)
    except Exception:
        return None


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text
