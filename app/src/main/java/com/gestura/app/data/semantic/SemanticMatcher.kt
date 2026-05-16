package com.gestura.app.data.semantic

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.Locale

class SemanticMatcher {
    private val aliasToCanonical = HashMap<String, String>()
    private val wordToVideoId = HashMap<String, String>()
    private var loaded = false

    companion object {
        private const val TAG = "Matcher"
    }

    fun loadFromAssets(context: Context) {
        try {
            // load gestura_synonyms.json — expected structure with alias_to_canonical
            context.assets.open("gestura_synonyms.json").use { stream ->
                val text = BufferedReader(InputStreamReader(stream)).use { it.readText() }
                val json = JSONObject(text)
                if (json.has("alias_to_canonical")) {
                    val aliasMap = json.getJSONObject("alias_to_canonical")
                    val keys = aliasMap.keys()
                    while (keys.hasNext()) {
                        val alias = keys.next()
                        val canonical = aliasMap.optString(alias)
                        if (!canonical.isNullOrEmpty()) {
                            aliasToCanonical[alias.lowercase(Locale.US).trim()] = canonical.lowercase(Locale.US).trim()
                        }
                    }
                } else {
                    // fallback if file is flat map (older format)
                    val keys = json.keys()
                    while (keys.hasNext()) {
                        val alias = keys.next()
                        val canonical = json.optString(alias)
                        if (!canonical.isNullOrEmpty()) {
                            aliasToCanonical[alias.lowercase(Locale.US).trim()] = canonical.lowercase(Locale.US).trim()
                        }
                    }
                }
            }
            Log.d(TAG, "Loaded aliases=${aliasToCanonical.size}")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load gestura_synonyms.json", e)
        }

        try {
            // load video_id_to_word.json — expected structure where key is id and value is object with "word"
            context.assets.open("video_id_to_word.json").use { stream ->
                val text = BufferedReader(InputStreamReader(stream)).use { it.readText() }
                val json = JSONObject(text)
                val keys = json.keys()
                while (keys.hasNext()) {
                    val k = keys.next()
                    val v = json.opt(k)
                    when (v) {
                        is String -> {
                            // older fallback: could be id->word or word->id; heuristics:
                            val keyIsNumeric = k.all { it.isDigit() }
                            if (keyIsNumeric) {
                                val word = v.lowercase(Locale.US).trim()
                                wordToVideoId[word] = k
                            } else {
                                val id = v
                                wordToVideoId[k.lowercase(Locale.US).trim()] = id
                            }
                        }
                        is JSONObject -> {
                            // expected: key is id, object contains "word"
                            val word = v.optString("word")
                            if (word.isNotBlank()) {
                                wordToVideoId[word.lowercase(Locale.US).trim()] = k
                            } else {
                                // fallback if object contains mapping differently
                                val idField = v.optString("id")
                                val candidateWord = v.optString("word")
                                if (candidateWord.isNotBlank()) {
                                    wordToVideoId[candidateWord.lowercase(Locale.US).trim()] = if (idField.isNotBlank()) idField else k
                                }
                            }
                        }
                        else -> {
                            // ignore
                        }
                    }
                }
            }
            Log.d(TAG, "Loaded words=${wordToVideoId.size}")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load video_id_to_word.json", e)
        }

        loaded = true
        Log.d(TAG, "SemanticMatcher loaded: words=${wordToVideoId.size} aliases=${aliasToCanonical.size}")
    }

    fun findBestMatch(input: String?): String? {
        if (input == null) return null
        val normalized = input.lowercase(Locale.US).trim()
        if (normalized.isEmpty()) return null

        // exact
        if (wordToVideoId.containsKey(normalized)) return normalized

        // alias
        val aliasResolved = aliasToCanonical[normalized]
        if (!aliasResolved.isNullOrEmpty()) return aliasResolved

        // prevent risky fallback for tiny unknown tokens
        if (normalized.length <= 2) return null

        var best: String? = null
        for (word in wordToVideoId.keys) {
            if (word.length <= 2) continue

            if (normalized.contains(word)) {
                best = word
                break
            }

            if (word.contains(normalized)) {
                best = word
                break
            }
        }

        return best
    }

    fun findVideoIdForWord(canonicalWord: String?): String? {
        if (canonicalWord == null) return null
        return wordToVideoId[canonicalWord.lowercase(Locale.US).trim()]
    }

    fun findVideoIdsForSentence(sentence: String?): List<String> {
        if (!loaded) return emptyList()
        if (sentence.isNullOrBlank()) return emptyList()
        val ids = ArrayList<String>()
        val tokens = sentence.lowercase(Locale.US).split(Regex("\\W+"))
        for (t in tokens) {
            if (t.isBlank()) continue
            val match = findBestMatch(t)
            val id = findVideoIdForWord(match)
            if (id != null) {
                ids.add(id)
                Log.d(TAG, "input=$t -> $match")
                Log.d(TAG, "video_id=$id")
            }
        }
        return ids
    }
}

