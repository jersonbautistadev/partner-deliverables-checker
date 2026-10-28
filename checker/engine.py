"""Pure, framework-independent rules and bounded upload inspection.

No network requests, subprocesses, Office rendering, or archive extraction.
"""

import hashlib
import io
import json
import re
import struct
import unicodedata
import warnings
import zipfile
import zlib
from pathlib import PurePosixPath
from xml.etree import ElementTree

from PIL import Image, UnidentifiedImageError

ENGINE_VERSION = "1.0.0"
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAX_DOCX_EXPANDED = 20 * 1024 * 1024
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TEXT_SLOTS = {"article", "caption"}
IMAGE_SLOTS = {"image", "logo"}


class InvalidUpload(ValueError):
    pass


def word_count(text):
    """Letters/digits; internal apostrophes and hyphens keep a word together."""
    return len(re.findall(r"[^\W_]+(?:['’\-][^\W_]+)*", unicodedata.normalize("NFKC", text)))


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def safe_xml(data):
    # Reject DTDs/entities before parsing, including UTF-16/32 encodings.
    if b"<!DOCTYPE" in data.replace(b"\x00", b"").upper() or b"<!ENTITY" in data.replace(b"\x00", b"").upper():
        raise InvalidUpload("DOCX XML contains a prohibited DTD/entity declaration.")
    try:
        return ElementTree.fromstring(data)
    except (ElementTree.ParseError, LookupError, ValueError) as exc:
        raise InvalidUpload("DOCX contains invalid XML.") from exc


def docx_text(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            parts = archive.infolist()
            names = [p.filename for p in parts]
            if len(parts) > 200 or len(names) != len(set(names)):
                raise InvalidUpload("DOCX has too many parts or duplicate entries.")
            if sum(p.file_size for p in parts) > MAX_DOCX_EXPANDED:
                raise InvalidUpload("Expanded DOCX exceeds 20 MiB.")
            for p in parts:
                path = PurePosixPath(p.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in p.filename or p.flag_bits & 1:
                    raise InvalidUpload("DOCX contains unsafe paths or encrypted entries.")
                if any(x in p.filename.lower() for x in ["vbaproject", "embeddings/", "activex/"]):
                    raise InvalidUpload("Macros, embedded objects and ActiveX are unsupported.")
                if p.filename.endswith(".rels"):
                    root = safe_xml(archive.read(p))
                    if any(e.get("TargetMode", "").lower() == "external" for e in root.iter()):
                        raise InvalidUpload("External DOCX relationships are unsupported; use plain text.")
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise InvalidUpload("Not a supported Word DOCX document.")
            content_types = archive.read("[Content_Types].xml")
            if b"macroEnabled" in content_types:
                raise InvalidUpload("Macro-enabled Word files are unsupported.")
            types = safe_xml(content_types)
            document_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
            if not any(e.get("PartName") == "/word/document.xml" and e.get("ContentType") == document_type for e in types):
                raise InvalidUpload("DOCX must declare the supported Word document content type.")
            document = safe_xml(archive.read("word/document.xml"))
            if document.tag != WORD_NS + "document":
                raise InvalidUpload("Unsupported Word document namespace.")
            body = document.find(WORD_NS + "body")
            if body is None:
                raise InvalidUpload("DOCX is missing its document body.")
            unsupported = {WORD_NS + x for x in ["ins", "del", "altChunk", "txbxContent", "fldChar", "instrText"]}
            if any(e.tag in unsupported for e in body.iter()):
                raise InvalidUpload("Accept tracked changes and remove fields/text boxes, or upload plain text.")
            paragraphs = []
            for paragraph in body.iter(WORD_NS + "p"):
                paragraphs.append("".join(
                    (e.text or "") if e.tag == WORD_NS + "t" else " "
                    for e in paragraph.iter()
                    if e.tag in {WORD_NS + "t", WORD_NS + "tab", WORD_NS + "br"}
                ))
            return "\n".join(paragraphs)
    except (zipfile.BadZipFile, KeyError, RuntimeError, NotImplementedError, EOFError, zlib.error) as exc:
        raise InvalidUpload("Invalid or unsupported DOCX archive.") from exc


def inspect_upload(name, data, slot):
    if not data:
        raise InvalidUpload("The uploaded file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise InvalidUpload("Each file must be at most 5 MiB.")
    ext = PurePosixPath(name).suffix.lower()
    metadata = {"extension": ext}
    if slot in TEXT_SLOTS:
        if ext == ".txt":
            if len(data) > MAX_TEXT_BYTES:
                raise InvalidUpload("Plain text must be at most 2 MiB.")
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise InvalidUpload("Plain text must be UTF-8 encoded.") from exc
            if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
                raise InvalidUpload("Plain text contains binary control characters.")
        elif ext == ".docx":
            text = docx_text(data)
        else:
            raise InvalidUpload("Article/caption slots accept only .txt and .docx.")
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise InvalidUpload("Extracted text must be at most 2 MiB.")
        if not text.strip():
            raise InvalidUpload("The document contains no supported body text.")
        metadata.update(text=text, words=word_count(text))
    elif slot in IMAGE_SLOTS:
        expected = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}.get(ext)
        if not expected:
            raise InvalidUpload("Image/logo slots accept only JPG and PNG.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data), formats=["JPEG", "PNG"]) as image:
                    if image.format != expected:
                        raise InvalidUpload("Image contents do not match the filename extension.")
                    width, height = image.size
                    if width * height > MAX_PIXELS:
                        raise InvalidUpload("Images must not exceed 20 megapixels.")
                    if getattr(image, "n_frames", 1) != 1:
                        raise InvalidUpload("Animated images are unsupported.")
                    image.verify()
                with Image.open(io.BytesIO(data), formats=["JPEG", "PNG"]) as image:
                    image.load()  # detect truncated images, not only valid headers
            metadata.update(width=width, height=height)
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError, struct.error,
                Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            if isinstance(exc, InvalidUpload):
                raise
            raise InvalidUpload("Invalid, truncated or excessively large image.") from exc
    else:
        raise InvalidUpload("Unknown submission slot.")
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "metadata": metadata}


def validate_rule(kind, slot, config):
    if slot not in TEXT_SLOTS | IMAGE_SLOTS:
        raise ValueError("Choose a supported file slot.")
    if not isinstance(config, dict):
        raise ValueError("Rule configuration must be an object.")
    if kind == "word_count":
        if slot not in TEXT_SLOTS:
            raise ValueError("Word counts require an article or caption slot.")
        lo, hi = config.get("min"), config.get("max")
        if lo is None and hi is None:
            raise ValueError("Enter at least one word-count bound.")
        if any(v is not None and (type(v) is not int or not 0 <= v <= 100000) for v in [lo, hi]):
            raise ValueError("Word bounds must be integers from 0 to 100,000.")
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("Minimum words cannot exceed maximum words.")
    elif kind == "dimensions":
        if slot not in IMAGE_SLOTS:
            raise ValueError("Dimensions require an image or logo slot.")
        if any(type(config.get(k)) is not int or config[k] < 1 for k in ["width", "height"]):
            raise ValueError("Enter positive integer width and height.")
        if config["width"] * config["height"] > MAX_PIXELS:
            raise ValueError("Configured dimensions exceed the 20 megapixel upload limit.")
    elif kind == "required_phrase":
        if slot not in TEXT_SLOTS or not isinstance(config.get("phrase"), str) or not config["phrase"].strip():
            raise ValueError("Enter a nonempty phrase for an article or caption.")
        if len(config["phrase"]) > 500:
            raise ValueError("Required phrase must be at most 500 characters.")
    elif kind not in {"manual", "required_file"}:
        raise ValueError("Unknown rule type; coordinator review required.")


def evaluate(rule, asset):
    """Return one finding. Bounds are inclusive. Unapproved rules never pass."""
    def result(status, message):
        return {"status": status, "message": message}

    if not rule["approved"] or rule["ambiguous"]:
        return result("needs_review", "Coordinator must clarify and approve this requirement.")
    kind, config = rule["kind"], rule["config"]
    try:
        validate_rule(kind, rule["slot"], config)
    except ValueError as exc:
        return result("needs_review", str(exc))
    if asset is None:
        return result("missing", f"Upload a file in the {rule['slot']} slot.")
    if kind == "required_file":
        return result("passed", "Required file is present and passed upload validation.")
    if kind == "manual":
        return result("needs_review", "Coordinator must inspect the file and record a decision.")
    metadata = asset["metadata"]
    if kind == "word_count":
        actual = metadata["words"]
        lo, hi = config.get("min"), config.get("max")
        passed = (lo is None or actual >= lo) and (hi is None or actual <= hi)
        return result("passed" if passed else "failed",
                      f"Found {actual} words. Inclusive range: {lo if lo is not None else 0} to {hi if hi is not None else 'no upper limit'}.")
    if kind == "dimensions":
        width, height = metadata["width"], metadata["height"]
        passed = (width, height) == (config["width"], config["height"])
        return result("passed" if passed else "failed",
                      f"Found {width} × {height} px. Required: {config['width']} × {config['height']} px (exact).")
    phrase = config["phrase"]
    passed = normalized(phrase) in normalized(metadata["text"])
    return result("passed" if passed else "failed",
                  f"Required phrase {'found' if passed else 'not found'}: {phrase!r}. Case-insensitive, whitespace-normalized match.")


def fingerprint(requirements, assets):
    payload = {"engine": ENGINE_VERSION, "requirements": requirements, "assets": assets}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()
