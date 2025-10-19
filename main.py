# Welcome to Cloud Functions for Firebase for Python!
# To get started, simply uncomment the below code or create your own.
# Deploy with `firebase deploy`

from firebase_functions import https_fn
from firebase_functions.options import set_global_options
from openai import OpenAI
import os
import json
import logging
import base64
import uuid
from typing import Tuple

import firebase_bootstrap
import handle.auth

# Optional local .env support (ignored in production). If python-dotenv is installed,
# it will load variables from a local .env file to ease local testing.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

# For cost control, you can set the maximum number of containers that can be
# running at the same time. This helps mitigate the impact of unexpected
# traffic spikes by instead downgrading performance. This limit is a per-function
# limit. You can override the limit for each function using the max_instances
# parameter in the decorator, e.g. @https_fn.on_request(max_instances=5).
set_global_options(max_instances=10)

app = firebase_bootstrap.get_firebase_app()


@https_fn.on_request()
def get_access_token(req: https_fn.Request) -> https_fn.Response:
    return handle.auth.get_access_token(req)


# Expect the OpenAI API key to be provided via environment variable OPENAI_API_KEY.
# In production (Firebase) set it as a secret:
#   firebase functions:secrets:set OPENAI_API_KEY
# Locally either export it or create a .env file with OPENAI_API_KEY=... (never commit the real key).
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.warning("OPENAI_API_KEY not set at import time. Function calls will return 500 until configured.")
    client = None  # Will check inside the handler
else:
    client = OpenAI(api_key=api_key)

OPENAI_TEXT_MODEL = "gpt-4o-mini"  # model for text-only requests
OPENAI_VISION_MODEL = "gpt-4o-mini"  # model for vision (image + text)


@https_fn.on_request(secrets=["OPENAI_API_KEY"])  # Declare secret dependency for deployment
def on_request_example(req: https_fn.Request) -> https_fn.Response:
    global client  # allow updating if it was None initially
    if client is None:
        # Try to pick up the key now (maybe secret became available after cold start)
        late_key = os.getenv("OPENAI_API_KEY")
        if late_key:
            try:
                client = OpenAI(api_key=late_key)
            except Exception as e:  # pragma: no cover (defensive)
                logging.error("Failed late init of OpenAI client: %s", e)
        if client is None:
            return https_fn.Response(
                "OpenAI client not configured: set secret OPENAI_API_KEY (firebase functions:secrets:set OPENAI_API_KEY) and redeploy.",
                status=500
            )
    original = req.args.get("text")
    if original is None:
        return https_fn.Response("No text parameter", status=400)

    try:
        response = client.responses.create(
            model=OPENAI_TEXT_MODEL,  # Adjust model as needed centrally
            input=original
        )
    except Exception as e:
        return https_fn.Response(f"OpenAI request failed: {e}", status=500)

    if hasattr(response, "to_dict"):
        payload = json.dumps(response.to_dict(), ensure_ascii=False)
    elif hasattr(response, "model_dump"):
        payload = json.dumps(response.model_dump(), ensure_ascii=False)
    else:
        payload = json.dumps({"response": str(response)}, ensure_ascii=False)

    return https_fn.Response(payload, status=200, headers={"Content-Type": "application/json"})


# Configurable prompt for look analysis (edit as needed)
ANALYZE_LOOK_PROMPT = (
    "You are a fashion and style assistant. Analyze the uploaded image and describe: "
    "1) clothing items, 2) colors/patterns, 3) overall style, 4) possible improvements. "
    "Be concise."
)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB limit (adjust as needed)

try:
    from werkzeug.utils import secure_filename  # type: ignore
except Exception:
    def secure_filename(name: str) -> str:  # minimal fallback
        return "".join(c for c in name if c.isalnum() or c in ("-", "_", ".")).strip(" ._")


def save_image_stub(image_bytes: bytes, mime: str) -> str:
    """Stub persistence: returns generated ID. Replace with real DB/storage logic."""
    return f"img_{uuid.uuid4().hex}"


def extract_image(req: https_fn.Request) -> Tuple[bytes, str, str]:
    """Extract image file from multipart/form-data request. Raises ValueError on problems."""
    if not getattr(req, "files", None):
        raise ValueError("No files found in request (multipart/form-data required with field 'image').")
    file = req.files.get("image")
    if file is None:
        raise ValueError("Missing file field 'image'.")
    filename = secure_filename(file.filename or "")
    if not filename:
        raise ValueError("Empty filename.")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported extension: {ext}.")
    mime = file.mimetype
    if mime not in ALLOWED_MIME:
        raise ValueError(f"Unsupported MIME type: {mime}.")
    data = file.read()
    if not data:
        raise ValueError("Empty file content.")
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise ValueError("File too large (limit 5MB).")
    return data, filename, mime


@https_fn.on_request(secrets=["OPENAI_API_KEY"])
def analyze_look(req: https_fn.Request) -> https_fn.Response:
    """POST multipart/form-data endpoint: accepts 'image' file (jpg/png/webp), analyzes style via OpenAI."""
    global client
    # Lazy client init if needed
    if client is None:
        late_key = os.getenv("OPENAI_API_KEY")
        if late_key:
            try:
                client = OpenAI(api_key=late_key)
            except Exception as e:
                logging.error("Late OpenAI init failed: %s", e)
        if client is None:
            return https_fn.Response(
                "OpenAI client not configured: set secret OPENAI_API_KEY and redeploy.", status=500
            )

    content_type = req.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        return https_fn.Response("Content-Type must be multipart/form-data", status=400)

    try:
        image_bytes, filename, mime = extract_image(req)
    except ValueError as ve:
        return https_fn.Response(str(ve), status=400)

    # Stub save
    image_id = save_image_stub(image_bytes, mime)

    # Prepare data URL for image (works with models expecting image_url)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"  # fallback representation

    # Build OpenAI vision request input array
    vision_input = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": ANALYZE_LOOK_PROMPT,
                },
                {
                    "type": "input_image",
                    "image_url": data_url,
                }
            ]
        }
    ]

    try:
        response = client.responses.create(
            model=OPENAI_VISION_MODEL,  # vision-capable model (adjust in constant)
            input=vision_input
        )
    except Exception as e:
        logging.exception("OpenAI vision request failed")
        return https_fn.Response(f"OpenAI request failed: {e}", status=500)

    usage = getattr(response, "usage", None)
    # Ensure usage is JSON serializable
    if usage is not None:
        if hasattr(usage, "to_dict"):
            usage_serializable = usage.to_dict()
        elif hasattr(usage, "__dict__"):
            usage_serializable = dict(usage.__dict__)
        else:
            usage_serializable = str(usage)
    else:
        usage_serializable = None

    if hasattr(response, "output_text"):
        analysis = response.output_text
        payload = {"image_id": image_id, "filename": filename, "analysis": analysis, "usage": usage_serializable}
    elif hasattr(response, "to_dict"):
        raw = response.to_dict()
        payload = {"image_id": image_id, "filename": filename, "raw": raw, "usage": usage_serializable}
    else:
        payload = {"image_id": image_id, "filename": filename, "raw": str(response), "usage": usage_serializable}

    logging.log(level=0, msg=f"got payload: {payload}")
    return https_fn.Response(json.dumps(payload, ensure_ascii=False), status=200, headers={"Content-Type": "application/json"})
