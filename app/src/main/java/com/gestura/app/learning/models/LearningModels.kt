package com.gestura.app.learning.models

import androidx.compose.ui.graphics.vector.ImageVector

data class LearningCourse(
    val id: String,
    val title: String,
    val description: String,
    val difficulty: String,
    val icon: ImageVector? = null,
    val isUnlocked: Boolean = false,
    val signs: List<LearningSign> = emptyList()
)

data class LearningSign(
    val word: String,
    val gloss: String,
    val videoId: String,
    val description: String = "",
    val instruction: String = "",
    val referenceAssetPath: String? = null,
    val practiceTarget: String = word
)

data class SignPlaybackItem(
    val originalWord: String,
    val matchedWord: String?,
    val videoId: String?,
    val assetPath: String?,
    val isKnown: Boolean
)

