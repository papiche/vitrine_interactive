#!/usr/bin/env python3
"""
UPlanet Shop Interface - Version Nostr Live
Connecte la vitrine interactive au script bash nostr_get_events.sh
"""
import cv2
import mediapipe as mp
import time
import numpy as np
import os
import subprocess
import json
import threading
from collections import deque
from datetime import datetime

# --- CONFIGURATION ---
HOME = os.path.expanduser("~")
NOSTR_SCRIPT = os.path.join(HOME, ".zen/Astroport.ONE/tools/nostr_get_events.sh")
WEBCAM_INDEX = 0
SCREEN_W, SCREEN_H = 1280, 720  # Résolution de rendu (redimensionnable)

# Couleurs (BGR)
C_BG = (15, 10, 20)       # Fond sombre
C_ACCENT = (0, 255, 255)  # Cyan Cyberpunk
C_TEXT = (255, 255, 255)
C_CARD = (30, 30, 40)     # Fond des cartes
C_AUTHOR = (0, 200, 100)  # Vert Matrix

# --- MOTEUR NOSTR (Background) ---
class NostrFeed:
    def __init__(self):
        self.events = []
        self.loading = True
        self.last_update = 0
        # On lance le chargement initial
        self.refresh_async()

    def refresh_async(self):
        """Lance la récupération sans bloquer l'interface"""
        t = threading.Thread(target=self._fetch_events)
        t.daemon = True
        t.start()

    def _fetch_events(self):
        """Exécute le script bash et parse le JSON"""
        print("[NOSTR] Récupération des messages...")
        self.loading = True
        
        new_events = []
        
        # Commande: Récupère les kind 1 (Notes) et 30800 (DIDs), limite 30, pas de GPS pour l'instant
        cmd = [
            NOSTR_SCRIPT,
            "--kind", "1",
            "--limit", "30",
            "--output", "json"
        ]
        
        if not os.path.exists(NOSTR_SCRIPT):
            print(f"[ERREUR] Script introuvable: {NOSTR_SCRIPT}")
            self._generate_demo_data() # Fallback si script absent
            self.loading = False
            return

        try:
            # Timeout de 5s pour ne pas bloquer si le relay lag
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if not line: continue
                    try:
                        ev = json.loads(line)
                        # Nettoyage et formatage
                        clean_ev = {
                            'content': ev.get('content', ''),
                            'pubkey': ev.get('pubkey', '???')[:8] + '...',
                            'created_at': ev.get('created_at', 0),
                            'id': ev.get('id', '')[:6],
                            'kind': ev.get('kind')
                        }
                        new_events.append(clean_ev)
                    except json.JSONDecodeError:
                        pass
                
                # Tri par date (le plus récent en haut)
                new_events.sort(key=lambda x: x['created_at'], reverse=True)
                self.events = new_events
                print(f"[NOSTR] {len(new_events)} événements chargés.")
            else:
                print(f"[NOSTR] Aucune donnée ou erreur: {result.stderr}")
                if not self.events: self._generate_demo_data()

        except Exception as e:
            print(f"[NOSTR] Erreur exécution: {e}")
            if not self.events: self._generate_demo_data()
            
        self.loading = False
        self.last_update = time.time()

    def _generate_demo_data(self):
        """Données de secours si le relay est vide"""
        titles = [
            "Bienvenue sur le Nœud Shop G1FabLab",
            "Le réseau UPlanet est actif 🟢",
            "Venez installer Linux sur vos machines !",
            "Offre Spéciale: Stockage Décentralisé",
            "Capteurs Forêt: Température 22°C - Humidité 45%",
            "Recherche contributeurs pour le code ẐEN",
            "Ceci est un message de démonstration."
        ]
        self.events = []
        for i, t in enumerate(titles):
            self.events.append({
                'content': t,
                'pubkey': 'system',
                'created_at': time.time() - (i*3600),
                'id': 'demo',
                'kind': 1
            })

# --- MOTEUR GRAPHIQUE ---
def wrap_text(text, font, scale, max_width):
    """Découpe le texte pour qu'il rentre dans la carte"""
    words = text.split(' ')
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        # Test taille
        (w, h), _ = cv2.getTextSize(' '.join(current_line), font, scale, 1)
        if w > max_width:
            current_line.pop() # Enlever le mot qui dépasse
            lines.append(' '.join(current_line))
            current_line = [word] # Nouveau début de ligne
            
    if current_line: lines.append(' '.join(current_line))
    return lines[:3] # Max 3 lignes pour ne pas surcharger

def draw_ui(img, feed, scroll_y, hand_active, hand_pos):
    """Dessine toute l'interface sur l'image"""
    h_img, w_img = img.shape[:2]
    
    # 1. Fond Cyber (Grille)
    # Effet de transparence sur la vidéo webcam
    overlay = img.copy()
    cv2.rectangle(overlay, (0,0), (w_img, h_img), C_BG, -1)
    cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)
    
    # Grille décorative
    grid_spacing = 50
    offset_y = int(scroll_y * 0.5) % grid_spacing
    for x in range(0, w_img, grid_spacing):
        cv2.line(img, (x, 0), (x, h_img), (30, 30, 40), 1)
    for y in range(0, h_img, grid_spacing):
        yy = (y - offset_y) % h_img
        cv2.line(img, (0, yy), (w_img, yy), (30, 30, 40), 1)

    # 2. Header
    cv2.rectangle(img, (0, 0), (w_img, 60), (20, 20, 30), -1)
    cv2.line(img, (0, 60), (w_img, 60), C_ACCENT, 2)
    cv2.putText(img, "UPLANET // NOSTR RELAY FEED", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, C_ACCENT, 2)
    
    # Status chargement
    if feed.loading:
        cv2.putText(img, "LOADING...", (w_img - 150, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    else:
        cv2.putText(img, f"{len(feed.events)} EVENTS", (w_img - 200, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # 3. Liste des Messages
    card_h = 100
    spacing = 15
    start_y = 100 - scroll_y # Position virtuelle du premier élément
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    for i, ev in enumerate(feed.events):
        y = int(start_y + i * (card_h + spacing))
        
        # Optimisation: Ne dessiner que ce qui est visible
        if y > -card_h and y < h_img:
            # Fond Carte
            margin = 50
            pt1 = (margin, y)
            pt2 = (w_img - margin, y + card_h)
            
            # Sub-overlay pour la carte
            sub_overlay = img[max(0, y):min(h_img, y+card_h), margin:w_img-margin]
            if sub_overlay.size > 0:
                rect = np.zeros(sub_overlay.shape, dtype=np.uint8)
                rect[:] = C_CARD
                res = cv2.addWeighted(sub_overlay, 0.3, rect, 0.7, 0)
                img[max(0, y):min(h_img, y+card_h), margin:w_img-margin] = res

            # Bordure
            cv2.rectangle(img, pt1, pt2, C_ACCENT, 1)
            
            # Contenu
            # Header message (Auteur + Date)
            dt = datetime.fromtimestamp(ev['created_at']).strftime('%H:%M')
            header_txt = f"{ev['pubkey']}  |  {dt}"
            cv2.putText(img, header_txt, (margin+10, y+25), font, 0.4, C_AUTHOR, 1)
            
            # Corps du message (wrappé)
            lines = wrap_text(ev['content'], font, 0.6, w_img - (margin*2) - 20)
            for j, line in enumerate(lines):
                cv2.putText(img, line, (margin+10, y+55 + (j*25)), font, 0.6, C_TEXT, 1)

    # 4. Scrollbar Indicator
    if len(feed.events) > 0:
        total_h = len(feed.events) * (card_h + spacing)
        visible_ratio = h_img / max(h_img, total_h)
        scroll_ratio = scroll_y / max(1, total_h - h_img)
        
        sb_h = int(h_img * visible_ratio)
        sb_y = int(scroll_ratio * (h_img - sb_h))
        
        cv2.rectangle(img, (w_img-10, sb_y), (w_img, sb_y+sb_h), C_ACCENT, -1)

    # 5. Cursor & Hand Feedback
    if hand_active:
        cx, cy = int(hand_pos[0] * w_img), int(hand_pos[1] * h_img)
        cv2.circle(img, (cx, cy), 15, C_ACCENT, 2)
        cv2.line(img, (cx-20, cy), (cx+20, cy), C_ACCENT, 1)
        cv2.line(img, (cx, cy-20), (cx, cy+20), C_ACCENT, 1)
    else:
        # Message "Attract Mode"
        txt = "LEVEZ LA MAIN POUR NAVIGUER"
        (tw, th), _ = cv2.getTextSize(txt, font, 1, 2)
        tx = (w_img - tw) // 2
        ty = h_img - 50
        # Effet clignotant
        alpha = (np.sin(time.time() * 5) + 1) / 2
        col = (int(C_ACCENT[0]*alpha), int(C_ACCENT[1]*alpha), int(C_ACCENT[2]*alpha))
        cv2.putText(img, txt, (tx, ty), font, 1, col, 2)


# --- MAIN LOOP ---
def main():
    # Init Hardware
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    if not cap.isOpened():
        print("Erreur Webcam")
        return

    # Init AI
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )

    # Init Nostr
    feed = NostrFeed()
    
    # State
    scroll_y = 0
    target_scroll_y = 0
    hand_y_smooth = 0.5
    last_interaction = time.time()
    
    cv2.namedWindow("Shop UI", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Shop UI", SCREEN_W, SCREEN_H)
    # cv2.setWindowProperty("Shop UI", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN) # Décommenter pour prod

    print("[SYSTEM] Shop Interactive UI Started.")

    while True:
        # 1. Capture
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (SCREEN_W, SCREEN_H))
        
        # 2. Detection
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)
        
        hand_active = False
        hand_pos = (0.5, 0.5)
        
        if results.multi_hand_landmarks:
            hand_active = True
            last_interaction = time.time()
            lm = results.multi_hand_landmarks[0]
            
            # Position Index
            ix = lm.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].x
            iy = lm.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].y
            hand_pos = (ix, iy)
            
            # Logique Scroll (Mapping)
            # Zone morte: 20% haut, 20% bas pour éviter scroll accidentel
            # On map 0.2-0.8 vers 0-1
            scroll_input = (iy - 0.2) / 0.6
            scroll_input = max(0, min(1, scroll_input))
            
            # Calcul hauteur totale contenu
            total_h = max(SCREEN_H, len(feed.events) * 115) # 115 = card_h + spacing
            max_scroll = total_h - SCREEN_H
            
            if max_scroll > 0:
                target_scroll_y = scroll_input * max_scroll
        
        # 3. Physique (Lissage Scroll)
        scroll_y += (target_scroll_y - scroll_y) * 0.1
        
        # 4. Refresh Auto (toutes les 60s si inactif)
        if time.time() - feed.last_update > 60:
            feed.refresh_async()

        # 5. Rendu
        draw_ui(frame, feed, scroll_y, hand_active, hand_pos)
        
        cv2.imshow("Shop UI", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()