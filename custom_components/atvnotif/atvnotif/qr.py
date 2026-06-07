import base64
import json
import re
import io
import logging
from .discover import decode_base58_uuid

_LOGGER = logging.getLogger(__name__)

def parse_qr_json(qr_text: str) -> dict:
    """Decodes and parses the reversed-base64 JSON QR code content."""
    try:
        # First try direct base64 decode of reversed or non-reversed text
        # The TV app reverses bytes and base64 encodes them. 
        # When we base64 decode, we get a reversed JSON string.
        # So we try direct base64 decode, then reverse the string.
        for text_candidate in [qr_text, qr_text[::-1]]:
            # Try to base64 decode
            for pad in ['', '=', '==', '===']:
                try:
                    decoded_bytes = base64.b64decode(text_candidate + pad)
                    # Try both normal and reversed byte order
                    for byte_candidate in [decoded_bytes, decoded_bytes[::-1]]:
                        try:
                            decoded_str = byte_candidate.decode('utf-8')
                            # Check if it looks like JSON
                            if '{' in decoded_str and '}' in decoded_str:
                                # Try parsing
                                data = json.loads(decoded_str)
                                if "ip" in data or "i" in data or "n" in data:
                                    # Convert pairing code to UUID format if present
                                    if "i" in data:
                                        data["pairing_code"] = decode_base58_uuid(data["i"])
                                    return data
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception as e:
        _LOGGER.debug("Failed parsing QR JSON from raw text %s: %s", qr_text, e)
    return None

def decode_qr_image(img_input, try_ocr: bool = True) -> dict:
    """Decodes a QR code from a file path, bytes, or file-like object.
    
    If QR code decoding fails and try_ocr is True, attempts to extract
    the IP address using OCR.
    
    Returns a dict with resolved properties:
    {
        "ip": "192.168.2.104",
        "pairing_code": "60ce69b0-ced7-4872-ba77-66f8dcaf8ba4",
        "name": "Vodafone Vodafone TV 3"
    }
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        raise ImportError("opencv-python and numpy are required to decode QR codes. Run 'pip install opencv-python numpy'")

    # Load image from path or bytes
    img = None
    if isinstance(img_input, str):
        if img_input.startswith(("http://", "https://")):
            try:
                import urllib.request
                req = urllib.request.Request(
                    img_input,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req, timeout=10.0) as response:
                    img_bytes = response.read()
                nparr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            except Exception as e:
                raise ValueError(f"Failed to fetch image from URL {img_input}: {e}")
        else:
            img = cv2.imread(img_input)
    elif isinstance(img_input, bytes):
        nparr = np.frombuffer(img_input, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif hasattr(img_input, "read"):
        img_bytes = img_input.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
    if img is None:
        raise ValueError("Failed to load image from input source")

    # Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Prepare candidates for QR decoding (original, inverted, adaptive threshold, etc.)
    candidates = [
        gray,
        255 - gray,  # Inverted (since TV app shows white-on-black QR code)
    ]
    
    # Try OTSU thresholding
    try:
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        candidates.append(otsu)
        candidates.append(255 - otsu)
    except Exception:
        pass

    # Try decoding with OpenCV QRCodeDetector
    detector = cv2.QRCodeDetector()
    for candidate in candidates:
        try:
            data, bbox, _ = detector.detectAndDecode(candidate)
            if data:
                parsed = parse_qr_json(data)
                if parsed:
                    return parsed
        except Exception:
            pass

    # Fallback 1: Try pyzbar if installed
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        from PIL import Image
        pil_img = Image.fromarray(gray)
        decoded_objs = pyzbar_decode(pil_img)
        for obj in decoded_objs:
            qr_text = obj.data.decode("utf-8")
            parsed = parse_qr_json(qr_text)
            if parsed:
                return parsed
    except ImportError:
        pass
    except Exception as e:
        _LOGGER.debug("pyzbar decoding failed: %s", e)

    # Fallback 2: Try calling zbarimg CLI if available
    # Save a temporary inverted/preprocessed version of the image to pass to zbarimg
    import subprocess
    import tempfile
    import os
    for i, candidate in enumerate(candidates):
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            cv2.imwrite(tmp_path, candidate)
            try:
                res = subprocess.run(["zbarimg", "-q", tmp_path], capture_output=True, text=True)
                if res.returncode == 0:
                    # zbarimg outputs: "QR-Code:<data>"
                    output_text = res.stdout.strip()
                    if output_text.startswith("QR-Code:"):
                        qr_text = output_text[len("QR-Code:"):]
                        parsed = parse_qr_json(qr_text)
                        if parsed:
                            os.remove(tmp_path)
                            return parsed
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        except Exception as e:
            _LOGGER.debug("zbarimg subprocess attempt failed for candidate %d: %s", i, e)

    # OCR Fallback for IP address extraction if QR code decoding failed
    if try_ocr:
        try:
            import pytesseract
            # Try to run OCR on grayscale
            ocr_text = pytesseract.image_to_string(gray)
            # Find IP address pattern
            ip_pattern = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
            match = ip_pattern.search(ocr_text)
            if match:
                return {
                    "ip": match.group(0),
                    "pairing_code": None,
                    "name": None,
                    "ocr_extracted": True
                }
        except ImportError:
            _LOGGER.debug("pytesseract is not installed; OCR fallback skipped.")
        except Exception as e:
            _LOGGER.debug("OCR extraction failed: %s", e)

    raise ValueError("Failed to decode QR code from the image")
