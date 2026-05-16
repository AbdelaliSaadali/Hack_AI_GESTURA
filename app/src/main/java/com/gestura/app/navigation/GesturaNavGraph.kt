package com.gestura.app.navigation

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.gestura.app.screens.AboutScreen
import com.gestura.app.screens.CustomSplashScreen
import com.gestura.app.screens.HelpScreen
import com.gestura.app.screens.HomeScreen
import com.gestura.app.screens.LearnScreen
import com.gestura.app.screens.LessonDetailScreen
import com.gestura.app.screens.ProfileScreen
import com.gestura.app.screens.SettingsScreen
import com.gestura.app.screens.camera.CameraScreen
import com.gestura.app.screens.VoiceToSignScreen
import com.gestura.app.viewmodel.AppSettingsViewModel
import com.gestura.app.viewmodel.LearnViewModel

@Composable
fun GesturaNavGraph(
    navController: NavHostController,
    appSettingsViewModel: AppSettingsViewModel,
    bottomPadding: Dp = 0.dp
) {
    val learnViewModel: LearnViewModel = viewModel()

    NavHost(
        navController = navController,
        startDestination = Screen.Splash.route,
    ) {
        composable(Screen.Splash.route) {
            CustomSplashScreen(navController = navController)
        }
        composable(Screen.Home.route) {
            HomeScreen(navController = navController, bottomPadding = bottomPadding)
        }
        composable(Screen.VoiceToSign.route) {
            VoiceToSignScreen(bottomPadding = bottomPadding)
        }
        composable(Screen.SignToText.route) {
            CameraScreen(bottomPadding = bottomPadding)
        }
        composable(Screen.Learning.route) {
            LearnScreen(
                navController = navController,
                viewModel = learnViewModel,
                bottomPadding = bottomPadding
            )
        }
        composable(
            route = Screen.Learning.detailRoutePattern,
            arguments = listOf(
                navArgument(Screen.Learning.lessonIdArg) {
                    type = NavType.StringType
                }
            ),
        ) { backStackEntry ->
            val lessonId = backStackEntry.arguments?.getString(Screen.Learning.lessonIdArg).orEmpty()
            LessonDetailScreen(
                navController = navController,
                lessonId = lessonId,
                viewModel = learnViewModel,
                bottomPadding = bottomPadding
            )
        }
        composable(Screen.Profile.route) {
            ProfileScreen(navController = navController)
        }
        composable(Screen.Settings.route) {
            SettingsScreen(
                navController = navController,
                viewModel = appSettingsViewModel,
            )
        }
        composable(Screen.Help.route) {
            HelpScreen(navController = navController)
        }
        composable(Screen.About.route) {
            AboutScreen(navController = navController)
        }
    }
}
