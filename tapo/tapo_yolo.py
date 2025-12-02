#!/usr/bin/env python3
import cv2
from ultralytics import YOLO
import argparse

# --- Configuration via la Ligne de Commande (CLI) ---

# 1. Créer un "parseur" d'arguments avec une description claire
parser = argparse.ArgumentParser(
    description="Détection d'objets avec YOLOv8 depuis un flux RTSP ou une webcam.",
    epilog="Exemple d'utilisation:\n"
           "  # Webcam locale, ne détecter que les humains:\n"
           "  python3 tapo_yolo.py -s 0 -f human\n\n"
           "  # Flux RTSP, ne détecter que les objets (pas les humains):\n"
           "  python3 tapo_yolo.py -f object",
    formatter_class=argparse.RawTextHelpFormatter
)

# 2. Définir les arguments que le script peut accepter
parser.add_argument(
    '-s', '--source',
    type=str,
    default='rtsp://chapichapo:chapichapo@192.1168.1.16:554/stream2',
    help="Source de la vidéo.\n"
         "  - Pour la webcam locale, utilisez '0'.\n"
         "  - Pour un flux RTSP, fournissez l'URL complète.\n"
         "  (défaut: le flux RTSP de la caméra Tapo)"
)
parser.add_argument(
    '-f', '--filter',
    type=str,
    default='all',
    choices=['all', 'human', 'object'],
    help="Filtre les types d'objets à détecter.\n"
         "  - 'all': Détecte toutes les classes (défaut).\n"
         "  - 'human': Ne détecte que les personnes (classe 'person').\n"
         "  - 'object': Détecte toutes les classes SAUF les personnes."
)

# 3. Analyser les arguments fournis par l'utilisateur
args = parser.parse_args()


# --- Initialisation ---

VIDEO_SOURCE = args.source
FILTER_TYPE = args.filter
MODEL_PATH = 'yolov8n.pt'
CONFIDENCE_THRESHOLD = 0.5

# Charger le modèle YOLOv8
try:
    model = YOLO(MODEL_PATH)
except Exception as e:
    print(f"Erreur lors du chargement du modèle : {e}")
    exit()

# --- Préparation du filtre de classes ---
classes_to_detect = None  # Par défaut, on détecte tout
class_names = model.names # Dictionnaire des classes {0: 'person', 1: 'bicycle', ...}

try:
    # Récupérer l'index de la classe 'person'
    person_class_index = [k for k, v in class_names.items() if v == 'person'][0]

    if FILTER_TYPE == 'human':
        classes_to_detect = [person_class_index]
        print("Mode de détection activé : Humains uniquement.")
    elif FILTER_TYPE == 'object':
        # On crée une liste de toutes les classes sauf celle de 'person'
        classes_to_detect = [k for k in class_names.keys() if k != person_class_index]
        print("Mode de détection activé : Objets uniquement (sans les humains).")
    else:
        print("Mode de détection activé : Toutes les classes.")

except IndexError:
    print("Attention : La classe 'person' n'a pas été trouvée dans le modèle. Le filtre ne peut pas être appliqué.")


# Préparer la source pour OpenCV
capture_source = VIDEO_SOURCE
if VIDEO_SOURCE.isdigit():
    capture_source = int(VIDEO_SOURCE)

# Se connecter au flux vidéo
cap = cv2.VideoCapture(capture_source)

if not cap.isOpened():
    print(f"Erreur: Impossible de se connecter à la source vidéo : {VIDEO_SOURCE}")
    exit()

print(f"\nDémarrage de la détection depuis la source : {VIDEO_SOURCE}")
print("Pressez 'q' sur la fenêtre pour quitter.")


# --- Boucle principale ---

while True:
    ret, frame = cap.read()
    if not ret:
        print("Fin du flux ou erreur de lecture.")
        break

    # Inférence YOLO avec le filtre de classes
    results = model(frame, conf=CONFIDENCE_THRESHOLD, classes=classes_to_detect, verbose=False)

    # Visualisation
    annotated_frame = results[0].plot()

    # Afficher le résultat
    cv2.imshow("Detection d'objets YOLOv8", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- Nettoyage ---
print("Arrêt du script.")
cap.release()
cv2.destroyAllWindows()