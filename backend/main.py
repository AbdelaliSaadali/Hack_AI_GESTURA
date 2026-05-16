import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Gestura API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load ASL skeleton landmarks on startup
LANDMARKS_PATH = Path(__file__).parent / "asl_landmarks.json"
with open(LANDMARKS_PATH, encoding="utf-8") as f:
    landmarks_db: dict[str, list] = json.load(f)

# Words ASL typically drops (articles, copulas, etc.)
ASL_DROP_WORDS = {
    "the", "a", "an", "is", "am", "are", "was", "were",
    "be", "been", "being", "do", "does", "did",
    "to", "of", "it", "its",
}

# Common English contractions → expanded forms
CONTRACTIONS = {
    "i'm": "i am",
    "i've": "i have",
    "i'll": "i will",
    "i'd": "i would",
    "you're": "you are",
    "you've": "you have",
    "you'll": "you will",
    "you'd": "you would",
    "he's": "he is",
    "he'll": "he will",
    "he'd": "he would",
    "she's": "she is",
    "she'll": "she will",
    "she'd": "she would",
    "it's": "it is",
    "we're": "we are",
    "we've": "we have",
    "we'll": "we will",
    "we'd": "we would",
    "they're": "they are",
    "they've": "they have",
    "they'll": "they will",
    "they'd": "they would",
    "that's": "that is",
    "who's": "who is",
    "what's": "what is",
    "where's": "where is",
    "when's": "when is",
    "why's": "why is",
    "how's": "how is",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "hasn't": "has not",
    "haven't": "have not",
    "hadn't": "had not",
    "won't": "will not",
    "wouldn't": "would not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "can't": "can not",
    "couldn't": "could not",
    "shouldn't": "should not",
    "let's": "let us",
}


# --- Models ---

class TranslateRequest(BaseModel):
    text: str


class SignInfo(BaseModel):
    gloss: str
    type: str          # "skeleton" or "fingerspell"
    found: bool
    frames: list       # list of frames, each frame = list of 180 [x,y,z]


class TranslateResponse(BaseModel):
    success: bool
    glosses: list[str]
    signs: list[SignInfo]


class LookupResponse(BaseModel):
    gloss: str
    type: str
    found: bool
    frames: list


class HealthResponse(BaseModel):
    status: str
    words_loaded: int


# --- Helpers ---

def normalize_text(text: str) -> list[str]:
    """Lowercase, expand contractions, strip punctuation, split into words."""
    text = text.lower().strip()

    for contraction, expansion in CONTRACTIONS.items():
        text = text.replace(contraction, expansion)

    text = re.sub(r"[^a-z\s]", "", text)

    words = [w for w in text.split() if w and w not in ASL_DROP_WORDS]
    return words


def words_to_glosses(words: list[str]) -> list[str]:
    return [w.upper() for w in words]


def compress_frames(frames):
    if not frames:
        return []
    # Keep only every Nth frame, max 20 frames
    step = max(1, len(frames) // 20)
    reduced = frames[::step][:20]
    # Keep only landmarks 0-74 (drop face landmarks 75-179)
    reduced = [frame[:75] for frame in reduced]
    # Round to 3 decimal places
    reduced = [
        [[round(c, 3) for c in lm] for lm in frame]
        for frame in reduced
    ]
    return reduced


# --- Endpoints ---

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", words_loaded=len(landmarks_db))


@app.get("/vocabulary")
async def vocabulary():
    return sorted(landmarks_db.keys())


@app.get("/lookup/{word}", response_model=LookupResponse)
async def lookup(word: str):
    gloss = word.upper().strip()
    frames = landmarks_db.get(gloss)
    if frames is None:
        raise HTTPException(status_code=404, detail=f"Gloss '{gloss}' not found")
    return LookupResponse(gloss=gloss, type="skeleton", found=True, frames=frames)


@app.post("/translate", response_model=TranslateResponse)
async def translate(req: TranslateRequest):
    words = normalize_text(req.text)
    glosses = words_to_glosses(words)

    signs: list[SignInfo] = []
    for gloss in glosses:
        frames = landmarks_db.get(gloss)
        if frames is not None:
            signs.append(SignInfo(
                gloss=gloss,
                type="skeleton",
                found=True,
                frames=compress_frames(frames),
            ))
        else:
            signs.append(SignInfo(
                gloss=gloss,
                type="fingerspell",
                found=False,
                frames=[],
            ))

    return TranslateResponse(success=True, glosses=glosses, signs=signs)

