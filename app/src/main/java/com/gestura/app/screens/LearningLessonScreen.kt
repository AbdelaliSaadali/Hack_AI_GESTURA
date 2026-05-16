package com.gestura.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.gestura.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LearningLessonScreen() {
    Scaffold(
        topBar = {
            LessonTopBar()
        },
        containerColor = BackgroundLight,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // ── Top Half: Reference Video ──
            ReferenceVideoBox(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
            )

            // ── Bottom Half: User Camera with Detection Overlay ──
            UserCameraBox(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
            )

            // ── Bottom Row: Streak + Next Button ──
            BottomActionRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 8.dp),
            )
        }
    }
}

// ──────────────────────────────────────────────
// Top App Bar with Progress
// ──────────────────────────────────────────────
@Suppress("DEPRECATION")
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LessonTopBar() {
    Column {
        TopAppBar(
            title = {
                Column {
                    Text(
                        text = "Lesson 1",
                        style = MaterialTheme.typography.labelMedium,
                        color = Primary,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = "Basic Greetings",
                        style = MaterialTheme.typography.titleLarge,
                        color = TextMain,
                    )
                }
            },
            navigationIcon = {
                IconButton(onClick = { }) {
                    Icon(
                        Icons.Filled.ArrowBack,
                        contentDescription = "Back",
                        tint = TextMain,
                    )
                }
            },
            actions = {
                IconButton(onClick = { }) {
                    Icon(
                        Icons.Filled.MoreVert,
                        contentDescription = "More",
                        tint = TextMuted,
                    )
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = BackgroundLight,
            ),
        )
        // Progress bar below the app bar
        LinearProgressIndicator(
            progress = { 0.35f },
            modifier = Modifier
                .fillMaxWidth()
                .height(4.dp)
                .padding(horizontal = 16.dp)
                .clip(RoundedCornerShape(2.dp)),
            color = Primary,
            trackColor = DividerLight,
        )
        Spacer(Modifier.height(8.dp))
    }
}

// ──────────────────────────────────────────────
// Reference Video Placeholder
// ──────────────────────────────────────────────
@Composable
private fun ReferenceVideoBox(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(20.dp))
            .background(SurfaceLight)
            .border(
                width = 1.dp,
                color = DividerLight,
                shape = RoundedCornerShape(20.dp),
            ),
        contentAlignment = Alignment.Center,
    ) {
        // Label at top-left
        Surface(
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(12.dp),
            shape = RoundedCornerShape(10.dp),
            color = Primary.copy(alpha = 0.1f),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(
                    Icons.Filled.PlayCircle,
                    contentDescription = null,
                    tint = Primary,
                    modifier = Modifier.size(16.dp),
                )
                Text(
                    text = "Watch & Learn",
                    style = MaterialTheme.typography.labelSmall,
                    color = Primary,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }

        // Center placeholder
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(
                imageVector = Icons.Filled.OndemandVideo,
                contentDescription = "Reference video",
                tint = TextMuted.copy(alpha = 0.4f),
                modifier = Modifier.size(56.dp),
            )
            Text(
                text = "Reference Sign Video",
                style = MaterialTheme.typography.bodyMedium,
                color = TextMuted,
            )
            Text(
                text = "\"Hello\" — Wave your hand gently",
                style = MaterialTheme.typography.bodySmall,
                color = TextMuted.copy(alpha = 0.7f),
            )
        }

        // Sign label bottom-right
        Surface(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(12.dp),
            shape = RoundedCornerShape(10.dp),
            color = Accent.copy(alpha = 0.15f),
        ) {
            Text(
                text = "Sign 3 of 10",
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                style = MaterialTheme.typography.labelSmall,
                color = AccentDark,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

// ──────────────────────────────────────────────
// User Camera with Hand Detection Overlay
// ──────────────────────────────────────────────
@Composable
private fun UserCameraBox(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(20.dp))
            .background(CameraPlaceholder),
    ) {
        // Camera placeholder content
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Icon(
                imageVector = Icons.Filled.CameraFront,
                contentDescription = null,
                tint = Color.White.copy(alpha = 0.25f),
                modifier = Modifier.size(48.dp),
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Front Camera Feed",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.35f),
            )
        }

        // "Your Turn" label top-left
        Surface(
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(12.dp),
            shape = RoundedCornerShape(10.dp),
            color = Color.White.copy(alpha = 0.15f),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(
                    Icons.Filled.PersonPin,
                    contentDescription = null,
                    tint = Color.White,
                    modifier = Modifier.size(16.dp),
                )
                Text(
                    text = "Your Turn",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.White,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }

        // ── Green Bounding Box (Hand Detected) ──
        Box(
            modifier = Modifier
                .align(Alignment.Center)
                .size(width = 160.dp, height = 180.dp)
                .border(
                    width = 2.5.dp,
                    color = Success,
                    shape = RoundedCornerShape(16.dp),
                ),
        ) {
            // "HAND DETECTED" label
            Surface(
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .offset(x = (-1).dp, y = (-12).dp),
                shape = RoundedCornerShape(6.dp),
                color = Success,
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Icon(
                        Icons.Filled.PanTool,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(10.dp),
                    )
                    Text(
                        text = "HAND DETECTED",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        fontSize = 9.sp,
                        letterSpacing = 0.8.sp,
                    )
                }
            }
        }

        // Accuracy badge bottom-right
        Surface(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(12.dp),
            shape = RoundedCornerShape(10.dp),
            color = Success.copy(alpha = 0.2f),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Icon(
                    Icons.Filled.CheckCircle,
                    contentDescription = null,
                    tint = Success,
                    modifier = Modifier.size(14.dp),
                )
                Text(
                    text = "87% Match",
                    style = MaterialTheme.typography.labelSmall,
                    color = Success,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
    }
}

// ──────────────────────────────────────────────
// Bottom Row: Streak + Next Sign
// ──────────────────────────────────────────────
@Suppress("DEPRECATION")
@Composable
private fun BottomActionRow(modifier: Modifier = Modifier) {
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Streak badge
        Surface(
            shape = RoundedCornerShape(14.dp),
            color = Accent.copy(alpha = 0.12f),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    Icons.Filled.LocalFireDepartment,
                    contentDescription = "Streak",
                    tint = Accent,
                    modifier = Modifier.size(24.dp),
                )
                Text(
                    text = "12 STREAK",
                    style = MaterialTheme.typography.labelLarge,
                    color = AccentDark,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.5.sp,
                )
            }
        }

        // Next Sign button
        Button(
            onClick = { },
            modifier = Modifier
                .weight(1f)
                .height(52.dp),
            shape = RoundedCornerShape(14.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Primary,
                contentColor = Color.White,
            ),
        ) {
            Text(
                text = "Next Sign",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.width(8.dp))
            Icon(
                Icons.Filled.ArrowForward,
                contentDescription = null,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun LearningLessonScreenPreview() {
    GesturaTheme(darkTheme = false) {
        LearningLessonScreen()
    }
}

