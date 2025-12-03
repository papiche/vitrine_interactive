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

## 🎮 Contrôles Gestuels

| Geste | Icône | Action | Durée |
|-------|-------|--------|-------|
| **Main gauche/droite** | 👋 | Naviguer entre les messages | Instantané |
| **Main ouverte** | ✋ | Ouvrir les détails du message | Maintenir 1s |
| **Poing fermé** | ✊ | Fermer les détails | Instantané |
| **Pouce levé** | 👍 | Capturer photo + QR code | Maintenir 1.5s |
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

## 📦 Prérequis

### Matériel
- **Écran** : TV, moniteur ou vidéoprojecteur (orienté vers la vitrine)
- **Ordinateur** : Raspberry Pi 4/5 ou PC (connecté au réseau UPlanet)
- **Webcam** : USB, bonne qualité, orientée vers les passants

### Logiciel
- Python 3.8+ avec environnement `~/.astro`
- OpenCV (`cv2`)
- MediaPipe (détection des mains)
- Flask (serveur web)
- IPFS daemon (pour stockage des photos)
- Noeud Astroport.ONE configuré

## 🔧 Installation

```bash
# Cloner le dépôt (si pas déjà fait)
cd ~/.zen/Astroport.ONE

# Activer l'environnement Python
source ~/.astro/bin/activate

# Installer les dépendances
pip install flask flask-cors opencv-python mediapipe qrcode[pil] requests

# Lancer la vitrine
cd vitrine_interactive
./start_vitrine.sh
```

### Options de démarrage

```bash
# Port personnalisé
./start_vitrine.sh --port 8080

# Caméra spécifique
./start_vitrine.sh --camera 1

# Les deux
./start_vitrine.sh --port 8080 --camera 1
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

### Capture Photo
1. 👍 Pouce levé maintenu 1.5s
2. 📸 Capture de l'image webcam
3. 📤 Upload automatique vers IPFS
4. 📡 Publication sur Nostr (avec lien IPFS)
5. 🔲 Affichage QR code vers `/g1` (10 secondes)

### Interface Cover Flow
- Style iPod avec effet 3D
- Réflexions et perspective
- Navigation fluide au clavier/souris/tactile
- Animations CSS optimisées pour Raspberry Pi

## 🔌 API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/` | GET | Interface principale |
| `/video_feed` | GET | Flux vidéo MJPEG de la webcam |
| `/api/gesture` | GET | État actuel des gestes détectés |
| `/api/events` | GET | Messages Nostr avec profils |
| `/api/capture` | POST | Capture photo + upload IPFS |
| `/api/profile/<pubkey>` | GET | Profil Nostr d'un auteur |
| `/api/qr` | GET | QR code pour le lien G1 |

## 📁 Structure du Projet

```
vitrine_interactive/
├── vitrine.py              # Serveur Flask principal
├── start_vitrine.sh        # Script de démarrage
├── templates/
│   └── shop_carousel.html  # Template HTML
├── static/
│   ├── shop_carousel.css   # Styles (dark/light modes)
│   └── shop_carousel.js    # Logique frontend
├── photos/                 # Photos capturées (ignoré par git)
│   └── .gitkeep
├── .gitignore
└── README.md
```

## ⚙️ Configuration

### Variables d'environnement (optionnelles)

```bash
export VITRINE_PORT=5555      # Port du serveur
export VITRINE_CAMERA=0       # Index de la caméra
```

### Paramètres dans `vitrine.py`

```python
# Zones de détection (0-1)
ZONE_LEFT = 0.25      # Zone gauche (< 25%)
ZONE_RIGHT = 0.75     # Zone droite (> 75%)

# Durées
SWIPE_COOLDOWN = 0.5       # Délai entre swipes (secondes)
THUMBS_UP_HOLD_TIME = 1.5  # Durée pour capture photo
OPEN_HAND_HOLD_TIME = 1.0  # Durée pour ouvrir détails
QR_DISPLAY_TIME = 10       # Durée affichage QR
DARK_MODE_TIMEOUT = 60     # Retour mode sombre
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

## 📜 Licence

AGPL-3.0 - Voir [LICENSE](../LICENSE)

## 🤝 Contribution

Projet CopyLaRadio / UPlanet - Contributions bienvenues !

---

**Contact** : support@qo-op.com | [CopyLaRadio](https://copylaradio.com)
