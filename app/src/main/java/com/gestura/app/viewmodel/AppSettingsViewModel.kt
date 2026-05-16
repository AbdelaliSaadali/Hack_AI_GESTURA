package com.gestura.app.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.gestura.app.data.settings.DetectionSensitivity
import com.gestura.app.data.settings.SettingsRepository
import com.gestura.app.data.settings.ThemeMode
import com.gestura.app.data.settings.UserPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AppSettingsUiState(
    val notificationsEnabled: Boolean = true,
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val language: String = "English",
    val cameraPermissionStatus: String = "Not checked",
    val detectionSensitivity: DetectionSensitivity = DetectionSensitivity.Medium,
    val backendMode: String = "Cloud AI",
    val isLoaded: Boolean = false,
)

class AppSettingsViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = SettingsRepository(application.applicationContext)

    private val _uiState = MutableStateFlow(AppSettingsUiState())
    val uiState: StateFlow<AppSettingsUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.preferencesFlow.collect { prefs ->
                _uiState.update {
                    it.copy(
                        notificationsEnabled = prefs.notificationsEnabled,
                        themeMode = prefs.themeMode,
                        language = prefs.language,
                        detectionSensitivity = prefs.detectionSensitivity,
                        backendMode = prefs.backendMode,
                        isLoaded = true,
                    )
                }
            }
        }
    }

    fun setThemeMode(mode: ThemeMode) {
        viewModelScope.launch {
            repository.setThemeMode(mode)
        }
    }

    fun setNotificationsEnabled(enabled: Boolean) {
        viewModelScope.launch {
            repository.setNotificationsEnabled(enabled)
        }
    }

    fun setLanguage(language: String) {
        viewModelScope.launch {
            repository.setLanguage(language)
        }
    }

    fun setCameraPermissionStatus(status: String) {
        _uiState.update { it.copy(cameraPermissionStatus = status) }
    }

    fun setDetectionSensitivity(sensitivity: DetectionSensitivity) {
        viewModelScope.launch {
            repository.setDetectionSensitivity(sensitivity)
        }
    }

    fun setBackendMode(mode: String) {
        viewModelScope.launch {
            repository.setBackendMode(mode)
        }
    }
}
