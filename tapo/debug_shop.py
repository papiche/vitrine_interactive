#!/usr/bin/env python3
import cv2
import mediapipe as mp
import time
import numpy as np
import os
from collections import deque

# --- CONFIG ---
WEBCAM_INDEX = 0
SCREEN_W, SCREEN_H = 1280, 720 # Taille fixe pour le test

# Init MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5, # Sensibilité augmentée
    min_tracking_confidence=0.5
)
mp_draw = mp.solutions.drawing_utils

def main():
    print(f"[TEST] Démarrage Camera {WEBCAM_INDEX}...")
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    
    # Vérification Camera
    if not cap.isOpened():
        print(f"[ERREUR] Impossible d'ouvrir la caméra {WEBCAM_INDEX}")
        # Essayer index 1 au cas où (souvent sur les laptops avec IR)
        cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            return

    # Fenêtre
    window_name = "DEBUG SHOP"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, SCREEN_W, SCREEN_H)

    wrist_history = deque(maxlen=20)
    state = "VEILLE" # VEILLE ou ACTIF
    
    print("[INFO] Appuyez sur 'q' pour quitter")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERREUR] Perte signal caméra")
            break

        # Miroir + RGB
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detection
        results = hands.process(rgb)
        
        # Création de l'image de fond (Bleu nuit pour voir si ça marche)
        display = np.zeros((720, 1280, 3), dtype=np.uint8)
        display[:] = (50, 20, 20) # BGR: Bleu foncé
        
        # Incrustation Webcam en petit en bas à droite (pour debug)
        small_cam = cv2.resize(frame, (320, 240))
        display[480:720, 960:1280] = small_cam

        hand_detected = False

        if results.multi_hand_landmarks:
            hand_detected = True
            lm = results.multi_hand_landmarks[0]
            
            # DESSINER LE SQUELETTE (C'est ça qui manquait pour le feedback)
            mp_draw.draw_landmarks(display, lm, mp_hands.HAND_CONNECTIONS)
            
            # Logique simple : Main levée (Poignet plus bas que l'index)
            wrist_y = lm.landmark[mp_hands.HandLandmark.WRIST].y
            index_y = lm.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].y
            
            # Texte d'info
            cv2.putText(display, f"Main detectee! Y={index_y:.2f}", (50, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Activation (Si index est dans la moitié haute de l'écran)
            if index_y < 0.5:
                state = "ACTIF - NAVIGATION"
                cv2.circle(display, (640, 360), 50, (0, 255, 255), -1) # Point Jaune central
            else:
                state = "VEILLE - LEVEZ LA MAIN"
        else:
            cv2.putText(display, "PAS DE MAIN", (50, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            state = "VEILLE"

        # Affichage État
        cv2.putText(display, f"ETAT: {state}", (50, 650), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

        cv2.imshow(window_name, display)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()