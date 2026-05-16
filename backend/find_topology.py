import json
import sys

import requests

from hand_topology_reconstruction import reconstruct_hand_topology


API_URL = "http://127.0.0.1:8000/translate"


def main():
    word = sys.argv[1] if len(sys.argv) > 1 else "coffee"
    safe_word = word.strip().replace(" ", "_").upper()

    resp = requests.post(API_URL, json={"text": word}, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    frames = []
    for sign in data.get("signs", []):
        if sign.get("found") and sign.get("frames"):
            frames = sign["frames"]
            break

    if not frames:
        raise RuntimeError(f"No frames returned for {word!r}")

    result = reconstruct_hand_topology(
        frames,
        output_path=f"reconstructed_topology_{safe_word}.json",
    )

    print(json.dumps({"word": word, "root": result.get("root"), "edges": result.get("edges"), "branches": result.get("branches")}, indent=2))


if __name__ == "__main__":
    main()
