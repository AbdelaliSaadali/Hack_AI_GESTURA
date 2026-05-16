package com.gestura.app.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.RecordVoiceOver
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(
    val route: String,
    val title: String,
    val icon: ImageVector,
) {
    data object Splash : Screen(
        route = "splash",
        title = "Splash",
        icon = Icons.Filled.Info, // Placeholder icon
    )

    data object Home : Screen(
        route = "home",
        title = "Home",
        icon = Icons.Filled.Home,
    )

    data object VoiceToSign : Screen(
        route = "voice_to_sign",
        title = "Voice",
        icon = Icons.Filled.RecordVoiceOver,
    )

    data object SignToText : Screen(
        route = "sign_to_text",
        title = "Camera",
        icon = Icons.Filled.Videocam,
    )

    data object Learning : Screen(
        route = "learning",
        title = "Learn",
        icon = Icons.Filled.School,
    ) {
        const val lessonIdArg = "lessonId"
        const val detailRoutePattern = "learning/{$lessonIdArg}"

        fun createLessonDetailRoute(lessonId: String): String = "learning/$lessonId"
    }

    data object Profile : Screen(
        route = "profile",
        title = "Profile",
        icon = Icons.Filled.Person,
    )

    data object Settings : Screen(
        route = "settings",
        title = "Settings",
        icon = Icons.Filled.Settings,
    )

    data object Help : Screen(
        route = "help",
        title = "Help",
        icon = Icons.Filled.HelpOutline,
    )

    data object About : Screen(
        route = "about",
        title = "About",
        icon = Icons.Filled.Info,
    )
}

val bottomNavItems = listOf(
    Screen.Home,
    Screen.VoiceToSign,
    Screen.SignToText,
    Screen.Learning,
)
