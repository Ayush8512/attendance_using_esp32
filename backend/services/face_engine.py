import io
import logging
from typing import List, Tuple
import numpy as np
from PIL import Image, ImageOps

try:
    import face_recognition
    USE_REAL_FR = True
except ImportError:
    USE_REAL_FR = False

logger = logging.getLogger("attendance.face_engine")

from config import FACE_MATCH_TOLERANCE

def load_and_orient_image(contents: bytes) -> np.ndarray:
    """
    Load an image from bytes, apply EXIF auto-transpose (fixes portrait mobile camera orientation),
    downscale large images to max 800x800 for FAST processing, ensure RGB format, 
    and convert to numpy array for dlib/face_recognition.
    """
    pil_img = Image.open(io.BytesIO(contents))
    pil_img = ImageOps.exif_transpose(pil_img)
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    
    pil_img.thumbnail((800, 800), Image.Resampling.LANCZOS)
    return np.array(pil_img)


async def extract_face_encoding(contents: bytes, is_registration: bool = False) -> List[float]:
    """
    Extract the first 128-d face encoding.
    (Note: Moved contents reading to route layer so file read is explicit)
    """
    if not contents:
        raise ValueError("Uploaded image is empty. Please capture a valid face photo.")

    if not USE_REAL_FR:
        raise ValueError("Face recognition engine is not installed on the server. Please ensure dlib/face_recognition is active.")

    try:
        base_image = load_and_orient_image(contents)
    except Exception as exc:
        logger.error("Failed to decode uploaded image: %s", exc)
        raise ValueError(f"Invalid image format: {exc}")

    rotations = [0, 90, 270, 180]
    face_locations = []
    working_image = base_image

    for angle in rotations:
        if angle == 0:
            candidate_img = base_image
        elif angle == 90:
            candidate_img = np.rot90(base_image, 1)
        elif angle == 270:
            candidate_img = np.rot90(base_image, 3)
        elif angle == 180:
            candidate_img = np.rot90(base_image, 2)

        locs = face_recognition.face_locations(candidate_img, number_of_times_to_upsample=1, model="hog")
        if not locs:
            locs = face_recognition.face_locations(candidate_img, number_of_times_to_upsample=2, model="hog")

        if locs:
            face_locations = locs
            working_image = candidate_img
            break

    if not face_locations:
        raise ValueError(
            "No face detected in photo. Please ensure your face is well-lit, upright, and clearly visible."
        )

    if len(face_locations) > 1:
        raise ValueError(
            f"Multiple faces detected in photo ({len(face_locations)} faces). Please ensure only one person is in the frame."
        )

    if not is_registration:
        try:
            top, right, bottom, left = face_locations[0]
            import cv2

            gray_full = cv2.cvtColor(working_image, cv2.COLOR_RGB2GRAY)

            edges = cv2.Canny(gray_full, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=70, minLineLength=50, maxLineGap=10)
            screen_lines = 0
            if lines is not None:
                for line in lines:
                    pts = line[0] if len(line.shape) > 1 and line.shape[0] == 1 else line
                    x1, y1, x2, y2 = pts[0], pts[1], pts[2], pts[3]
                    if left < x1 < right and top < y1 < bottom and left < x2 < right and top < y2 < bottom:
                        continue
                    angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
                    if angle < 6 or angle > 174 or (84 < angle < 96):
                        screen_lines += 1

            face_region = working_image[top:bottom, left:right]
            high_freq_ratio = 0.0
            laplacian_var = 0.0
            texture_uniformity = 10.0
            mean_saturation = 50.0

            if face_region.size > 0:
                face_gray = cv2.cvtColor(face_region, cv2.COLOR_RGB2GRAY)
                face_resized = cv2.resize(face_gray, (128, 128))

                f = np.fft.fft2(face_resized)
                fshift = np.fft.fftshift(f)
                h, w = face_resized.shape
                cy, cx = h // 2, w // 2
                radius = min(h, w) // 5
                y, x = np.ogrid[:h, :w]
                mask = (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
                low_energy = np.sum(np.abs(fshift)[mask])
                total_energy = np.sum(np.abs(fshift))
                high_freq_ratio = float((total_energy - low_energy) / (total_energy + 1e-6))

                face_small = cv2.resize(face_gray, (64, 64))
                laplacian_var = float(cv2.Laplacian(face_small, cv2.CV_64F).var())

                h_s, w_s = face_small.shape
                block_vars = []
                bh, bw = h_s // 4, w_s // 4
                for row in range(4):
                    for col in range(4):
                        block = face_small[row * bh:(row + 1) * bh, col * bw:(col + 1) * bw]
                        block_vars.append(float(np.std(block)))
                texture_uniformity = float(np.std(block_vars))

                face_hsv = cv2.cvtColor(face_region, cv2.COLOR_RGB2HSV)
                mean_saturation = float(np.mean(face_hsv[:, :, 1]))

            logger.info(
                "[ANTI-SPOOF] screen_lines=%d, high_freq=%.4f, laplacian=%.2f, uniformity=%.2f",
                screen_lines, high_freq_ratio, laplacian_var, texture_uniformity
            )

            if high_freq_ratio > 0.47:
                logger.warning("[ANTI-SPOOF BLOCKED] High Moiré / LCD pixel grid detected: %.4f", high_freq_ratio)
                raise ValueError(
                    "⚠️ Liveness Check Failed! Digital screen pixel lattice / Moiré pattern detected. "
                    "Showing photos on screens is not allowed. Please use your real face."
                )

            spoof_flags = 0
            if laplacian_var > 1400:
                spoof_flags += 1
            if texture_uniformity < 2.5:
                spoof_flags += 1
            if mean_saturation > 165:
                spoof_flags += 1
            if screen_lines > 60 and high_freq_ratio > 0.42:
                spoof_flags += 1

            if spoof_flags >= 2:
                logger.warning("[ANTI-SPOOF BLOCKED] Secondary texture flags: %d", spoof_flags)
                raise ValueError(
                    "⚠️ Liveness Check Failed! Artificial photo surface detected. "
                    "Please stand in front of the camera with your real face."
                )

        except ValueError:
            raise
        except Exception as spoof_exc:
            logger.warning("[ANTI-SPOOF] Check error (non-blocking): %s", spoof_exc)

    jitters = 3 if is_registration else 1
    encodings = face_recognition.face_encodings(
        working_image,
        known_face_locations=face_locations,
        num_jitters=jitters,
    )

    if not encodings:
        raise ValueError("Could not extract facial features. Please retake photo with clearer lighting.")

    return encodings[0].tolist()


def compute_match_confidence(distance: float, tolerance: float = FACE_MATCH_TOLERANCE) -> float:
    """Calculate an intuitive percentage match score (0-100%)."""
    if distance <= tolerance:
        score = 100.0 - (distance / tolerance) * 40.0
    else:
        score = max(0.0, 60.0 - ((distance - tolerance) / (1.0 - tolerance)) * 60.0)
    return round(score, 1)


def match_encoding(
    known_encoding: List[float],
    unknown_encoding: List[float],
    tolerance: float = FACE_MATCH_TOLERANCE,
) -> Tuple[bool, float, float]:
    """Compare two face encodings. Returns (is_match, distance, confidence_percentage)."""
    known = np.array(known_encoding)
    unknown = np.array(unknown_encoding)
    if USE_REAL_FR:
        distance = float(face_recognition.face_distance([known], unknown)[0])
    else:
        distance = float(np.linalg.norm(known - unknown))
    is_match = distance <= tolerance
    confidence = compute_match_confidence(distance, tolerance)
    return is_match, distance, confidence

class FaceIndex:
    def __init__(self):
        self.roll_numbers = []
        self.encodings_matrix = np.empty((0, 128))
        self.is_loaded = False

    def load_all(self, students_data):
        "\""Load all students into numpy matrix for vectorized search."\""
        if not students_data:
            self.roll_numbers = []
            self.encodings_matrix = np.empty((0, 128))
            self.is_loaded = True
            return
            
        import json
        self.roll_numbers = [s["roll_no"] for s in students_data]
        encodings = [json.loads(s["face_encoding"]) for s in students_data]
        self.encodings_matrix = np.array(encodings)
        self.is_loaded = True
        logger.info(f"FaceIndex loaded {len(self.roll_numbers)} students into optimized numpy matrix.")

    def add_student(self, roll_no: str, encoding: list):
        "\""Append a new student without full reload."\""
        self.roll_numbers.append(roll_no)
        new_row = np.array(encoding).reshape(1, -1)
        if self.encodings_matrix.shape[0] == 0:
            self.encodings_matrix = new_row
        else:
            self.encodings_matrix = np.vstack([self.encodings_matrix, new_row])

    def search(self, unknown_encoding: list, tolerance: float = FACE_MATCH_TOLERANCE):
        "\""Returns (best_roll_no, distance, confidence) or (None, 0, 0)"\""
        if self.encodings_matrix.shape[0] == 0:
            return None, 0.0, 0.0
            
        unknown = np.array(unknown_encoding)
        # Vectorized L2 distance across ALL students at once
        distances = np.linalg.norm(self.encodings_matrix - unknown, axis=1)
        best_idx = np.argmin(distances)
        best_distance = float(distances[best_idx])
        
        if best_distance <= tolerance:
            confidence = compute_match_confidence(best_distance, tolerance)
            return self.roll_numbers[best_idx], best_distance, confidence
        return None, best_distance, 0.0

global_face_index = FaceIndex()
