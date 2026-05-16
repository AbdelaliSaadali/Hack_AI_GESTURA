package com.gestura.app.learning

import kotlinx.coroutines.delay
import kotlin.random.Random

class MockPracticeEvaluator : PracticeEvaluator {
    override suspend fun evaluate(targetWord: String): PracticeResult {
        // simulate processing
        delay(1000)
        val r = Random.nextFloat()
        return when {
            r > 0.8f -> PracticeResult(
                targetWord = targetWord,
                predictedWord = targetWord,
                confidence = 0.92f,
                margin = 0.2f,
                status = PracticeStatus.Correct,
                feedbackMessage = "Good job! Your sign matches the target."
            )
            r > 0.6f -> PracticeResult(
                targetWord = targetWord,
                predictedWord = "${targetWord}_close",
                confidence = 0.6f,
                margin = 0.08f,
                status = PracticeStatus.AlmostCorrect,
                feedbackMessage = "Almost correct. Try to keep both hands visible and repeat slowly."
            )
            r > 0.4f -> PracticeResult(
                targetWord = targetWord,
                predictedWord = "other",
                confidence = 0.3f,
                margin = 0.02f,
                status = PracticeStatus.Wrong,
                feedbackMessage = "Not quite. Watch the reference and try again."
            )
            else -> PracticeResult(
                targetWord = targetWord,
                predictedWord = null,
                confidence = 0.0f,
                margin = 0f,
                status = PracticeStatus.Uncertain,
                feedbackMessage = "Camera was not confident. Improve lighting and keep your hands inside the frame."
            )
        }
    }
}

