#!/usr/bin/env python3
"""
Test live camera — ouvre la webcam, applique le profil hardware auto-detecte,
lance la detection/reconnaissance de visages et log les resultats en console.

Affiche une fenetre OpenCV avec :
  - Flux camera en direct
  - Rectangles autour des visages detectes (Haar Cascade)
  - Si face_recognition est active (profil medium/high) : identification des visages
  - Infos du profil hardware en overlay

Controles :
  ESC / q  : quitter
  SPACE    : capturer une photo et lancer la reconnaissance complete
  s        : afficher les stats face database
  p        : afficher le profil hardware

Usage :
    python3 test_live_camera.py [--camera 0] [--profile minimal|low|medium|high] [--duration 30]
"""

import sys
import os
import time
import argparse
import tempfile
from pathlib import Path

# Set profile override before importing hardware_profile
parser = argparse.ArgumentParser(description="Test live camera avec profil hardware")
parser.add_argument("--camera", type=int, default=0, help="Index camera (default: 0)")
parser.add_argument("--profile", type=str, default="", help="Forcer un profil: minimal|low|medium|high")
parser.add_argument("--duration", type=int, default=0, help="Duree en secondes (0 = illimite, ESC pour quitter)")
parser.add_argument("--headless", action="store_true", help="Mode sans fenetre (log console uniquement)")
args = parser.parse_args()

if args.profile:
    os.environ["VITRINE_PROFILE"] = args.profile

import cv2
import numpy as np

from hardware_profile import HW

# Conditional face recognition import based on profile
face_recognizer = None
HAS_FACE_RECOGNITION = False

if HW.face_recognition:
    try:
        from face_recognition_module import FaceRecognizer
        face_recognizer = FaceRecognizer()
        HAS_FACE_RECOGNITION = True
    except ImportError as e:
        print(f"[WARN] face_recognition_module non disponible: {e}")

# Haar Cascade for lightweight detection (always available)
cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(cascade_path)

# ---- Couleurs ----
GREEN = (0, 255, 0)
ORANGE = (0, 165, 255)
CYAN = (255, 255, 0)
WHITE = (255, 255, 255)
RED = (0, 0, 255)


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def detect_faces_haar(frame, scale, min_size):
    """Detection legere via Haar Cascade. Retourne liste de (x,y,w,h)."""
    small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.3, minNeighbors=3,
        minSize=(min_size, min_size), flags=cv2.CASCADE_SCALE_IMAGE
    )
    # Scale back coordinates
    result = []
    for (x, y, w, h) in faces:
        result.append((int(x / scale), int(y / scale), int(w / scale), int(h / scale)))
    return result


def draw_overlay(frame, fps, face_count, frame_num):
    """Dessine les infos du profil et stats en overlay."""
    h, fh = frame.shape[0], 18
    lines = [
        f"Profil: {HW.profile_name} ({HW.label})",
        f"Board: {HW.board} | RAM: {HW.ram_mb}MB | CPUs: {HW.cpus}",
        f"Resolution: {HW.frame_width}x{HW.frame_height} | FPS cible: {HW.camera_fps}",
        f"FPS reel: {fps:.1f} | Faces: {face_count} | Frame: {frame_num}",
        f"JPEG quality: {HW.jpeg_quality} | Face interval: {HW.face_detection_interval}",
        f"Face recognition: {'OUI' if HAS_FACE_RECOGNITION else 'NON'} (profil: {HW.profile_name})",
        f"Nostr limit: {HW.nostr_limit} | Refresh: {HW.nostr_refresh}s",
    ]
    # Fond semi-transparent
    overlay = frame.copy()
    cv2.rectangle(overlay, (5, 5), (520, 10 + fh * len(lines)), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    for i, line in enumerate(lines):
        cv2.putText(frame, line, (10, 22 + i * fh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, CYAN, 1, cv2.LINE_AA)


def main():
    log("=" * 60)
    log("TEST LIVE CAMERA — Detection & Reconnaissance de visages")
    log("=" * 60)
    log(HW.summary())
    log(f"Camera index: {args.camera}")
    log(f"Face recognition: {'ACTIVE' if HAS_FACE_RECOGNITION else 'DESACTIVEE'}")
    if not HAS_FACE_RECOGNITION:
        log(f"  -> Raison: profil '{HW.profile_name}' (face_recognition={HW.face_recognition})")
    log(f"Mode: {'headless (console)' if args.headless else 'fenetre OpenCV'}")
    if args.duration > 0:
        log(f"Duree: {args.duration}s")
    log("-" * 60)

    # Open camera
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        log(f"ERREUR: impossible d'ouvrir la camera {args.camera}")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, HW.frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HW.frame_height)
    cap.set(cv2.CAP_PROP_FPS, HW.camera_fps)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    log(f"Camera ouverte: {actual_w}x{actual_h} @ {actual_fps:.0f}fps")

    frame_count = 0
    face_count = 0
    last_faces = []
    fps_start = time.time()
    fps_frames = 0
    current_fps = 0.0
    start_time = time.time()
    last_recognition_results = []

    log("")
    log("Controles :")
    if not args.headless:
        log("  ESC/q     : quitter")
        log("  ESPACE    : capturer photo + reconnaissance complete")
        log("  s         : stats base de visages")
        log("  p         : profil hardware")
    log("")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                log("ERREUR: lecture frame echouee")
                time.sleep(0.1)
                continue

            frame_count += 1
            fps_frames += 1

            # Calculate FPS every second
            elapsed = time.time() - fps_start
            if elapsed >= 1.0:
                current_fps = fps_frames / elapsed
                fps_frames = 0
                fps_start = time.time()

            # Face detection at configured interval
            if frame_count % HW.face_detection_interval == 0:
                t0 = time.time()
                last_faces = detect_faces_haar(frame, HW.face_scale, HW.face_min_size)
                dt = (time.time() - t0) * 1000
                face_count = len(last_faces)
                if face_count > 0:
                    log(f"Frame {frame_count}: {face_count} visage(s) detecte(s) ({dt:.1f}ms)")

            # Draw face rectangles
            for (x, y, w, h) in last_faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), GREEN, 2)
                cv2.putText(frame, "Visage", (x, y - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, GREEN, 1)

            # Draw last recognition results
            for res in last_recognition_results:
                top, right, bottom, left = res.get("box", (0, 0, 0, 0))
                status = res.get("status", "")
                label = res.get("name") or res.get("user_id", "?")[:12]
                color = GREEN if status == "recognized" else ORANGE
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, f"{label} ({status})", (left, top - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            if not args.headless:
                draw_overlay(frame, current_fps, face_count, frame_count)
                cv2.imshow("Test Vitrine - Live Camera", frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):  # ESC or q
                    log("Fermeture demandee par l'utilisateur")
                    break
                elif key == ord(" "):  # SPACE — capture + recognition
                    log("--- CAPTURE PHOTO ---")
                    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False,
                                                     dir=str(Path(__file__).parent / "photos"))
                    cv2.imwrite(tmp.name, frame)
                    log(f"Photo sauvegardee: {tmp.name}")

                    if HAS_FACE_RECOGNITION and face_recognizer:
                        t0 = time.time()
                        results = face_recognizer.process_photo(tmp.name)
                        dt = (time.time() - t0) * 1000
                        last_recognition_results = results
                        log(f"Reconnaissance: {len(results)} visage(s) en {dt:.0f}ms")
                        for r in results:
                            log(f"  -> {r['status']}: {r.get('name') or r['user_id']}"
                                f" (similarite: {r.get('similarity', 0):.2f},"
                                f" visites: {r.get('visit_count', 0)})")
                    else:
                        # Haar-only detection on captured frame
                        faces = detect_faces_haar(frame, HW.face_scale, HW.face_min_size)
                        log(f"Detection Haar uniquement: {len(faces)} visage(s)")
                        log("  (reconnaissance desactivee pour ce profil)")
                elif key == ord("s"):
                    if HAS_FACE_RECOGNITION and face_recognizer:
                        stats = face_recognizer.get_stats()
                        log(f"Stats base visages: {stats}")
                    else:
                        log("Stats non disponibles (face recognition desactivee)")
                elif key == ord("p"):
                    log(HW.summary())

            # Duration limit
            if args.duration > 0 and (time.time() - start_time) >= args.duration:
                log(f"Duree {args.duration}s atteinte, arret automatique")
                break

            # Throttle according to profile
            time.sleep(HW.capture_loop_sleep)

    except KeyboardInterrupt:
        log("Interrompu (Ctrl+C)")
    finally:
        cap.release()
        if not args.headless:
            cv2.destroyAllWindows()

    # Final summary
    total_time = time.time() - start_time
    avg_fps = frame_count / total_time if total_time > 0 else 0
    log("")
    log("=" * 60)
    log("RESULTATS DU TEST")
    log("=" * 60)
    log(f"Profil utilise       : {HW.profile_name} ({HW.label})")
    log(f"Board                : {HW.board}")
    log(f"RAM                  : {HW.ram_mb} MB")
    log(f"Resolution camera    : {actual_w}x{actual_h}")
    log(f"Duree du test        : {total_time:.1f}s")
    log(f"Frames traites       : {frame_count}")
    log(f"FPS moyen            : {avg_fps:.1f}")
    log(f"Face recognition     : {'ACTIVE' if HAS_FACE_RECOGNITION else 'DESACTIVEE'}")
    log(f"Face detect interval : toutes les {HW.face_detection_interval} frames")
    log(f"JPEG quality         : {HW.jpeg_quality}")
    log(f"Nostr limit/refresh  : {HW.nostr_limit} events / {HW.nostr_refresh}s")
    log("=" * 60)


if __name__ == "__main__":
    main()
