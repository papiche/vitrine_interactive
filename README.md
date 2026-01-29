# 🖐️ Vitrine Interactive UPlanet

**Transformez Votre Vitrine en Vendeur Interactif 24/7**

Révolutionnez l'expérience client avant même qu'ils n'entrent dans votre boutique. Ce projet transforme une simple vitrine en un canal de vente et de communication dynamique, accessible par de simples gestes, 24h/24 et 7j/7.

Imaginez : un passant s'arrête devant votre magasin fermé. Au lieu de simplement regarder, il navigue dans vos offres, consulte vos produits, prend rendez-vous ou planifie même un achat, le tout sans toucher à rien, par de simples mouvements de la main. C'est la promesse de la vitrine interactive.

## ✨ Avantages Clés pour Votre Commerce

- **Augmentation de l'Engagement** : Captez l'attention des passants avec une expérience "wow" et transformez-les en clients potentiels, même en dehors des heures d'ouverture.
- **Génération de Leads Continue** : Ne perdez plus jamais un client. Permettez la prise de rendez-vous ou la collecte d'emails à toute heure.
- **Canal de Vente Additionnel** : Mettez en avant des offres exclusives, vos nouveautés ou promotions.
- **Modernisation de l'Image de Marque** : Positionnez votre commerce comme innovant et à la pointe de la technologie.
- **Interaction Sans Contact** : Solution hygiénique et futuriste, parfaitement adaptée aux attentes modernes.
- **🆕 Reconnaissance Faciale** : Identifiez les visiteurs récurrents et personnalisez leur expérience !

## 👤 Reconnaissance Faciale

La vitrine peut maintenant détecter et reconnaître les visages des visiteurs !

### Fonctionnalités

| Fonctionnalité | Description |
|----------------|-------------|
| **Détection automatique** | Chaque photo capture les visages présents |
| **Base d'apprentissage** | Constitution progressive d'une base de visiteurs |
| **Reconnaissance** | Identification des visiteurs récurrents |
| **Compteur de visites** | Suivi du nombre de visites par personne |
| **Nommage** | Possibilité de nommer les visiteurs connus |

### Affichage dans l'Interface

- **Barre de statut** : Compteur de visiteurs connus (👤 X visitors)
- **Widget flottant** : Affiche le nombre total de visiteurs
- **Modal QR** : Après capture, affiche les visages détectés avec :
  - ✓ **Known** (vert) : Visiteur reconnu + nombre de visites
  - ★ **New** (orange) : Nouveau visiteur

### Structure des Données

```
vitrine_interactive/
├── faces/                    # Base de données des visages
│   ├── embeddings.json       # Embeddings + métadonnées
│   ├── unknown/              # Visages non identifiés (review)
│   └── users/                # Dossiers par utilisateur
│       ├── user_abc123/
│       │   ├── face_001.jpg
│       │   └── face_002.jpg
│       └── user_def456/
```

## 🎮 Contrôles Gestuels

| Geste | Icône | Action | Durée |
|-------|-------|--------|-------|
| **Main gauche/droite** | 👋 | Naviguer entre les messages | Instantané |
| **Main ouverte** | ✋ | Ouvrir les détails du message | Maintenir 1s |
| **Poing fermé** | ✊ | Fermer les détails | Instantané |
| **Pouce levé** | 👍 | Capturer photo + Face ID + QR code | Maintenir 1.5s |
| **Main disparaît** | ❌ | Fermer les détails ouverts | Automatique |

### Zones de Navigation

```
┌─────────────────────────────────────────────┐
│  ◀ PRÉCÉDENT  │    CENTRE     │  SUIVANT ▶  │
│    (< 25%)    │   (35-65%)    │   (> 75%)   │
│               │ ✋ Détails    │             │
└─────────────────────────────────────────────┘
```

## 🎨 Modes d'Affichage

- **Mode Sombre** : Affichage par défaut (économie d'énergie, ambiance)
- **Mode Clair** : S'active automatiquement quand une main est détectée (meilleure visibilité en plein jour)
- **Retour au mode sombre** : Après 60 secondes sans détection de main

## 🚀 Cas d'Usage

- **Agence Immobilière** : Parcourir les biens, filtrer, planifier une visite
- **Restaurant / Bar** : Menu du jour, suggestions, réservation de table
- **Boutique de Mode** : Collection en carousel, tailles disponibles, lien d'achat via QR
- **Salon de Coiffure** : Créneaux disponibles, prise de rendez-vous
- **Concessionnaire** : Configuration véhicule, demande d'essai
- **Centre Commercial** : Reconnaissance des clients VIP, offres personnalisées

## 📦 Prérequis

### Matériel
- **Écran** : TV, moniteur ou vidéoprojecteur (orienté vers la vitrine)
- **Ordinateur** : Raspberry Pi 4/5 ou PC (connecté au réseau UPlanet)
- **Webcam** : USB, bonne qualité, orientée vers les passants

### Logiciel
- Python 3.8+ avec environnement `~/.astro`
- OpenCV (`cv2`)
- MediaPipe (détection des mains et visages)
- Flask (serveur web)
- IPFS daemon (pour stockage des photos)
- Noeud Astroport.ONE configuré

### Optionnel (meilleure reconnaissance faciale)
```bash
pip install face_recognition dlib
```

## 🔧 Installation

```bash
# Installez Astroport.ONE (si pas déjà fait)
bash <(wget -qO- https://install.astroport.com)

# Sélectionnez votre UPlanet ẐEN || ORIGIN
UPLANETNAME=$(cat ~/.ipfs/swarm.key 2>/dev/null || echo "EnfinLibre")

# Installer les dépendances de base
pip install flask flask-cors opencv-python mediapipe qrcode[pil] requests

# (Optionnel) Installer face_recognition pour une meilleure reconnaissance
pip install face_recognition dlib

# Lancer la vitrine
cd ~/.zen/workspace/vitrine_interactive
./start_vitrine.sh
```

### Options de démarrage

```bash
# Port personnalisé
./start_vitrine.sh --port 5555

# Caméra spécifique
./start_vitrine.sh --camera 1

# Les deux
./start_vitrine.sh --port 5555 --camera 1
```

## 🌐 Accès à l'Interface

Une fois lancé, ouvrez dans un navigateur :

```
http://localhost:5555
```

Ou sur un autre appareil du réseau :
```
http://<IP_DU_RASPBERRY>:5555
```

## 📡 Fonctionnalités Techniques

### Flux Nostr
- Affiche les messages (kind 1) du relais Astroport local
- Récupère les profils (kind 0) des auteurs
- Affiche : avatar, nom, NIP-05, bannière, bio

### Capture Photo + Face ID
1. 👍 Pouce levé maintenu 1.5s
2. 📸 Capture de l'image webcam
3. 👤 Détection et reconnaissance des visages
4. 📤 Upload automatique vers IPFS
5. 📡 Publication sur Nostr (avec lien IPFS)
6. 🔲 Affichage QR code + résultats Face ID (10 secondes)

### Interface Cover Flow
- Style iPod avec effet 3D
- Réflexions et perspective
- Navigation fluide au clavier/souris/tactile
- Animations CSS optimisées pour Raspberry Pi

## 🔌 API Endpoints

### Endpoints Principaux

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/` | GET | Interface principale |
| `/video_feed` | GET | Flux vidéo MJPEG de la webcam |
| `/api/gesture` | GET | État actuel des gestes détectés |
| `/api/events` | GET | Messages Nostr avec profils |
| `/api/capture` | POST | Capture photo + Face ID + upload IPFS |
| `/api/profile/<pubkey>` | GET | Profil Nostr d'un auteur |
| `/api/qr` | GET | QR code pour le lien G1 |

### Endpoints Reconnaissance Faciale

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/faces/stats` | GET | Statistiques de la base de visages |
| `/api/faces/users` | GET | Liste de tous les visiteurs reconnus |
| `/api/faces/user/<id>` | GET | Détails d'un visiteur spécifique |
| `/api/faces/user/<id>/name` | POST | Nommer un visiteur |
| `/api/faces/process` | POST | Traiter une photo spécifique |
| `/api/faces/batch` | POST | Traiter toutes les photos existantes |

### Exemples d'utilisation

```bash
# Obtenir les statistiques
curl http://localhost:5555/api/faces/stats

# Lister les visiteurs
curl http://localhost:5555/api/faces/users

# Nommer un visiteur
curl -X POST http://localhost:5555/api/faces/user/user_abc123/name \
  -H "Content-Type: application/json" \
  -d '{"name": "Jean Dupont"}'

# Traiter toutes les photos existantes (batch)
curl -X POST http://localhost:5555/api/faces/batch
```

## 📁 Structure du Projet

```
vitrine_interactive/
├── vitrine.py                  # Serveur Flask principal
├── face_recognition_module.py  # Module de reconnaissance faciale
├── start_vitrine.sh            # Script de démarrage
├── templates/
│   └── shop_carousel.html      # Template HTML
├── static/
│   ├── shop_carousel.css       # Styles (dark/light modes, face UI)
│   └── shop_carousel.js        # Logique frontend + face handling
├── photos/                     # Photos capturées
├── faces/                      # Base de données des visages
│   ├── embeddings.json         # Embeddings vectoriels
│   ├── unknown/                # Nouveaux visages non identifiés
│   └── users/                  # Dossiers par utilisateur
└── README.md
```

## ⚙️ Configuration

### Variables d'environnement

1. Copier `.env.template` vers `.env` et configurer :

```bash
cp .env.template .env
# Éditer .env avec vos paramètres
```

Ou utiliser le script de gestion :

```bash
./manage_env.sh init              # Créer .env depuis .env.template
./manage_env.sh show              # Afficher les variables
./manage_env.sh set VITRINE_QR_DISPLAY_TIME 15
./manage_env.sh get VITRINE_QR_DISPLAY_TIME
./manage_env.sh validate          # Vérifier les types
./manage_env.sh help              # Aide
```

Variables principales (défauts dans `.env.template`) :

| Variable | Description | Défaut |
|----------|-------------|--------|
| `VITRINE_ZONE_LEFT` / `VITRINE_ZONE_RIGHT` | Zones de swipe (0-1) | 0.25 / 0.75 |
| `VITRINE_SWIPE_COOLDOWN` | Délai entre swipes (s) | 0.5 |
| `VITRINE_THUMBS_UP_HOLD_TIME` | Durée pouce levé → capture (s) | 3.0 |
| `VITRINE_OPEN_HAND_HOLD_TIME` | Durée main ouverte → détails (s) | 2.0 |
| `VITRINE_QR_DISPLAY_TIME` | Affichage QR après capture (s) | 10 |
| `VITRINE_DARK_MODE_TIMEOUT` | Retour mode sombre sans main (s) | 30 |
| `VITRINE_FACE_MATCH_THRESHOLD` | Seuil reconnaissance (0.6 = défaut) | 0.6 |
| `VITRINE_MIN_FACE_SIZE` | Taille min visage (pixels) | 50 |

Variables optionnelles (port, caméra) : `VITRINE_PORT`, `VITRINE_CAMERA` (si utilisées par le script de démarrage).

## 🛠️ Gestion des Visages (CLI)

Le module de reconnaissance peut être utilisé en ligne de commande :

```bash
# Traiter toutes les photos existantes (initialisation)
python face_recognition_module.py --batch

# Traiter une photo spécifique
python face_recognition_module.py --photo photos/photo_20251203_170102.jpg

# Afficher les statistiques
python face_recognition_module.py --stats

# Lister tous les utilisateurs
python face_recognition_module.py --users

# Nommer un utilisateur
python face_recognition_module.py --name user_abc123 "Jean Dupont"
```

## 🐛 Dépannage

### La webcam n'est pas détectée
```bash
# Lister les caméras
ls /dev/video*

# Tester avec un autre index
./start_vitrine.sh --camera 1
```

### Les gestes ne sont pas reconnus
- Vérifier l'éclairage (éviter contre-jour)
- Positionner la main bien visible dans le cadre
- La main doit être à ~50cm-1m de la caméra

### Le pouce levé n'est pas détecté
- Lever le pouce bien haut (au-dessus des autres doigts)
- Fermer les 4 autres doigts en poing
- Maintenir la position stable pendant 1.5s

### Mode clair ne s'active pas
- Vérifier que la main est bien détectée (indicateur vert)
- Le mode clair s'active dès détection d'une main

### Face recognition ne fonctionne pas
```bash
# Vérifier si face_recognition est installé
python -c "import face_recognition; print('OK')"

# Si non installé, utiliser MediaPipe (fallback)
# La détection fonctionne, mais reconnaissance moins précise

# Pour installer face_recognition
pip install face_recognition dlib
```

### Purger la base de visages
```bash
# Supprimer la base pour recommencer
rm -rf faces/
# Les dossiers seront recréés automatiquement
```

## 📜 Licence

AGPL-3.0 - Voir [LICENSE](../LICENSE)

## 🤝 Contribution

Projet CopyLaRadio / UPlanet - Contributions bienvenues !

---

**Contact** : support@qo-op.com | [CopyLaRadio](https://copylaradio.com)
