package com.gestura.app.viewmodel

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

data class SettingsUiState(
    val notificationsEnabled: Boolean = true,
    val darkModeEnabled: Boolean = false,
    val language: String = "English",
    val cameraPermissionStatus: String = "Not checked",
    val ttsEnabled: Boolean = true,
    val backendMode: String = "Cloud AI",
)

class SettingsViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    fun toggleNotifications(enabled: Boolean) {
        _uiState.update { it.copy(notificationsEnabled = enabled) }
    }

    fun toggleDarkMode(enabled: Boolean) {
        _uiState.update { it.copy(darkModeEnabled = enabled) }
    }

    fun setLanguage(language: String) {
        _uiState.update { it.copy(language = language) }
    }

    fun setCameraPermissionStatus(status: String) {
        _uiState.update { it.copy(cameraPermissionStatus = status) }
    }

    fun toggleTextToSpeech(enabled: Boolean) {
        _uiState.update { it.copy(ttsEnabled = enabled) }
    }

    fun setBackendMode(mode: String) {
        _uiState.update { it.copy(backendMode = mode) }
    }
}

