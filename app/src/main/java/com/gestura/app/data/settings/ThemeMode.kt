package com.gestura.app.data.settings

enum class ThemeMode(val label: String) {
    LIGHT("Light"),
    DARK("Dark"),
    SYSTEM("System default");

    companion object {
        fun fromStored(value: String): ThemeMode {
            return entries.firstOrNull { it.name == value } ?: SYSTEM
        }
    }
}
