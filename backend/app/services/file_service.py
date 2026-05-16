import os
from flask import current_app, url_for


def upload_to_s3(file_obj, key, content_type=None):
    import boto3
    import mimetypes
    s3 = boto3.client(
        "s3",
        aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
        region_name=current_app.config["AWS_REGION"],
    )
    # Determine content type from key/filename if not provided
    if not content_type:
        guessed = mimetypes.guess_type(key)[0]
        content_type = guessed if guessed else "application/octet-stream"

    extra_args = {"ContentType": content_type}
    s3.upload_fileobj(file_obj, current_app.config["AWS_S3_BUCKET"], key, ExtraArgs=extra_args)
    return key


def get_signed_url(key, expiry=3600, filename=None, content_type=None):
    import boto3
    s3 = boto3.client(
        "s3",
        aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
        region_name=current_app.config["AWS_REGION"],
    )
    
    params = {"Bucket": current_app.config["AWS_S3_BUCKET"], "Key": key}
    
    disposition = "inline"
    if filename:
        disposition += f'; filename="{filename}"'
    params["ResponseContentDisposition"] = disposition
    
    if content_type:
        params["ResponseContentType"] = content_type
        
    return s3.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expiry,
    )


def delete_from_s3(key):
    """Delete an object from S3 by its key. Silently ignores missing keys."""
    import boto3
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
            region_name=current_app.config["AWS_REGION"],
        )
        s3.delete_object(
            Bucket=current_app.config["AWS_S3_BUCKET"],
            Key=key
        )
        current_app.logger.info(f"[S3] Deleted preview object: {key}")
    except Exception as e:
        current_app.logger.error(f"[S3] Failed to delete {key}: {e}")
