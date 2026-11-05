import io
import json
import logging
import asyncio
import threading
from typing import List, Tuple, Optional, Dict, Any
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
    downscale large images to max 512x512 with fast BILINEAR filter for high-concurrency throughput,
    ensure RGB format, and convert to numpy array for dlib/face_recognition.
    """
    pil_img = Image.open(io.BytesIO(contents))
    pil_img = ImageOps.exif_transpose(pil_img)
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    
    pil_img.thumbnail((512, 512), Image.Resampling.BILINEAR)
    return np.ascontiguousarray(np.array(pil_img), dtype=np.uint8)


def _sync_extract_face_encoding(contents: bytes, is_registration: bool = False) -> List[float]:
    """
    Synchronous CPU-intensive face detection and feature extraction.
    Designed to run inside ThreadPoolExecutor to prevent blocking the asyncio event loop.
    Optimized multi-stage detection:
      1. Fast upright check (0 deg) with upsample=0 (~40ms)
      2. Fast upright check (0 deg) with upsample=1 (~90ms)
      3. Rotations check [90, 270, 180] only if upright returns no face.
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

    face_locations = []
    working_image = base_image

    # Stage 1: Try upright orientation (99% of smartphone selfies with EXIF are upright)
    face_locations = face_recognition.face_locations(base_image, number_of_times_to_upsample=0, model="hog")
    if not face_locations:
        face_locations = face_recognition.face_locations(base_image, number_of_times_to_upsample=1, model="hog")

    # Stage 2: Fallback to rotations only if upright photo yielded no faces
    if not face_locations:
        for angle in [90, 270, 180]:
            k = 1 if angle == 90 else (3 if angle == 270 else 2)
            candidate_img = np.ascontiguousarray(np.rot90(base_image, k), dtype=np.uint8)
            locs = face_recognition.face_locations(candidate_img, number_of_times_to_upsample=0, model="hog")
            if not locs:
                locs = face_recognition.face_locations(candidate_img, number_of_times_to_upsample=1, model="hog")
            if locs:
                face_locations = locs
                working_image = candidate_img
                break

    # Stage 3: Adaptive low-light contrast enhancement (CLAHE) for dim rooms and indoor shadows
    if not face_locations:
        try:
            import cv2
            lab = cv2.cvtColor(base_image, cv2.COLOR_RGB2LAB)
            l_chan, a_chan, b_chan = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            cl = clahe.apply(l_chan)
            enhanced = cv2.cvtColor(cv2.merge((cl, a_chan, b_chan)), cv2.COLOR_LAB2RGB)
            enhanced = np.ascontiguousarray(enhanced, dtype=np.uint8)
            locs = face_recognition.face_locations(enhanced, number_of_times_to_upsample=1, model="hog")
            if locs:
                face_locations = locs
                working_image = enhanced
        except Exception as e:
            logger.debug("CLAHE enhancement fallback skipped: %s", e)

    if not face_locations:
        raise ValueError(
            "No face detected in photo. Please ensure your face is well-lit, upright, and clearly visible."
        )

    # Smart Primary Face Filtering: Filter out tiny background false positives (e.g. posters, books)
    if len(face_locations) > 1:
        # Sort face bounding boxes by area descending: (bottom - top) * (right - left)
        face_locations.sort(key=lambda b: (b[2] - b[0]) * (b[1] - b[3]), reverse=True)
        primary_area = (face_locations[0][2] - face_locations[0][0]) * (face_locations[0][1] - face_locations[0][3])
        second_area = (face_locations[1][2] - face_locations[1][0]) * (face_locations[1][1] - face_locations[1][3])
        # If the primary selfie face is at least 2.5x larger than any background artifact, select the primary face
        if primary_area >= 2.5 * second_area:
            logger.info("Filtered %d background artifacts; keeping primary selfie face (area=%d vs secondary=%d).", len(face_locations) - 1, primary_area, second_area)
            face_locations = [face_locations[0]]
        else:
            raise ValueError(
                f"Multiple people detected in frame ({len(face_locations)} faces). Please ensure only you are visible."
            )

    # Anti-spoofing and liveness analysis (only during live attendance verification)
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

            if high_freq_ratio > 0.52:
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
            if screen_lines > 60 and high_freq_ratio > 0.48:
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

    working_image = np.ascontiguousarray(working_image, dtype=np.uint8)
    jitters = 3 if is_registration else 1
    encodings = face_recognition.face_encodings(
        working_image,
        known_face_locations=face_locations,
        num_jitters=jitters,
    )

    if not encodings:
        raise ValueError("Could not extract facial features. Please retake photo with clearer lighting.")

    return encodings[0].tolist()


_face_extraction_lock = None

def get_face_extraction_lock() -> asyncio.Lock:
    global _face_extraction_lock
    if _face_extraction_lock is None:
        _face_extraction_lock = asyncio.Lock()
    return _face_extraction_lock

async def extract_face_encoding(contents: bytes, is_registration: bool = False) -> List[float]:
    """
    Serialize CPU-intensive Dlib neural net calls using an async lock.
    Eliminates Dlib C++ multithreading memory corruption (0xC0000005) while keeping
    the FastAPI event loop fully responsive for concurrent traffic.
    """
    lock = get_face_extraction_lock()
    async with lock:
        return await asyncio.to_thread(_sync_extract_face_encoding, contents, is_registration)


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
    known = np.array(known_encoding, dtype=np.float32)
    unknown = np.array(unknown_encoding, dtype=np.float32)
    if USE_REAL_FR:
        distance = float(face_recognition.face_distance([known], unknown)[0])
    else:
        distance = float(np.linalg.norm(known - unknown))
    is_match = distance <= tolerance
    confidence = compute_match_confidence(distance, tolerance)
    return is_match, distance, confidence


class FaceIndex:
    """
    Thread-safe, in-memory vectorized face search index.
    Pre-loads all student facial encodings into a single contiguous NumPy matrix.
    Performs 1-to-N distance comparisons across 500+ students in ~0.2 milliseconds.
    Eliminates all per-verification database reads and JSON parsing overhead.
    """
    def __init__(self):
        self.roll_numbers: List[str] = []
        self.student_metadata: Dict[str, Dict[str, Any]] = {}
        self.encodings_matrix: np.ndarray = np.empty((0, 128), dtype=np.float32)
        self.is_loaded: bool = False
        self._lock = threading.Lock()

    def load_all(self, students_data: List[Dict[str, Any]]) -> None:
        """Load all enrolled students into the in-memory index."""
        with self._lock:
            if not students_data:
                self.roll_numbers = []
                self.student_metadata = {}
                self.encodings_matrix = np.empty((0, 128), dtype=np.float32)
                self.is_loaded = True
                return

            valid_rolls = []
            valid_encs = []
            meta = {}

            for s in students_data:
                r_no = str(s["roll_no"]).strip().upper()
                raw_enc = s["face_encoding"]
                if isinstance(raw_enc, str):
                    try:
                        enc = json.loads(raw_enc)
                    except Exception:
                        continue
                elif isinstance(raw_enc, list):
                    enc = raw_enc
                else:
                    continue

                if len(enc) == 128:
                    valid_rolls.append(r_no)
                    valid_encs.append(enc)
                    meta[r_no] = {
                        "roll_no": r_no,
                        "name": s.get("name") or "",
                        "device_id": (s.get("device_id") or "").strip(),
                        "branch_code": (s.get("branch_code") or "").strip().upper(),
                        "branch_name": (s.get("branch_name") or "").strip(),
                        "section": (s.get("section") or "").strip().upper(),
                        "year": s.get("year") or 1,
                        "class_roll_no": (s.get("class_roll_no") or "").strip(),
                        "is_locked": bool(s.get("is_locked", 1)),
                        "cache_flag": int(s.get("cache_flag") or 0),
                        "face_encoding": enc,
                    }

            self.roll_numbers = valid_rolls
            self.encodings_matrix = np.array(valid_encs, dtype=np.float32)
            self.student_metadata = meta
            self.is_loaded = True
            logger.info("FaceIndex pre-loaded %d students into memory matrix.", len(self.roll_numbers))

    def get_student(self, roll_no: str) -> Optional[Dict[str, Any]]:
        """Instant dictionary lookup for 1-to-1 verification."""
        with self._lock:
            return self.student_metadata.get(roll_no.strip().upper())

    def update_student_device(self, roll_no: str, device_id: str) -> None:
        """Update hardware device binding in memory."""
        with self._lock:
            clean = roll_no.strip().upper()
            if clean in self.student_metadata:
                self.student_metadata[clean]["device_id"] = device_id.strip()

    def add_or_update_student(
        self,
        roll_no: str,
        name: str,
        encoding: List[float],
        device_id: str = "",
        branch_code: str = "",
        branch_name: str = "",
        section: str = "",
        year: int = 1,
        class_roll_no: str = "",
        is_locked: bool = True
    ) -> None:
        """Add or update a student in the vectorized index without a full reload."""
        with self._lock:
            clean = roll_no.strip().upper()
            self.student_metadata[clean] = {
                "roll_no": clean,
                "name": name,
                "device_id": device_id.strip(),
                "branch_code": branch_code.strip().upper(),
                "branch_name": branch_name.strip(),
                "section": section.strip().upper(),
                "year": year,
                "class_roll_no": class_roll_no.strip(),
                "is_locked": is_locked,
                "face_encoding": encoding,
            }

            enc_vec = np.array(encoding, dtype=np.float32).reshape(1, -1)
            if clean in self.roll_numbers:
                idx = self.roll_numbers.index(clean)
                self.encodings_matrix[idx] = enc_vec
            else:
                self.roll_numbers.append(clean)
                if self.encodings_matrix.shape[0] == 0:
                    self.encodings_matrix = enc_vec
                else:
                    self.encodings_matrix = np.vstack([self.encodings_matrix, enc_vec])

    def update_student_cache_flag(self, roll_no: str, flag: int) -> None:
        with self._lock:
            clean = roll_no.strip().upper()
            if clean in self.student_metadata:
                self.student_metadata[clean]["cache_flag"] = int(flag)

    def remove_student(self, roll_no: str) -> None:
        """Remove student from memory on deletion."""
        with self._lock:
            clean = roll_no.strip().upper()
            if clean in self.student_metadata:
                del self.student_metadata[clean]
            if clean in self.roll_numbers:
                idx = self.roll_numbers.index(clean)
                self.roll_numbers.pop(idx)
                self.encodings_matrix = np.delete(self.encodings_matrix, idx, axis=0)

    def search_1toN(
        self,
        unknown_encoding: List[float],
        tolerance: float = FACE_MATCH_TOLERANCE
    ) -> Tuple[Optional[Dict[str, Any]], float, float]:
        """
        Perform vectorized L2 search across all enrolled students in C/BLAS in ~0.2ms.
        Returns: (matched_student_dict, distance, confidence_percentage) or (None, best_distance, 0.0)
        """
        with self._lock:
            if self.encodings_matrix.shape[0] == 0:
                return None, 1.0, 0.0

            unknown = np.array(unknown_encoding, dtype=np.float32)
            # Vectorized Euclidean Distance: || known_i - unknown ||
            distances = np.linalg.norm(self.encodings_matrix - unknown, axis=1)
            best_idx = int(np.argmin(distances))
            best_distance = float(distances[best_idx])

            if best_distance <= tolerance:
                confidence = compute_match_confidence(best_distance, tolerance)
                matched_roll = self.roll_numbers[best_idx]
                return self.student_metadata.get(matched_roll), best_distance, confidence
            return None, best_distance, 0.0


global_face_index = FaceIndex()
