package com.gestura.app.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val LightColorScheme = lightColorScheme(
    primary = BluePrimary,
    onPrimary = TextOnDark, // White
    primaryContainer = BlueContainerLight,
    onPrimaryContainer = BlueDark,
    secondary = TextMutedLight,
    onSecondary = TextOnDark,
    tertiary = AmberAccent,
    onTertiary = TextMainLight,
    background = BackgroundLight,
    onBackground = TextMainLight,
    surface = SurfaceLight,
    onSurface = TextMainLight,
    surfaceVariant = BackgroundLight,
    onSurfaceVariant = TextMutedLight,
    outline = OutlineLight,
    error = ErrorRed,
    onError = TextOnDark,
)

private val DarkColorScheme = darkColorScheme(
    primary = BlueLight,
    onPrimary = BlueDark,
    primaryContainer = BlueContainerDark,
    onPrimaryContainer = BlueContainerLight,
    secondary = TextMutedDark,
    onSecondary = TextMainDark,
    tertiary = AmberAccent,
    onTertiary = TextMainDark,
    background = BackgroundDark,
    onBackground = TextMainDark,
    surface = SurfaceDark,
    onSurface = TextMainDark,
    surfaceVariant = SurfaceVariantDark,
    onSurfaceVariant = TextMutedDark,
    outline = OutlineDark,
    error = ErrorRed,
    onError = TextOnDark,
)

@Composable
fun GesturaTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = GesturaTypography,
        content = content,
    )
}
