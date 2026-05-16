package com.gestura.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavController
import com.gestura.app.components.LessonTopBar
import com.gestura.app.components.AssetVideoPlayer
import com.gestura.app.data.LessonSign
import com.gestura.app.viewmodel.LearnViewModel
import com.gestura.app.components.ReferenceBottomSheet
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.media3.common.util.UnstableApi

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LessonDetailScreen(
    navController: NavController,
    lessonId: String,
    viewModel: LearnViewModel,
    bottomPadding: Dp = 0.dp
) {
    val uiState by viewModel.uiState.collectAsState()
    val colors = MaterialTheme.colorScheme
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(lessonId) { viewModel.selectLesson(lessonId) }
    LaunchedEffect(Unit) {
        viewModel.events.collect { message ->
            snackbarHostState.showSnackbar(message)
        }
    }

    val lesson = viewModel.getLessonById(lessonId)
    if (lesson == null) {
        LessonNotFoundScreen(onBack = { navController.popBackStack() })
        return
    }

    val progress = viewModel.getProgress(lessonId)
    val currentSign = viewModel.getCurrentSign(uiState) ?: lesson.signs.firstOrNull()
    val signIndex = uiState.currentSignIndex.coerceAtLeast(0)
    val isCompleted = progress.isCompleted || progress.completedSigns >= progress.totalSigns

    var showReference by remember { mutableStateOf(false) }
    val sheetState = rememberModalBottomSheetState()

    Scaffold(
        containerColor = colors.background,
        snackbarHost = { SnackbarHost(hostState = snackbarHostState) },
        topBar = {
            Column {
                LessonTopBar(
                    title = lesson.title,
                    subtitle = "Lesson",
                    onBackClick = { navController.popBackStack() },
                    onRestartLesson = viewModel::restartLesson,
                    onMarkComplete = viewModel::markLessonComplete,
                    onLessonInfo = viewModel::showLessonInfo,
                )
                LinearProgressIndicator(
                    progress = { progress.progressFraction.coerceIn(0f, 1f) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(4.dp)
                        .padding(horizontal = 16.dp)
                        .clip(RoundedCornerShape(2.dp)),
                    color = colors.primary,
                    trackColor = colors.outline.copy(alpha = 0.4f),
                )
                Spacer(modifier = Modifier.height(8.dp))
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .padding(bottom = bottomPadding), // Respect bottom nav bar
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
                ReferenceVideoCard(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    sign = currentSign,
                    signIndex = signIndex,
                    totalSigns = lesson.signs.size,
                    onWatchLearn = {
                        // open bottom sheet showing reference
                        showReference = true
                    },
                )

            PracticeCard(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
            )

            BottomActionRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 8.dp),
                streak = uiState.streakCount,
                isCompleted = isCompleted,
                onNextSign = viewModel::nextSign,
            )
        }
    }

    // Reference bottom sheet
    if (showReference) {
        ModalBottomSheet(onDismissRequest = { showReference = false }, sheetState = sheetState) {
            ReferenceBottomSheet(
                title = currentSign?.word ?: "",
                videoId = currentSign?.videoId,
                referenceAssetPath = currentSign?.referenceAssetPath,
                instruction = currentSign?.instruction ?: "",
                onClose = { showReference = false },
                onPractice = {
                    currentSign?.let { viewModel.startPractice(it.word) }
                    showReference = false
                }
            )
        }
    }
}

@Composable
private fun LessonNotFoundScreen(onBack: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Lesson not found", style = MaterialTheme.typography.titleMedium, color = colors.onBackground)
            Spacer(modifier = Modifier.height(12.dp))
            Button(onClick = onBack) {
                Text("Back to lessons", color = colors.onPrimary)
            }
        }
    }
}

@OptIn(UnstableApi::class)
@Composable
private fun ReferenceVideoCard(
    modifier: Modifier,
    sign: LessonSign?,
    signIndex: Int,
    totalSigns: Int,
    onWatchLearn: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(20.dp))
            .background(colors.surface)
            .border(1.dp, colors.outline.copy(alpha = 0.6f), RoundedCornerShape(20.dp)),
    ) {
        // If video asset exists, show the player
        if (sign?.referenceAssetPath != null && sign.referenceAssetPath.endsWith(".mp4")) {
            Box(modifier = Modifier.fillMaxSize()) {
                AssetVideoPlayer(sign.referenceAssetPath)
            }
            // Watch & Learn button overlaid
            Button(
                onClick = onWatchLearn,
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(12.dp),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = colors.primary.copy(alpha = 0.12f),
                    contentColor = colors.primary,
                ),
            ) {
                Icon(Icons.Filled.PlayCircle, contentDescription = null, modifier = Modifier.size(16.dp), tint = colors.primary)
                Spacer(modifier = Modifier.size(6.dp))
                Text("Watch & Learn", color = colors.primary)
            }
        } else {
            // No video available - show placeholder
            Button(
                onClick = onWatchLearn,
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(12.dp),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = colors.primary.copy(alpha = 0.12f),
                    contentColor = colors.primary,
                ),
            ) {
                Icon(Icons.Filled.PlayCircle, contentDescription = null, modifier = Modifier.size(16.dp), tint = colors.primary)
                Spacer(modifier = Modifier.size(6.dp))
                Text("Watch & Learn", color = colors.primary)
            }

            Column(
                modifier = Modifier.align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    Icons.Filled.OndemandVideo,
                    contentDescription = null,
                    tint = colors.onSurfaceVariant.copy(alpha = 0.55f),
                    modifier = Modifier.size(56.dp),
                )
                Text("Reference Video", color = colors.onSurfaceVariant)
                Text(
                    text = sign?.word ?: "",
                    style = MaterialTheme.typography.titleMedium,
                    color = colors.onSurface,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = "video id: ${sign?.videoId ?: "N/A"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = colors.onSurfaceVariant,
                )
                Text(
                    text = "Reference video unavailable",
                    style = MaterialTheme.typography.bodySmall,
                    color = colors.onSurfaceVariant,
                )
                Text(
                    text = sign?.instruction ?: "Tap to watch reference video",
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.onSurfaceVariant.copy(alpha = 0.8f),
                )
            }
        }

        Surface(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(12.dp),
            shape = RoundedCornerShape(10.dp),
            color = colors.primaryContainer.copy(alpha = 0.85f),
        ) {
            Text(
                text = "Sign ${signIndex + 1} of $totalSigns",
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                style = MaterialTheme.typography.labelSmall,
                color = colors.onPrimaryContainer,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

@Composable
private fun PracticeCard(modifier: Modifier) {
    val colors = MaterialTheme.colorScheme
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(20.dp))
            .background(colors.surfaceVariant),
    ) {
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Icon(
                Icons.Filled.CameraFront,
                contentDescription = null,
                tint = colors.onSurfaceVariant.copy(alpha = 0.55f),
                modifier = Modifier.size(48.dp),
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "Practice camera mode coming soon",
                style = MaterialTheme.typography.bodySmall,
                color = colors.onSurfaceVariant.copy(alpha = 0.75f),
            )
        }

        Surface(
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(12.dp),
            shape = RoundedCornerShape(10.dp),
            color = colors.surface.copy(alpha = 0.7f),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(Icons.Filled.PersonPin, contentDescription = null, tint = colors.onSurface, modifier = Modifier.size(16.dp))
                Text(
                    text = "Your Turn",
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.onSurface,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }

        Box(
            modifier = Modifier
                .align(Alignment.Center)
                .size(width = 160.dp, height = 180.dp)
                .border(2.5.dp, colors.tertiary, RoundedCornerShape(16.dp)),
        ) {
            Surface(
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .offset(x = (-1).dp, y = (-12).dp),
                shape = RoundedCornerShape(6.dp),
                color = colors.tertiary,
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Icon(Icons.Filled.PanTool, contentDescription = null, tint = colors.onTertiary, modifier = Modifier.size(10.dp))
                    Text(
                        text = "HAND DETECTED",
                        style = MaterialTheme.typography.labelSmall,
                        color = colors.onTertiary,
                        fontWeight = FontWeight.Bold,
                        fontSize = 9.sp,
                        letterSpacing = 0.8.sp,
                    )
                }
            }
        }

        Surface(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(12.dp),
            shape = RoundedCornerShape(10.dp),
            color = colors.primary.copy(alpha = 0.18f),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Icon(Icons.Filled.CheckCircle, contentDescription = null, tint = colors.primary, modifier = Modifier.size(14.dp))
                Text(
                    text = "Practice ready",
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.primary,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

@Composable
private fun BottomActionRow(
    modifier: Modifier,
    streak: Int,
    isCompleted: Boolean,
    onNextSign: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            shape = RoundedCornerShape(14.dp),
            color = colors.primaryContainer.copy(alpha = 0.7f),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    Icons.Filled.LocalFireDepartment,
                    contentDescription = "Streak",
                    tint = colors.tertiary,
                    modifier = Modifier.size(24.dp),
                )
                Text(
                    text = "$streak STREAK",
                    style = MaterialTheme.typography.labelLarge,
                    color = colors.onPrimaryContainer,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        Button(
            onClick = onNextSign,
            enabled = !isCompleted,
            modifier = Modifier
                .weight(1f)
                .height(52.dp),
            shape = RoundedCornerShape(14.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = colors.primary,
                contentColor = colors.onPrimary,
            ),
        ) {
            Text(
                text = if (isCompleted) "Lesson Complete" else "Next Sign",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
            )
            if (!isCompleted) {
                Spacer(modifier = Modifier.width(8.dp))
                Icon(
                    Icons.AutoMirrored.Filled.ArrowForward,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = colors.onPrimary,
                )
            }
        }
    }
}
