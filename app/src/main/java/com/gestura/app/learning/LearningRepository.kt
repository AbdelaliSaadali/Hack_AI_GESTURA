package com.gestura.app.learning

import android.content.Context
import android.util.Log
import com.gestura.app.learning.models.LearningCourse
import com.gestura.app.learning.models.LearningSign
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.Locale

class LearningRepository(private val context: Context) {
    private val TAG = "LearningRepo"
    private val wordToVideoId = HashMap<String, String>()
    private val wordToGloss = HashMap<String, String>()
    private var loaded = false

    fun loadAssets() {
        try {
            context.assets.open("video_id_to_word.json").use { stream ->
                val text = BufferedReader(InputStreamReader(stream)).use { it.readText() }
                val json = JSONObject(text)
                val keys = json.keys()
                while (keys.hasNext()) {
                    val k = keys.next()
                    val v = json.opt(k)
                    if (v is JSONObject) {
                        val word = v.optString("word").lowercase(Locale.US).trim()
                        if (word.isNotBlank()) {
                            wordToVideoId[word] = k
                            wordToGloss[word] = v.optString("gloss").ifBlank { word }
                        }
                    } else if (v is String) {
                        val keyIsNumeric = k.all { it.isDigit() }
                        if (keyIsNumeric) {
                            val word = v.lowercase(Locale.US).trim()
                            wordToVideoId[word] = k
                            wordToGloss[word] = word
                        } else {
                            wordToVideoId[k.lowercase(Locale.US).trim()] = v
                        }
                    }
                }
            }
            Log.d(TAG, "Loaded words=${wordToVideoId.size}")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load video_id_to_word.json", e)
        }
        loaded = true
    }

    fun hasWord(word: String): Boolean {
        return wordToVideoId.containsKey(word.lowercase(Locale.US).trim())
    }

    fun getVideoId(word: String): String? {
        return wordToVideoId[word.lowercase(Locale.US).trim()]
    }

    fun getGloss(word: String): String {
        return wordToGloss[word.lowercase(Locale.US).trim()] ?: word
    }

    fun buildCourses(): List<LearningCourse> {
        if (!loaded) loadAssets()

        val coursesConfig = listOf(
            Pair("basic_greetings", listOf("hello", "good", "yes", "no", "you", "here")),
            Pair("introductions", listOf("name", "who", "what", "how", "you")),
            Pair("daily_expressions", listOf("want", "have", "like", "give", "take")),
            Pair("food_drinks", listOf("eat", "drink", "apple", "pizza", "corn", "orange")),
            Pair("family", listOf("family", "mother", "boy", "girl", "brother", "man")),
            Pair("emergency", listOf("help", "sick", "bad", "hot", "crash")),
            Pair("school", listOf("school", "class", "book", "write", "time")),
            Pair("colors", listOf("black", "blue", "brown", "green", "orange", "pink", "purple", "red", "white", "yellow")),
            Pair("animals", listOf("dog", "cat", "bird", "cow", "fish")),
            Pair("sports", listOf("ball", "basketball", "football", "play"))
        )

        val result = ArrayList<LearningCourse>()
        for ((id, words) in coursesConfig) {
            val signs = ArrayList<LearningSign>()
            for (w in words) {
                if (hasWord(w)) {
                    val vid = getVideoId(w) ?: continue
                    val gloss = getGloss(w)
                    val foundPath = AssetUtils.findReferenceVideoAsset(context, vid, w)
                    signs.add(
                        LearningSign(
                            word = w,
                            gloss = gloss,
                            videoId = vid,
                            description = "",
                            instruction = "Watch the raw sign video and mimic the motion",
                            referenceAssetPath = foundPath,
                            practiceTarget = w
                        )
                    )
                }
            }

            val unlocked = when (id) {
                "basic_greetings", "introductions", "daily_expressions", "food_drinks" -> true
                else -> false
            }

            if (signs.isNotEmpty() || unlocked) {
                val title = id.replace('_', ' ').replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.getDefault()) else it.toString() }
                result.add(
                    LearningCourse(
                        id = id,
                        title = title,
                        description = "Learn common signs: ${signs.size} items",
                        difficulty = when (id) {
                            "basic_greetings" -> "Starter"
                            "introductions" -> "Beginner"
                            "daily_expressions" -> "Beginner"
                            "food_drinks" -> "Beginner"
                            else -> "Intermediate"
                        },
                        isUnlocked = unlocked,
                        signs = signs
                    )
                )
            }
        }

        return result
    }

    fun getCourseById(id: String): LearningCourse? {
        return buildCourses().firstOrNull { it.id == id }
    }

    fun getSignByWord(word: String): LearningSign? {
        val vid = getVideoId(word) ?: return null
        val path = AssetUtils.findReferenceVideoAsset(context, vid, word)
        return LearningSign(
            word = word,
            gloss = getGloss(word),
            videoId = vid,
            referenceAssetPath = path,
            practiceTarget = word
        )
    }

    fun getNextSign(courseId: String, currentIndex: Int): LearningSign? {
        val course = getCourseById(courseId) ?: return null
        val next = currentIndex + 1
        return if (next in course.signs.indices) course.signs[next] else null
    }
}

