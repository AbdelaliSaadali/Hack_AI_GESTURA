package com.gestura.app.screens.camera

import androidx.camera.core.CameraSelector
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

data class CameraUiState(
    val translatedText: String = CameraViewModel.IDLE_TRANSLATION_TEXT,
    val confidence: Float = 0f,
    val isTranslating: Boolean = false,
    val cameraFacing: Int = CameraSelector.LENS_FACING_BACK,
    val permissionGranted: Boolean = false,
    val statusLabel: String = "READY",
)

class CameraViewModel : ViewModel() {

    companion object {
        const val IDLE_TRANSLATION_TEXT = "Waiting for detection"
    }

    private val _uiState = MutableStateFlow(CameraUiState())
    val uiState: StateFlow<CameraUiState> = _uiState.asStateFlow()

    fun onPermissionResult(granted: Boolean) {
        _uiState.update { it.copy(permissionGranted = granted) }
    }

    fun flipCamera() {
        _uiState.update { state ->
            state.copy(
                cameraFacing = if (state.cameraFacing == CameraSelector.LENS_FACING_BACK) {
                    CameraSelector.LENS_FACING_FRONT
                } else {
                    CameraSelector.LENS_FACING_BACK
                }
            )
        }
    }

    fun clearTranslation() {
        _uiState.update {
            it.copy(
                translatedText = IDLE_TRANSLATION_TEXT,
                confidence = 0f,
                isTranslating = false,
                statusLabel = "READY",
            )
        }
    }

    fun onAnalysisResult(result: AnalysisResult) {
        val hasDetection = result.translatedText.isNotBlank()
        _uiState.update {
            it.copy(
                translatedText = if (hasDetection) result.translatedText else IDLE_TRANSLATION_TEXT,
                confidence = if (hasDetection) result.confidence else 0f,
                isTranslating = if (hasDetection) result.isTranslating else false,
                statusLabel = if (!hasDetection) {
                    "READY"
                } else if (result.isTranslating) {
                    "TRANSLATING..."
                } else {
                    "DETECTED"
                },
            )
        }
    }
}
