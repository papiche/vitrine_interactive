#!/usr/bin/env python3
"""
UPlanet Shop Carousel - Interface "Cover Flow"
Navigation horizontale par geste + Affichage images + Webcam PIP
"""
import cv2
import mediapipe as mp
import time
import numpy as np
import os
import subprocess
import json
import threading
import re
import requests
from io import BytesIO
from collections import deque
from datetime import datetime

# --- CONFIGURATION ---
HOME = os.path.expanduser("~")
NOSTR_SCRIPT = os.path.join(HOME, ".zen/Astroport.ONE/tools/nostr_get_events.sh")
WEBCAM_INDEX = 0
SCREEN_W, SCREEN_H = 1280, 720

# Zones de navigation (0.0 à 1.0 sur l'axe X)
ZONE_LEFT = 0.3   # Si main < 30% -> Précédent
ZONE_RIGHT = 0.7  # Si main > 70% -> Suivant

# Couleurs (BGR)
C_BG = (10, 10, 15)       # Fond presque noir
C_ACCENT = (0, 255, 255)  # Jaune/Cyan
C_TEXT = (255, 255, 255)
C_CARD_BG = (40, 40, 50)  # Gris foncé
C_PIP_BORDER = (0, 0, 255)# Rouge enregistrement

# --- GESTION DES IMAGES ---
class ImageManager:
    def __init__(self):
        self.cache = {} # url -> numpy image
        self.queue = deque(maxlen=20)
        self.placeholder = np.zeros((300, 400, 3), dtype=np.uint8)
        self.placeholder[:] = (30, 30, 30)
        cv2.putText(self.placeholder, "TEXT ONLY", (100, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (100,100,100), 2)
        
        # Thread de téléchargement
        t = threading.Thread(target=self._worker)
        t.daemon = True
        t.start()

    def get_image(self, url):
        if not url: return self.placeholder
        if url in self.cache: return self.cache[url]
        if url not in self.queue: self.queue.append(url)
        return self.placeholder # En attendant le chargement

    def _worker(self):
        while True:
            if self.queue:
                url = self.queue.popleft()
                if url in self.cache: continue
                try:
                    resp = requests.get(url, timeout=3)
                    if resp.status_code == 200:
                        arr = np.asarray(bytearray(resp.content), dtype=np.uint8)
                        img = cv2.imdecode(arr, -1)
                        if img is not None:
                            # Redimensionner pour économiser RAM et affichage
                            img = cv2.resize(img, (400, 300))
                            self.cache[url] = img
                except:
                    pass
            time.sleep(0.1)

img_mgr = ImageManager()

# --- MOTEUR NOSTR ---
class NostrFeed:
    def __init__(self):
        self.events = []
        self.loading = True
        self.lock = threading.Lock()
        self.refresh_async()

    def refresh_async(self):
        t = threading.Thread(target=self._fetch_events)
        t.daemon = True
        t.start()

    def _extract_image(self, content):
        # Regex basique pour trouver une URL image
        urls = re.findall(r'(https?://\S+\.(?:jpg|jpeg|png|webp))', content, re.IGNORECASE)
        return urls[0] if urls else None

    def _fetch_events(self):
        print("[NOSTR] Chargement...")
        cmd = [NOSTR_SCRIPT, "--kind", "1", "--limit", "20", "--output", "json"]
        
        new_events = []
        try:
            # Fallback Demo si script absent
            if not os.path.exists(NOSTR_SCRIPT):
                raise Exception("Script missing")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if not line: continue
                    try:
                        ev = json.loads(line)
                        img_url = self._extract_image(ev.get('content',''))
                        # On nettoie le content en enlevant l'URL de l'image pour éviter doublon
                        clean_content = ev.get('content','')
                        if img_url: clean_content = clean_content.replace(img_url, '')
                        
                        new_events.append({
                            'id': ev.get('id', '')[:6],
                            'pubkey': ev.get('pubkey', '???')[:6],
                            'created_at': ev.get('created_at', 0),
                            'content': clean_content.strip(),
                            'image': img_url
                        })
                    except: pass
        except:
            # DONNÉES DÉMO
            demos = [
                ("Bienvenue au G1FabLab", None),
                ("Nos serveurs sont autonomes", "https://raw.githubusercontent.com/papiche/Astroport.ONE/master/ASTROPORT_STATION.png"),
                ("La Forêt UPlanet en direct", "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Morvan_Forest.jpg/640px-Morvan_Forest.jpg"),
                ("Rejoignez le réseau !", None)
            ]
            for txt, img in demos:
                new_events.append({
                    'id': 'demo', 'pubkey': 'System', 'created_at': time.time(),
                    'content': txt, 'image': img
                })

        with self.lock:
            # Trier et garder
            new_events.sort(key=lambda x: x['created_at'], reverse=True)
            self.events = new_events
            self.loading = False
            print(f"[NOSTR] {len(self.events)} items.")

# --- MOTEUR GRAPHIQUE ---

def draw_wrapped_text(img, text, x, y, max_w, font_scale=0.6, color=(255,255,255)):
    font = cv2.FONT_HERSHEY_SIMPLEX
    words = text.split()
    line = []
    dy = 25
    for word in words:
        line.append(word)
        (w, h), _ = cv2.getTextSize(" ".join(line), font, font_scale, 1)
        if w > max_w:
            line.pop()
            cv2.putText(img, " ".join(line), (x, y), font, font_scale, color, 1)
            line = [word]
            y += dy
    if line:
        cv2.putText(img, " ".join(line), (x, y), font, font_scale, color, 1)

def draw_card(img, event, x, y, w, h, scale=1.0, alpha=1.0):
    """Dessine une carte individuelle"""
    # Si alpha est faible, on dessine sombre
    overlay = img.copy()
    
    # 1. Fond Carte
    pt1 = (int(x), int(y))
    pt2 = (int(x+w), int(y+h))
    
    # Clip coordinates
    if pt1[0] >= SCREEN_W or pt2[0] <= 0: return # Hors champ
    
    # Dessin Fond
    bg_color = tuple([int(c*scale) for c in C_CARD_BG])
    cv2.rectangle(img, pt1, pt2, bg_color, -1)
    
    # 2. Image (Top half)
    img_h = int(h * 0.55)
    pic = img_mgr.get_image(event['image'])
    if pic is not None:
        try:
            # Resize fit
            pic_resized = cv2.resize(pic, (int(w-20), int(img_h-20)))
            # Centrer l'image
            ix = int(x + 10)
            iy = int(y + 10)
            # Collage safe
            h_pic, w_pic = pic_resized.shape[:2]
            
            # Gestion des bords d'écran pour le collage numpy
            y1, y2 = iy, iy+h_pic
            x1, x2 = ix, ix+w_pic
            
            if x1 < SCREEN_W and x2 > 0: # Si visible
                # Calcul des crops si hors écran
                crop_x1 = 0
                crop_x2 = w_pic
                if x1 < 0: 
                    crop_x1 = -x1
                    x1 = 0
                if x2 > SCREEN_W:
                    crop_x2 = w_pic - (x2 - SCREEN_W)
                    x2 = SCREEN_W
                
                if crop_x2 > crop_x1:
                    img[y1:y2, x1:x2] = pic_resized[:, crop_x1:crop_x2]
        except Exception as e:
            print(e)

    # 3. Texte (Bottom half)
    text_y = int(y + img_h + 30)
    # Auteur
    cv2.putText(img, f"@{event['pubkey']}", (int(x+15), int(y + img_h + 15)), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.4*scale, C_ACCENT, 1)
    # Contenu
    if x + 15 < SCREEN_W and x + w - 15 > 0: # Optimisation texte
        draw_wrapped_text(img, event['content'], int(x+15), text_y, int(w-30), 0.5*scale, C_TEXT)

    # 4. Bordure (si actif)
    if scale > 0.9:
        cv2.rectangle(img, pt1, pt2, C_ACCENT, 2)

def main():
    # Hardware
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    if not cap.isOpened(): return

    # AI
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)

    # Data
    feed = NostrFeed()
    
    # State Carousel
    current_idx = 0.0 # Float pour animation fluide
    target_idx = 0
    
    # UI Constants
    CARD_W = 400
    CARD_H = 500
    SPACING = 50
    
    cv2.namedWindow("UPlanet Showcase", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("UPlanet Showcase", SCREEN_W, SCREEN_H)

    while True:
        ret, frame = cap.read()
        if not ret: break
        
        # 1. Flip & Petit format pour PIP
        frame = cv2.flip(frame, 1)
        pip_frame = cv2.resize(frame, (320, 240))
        
        # 2. Main Canvas (Fond)
        display = np.zeros((SCREEN_H, SCREEN_W, 3), dtype=np.uint8)
        display[:] = C_BG
        
        # 3. Detection Geste
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)
        
        hand_detected = False
        action_text = ""
        
        if results.multi_hand_landmarks:
            hand_detected = True
            lm = results.multi_hand_landmarks[0]
            ix = lm.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].x
            
            # --- LOGIQUE NAVIGATION ---
            # Si main à Gauche -> Reculer
            if ix < ZONE_LEFT:
                target_idx -= 0.1 # Vitesse de défilement
                action_text = "<< PRECEDENT"
                # Dessiner zone active gauche
                overlay = display.copy()
                cv2.rectangle(overlay, (0,0), (int(SCREEN_W*ZONE_LEFT), SCREEN_H), (50,50,50), -1)
                cv2.addWeighted(overlay, 0.5, display, 0.5, 0, display)
                
            # Si main à Droite -> Avancer
            elif ix > ZONE_RIGHT:
                target_idx += 0.1
                action_text = "SUIVANT >>"
                # Dessiner zone active droite
                overlay = display.copy()
                cv2.rectangle(overlay, (int(SCREEN_W*ZONE_RIGHT),0), (SCREEN_W, SCREEN_H), (50,50,50), -1)
                cv2.addWeighted(overlay, 0.5, display, 0.5, 0, display)
            else:
                action_text = "|| PAUSE"
                # Arrondir target vers l'entier le plus proche pour "snapper"
                target_idx = round(target_idx)

        # Clamp (Limites du carrousel)
        max_idx = max(0, len(feed.events) - 1)
        target_idx = max(0, min(max_idx, target_idx))
        
        # Physique (Lissage)
        current_idx += (target_idx - current_idx) * 0.1
        
        # 4. Dessin du Carrousel
        # Centre de l'écran
        center_x = SCREEN_W // 2
        center_y = (SCREEN_H - CARD_H) // 2
        
        # On dessine les cartes visibles (current +/- 2)
        start_i = int(current_idx) - 2
        end_i = int(current_idx) + 3
        
        # Ordre de dessin: du plus loin au plus proche (Painter's algorithm)
        # On doit dessiner d'abord les index éloignés, puis le central
        indices_to_draw = sorted(range(start_i, end_i), key=lambda i: -abs(i - current_idx))
        
        for i in indices_to_draw:
            if 0 <= i < len(feed.events):
                # Offset par rapport au centre
                offset = i - current_idx
                
                # Position X : Centre + (offset * largeur_carte)
                x = center_x + (offset * (CARD_W + SPACING)) - (CARD_W // 2)
                
                # Scale : Plus c'est loin, plus c'est petit
                scale = 1.0 - (min(abs(offset), 2.0) * 0.2)
                
                # Opacity/Lighting
                # Pas géré parfaitement en rect simple, mais simulé par taille
                
                # Calcul taille finale
                w_scaled = int(CARD_W * scale)
                h_scaled = int(CARD_H * scale)
                
                # Recentrer en fonction du scale
                y_scaled = center_y + (CARD_H - h_scaled) // 2
                x_scaled = x + (CARD_W - w_scaled) // 2
                
                draw_card(display, feed.events[i], x_scaled, y_scaled, w_scaled, h_scaled, scale)

        # 5. UI Elements
        # Titre
        cv2.putText(display, "UPLANET SHOWCASE", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, C_ACCENT, 2)
        cv2.putText(display, f"{action_text}", (SCREEN_W//2 - 100, SCREEN_H - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, C_TEXT, 2)

        # 6. PIP Webcam (Retour Caméra en bas à droite)
        # Position: coin bas droite
        h_pip, w_pip = pip_frame.shape[:2]
        pip_y = SCREEN_H - h_pip - 20
        pip_x = SCREEN_W - w_pip - 20
        
        # Bordure PIP
        cv2.rectangle(display, (pip_x-2, pip_y-2), (pip_x+w_pip+2, pip_y+h_pip+2), C_PIP_BORDER, 2)
        
        # Incrustation
        display[pip_y:pip_y+h_pip, pip_x:pip_x+w_pip] = pip_frame
        
        # Dessiner le squelette main SUR le PIP pour feedback
        if hand_detected:
            # On doit remapper les coords (0-1) vers la taille du PIP (320x240)
            # Puis ajouter l'offset du PIP (pip_x, pip_y)
            mp.solutions.drawing_utils.draw_landmarks(
                display[pip_y:pip_y+h_pip, pip_x:pip_x+w_pip], 
                results.multi_hand_landmarks[0], 
                mp_hands.HAND_CONNECTIONS
            )

        cv2.imshow("UPlanet Showcase", display)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()