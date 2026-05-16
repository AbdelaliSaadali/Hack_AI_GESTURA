package com.gestura.app.data.settings

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import java.io.IOException

private val Context.dataStore by preferencesDataStore(name = "gestura_settings")

class SettingsRepository(private val context: Context) {

    private object Keys {
        val NotificationsEnabled = booleanPreferencesKey("notifications_enabled")
        val ThemeMode = stringPreferencesKey("theme_mode")
        val Language = stringPreferencesKey("language")
        val DetectionSensitivity = stringPreferencesKey("detection_sensitivity")
        val BackendMode = stringPreferencesKey("backend_mode")
    }

    val preferencesFlow: Flow<UserPreferences> = context.dataStore.data
        .catch { exception ->
            if (exception is IOException) {
                emit(emptyPreferences())
            } else {
                throw exception
            }
        }
        .map { preferences: Preferences -> preferences.toUserPreferences() }

    suspend fun setThemeMode(mode: ThemeMode) {
        context.dataStore.edit { prefs ->
            prefs[Keys.ThemeMode] = mode.name
        }
    }

    suspend fun setNotificationsEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.NotificationsEnabled] = enabled
        }
    }

    suspend fun setLanguage(language: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.Language] = language
        }
    }

    suspend fun setDetectionSensitivity(sensitivity: DetectionSensitivity) {
        context.dataStore.edit { prefs ->
            prefs[Keys.DetectionSensitivity] = sensitivity.name
        }
    }

    suspend fun setBackendMode(mode: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.BackendMode] = mode
        }
    }

    private fun Preferences.toUserPreferences(): UserPreferences {
        return UserPreferences(
            notificationsEnabled = this[Keys.NotificationsEnabled] ?: true,
            themeMode = ThemeMode.fromStored(this[Keys.ThemeMode] ?: ThemeMode.SYSTEM.name),
            language = this[Keys.Language] ?: "English",
            detectionSensitivity = DetectionSensitivity.fromStored(
                this[Keys.DetectionSensitivity] ?: DetectionSensitivity.Medium.name
            ),
            backendMode = this[Keys.BackendMode] ?: "Cloud AI",
        )
    }
}
