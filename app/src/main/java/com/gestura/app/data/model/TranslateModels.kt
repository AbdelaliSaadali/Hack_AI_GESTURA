package com.gestura.app.data.model

data class TranslateRequest(
    val text: String,
)

data class TranslateResponse(
    val success: Boolean,
    val glosses: List<String>,
    val signs: List<SignItem>,
)

/**
 * A single sign returned by the backend.
 *
 * @param gloss   The uppercase gloss label (e.g. "HELLO").
 * @param type    "skeleton" → animate keyframe data, "fingerspell" → show letters.
 * @param found   Whether the backend found sign data for this gloss.
 * @param frames  For type == "skeleton": list of frames, each frame is a list of
 *                180 landmarks, each landmark is [x, y, z] floats (0..1 normalised).
 *                For type == "fingerspell": empty list.
 */
data class SignItem(
    val gloss: String,
    val type: String,
    val found: Boolean,
    val frames: List<List<List<Float>>>,
)

