import cv2
import numpy as np
import easyocr

reader = easyocr.Reader(['en'], gpu=False, verbose=False)


# -------------------------
# PREPROCESS (STABLE)
# -------------------------
def preprocess(img):
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    img = cv2.GaussianBlur(img, (3, 3), 0)

    return cv2.adaptiveThreshold(
        img, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31, 7
    )


# -------------------------
# ALIGNMENT (ONLY ORB - NO MIX)
# -------------------------
def align(img1, img2):

    orb = cv2.ORB_create(4000)

    k1, d1 = orb.detectAndCompute(img1, None)
    k2, d2 = orb.detectAndCompute(img2, None)

    if d1 is None or d2 is None:
        return img1

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(d1, d2)

    if len(matches) < 20:
        return img1

    matches = sorted(matches, key=lambda x: x.distance)[:300]

    src = np.float32([k1[m.queryIdx].pt for m in matches])
    dst = np.float32([k2[m.trainIdx].pt for m in matches])

    M, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)

    h, w = img2.shape
    return cv2.warpPerspective(img1, M, (w, h), borderValue=255)


# -------------------------
# COMPONENTS (FIXED FILTERING)
# -------------------------
def get_components(img):

    contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    h, w = img.shape

    min_area = (h * w) * 0.0004
    max_area = (h * w) * 0.2

    for c in contours:
        x, y, w1, h1 = cv2.boundingRect(c)
        area = w1 * h1

        if min_area < area < max_area:
            boxes.append((x, y, w1, h1))

    return boxes


# -------------------------
# MAIN ENGINE
# -------------------------
def run_qa_analysis(img_in, img_out, features):

    if np.array_equal(img_in, img_out):
        display = cv2.cvtColor(img_out, cv2.COLOR_GRAY2BGR)
        cv2.putText(
            display,
            "NO DIFFERENCE DETECTED",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )
        return display

    else:
        img_in = preprocess(img_in)
        img_out = preprocess(img_out)

        img_in = align(img_in, img_out)

        boxes_in = get_components(img_in)
        boxes_out = get_components(img_out)

        display = cv2.cvtColor(img_out, cv2.COLOR_GRAY2BGR)

        # -------------------------
        # CHANGE DETECTION (IoU BASED)
        # -------------------------
        if features.get("changes"):

            for (x, y, w, h) in boxes_out:

                found = False

                for (x2, y2, w2, h2) in boxes_in:

                    ix1 = max(x, x2)
                    iy1 = max(y, y2)
                    ix2 = min(x + w, x2 + w2)
                    iy2 = min(y + h, y2 + h2)

                    if ix2 > ix1 and iy2 > iy1:
                        found = True
                        break

                if not found:
                    cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 255), 2)
                    cv2.putText(display, "CHANGE", (x, y - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # -------------------------
        # CLASH (GEOMETRIC SHIFT ONLY)
        # -------------------------
        if features.get("clash"):

            for (x, y, w, h) in boxes_out:

                c_out = np.array([x + w // 2, y + h // 2])

                for (x2, y2, w2, h2) in boxes_in:

                    c_in = np.array([x2 + w2 // 2, y2 + h2 // 2])

                    dist = np.linalg.norm(c_out - c_in)

                    if dist < 10:
                        cv2.rectangle(display, (x, y), (x + w, y + h), (0, 165, 255), 2)
                        cv2.putText(display, "CLASH", (x, y - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
                        break

        # -------------------------
        # ANNOTATION (OCR REAL CHECK)
        # -------------------------
        if features.get("annotation"):

            text_results = reader.readtext(img_out)

            for (x, y, w, h) in boxes_out:

                cx, cy = x + w // 2, y + h // 2
                labeled = False

                for (bbox, text, prob) in text_results:

                    (tl, tr, br, bl) = bbox
                    tx = int((tl[0] + br[0]) / 2)
                    ty = int((tl[1] + br[1]) / 2)

                    if np.linalg.norm([cx - tx, cy - ty]) < 50:
                        labeled = True
                        break

                if not labeled:
                    cv2.rectangle(display, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    cv2.putText(display, "UNLABELED", (x, y - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        return display