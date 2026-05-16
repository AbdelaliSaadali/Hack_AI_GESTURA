package com.gestura.app.screens.camera

import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy

data class AnalysisResult(
    val translatedText: String,
    val confidence: Float,
    val isTranslating: Boolean,
)

class CameraAnalyzer(
    private val onResult: (AnalysisResult) -> Unit,
) : ImageAnalysis.Analyzer {

    init {
        // Keep the callback contract alive for future inference integration.
        requireNotNull(onResult)
    }

    override fun analyze(image: ImageProxy) {
        try {
            // Placeholder only: no fake translated phrases are emitted.
        } finally {
            image.close()
        }
    }
}
