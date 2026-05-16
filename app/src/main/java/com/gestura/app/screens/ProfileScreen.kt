package com.gestura.app.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.EmojiEvents
import androidx.compose.material.icons.filled.Face
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import kotlinx.coroutines.launch

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(navController: NavController) {
    val colors = MaterialTheme.colorScheme
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    Scaffold(
        containerColor = colors.background,
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = { Text("Profile", color = colors.onBackground) },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = colors.onBackground)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = colors.background),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Card(
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(containerColor = colors.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
            ) {
                Column(
                    modifier = Modifier.padding(20.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Surface(shape = CircleShape, color = colors.primaryContainer) {
                        Icon(
                            Icons.Filled.Face,
                            contentDescription = null,
                            tint = colors.onPrimaryContainer,
                            modifier = Modifier.padding(18.dp),
                        )
                    }
                    Text("Sarah Johnson", style = MaterialTheme.typography.headlineSmall, color = colors.onSurface, fontWeight = FontWeight.Bold)
                    Text("sarah@gestura.app", style = MaterialTheme.typography.bodyMedium, color = colors.onSurfaceVariant)
                    Button(onClick = { scope.launch { snackbarHostState.showSnackbar("Edit profile coming soon") } }) {
                        Icon(Icons.Filled.Edit, contentDescription = null, tint = colors.onPrimary)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Edit Profile", color = colors.onPrimary)
                    }
                }
            }

            StatGrid()

            Card(
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(containerColor = colors.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Achievements", style = MaterialTheme.typography.titleLarge, color = colors.onSurface, fontWeight = FontWeight.SemiBold)
                    AchievementRow(Icons.Filled.LocalFireDepartment, "12-day streak", "Keep signing every day")
                    AchievementRow(Icons.Filled.School, "Lesson finisher", "Completed 4 beginner lessons")
                    AchievementRow(Icons.Filled.Translate, "248 words learned", "Your progress is growing")
                    Button(onClick = { scope.launch { snackbarHostState.showSnackbar("Achievement details coming soon") } }) {
                        Icon(Icons.Filled.EmojiEvents, contentDescription = null, tint = colors.onPrimary)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("View Achievements", color = colors.onPrimary)
                    }
                }
            }
        }
    }
}

@Composable
private fun StatGrid() {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
        ProfileStatCard(Modifier.weight(1f), "12", "Streak", Icons.Filled.LocalFireDepartment)
        ProfileStatCard(Modifier.weight(1f), "248", "Words", Icons.Filled.Translate)
    }
}

@Composable
private fun ProfileStatCard(modifier: Modifier, value: String, label: String, icon: androidx.compose.ui.graphics.vector.ImageVector) {
    val colors = MaterialTheme.colorScheme
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = colors.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Icon(icon, contentDescription = null, tint = colors.primary)
            Text(value, style = MaterialTheme.typography.headlineMedium, color = colors.onSurface, fontWeight = FontWeight.Bold)
            Text(label, style = MaterialTheme.typography.bodySmall, color = colors.onSurfaceVariant)
        }
    }
}

@Composable
private fun AchievementRow(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, subtitle: String) {
    val colors = MaterialTheme.colorScheme
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Surface(shape = RoundedCornerShape(12.dp), color = colors.primaryContainer) {
            Icon(icon, contentDescription = null, tint = colors.onPrimaryContainer, modifier = Modifier.padding(10.dp))
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(title, color = colors.onSurface, fontWeight = FontWeight.SemiBold)
            Text(subtitle, color = colors.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
    }
}
