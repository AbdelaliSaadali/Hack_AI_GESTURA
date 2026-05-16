package com.gestura.app.learning

import com.gestura.app.learning.models.SignPlaybackItem

sealed class PracticeStatus {
    object NotStarted : PracticeStatus()
    object Recording : PracticeStatus()
    object Correct : PracticeStatus()
    object AlmostCorrect : PracticeStatus()
    object Wrong : PracticeStatus()
    object Uncertain : PracticeStatus()
}

data class PracticeResult(
    val targetWord: String,
    val predictedWord: String?,
    val confidence: Float,
    val margin: Float,
    val status: PracticeStatus,
    val feedbackMessage: String
)

interface PracticeEvaluator {
    suspend fun evaluate(targetWord: String): PracticeResult
}

