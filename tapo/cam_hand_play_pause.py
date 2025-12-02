#!/usr/bin/env python3
import cv2
import mediapipe as mp
import os
import time

# --- Configuration ---
VIDEO_FILE = './UPlanet___Un_Meilleur_Internet.mp4'
WEBCAM_INDEX = 0

# --- Vérification du fichier vidéo ---
if not os.path.exists(VIDEO_FILE):
    print(f"Erreur : Le fichier vidéo '{VIDEO_FILE}' n'a pas été trouvé.")
    print("Assurez-vous qu'il se trouve dans le même dossier que le script.")
    exit()

# --- Initialisation de MediaPipe Hands ---
mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(static_image_mode=False,
                                max_num_hands=1,
                                min_detection_confidence=0.7,
                                min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# --- Fonctions de détection de gestes ---
def get_hand_gesture(hand_landmarks):
    """Analyse les landmarks et retourne 'open', 'closed' ou None."""
    
    # Points de repère des extrémités des doigts (sauf le pouce)
    finger_tips_indices = [
        mp_hands.HandLandmark.INDEX_FINGER_TIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
        mp_hands.HandLandmark.RING_FINGER_TIP,
        mp_hands.HandLandmark.PINKY_TIP
    ]
    
    # Points de repère des articulations inférieures correspondantes (PIP)
    finger_pip_indices = [
        mp_hands.HandLandmark.INDEX_FINGER_PIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_PIP,
        mp_hands.HandLandmark.RING_FINGER_PIP,
        mp_hands.HandLandmark.PINKY_PIP
    ]

    fingers_open_count = 0
    fingers_closed_count = 0

    for tip_index, pip_index in zip(finger_tips_indices, finger_pip_indices):
        tip = hand_landmarks.landmark[tip_index]
        pip = hand_landmarks.landmark[pip_index]
        
        # L'origine (0,0) est en haut à gauche.
        # Si la coordonnée Y de l'extrémité est plus petite, le doigt est levé.
        if tip.y < pip.y:
            fingers_open_count += 1
        else:
            fingers_closed_count += 1
            
    if fingers_open_count == 4:
        return 'open'
    elif fingers_closed_count == 4:
        return 'closed'
    
    return None

# --- Programme principal ---

# Initialiser la capture de la webcam et de la vidéo
cap_webcam = cv2.VideoCapture(WEBCAM_INDEX)
cap_video = cv2.VideoCapture(VIDEO_FILE)

is_playing = False
last_video_frame = None
last_gesture_time = 0
gesture_cooldown = 0.5  # 500 ms de délai entre les commandes

print("Lancement du lecteur vidéo par gestes.")
print("  - Main ouverte : Jouer/Reprendre la vidéo")
print("  - Main fermée : Mettre en pause")
print("Pressez 'q' sur une des fenêtres pour quitter.")

while cap_webcam.isOpened():
    # --- 1. Gérer la fenêtre de contrôle (Webcam) ---
    ret_cam, cam_frame = cap_webcam.read()
    if not ret_cam:
        break
    
    # Effet miroir pour une interaction naturelle
    cam_frame = cv2.flip(cam_frame, 1)

    # Détection de la main
    rgb_frame = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2RGB)
    results = hands_detector.process(rgb_frame)

    if results.multi_hand_landmarks:
        hand_landmarks = results.multi_hand_landmarks[0]
        mp_drawing.draw_landmarks(cam_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
        
        # Analyser le geste et appliquer un cooldown pour éviter les changements rapides
        current_time = time.time()
        if (current_time - last_gesture_time) > gesture_cooldown:
            gesture = get_hand_gesture(hand_landmarks)
            if gesture == 'open':
                is_playing = True
                last_gesture_time = current_time
                print("Commande détectée : PLAY")
            elif gesture == 'closed':
                is_playing = False
                last_gesture_time = current_time
                print("Commande détectée : PAUSE")

    # Afficher le statut (PLAY/PAUSE) sur la fenêtre de contrôle
    status_text = "PLAYING" if is_playing else "PAUSED"
    text_color = (0, 255, 0) if is_playing else (0, 0, 255)
    cv2.putText(cam_frame, status_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, text_color, 3)
    
    cv2.imshow('Controle', cam_frame)

    # --- 2. Gérer la fenêtre du lecteur vidéo ---
    if is_playing:
        ret_vid, video_frame = cap_video.read()
        # Si la vidéo est terminée, on la rembobine pour la jouer en boucle
        if not ret_vid:
            cap_video.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret_vid, video_frame = cap_video.read()
        
        if ret_vid:
            last_video_frame = video_frame

    # On affiche la dernière image capturée (figée si en pause)
    if last_video_frame is not None:
        cv2.imshow('Lecteur Video', last_video_frame)

    # Quitter avec la touche 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- Nettoyage ---
print("Arrêt du script.")
cap_webcam.release()
cap_video.release()
cv2.destroyAllWindows()