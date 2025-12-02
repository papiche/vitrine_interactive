#!/usr/bin/env python3
import cv2

# --- Configuration ---
# L'adresse de votre flux vidéo
RTSP_URL = 'rtsp://chapichapo:chapichapo@192.168.1.16:554/stream2' 

# --- Programme principal ---

# Se connecter à la source vidéo
cap = cv2.VideoCapture(RTSP_URL)

# Vérifier si la connexion a réussi
if not cap.isOpened():
    print("Erreur : Impossible de se connecter au flux vidéo.")
    print("Veuillez vérifier l'URL RTSP et que la caméra est bien en ligne.")
    exit()
else:
    print("Connexion au flux réussie. Affichage de la vidéo...")
    print("Appuyez sur la touche 'q' sur la fenêtre pour quitter.")

# Boucle principale pour lire et afficher les images
while True:
    # Lire une image (une "frame") du flux vidéo
    # 'ret' est un booléen (True si la lecture a réussi, False sinon)
    # 'frame' est l'image elle-même
    ret, frame = cap.read()

    # Si la lecture échoue (fin du flux, problème réseau...), on quitte la boucle
    if not ret:
        print("Erreur de lecture du flux. Fermeture.")
        break

    # Afficher l'image dans une fenêtre nommée "Flux Camera"
    cv2.imshow('Flux Camera', frame)

    # Attendre 1 milliseconde qu'une touche soit pressée.
    # C'est essentiel pour que l'affichage se rafraîchisse.
    # Si la touche pressée est 'q', on quitte la boucle.
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- Nettoyage ---

# Libérer la ressource de la caméra
cap.release()

# Fermer toutes les fenêtres créées par OpenCV
cv2.destroyAllWindows()

print("Programme terminé.")