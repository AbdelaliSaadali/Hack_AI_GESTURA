<div align="center">
  <img src="/Logo.jpeg" alt="Gestura Logo" width="120" height="120" />

  # 🤟 Gestura

  **AI-Powered Sign Language Learning, Recognition & Communication Assistant**

  [![Android](https://img.shields.io/badge/Platform-Android-3DDC84?style=flat&logo=android&logoColor=white)](https://www.android.com/)
  [![Kotlin](https://img.shields.io/badge/Language-Kotlin-7F52FF?style=flat&logo=kotlin&logoColor=white)](https://kotlinlang.org/)
  [![Jetpack Compose](https://img.shields.io/badge/UI-Jetpack%20Compose-4285F4?style=flat&logo=jetpack-compose&logoColor=white)](https://developer.android.com/jetpack/compose)
  [![Python](https://img.shields.io/badge/Backend-Python-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
  [![AI](https://img.shields.io/badge/AI-MediaPipe-0082FB?style=flat&logo=google&logoColor=white)](https://mediapipe.dev/)
  [![OpenCV](https://img.shields.io/badge/Vision-OpenCV-5C3EE8?style=flat&logo=opencv&logoColor=white)](https://opencv.org/)
  [![Blender](https://img.shields.io/badge/3D-Blender-F5792A?style=flat&logo=blender&logoColor=white)](https://www.blender.org/)

  > ⚠️ **Hackathon / Prime7** — Built for an AI innovation challenge focused on accessibility and rural inclusion.

</div>

<br />

---

## 📖 Overview

**Gestura** is an AI-powered sign language learning and communication assistant designed to support accessibility, especially in rural and underserved communities where access to sign language learning centers may be limited.

The platform combines:

- **Voice-to-Sign**: converts spoken words into sign language avatar animations.
- **Sign-to-Text**: recognizes signs from camera input and converts them into text.
- **Learning Portal**: provides structured lessons, raw reference videos, practice mode, progress tracking, and AI-based feedback.

Gestura is designed to work as locally as possible, reducing dependency on internet connectivity and making it more suitable for schools, families, associations, health points, and rural inclusion programs.

---

## 🎯 Problem

Many deaf or hard-of-hearing people face communication barriers, especially in places where:

- sign language learning centers are unavailable;
- families and teachers do not know sign language;
- rural areas lack accessibility tools;
- internet access may be unstable;
- existing solutions are often limited to static images or alphabets.

Gestura aims to make sign language learning and basic communication more accessible through a mobile AI assistant.

---

## 💡 Solution

Gestura provides a mobile-first platform with three main modules:

### 1. Voice-to-Sign

The user speaks naturally. The Android app captures the voice, transcribes it, matches words locally, and displays a sign animation using local assets.

**Pipeline:**

```text
Speech input
↓
Android SpeechRecognizer
↓
Transcription
↓
Semantic matching
↓
video_id lookup
↓
Local FBX avatar animation
```

**Main features:**

- Android SpeechRecognizer integration
- Local semantic matcher
- Synonym support
- JSON-based word mapping
- Local FBX upper-body avatar animations
- No live backend required for the demo runtime

---

### 2. Sign-to-Text

The user performs a sign in front of the camera. The backend extracts body and hand landmarks, compares them to clean sign templates, and returns the most likely word.

**Pipeline:**

```text
Camera frame
↓
MediaPipe Hands + Pose
↓
Hand assignment
↓
Feature extraction
↓
Hand-first template matching
↓
Confidence + explainability
↓
Recognized word
```

**Implemented features:**

- Webcam / camera input
- MediaPipe Hands + Pose
- OpenCV frame capture
- Hand-first recognition
- Left/right hand assignment
- Template matching using cleaned skeletons
- Hand-count penalty
- Confidence scoring
- Explainable distance groups:
  - `Lshape`
  - `Rshape`
  - `Space`
  - `Body`
- Auto-video validation mode for WLASL videos

**Example command:**

```bash
cd backend
source venv/bin/activate

python3 sign_to_text_webcam.py \
  --camera 0 \
  --words help sick eat drink school family mother yes no want \
  --seconds 3 \
  --mirror \
  --min-confidence 35 \
  --top-k 10
```

---

### 3. Learning Portal

The Learning Portal turns Gestura into an interactive sign language learning platform.

It includes:

- lesson categories;
- raw reference videos;
- sign-by-sign learning;
- progress tracking;
- streak tracking;
- practice mode;
- AI-based feedback using the Sign-to-Text evaluator.

**Practice logic:**

```text
Target lesson word
↓
User performs sign
↓
Sign-to-Text recognition
↓
Confidence + margin check
↓
Correct / Almost Correct / Wrong / Uncertain
```

**Example backend practice command:**

```bash
python3 elearning_practice_backend.py \
  --practice-target family \
  --words family school mother yes no \
  --seconds 3 \
  --mirror \
  --practice-min-confidence 45 \
  --practice-min-margin 8 \
  --top-k 5
```

---

## 🧠 AI / Recognition Approach

Gestura uses a practical AI pipeline based on landmarks and normalized templates.

For the hackathon prototype, the Sign-to-Text module does not train a deep neural network from scratch. Instead, it uses:

- MediaPipe landmark extraction;
- normalized hand and body features;
- clean skeleton templates;
- hand-shape comparison;
- hand-position comparison;
- left/right hand swapping support;
- confidence scoring;
- margin-based decision logic;
- hand-count penalty to reduce confusion between one-hand and two-hand signs.

This approach is lightweight, explainable, and suitable for a fast prototype.

---

## 🧩 Current Demo Vocabulary

The project supports a selected set of WLASL-based words through `video_id_to_word.json`.

**Useful demo words include:**

```
help      sick      eat       drink
school    family    mother    yes
no        want      good      bad
write     book      time      class
city      with      how
```

**For the rural inclusion demo, we recommend:**

```
help      sick      eat       drink
school    family    mother    yes
no        want
```

---

## 🏗️ Technical Architecture

Gestura has three main technical layers:

### User-Facing Layer
| Component | Details |
|-----------|---------|
| Android app | Kotlin, Jetpack Compose |
| Screens | Home, Voice-to-Sign, Sign-to-Text, Learning Portal, Profile & Settings |

### Core Processing Layer
| Component | Details |
|-----------|---------|
| Speech recognition | Android SpeechRecognizer |
| Semantic matching | Local JSON-based matcher |
| Vision | Camera frame capture, MediaPipe Hands + Pose |
| Recognition | Feature extraction, hand-first matcher |
| Evaluation | Practice evaluator, local result generation |

### Data / Infrastructure Layer
| Component | Details |
|-----------|---------|
| Datasets | WLASL videos, MediaPipe landmarks |
| Templates | Clean skeletons, JSON metadata |
| Assets | Raw reference videos, FBX avatar assets |
| Processing | Offline Python pipeline |

---

## 🛠️ Tech Stack

### Mobile
- Android · Kotlin · Jetpack Compose · CameraX · Material Design 3

### AI / Vision
- MediaPipe · OpenCV · NumPy · Python

### Data
- JSON · WLASL metadata · Clean skeleton templates · Local Android assets

### 3D / Animation
- Blender · FBX · Ready Player Me / Wolf3D avatar pipeline

### Development
- Android Studio · VS Code · Git / GitHub

---

## 📁 Project Structure

```
Gestura/
├── app/
│   └── src/main/
│       ├── java/com/gestura/app/
│       │   ├── screens/
│       │   ├── viewmodel/
│       │   ├── learning/
│       │   └── components/
│       ├── res/
│       └── assets/
│           ├── video_id_to_word.json
│           ├── gestura_synonyms.json
│           ├── videos/                   # raw reference videos, excluded from public repo
│           └── upper_body_trimmed/       # FBX assets, excluded from public repo
│
├── backend/
│   ├── sign_to_text_webcam.py
│   ├── elearning_practice_backend.py
│   ├── extract_landmarks.py
│   ├── build_clean_skeleton.py
│   ├── stabilize_hand_identity.py
│   └── data/                             # generated/intermediate data, excluded
│
├── README.md
└── .gitignore
```

---

## ⚠️ Public Repository Notice

This public repository intentionally excludes heavy or sensitive assets.

**Not included:**

- raw WLASL videos;
- MP4 learning videos;
- generated FBX avatar animations;
- Blender files;
- large intermediate datasets;
- private/local configuration files;
- build outputs.

These assets are excluded to keep the repository lightweight and safe for public hackathon submission.

> To run the full local demo, the required assets must be placed manually in the expected folders.

---

## 📦 Assets Expected Locally

### Reference videos for Learning Portal

**Expected location:**
```
app/src/main/assets/videos/
```

**Example:**
```
app/src/main/assets/videos/69316.mp4
app/src/main/assets/videos/69364.mp4
app/src/main/assets/videos/69470.mp4
```

### Avatar animations for Voice-to-Sign

**Expected location:**
```
app/src/main/assets/upper_body_trimmed/
```

**Example:**
```
app/src/main/assets/upper_body_trimmed/69331_upper.fbx
```

### Clean skeleton templates for Sign-to-Text

**Expected location:**
```
backend/data/clean_skeletons/
```

**Example:**
```
backend/data/clean_skeletons/69316_clean.json
```

---

## 🚀 Running the Android App

1. Open the project in **Android Studio**.
2. Sync Gradle.
3. Select an Android emulator or physical device.
4. Run the app.

**Test:**
- Voice-to-Sign
- Sign-to-Text UI
- Learning Portal

> **Note:** Full demo playback requires the local assets mentioned above.

---

## 🧪 Running the Sign-to-Text Backend

**Install dependencies:**

```bash
cd backend

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install opencv-python mediapipe numpy
```

**Run webcam recognition:**

```bash
python3 sign_to_text_webcam.py \
  --camera 0 \
  --words help sick eat drink school family mother yes no want \
  --seconds 3 \
  --mirror \
  --min-confidence 35 \
  --top-k 10
```

**Run WLASL video validation:**

```bash
python3 sign_to_text_webcam.py \
  --camera data/raw_videos/69364.mp4 \
  --auto-video \
  --words help sick eat drink school family mother yes no want \
  --min-confidence 0 \
  --top-k 10
```

---

## 🎓 Running E-Learning Practice Mode

**Example:**

```bash
python3 elearning_practice_backend.py \
  --practice-target family \
  --words family school mother yes no \
  --seconds 3 \
  --mirror \
  --practice-min-confidence 45 \
  --practice-min-margin 8 \
  --top-k 5
```

**Possible results:**

```
CORRECT
ALMOST CORRECT
WRONG
UNCERTAIN
```

The evaluator uses prediction confidence and confidence margin to avoid unsafe feedback.

---

## 🧪 Validation Example

**Example successful practice result:**

```
Target:     FAMILY
Prediction: family
Confidence: 72.8%
Margin:     34.9%
Result:     CORRECT
```

**Example Sign-to-Text result:**

```
1. family   conf=72.0%  dist=0.2659
2. mother   conf=49.5%  dist=0.4796
```

---

## 🌍 Use Case: Rural Inclusion

Gestura is especially relevant for rural or underserved areas because:

- it can run locally;
- it supports learning without a physical sign language center;
- it can help schools teach basic signs;
- it can support families communicating with deaf members;
- it can assist associations and healthcare points with basic communication.

---

## 💰 Realistic Product Direction

Gestura should not be positioned as a certified interpreter replacement.

**The realistic positioning is:**

> An AI learning and basic communication assistant for sign language inclusion.

**Potential users:**

- schools;
- NGOs;
- rural learning centers;
- accessibility associations;
- families;
- healthcare points;
- training centers.

---

## 🔮 Future Improvements

Planned improvements:

- Android-native Sign-to-Text engine;
- stronger motion features;
- contact-zone features;
- more robust multi-user evaluation;
- larger sign vocabulary;
- teacher dashboard;
- persistent learning progress;
- offline learning packages;
- support for more sign languages;
- better video player integration in the Learning Portal;
- improved confidence calibration.

---

## 👥 Team

Developed by:

- **Abdelali Saadali**

---

## 📜 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

---

> **Important:** Before pushing, make sure the README does **not** claim that the full dataset/assets are included. This version says clearly that raw videos and FBX files are excluded intentionally.
