package com.gestura.app.data.settings

enum class DetectionSensitivity(val label: String) {
    Low("Low"),
    Medium("Medium"),
    High("High");

    companion object {
        fun fromStored(value: String): DetectionSensitivity {
            return entries.firstOrNull { it.name == value } ?: Medium
        }
    }
}

data class UserPreferences(
    val notificationsEnabled: Boolean = true,
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val language: String = "English",
    val detectionSensitivity: DetectionSensitivity = DetectionSensitivity.Medium,
    val backendMode: String = "Cloud AI",
)
