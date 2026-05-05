import os

import cv2
import numpy as np


_HOG_PERSON_DETECTOR = cv2.HOGDescriptor()
_HOG_PERSON_DETECTOR.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
_PATIENT_BG_SUBTRACTOR = cv2.createBackgroundSubtractorMOG2(history=120, varThreshold=32, detectShadows=False)


def _get_env_float(name, default):
    raw_value = os.getenv(name)
    if raw_value is None:
        return float(default)
    try:
        return float(raw_value)
    except ValueError:
        return float(default)


def _clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


# -------------------------------
# Skin Detection
# -------------------------------
def detect_skin(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)

    hsv_lower_skin = np.array([0, 35, 60], dtype=np.uint8)
    hsv_upper_skin = np.array([25, 185, 255], dtype=np.uint8)

    ycrcb_lower_skin = np.array([0, 133, 77], dtype=np.uint8)
    ycrcb_upper_skin = np.array([255, 173, 127], dtype=np.uint8)

    hsv_mask = cv2.inRange(hsv, hsv_lower_skin, hsv_upper_skin)
    ycrcb_mask = cv2.inRange(ycrcb, ycrcb_lower_skin, ycrcb_upper_skin)

    mask = cv2.bitwise_and(hsv_mask, ycrcb_mask)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)

    return mask


def _extract_exposed_skin_roi(skin_mask, frame_pixels):
    contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_skin_area = max(int(frame_pixels * 0.004), 500)

    exposed_skin_mask = np.zeros_like(skin_mask)
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_skin_area:
            continue
        cv2.drawContours(exposed_skin_mask, [contour], -1, 255, thickness=cv2.FILLED)

    erosion_kernel = np.ones((5, 5), np.uint8)
    exposed_skin_mask = cv2.erode(exposed_skin_mask, erosion_kernel, iterations=1)
    exposed_skin_mask = cv2.GaussianBlur(exposed_skin_mask, (3, 3), 0)
    _, exposed_skin_mask = cv2.threshold(exposed_skin_mask, 100, 255, cv2.THRESH_BINARY)

    return exposed_skin_mask


def _detect_patient_bbox(frame):
    frame_height, frame_width = frame.shape[:2]
    longest_side = max(frame_width, frame_height)
    resize_scale = min(1.0, 640.0 / float(longest_side))

    if resize_scale < 1.0:
        resized = cv2.resize(
            frame,
            (int(frame_width * resize_scale), int(frame_height * resize_scale)),
            interpolation=cv2.INTER_AREA,
        )
    else:
        resized = frame

    rects, weights = _HOG_PERSON_DETECTOR.detectMultiScale(
        resized,
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.05,
    )

    if len(rects) == 0:
        return None

    center_x = frame_width / 2.0
    center_y = frame_height / 2.0
    best_score = -1e9
    best_bbox = None

    for index, rect in enumerate(rects):
        x, y, w, h = [int(value) for value in rect]

        if resize_scale < 1.0:
            x = int(x / resize_scale)
            y = int(y / resize_scale)
            w = int(w / resize_scale)
            h = int(h / resize_scale)

        box_area = float(max(w * h, 1))
        box_center_x = x + (w / 2.0)
        box_center_y = y + (h / 2.0)
        center_distance = abs(box_center_x - center_x) / max(center_x, 1.0) + abs(
            box_center_y - center_y
        ) / max(center_y, 1.0)
        detection_weight = float(weights[index]) if index < len(weights) else 0.0

        score = (detection_weight * 12.0) + (box_area / float(frame_width * frame_height)) - (center_distance * 0.6)
        if score > best_score:
            best_score = score
            best_bbox = (x, y, w, h)

    return best_bbox


def _detect_patient_bbox_from_foreground(frame):
    frame_height, frame_width = frame.shape[:2]
    frame_area = float(max(frame_height * frame_width, 1))

    fg_mask = _PATIENT_BG_SUBTRACTOR.apply(frame)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    center_x = frame_width / 2.0
    center_y = frame_height / 2.0
    best_score = -1e9
    best_bbox = None

    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < (frame_area * 0.03):
            continue

        x, y, w, h = cv2.boundingRect(contour)
        box_area = float(max(w * h, 1))
        box_ratio = box_area / frame_area
        if box_ratio > 0.78:
            continue

        aspect_ratio = w / float(max(h, 1))
        if aspect_ratio > 2.6 or aspect_ratio < 0.2:
            continue

        box_center_x = x + (w / 2.0)
        box_center_y = y + (h / 2.0)
        center_distance = abs(box_center_x - center_x) / max(center_x, 1.0) + abs(
            box_center_y - center_y
        ) / max(center_y, 1.0)

        score = (box_ratio * 1.8) - (center_distance * 0.7)
        if score > best_score:
            best_score = score
            best_bbox = (x, y, w, h)

    return best_bbox


def _build_patient_mask(frame):
    frame_height, frame_width = frame.shape[:2]
    patient_mask = np.zeros((frame_height, frame_width), dtype=np.uint8)

    patient_bbox = _detect_patient_bbox(frame)
    if patient_bbox is None:
        patient_bbox = _detect_patient_bbox_from_foreground(frame)
    patient_detected = patient_bbox is not None

    if patient_detected:
        x, y, w, h = patient_bbox
        pad_x = max(int(w * 0.12), 10)
        pad_y = max(int(h * 0.12), 10)

        x1 = max(x - pad_x, 0)
        y1 = max(y - pad_y, 0)
        x2 = min(x + w + pad_x, frame_width)
        y2 = min(y + h + pad_y, frame_height)
    else:
        x1 = int(frame_width * 0.18)
        y1 = int(frame_height * 0.08)
        x2 = int(frame_width * 0.82)
        y2 = int(frame_height * 0.96)

    cv2.rectangle(patient_mask, (x1, y1), (x2, y2), 255, thickness=cv2.FILLED)
    return patient_mask, patient_detected


# -------------------------------
# Bleeding Detection (ROBUST + CALIBRATED)
# -------------------------------
def detect_bleeding(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    frame_height, frame_width = frame.shape[:2]
    frame_pixels = max(frame_height * frame_width, 1)

    calibration_sensitivity = _clamp(_get_env_float("BLEEDING_SENSITIVITY", 1.0), 0.6, 1.8)
    threshold_scale = _clamp(_get_env_float("BLEEDING_THRESHOLD_SCALE", 1.0), 0.6, 1.8)
    base_low_threshold = _clamp(_get_env_float("BLEEDING_LOW_THRESHOLD", 1.8), 0.4, 8.0)
    base_high_threshold = _clamp(_get_env_float("BLEEDING_HIGH_THRESHOLD", 5.0), 1.0, 20.0)
    high_skin_confidence_min = _clamp(
        _get_env_float("BLEEDING_HIGH_SKIN_CONFIDENCE_MIN", 3.0), 1.5, 8.0
    )
    high_contour_confidence_min = _clamp(
        _get_env_float("BLEEDING_HIGH_CONTOUR_CONFIDENCE_MIN", 0.9), 0.4, 3.0
    )
    high_confidence_margin = _clamp(
        _get_env_float("BLEEDING_HIGH_CONFIDENCE_MARGIN", 0.8), 0.0, 4.0
    )
    require_patient_detection = str(
        os.getenv("BLEEDING_REQUIRE_PATIENT_DETECTION", "1")
    ).strip().lower() in ("1", "true", "yes", "on")

    avg_brightness = float(np.mean(hsv[:, :, 2]))
    sat_floor = int(_clamp(125 - ((avg_brightness - 100.0) * 0.18), 95, 145))
    val_floor = int(_clamp(60 - ((avg_brightness - 100.0) * 0.10), 45, 85))

    # Red color ranges (adaptive to brightness)
    lower_red1 = np.array([0, sat_floor, val_floor])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, sat_floor, val_floor])
    upper_red2 = np.array([180, 255, 255])

    red_mask = (
        cv2.inRange(hsv, lower_red1, upper_red1)
        + cv2.inRange(hsv, lower_red2, upper_red2)
    )

    # Additional red-dominance gate in BGR space to suppress skin-tone false positives
    b_channel, g_channel, r_channel = cv2.split(frame)
    b_channel = b_channel.astype(np.float32)
    g_channel = g_channel.astype(np.float32)
    r_channel = r_channel.astype(np.float32)

    red_dominance = (
        (r_channel > g_channel * 1.18)
        & (r_channel > b_channel * 1.18)
        & ((r_channel - g_channel) > 22)
        & ((r_channel - b_channel) > 22)
    )
    red_dominance_mask = (red_dominance.astype(np.uint8)) * 255
    red_mask = cv2.bitwise_and(red_mask, red_dominance_mask)

    kernel = np.ones((3, 3), np.uint8)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)

    patient_mask, patient_detected = _build_patient_mask(frame)
    red_mask = cv2.bitwise_and(red_mask, patient_mask)

    skin_mask = detect_skin(frame)
    exposed_skin_mask = _extract_exposed_skin_roi(skin_mask, frame_pixels)
    exposed_skin_mask = cv2.bitwise_and(exposed_skin_mask, patient_mask)

    # Only red on skin
    bleeding_mask = cv2.bitwise_and(red_mask, exposed_skin_mask)

    contours, _ = cv2.findContours(
        bleeding_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    valid_bleed_area = 0
    contour_count = 0
    largest_contour_area = 0.0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 120:
            continue
        contour_count += 1
        valid_bleed_area += area
        if area > largest_contour_area:
            largest_contour_area = area

    skin_pixels = cv2.countNonZero(exposed_skin_mask)
    skin_red_pixels = cv2.countNonZero(bleeding_mask)
    red_pixels = cv2.countNonZero(red_mask)
    patient_pixels = cv2.countNonZero(patient_mask)
    patient_coverage = patient_pixels / frame_pixels
    minimum_skin_pixels = max(int(frame_pixels * 0.012), 900)
    insufficient_skin_context = skin_pixels < minimum_skin_pixels

    skin_confidence = 0.0
    if skin_pixels > 0:
        skin_confidence = (skin_red_pixels / skin_pixels) * 100

    largest_skin_region_ratio = 0.0
    if skin_pixels > 0:
        largest_skin_region_ratio = (largest_contour_area / skin_pixels) * 100

    fabric_like_red_region = (
        skin_pixels > 0
        and contour_count <= 2
        and (skin_confidence >= 22.0 or largest_skin_region_ratio >= 18.0)
    )

    global_confidence = (red_pixels / frame_pixels) * 100
    contour_confidence = (valid_bleed_area / frame_pixels) * 100

    skin_coverage = skin_pixels / frame_pixels
    if skin_coverage < 0.08:
        confidence = (0.35 * skin_confidence) + (0.50 * global_confidence) + (0.15 * contour_confidence)
    else:
        confidence = (0.55 * skin_confidence) + (0.35 * global_confidence) + (0.10 * contour_confidence)

    # Adaptive compensation
    low_light_boost = _clamp(95.0 / max(avg_brightness, 45.0), 1.0, 1.18)
    distance_boost = _clamp(0.10 / max(skin_coverage, 0.10), 1.0, 1.10)
    confidence = confidence * low_light_boost * distance_boost * calibration_sensitivity

    # If exposed skin is not visible enough, avoid classifying red clothing/background as bleeding
    if insufficient_skin_context:
        confidence *= 0.20
        if skin_red_pixels < 180:
            confidence = 0.0

    # If patient wasn't confidently detected, keep detector conservative
    if not patient_detected:
        confidence *= 0.55

    # Suppress large uniform red areas (typical of clothing) from escalating risk
    if fabric_like_red_region:
        confidence *= 0.34
        if skin_confidence >= 35.0:
            confidence *= 0.6

    low_threshold = base_low_threshold * threshold_scale
    high_threshold = base_high_threshold * threshold_scale
    high_threshold = max(high_threshold, low_threshold + 0.4)

    # Guard for tiny red speckles / sensor noise
    if red_pixels < 180 and skin_red_pixels < 120:
        confidence = 0.0

    if require_patient_detection and not patient_detected:
        confidence = 0.0

    # Final decision
    if confidence < low_threshold:
        bleeding = False
        risk = "Low"
    elif confidence < high_threshold:
        bleeding = True
        risk = "Medium"
    else:
        bleeding = True
        high_risk_candidate = (
            contour_count > 0
            and (
                skin_confidence >= high_skin_confidence_min
                or contour_confidence >= high_contour_confidence_min
            )
            and confidence >= (high_threshold + high_confidence_margin)
        )
        if (
            high_risk_candidate
            and patient_detected
            and not fabric_like_red_region
            and not insufficient_skin_context
        ):
            risk = "High"
        else:
            risk = "Medium"

    return {
        "bleeding_detected": bleeding,
        "risk_level": risk,
        "confidence": round(confidence, 2),
        "skin_coverage": round(skin_coverage, 4),
        "skin_pixels": int(skin_pixels),
        "skin_red_pixels": int(skin_red_pixels),
        "red_pixels": int(red_pixels),
        "patient_detected": bool(patient_detected),
        "patient_coverage": round(patient_coverage, 4),
        "insufficient_skin_context": bool(insufficient_skin_context),
        "largest_skin_region_ratio": round(largest_skin_region_ratio, 2),
        "fabric_like_red_region": bool(fabric_like_red_region),
        "low_threshold": round(low_threshold, 2),
        "high_threshold": round(high_threshold, 2),
        "high_skin_confidence_min": round(high_skin_confidence_min, 2),
        "high_contour_confidence_min": round(high_contour_confidence_min, 2),
        "high_confidence_margin": round(high_confidence_margin, 2),
        "require_patient_detection": bool(require_patient_detection),
        "avg_brightness": round(avg_brightness, 2),
        "suspected_condition": (
            "Possible external bleeding on exposed skin"
            if bleeding
            else "No visible external bleeding"
        ),
    }
