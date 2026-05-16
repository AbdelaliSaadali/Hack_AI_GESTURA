package com.gestura.app.data

enum class LessonDifficulty {
    Beginner,
    Intermediate,
    Advanced,
}

data class LessonSign(
    val id: String,
    val word: String,
    val instruction: String,
    val referenceLabel: String,
    val videoId: String = "",
    val referenceAssetPath: String? = null,
)

data class Lesson(
    val id: String,
    val title: String,
    val description: String,
    val signs: List<LessonSign>,
    val difficulty: LessonDifficulty,
    val unlocked: Boolean,
    val tag: String? = null,
)

data class LessonProgress(
    val lessonId: String,
    val completedSigns: Int,
    val totalSigns: Int,
    val isCompleted: Boolean,
) {
    val progressFraction: Float
        get() = if (totalSigns == 0) 0f else completedSigns.toFloat() / totalSigns.toFloat()
}

