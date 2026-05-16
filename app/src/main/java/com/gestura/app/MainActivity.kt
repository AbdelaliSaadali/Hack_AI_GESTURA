/**
 * Main entry point for the Gestura app.
 * Developed by Abdelali Saadali.
 * © 2026 Abdelali Saadali. All rights reserved.
 */
package com.gestura.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gestura.app.data.settings.ThemeMode
import com.gestura.app.ui.theme.GesturaTheme
import com.gestura.app.viewmodel.AppSettingsViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // Handle the splash screen transition
        installSplashScreen()

        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val appSettingsViewModel: AppSettingsViewModel = viewModel()
            val settingsState by appSettingsViewModel.uiState.collectAsStateWithLifecycle()

            val darkTheme = when (settingsState.themeMode) {
                ThemeMode.LIGHT -> false
                ThemeMode.DARK -> true
                ThemeMode.SYSTEM -> isSystemInDarkTheme()
            }

            GesturaTheme(darkTheme = darkTheme) {
                Surface(modifier = Modifier.fillMaxSize()) {
                    GesturaApp(appSettingsViewModel = appSettingsViewModel)
                }
            }
        }
    }
}
