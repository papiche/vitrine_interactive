#!/usr/bin/env python3
import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import math

# --- Configuration et Initialisation ---

# 1. Configuration générale
RTSP_URL = 'rtsp://chapichapo:chapichapo@192.168.1.16:554/stream2' 
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
SMOOTHING_FACTOR = 7
CLICK_DISTANCE_THRESHOLD = 40

# 2. Initialisation de MediaPipe Hands (pour le contrôle de la souris)
mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(static_image_mode=False,
                                max_num_hands=1,
                                min_detection_confidence=0.7,
                                min_tracking_confidence=0.5)

# 3. NOUVEAU : Initialisation de MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
face_detector = mp_face_detection.FaceDetection(model_selection=0, 
                                                min_detection_confidence=0.5)

# 4. NOUVEAU : Initialisation de MediaPipe Object Detection
mp_object_detection = mp.solutions.object_detection
# Assurez-vous que le fichier 'efficientdet_lite0.tflite' est dans le même dossier
object_detector = mp_object_detection.ObjectDetector(model_asset_path='efficientdet_lite0.tflite',
                                                     min_detection_confidence=0.5)

# Utilitaire pour le dessin
mp_drawing = mp.solutions.drawing_utils

# Variables pour le lissage de la souris
mouse_x, mouse_y = 0, 0


# --- Programme principal ---
cap = cv2.VideoCapture(RTSP_URL)

if not cap.isOpened():
    print("Erreur: Impossible de se connecter au flux vidéo.")
    exit()

print(f"Démarrage du système. Résolution de l'écran : {SCREEN_WIDTH}x{SCREEN_HEIGHT}")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame_height, frame_width, _ = frame.shape
    
    # Conversion BGR -> RGB et effet miroir
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb_frame = cv2.flip(rgb_frame, 1)

    # --- Détections ---
    # Pour de meilleures performances, on passe l'image en lecture seule
    rgb_frame.flags.writeable = False
    
    # Exécuter les trois détections
    hand_results = hands_detector.process(rgb_frame)
    face_results = face_detector.process(rgb_frame)
    object_results = object_detector.process(rgb_frame)

    # On repasse l'image en mode écriture pour dessiner dessus
    rgb_frame.flags.writeable = True
    display_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)

    # --- Traitement et Affichage des Résultats ---

    # A. Traitement des MAINS (et contrôle souris)
    if hand_results.multi_hand_landmarks:
        hand_landmarks = hand_results.multi_hand_landmarks[0]
        mp_drawing.draw_landmarks(display_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
        
        # Logique de contrôle de la souris (inchangée)
        index_finger_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
        target_screen_x = np.interp(index_finger_tip.x, (0.0, 1.0), (0, SCREEN_WIDTH))
        target_screen_y = np.interp(index_finger_tip.y, (0.0, 1.0), (0, SCREEN_HEIGHT))
        mouse_x = mouse_x + (target_screen_x - mouse_x) / SMOOTHING_FACTOR
        mouse_y = mouse_y + (target_screen_y - mouse_y) / SMOOTHING_FACTOR
        pyautogui.moveTo(mouse_x, mouse_y)

        thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]
        thumb_px = (thumb_tip.x * frame_width, thumb_tip.y * frame_height)
        index_px = (index_finger_tip.x * frame_width, index_finger_tip.y * frame_height)
        distance = math.sqrt((thumb_px[0] - index_px[0])**2 + (thumb_px[1] - index_px[1])**2)
        if distance < CLICK_DISTANCE_THRESHOLD:
            pyautogui.click()
            pyautogui.sleep(0.2)

    # B. NOUVEAU : Dessiner les boîtes pour les VISAGES
    if face_results.detections:
        for detection in face_results.detections:
            mp_drawing.draw_detection(display_frame, detection)
            cv2.putText(display_frame, 'Visage', 
                        (int(detection.location_data.relative_bounding_box.xmin * frame_width), 
                         int(detection.location_data.relative_bounding_box.ymin * frame_height) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)


    # C. NOUVEAU : Dessiner les boîtes pour les OBJETS
    if object_results.detections:
        for detection in object_results.detections:
            bbox = detection.location_data.relative_bounding_box
            start_point = (int(bbox.xmin * frame_width), int(bbox.ymin * frame_height))
            end_point = (int((bbox.xmin + bbox.width) * frame_width), int((bbox.ymin + bbox.height) * frame_height))
            
            # Afficher le nom de l'objet et son score de confiance
            category_name = detection.categories[0].category_name
            score = round(detection.categories[0].score * 100, 1)
            label = f'{category_name} ({score}%)'
            
            # Logique d'interaction : l'objet est-il "tenu" ?
            is_held = False
            if hand_results.multi_hand_landmarks:
                hand_landmarks = hand_results.multi_hand_landmarks[0]
                # On vérifie si le centre de la paume est dans la boîte de l'objet
                wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
                wrist_px = (wrist.x * frame_width, wrist.y * frame_height)
                if start_point[0] < wrist_px[0] < end_point[0] and start_point[1] < wrist_px[1] < end_point[1]:
                    is_held = True

            # Dessiner la boîte (verte si tenue, rouge sinon)
            box_color = (0, 255, 0) if is_held else (0, 0, 255)
            cv2.rectangle(display_frame, start_point, end_point, box_color, 2)
            cv2.putText(display_frame, label, (start_point[0], start_point[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, box_color, 2)


    # Affichage final
    cv2.imshow('Detection Multiple', display_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Nettoyage
cap.release()
cv2.destroyAllWindows()
hands_detector.close()
face_detector.close()
object_detector.close()