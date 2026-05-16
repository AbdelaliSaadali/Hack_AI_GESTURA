package com.gestura.app

import android.util.Log
import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.gestura.app.components.GesturaBottomBar
import com.gestura.app.navigation.GesturaNavGraph
import com.gestura.app.navigation.Screen
import com.gestura.app.navigation.bottomNavItems
import com.gestura.app.viewmodel.AppSettingsViewModel

@Composable
fun GesturaApp(appSettingsViewModel: AppSettingsViewModel) {
    val navController = rememberNavController()
    val colors = MaterialTheme.colorScheme

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination
    val currentRoute = currentDestination?.route

    // Keep bottom bar visible for main routes
    val showBottomBar = currentRoute in bottomNavItems.map { it.route } ||
            currentRoute == Screen.Learning.detailRoutePattern ||
            currentRoute == Screen.Home.route

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        containerColor = colors.background,
        bottomBar = {
            if (showBottomBar && currentRoute != Screen.Splash.route) {
                GesturaBottomBar(
                    currentRoute = currentRoute,
                    onNavigate = { screen ->
                        navController.navigate(screen.route) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                )
            }
        },
        contentWindowInsets = WindowInsets(0, 0, 0, 0) // We'll handle insets manually for more control
    ) { innerPadding ->
        // Use a Box to layer the bottom bar correctly. 
        // We pass the innerPadding to the NavGraph screens so they can handle their own bottom spacing.
        Box(modifier = Modifier.fillMaxSize()) {
            GesturaNavGraph(
                navController = navController,
                appSettingsViewModel = appSettingsViewModel,
                // Passing bottom padding explicitly to screens
                bottomPadding = if (showBottomBar) innerPadding.calculateBottomPadding() else 0.dp
            )
        }
    }
}
