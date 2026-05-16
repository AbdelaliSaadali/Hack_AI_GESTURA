package com.gestura.app.screens

import android.util.Log
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavController
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.rememberNavController
import com.gestura.app.components.ProfileMenu
import com.gestura.app.navigation.Screen
import com.gestura.app.ui.theme.*

@Composable
fun HomeScreen(navController: NavController, bottomPadding: Dp = 0.dp) {
    val colors = MaterialTheme.colorScheme

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background)
            // Handle status bar inset
            .statusBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp)
            // Handle bottom bar padding + extra spacing
            .padding(top = 16.dp, bottom = bottomPadding + 24.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        HomeHeader(navController = navController)

        TalkToSignerCard(onStartSpeaking = {
            Log.d("NAV_DEBUG", "Start Speaking clicked, navigating to: ${Screen.VoiceToSign.route}")
            navController.navigate(Screen.VoiceToSign.route) {
                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                launchSingleTop = true
            }
        })

        UnderstandSignerCard(onOpenCamera = {
            Log.d("NAV_DEBUG", "Open Camera clicked, navigating to: ${Screen.SignToText.route}")
            navController.navigate(Screen.SignToText.route) {
                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                launchSingleTop = true
            }
        })

        LearningPortalCard()
    }
}

@Composable
private fun HomeHeader(navController: NavController) {
    val colors = MaterialTheme.colorScheme
    var profileMenuExpanded by remember { mutableStateOf(false) }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column {
            Text(
                text = "Welcome back,",
                style = MaterialTheme.typography.bodyLarge,
                color = colors.onSurfaceVariant,
            )
            Text(
                text = "Sarah",
                style = MaterialTheme.typography.headlineLarge,
                color = colors.primary,
                fontWeight = FontWeight.Bold,
            )
        }

        Box {
            IconButton(onClick = { profileMenuExpanded = true }) {
                Box(
                    modifier = Modifier
                        .size(48.dp)
                        .clip(CircleShape)
                        .background(colors.primaryContainer),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = Icons.Filled.Person,
                        contentDescription = "Profile menu",
                        tint = colors.onPrimaryContainer,
                        modifier = Modifier.size(28.dp),
                    )
                }
            }

            ProfileMenu(
                expanded = profileMenuExpanded,
                onDismissRequest = { profileMenuExpanded = false },
                onNavigate = { route ->
                    profileMenuExpanded = false
                    navController.navigate(route) {
                        popUpTo(navController.graph.findStartDestination().id) {
                            saveState = true
                        }
                        launchSingleTop = true
                        restoreState = true
                    }
                },
                onLogoutComingSoon = { profileMenuExpanded = false },
            )
        }
    }
}

@Composable
private fun TalkToSignerCard(onStartSpeaking: () -> Unit) {
    val colors = MaterialTheme.colorScheme

    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        elevation = CardDefaults.elevatedCardElevation(defaultElevation = 4.dp),
        colors = CardDefaults.elevatedCardColors(containerColor = colors.surface),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(colors.primaryContainer),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        Icons.Filled.RecordVoiceOver,
                        contentDescription = null,
                        tint = colors.onPrimaryContainer,
                        modifier = Modifier.size(24.dp),
                    )
                }
                Column {
                    Text(
                        text = "Talk to a Signer",
                        style = MaterialTheme.typography.titleLarge,
                        color = colors.onSurface,
                    )
                    Text(
                        text = "Voice → Sign Language Translation",
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.onSurfaceVariant,
                    )
                }
            }

            Text(
                text = "Speak naturally and watch your words transform into expressive sign language through our 3D avatar in real time.",
                style = MaterialTheme.typography.bodyMedium,
                color = colors.onSurfaceVariant,
            )

            Button(
                onClick = onStartSpeaking,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = colors.primary,
                    contentColor = colors.onPrimary,
                ),
                contentPadding = PaddingValues(vertical = 14.dp),
            ) {
                Icon(
                    Icons.Filled.Mic,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text("Start Speaking", style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}

@Composable
private fun UnderstandSignerCard(onOpenCamera: () -> Unit) {
    val colors = MaterialTheme.colorScheme

    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        elevation = CardDefaults.elevatedCardElevation(defaultElevation = 4.dp),
        colors = CardDefaults.elevatedCardColors(containerColor = colors.surface),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(colors.primaryContainer),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        Icons.Filled.Videocam,
                        contentDescription = null,
                        tint = colors.onPrimaryContainer,
                        modifier = Modifier.size(24.dp),
                    )
                }
                Column {
                    Text(
                        text = "Understand a Signer",
                        style = MaterialTheme.typography.titleLarge,
                        color = colors.onSurface,
                    )
                    Text(
                        text = "Sign Language → Text Translation",
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.onSurfaceVariant,
                    )
                }
            }

            Text(
                text = "Point your camera at a signer and get instant text translation on your screen, powered by AI vision.",
                style = MaterialTheme.typography.bodyMedium,
                color = colors.onSurfaceVariant,
            )

            OutlinedButton(
                onClick = onOpenCamera,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = colors.primary),
                border = BorderStroke(1.5.dp, colors.primary),
                contentPadding = PaddingValues(vertical = 14.dp),
            ) {
                Icon(
                    Icons.Outlined.CameraAlt,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text("Open Camera", style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}

@Composable
private fun LearningPortalCard() {
    val colors = MaterialTheme.colorScheme

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = colors.surfaceVariant),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(
                            Brush.linearGradient(
                                colors = listOf(colors.primary, colors.primaryContainer)
                            )
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        Icons.Filled.School,
                        contentDescription = null,
                        tint = colors.onPrimary,
                        modifier = Modifier.size(24.dp),
                    )
                }
                Column {
                    Text(
                        text = "Learning Portal",
                        style = MaterialTheme.typography.titleLarge,
                        color = colors.onSurface,
                    )
                    Text(
                        text = "Interactive sign language courses",
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.onSurfaceVariant,
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                DarkStatCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Filled.LocalFireDepartment,
                    iconTint = colors.tertiary,
                    value = "12",
                    label = "Week Streak",
                )
                DarkStatCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Filled.Translate,
                    iconTint = colors.primary,
                    value = "248",
                    label = "Words Learned",
                )
            }

            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        "Current: Basic Greetings",
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.onSurfaceVariant,
                    )
                    Text(
                        "65%",
                        style = MaterialTheme.typography.labelMedium,
                        color = colors.tertiary,
                    )
                }
                LinearProgressIndicator(
                    progress = { 0.65f },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(6.dp)
                        .clip(RoundedCornerShape(3.dp)),
                    color = colors.tertiary,
                    trackColor = colors.outline.copy(alpha = 0.4f),
                )
            }
        }
    }
}

@Composable
private fun DarkStatCard(
    modifier: Modifier = Modifier,
    icon: ImageVector,
    iconTint: Color,
    value: String,
    label: String,
) {
    val colors = MaterialTheme.colorScheme

    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        color = colors.surface,
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = iconTint,
                modifier = Modifier.size(28.dp),
            )
            Column {
                Text(
                    text = value,
                    style = MaterialTheme.typography.headlineSmall,
                    color = colors.onSurface,
                )
                Text(
                    text = label,
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.onSurfaceVariant,
                )
            }
        }
    }
}
