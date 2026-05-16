package com.gestura.app.screens.camera

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel

@Composable
fun CameraScreen(
    cameraViewModel: CameraViewModel = viewModel(),
    bottomPadding: Dp = 0.dp
) {
    val uiState by cameraViewModel.uiState.collectAsState()
    val context = LocalContext.current
    val colors = MaterialTheme.colorScheme
    val idleText = CameraViewModel.IDLE_TRANSLATION_TEXT

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        cameraViewModel.onPermissionResult(granted)
    }

    val hasPermission = ContextCompat.checkSelfPermission(
        context,
        Manifest.permission.CAMERA,
    ) == PackageManager.PERMISSION_GRANTED

    LaunchedEffect(hasPermission) {
        cameraViewModel.onPermissionResult(hasPermission)
    }

    val ttsManager = remember { TextToSpeechManager(context) }
    DisposableEffect(Unit) {
        onDispose { ttsManager.release() }
    }

    if (!uiState.permissionGranted) {
        CameraPermissionFallback(
            onRequestPermission = {
                permissionLauncher.launch(Manifest.permission.CAMERA)
            }
        )
        return
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background),
    ) {
        CameraPreview(
            modifier = Modifier.fillMaxSize(),
            lensFacing = uiState.cameraFacing,
            onAnalysisResult = cameraViewModel::onAnalysisResult,
            onCameraError = { error ->
                Log.e("CAMERA_SCREEN", "Camera error", error)
            },
        )

        TopStatusOverlay(
            modifier = Modifier.align(Alignment.TopCenter),
            facingFront = uiState.cameraFacing == CameraSelector.LENS_FACING_FRONT,
        )

        Column(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .padding(bottom = bottomPadding), // Respect bottom nav bar
            verticalArrangement = Arrangement.spacedBy(0.dp),
        ) {
            TranslationOverlayCard(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                translatedText = uiState.translatedText,
                confidence = uiState.confidence,
                status = uiState.statusLabel,
                isTranslating = uiState.isTranslating,
                idleText = idleText,
            )

            Spacer(modifier = Modifier.height(12.dp))

            ControlButtonsRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp)
                    .padding(bottom = 20.dp),
                onClear = cameraViewModel::clearTranslation,
                onSpeak = { ttsManager.speak(uiState.translatedText) },
                onFlip = cameraViewModel::flipCamera,
                isSpeakEnabled = uiState.translatedText.isNotBlank() && uiState.translatedText != idleText,
            )
        }
    }
}

@Composable
private fun CameraPermissionFallback(
    onRequestPermission: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            modifier = Modifier.padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "Camera permission is required to translate signs.",
                style = MaterialTheme.typography.bodyLarge,
                color = colors.onBackground,
                textAlign = TextAlign.Center,
            )
            Button(onClick = onRequestPermission) {
                Text("Grant Camera Permission")
            }
        }
    }
}

@Composable
private fun TopStatusOverlay(
    modifier: Modifier = Modifier,
    facingFront: Boolean,
) {
    val colors = MaterialTheme.colorScheme

    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        colors.background.copy(alpha = 0.7f),
                        Color.Transparent,
                    )
                )
            )
            .statusBarsPadding()
            .padding(horizontal = 20.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(10.dp)
                    .clip(CircleShape)
                    .background(colors.error),
            )
            Text(
                text = "LIVE",
                style = MaterialTheme.typography.labelMedium,
                color = colors.onBackground,
                fontWeight = FontWeight.Bold,
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = colors.surface.copy(alpha = 0.55f),
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Icon(
                        Icons.Filled.AutoAwesome,
                        contentDescription = null,
                        tint = colors.tertiary,
                        modifier = Modifier.size(16.dp),
                    )
                    Text(
                        text = "AI Active",
                        style = MaterialTheme.typography.labelSmall,
                        color = colors.onSurface,
                    )
                }
            }
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = colors.surface.copy(alpha = 0.55f),
            ) {
                Text(
                    text = if (facingFront) "Front" else "Back",
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.onSurface,
                )
            }
        }
    }
}

@Composable
private fun TranslationOverlayCard(
    modifier: Modifier = Modifier,
    translatedText: String,
    confidence: Float,
    status: String,
    isTranslating: Boolean,
    idleText: String,
) {
    val colors = MaterialTheme.colorScheme

    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(24.dp),
        color = colors.surfaceVariant.copy(alpha = 0.92f),
        tonalElevation = 0.dp,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(if (isTranslating) colors.tertiary else colors.primary),
                )
                Text(
                    text = status,
                    style = MaterialTheme.typography.labelMedium,
                    color = if (isTranslating) colors.tertiary else colors.primary,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.5.sp,
                )
            }

            Text(
                text = translatedText.ifBlank { idleText },
                style = MaterialTheme.typography.headlineMedium,
                color = colors.onSurface,
                fontWeight = FontWeight.Bold,
                lineHeight = 30.sp,
            )

            if (confidence > 0f) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Icon(
                        Icons.Filled.Verified,
                        contentDescription = null,
                        tint = colors.primary,
                        modifier = Modifier.size(14.dp),
                    )
                    Text(
                        text = "Confidence: ${(confidence * 100).toInt()}%",
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun ControlButtonsRow(
    modifier: Modifier = Modifier,
    onClear: () -> Unit,
    onSpeak: () -> Unit,
    onFlip: () -> Unit,
    isSpeakEnabled: Boolean,
) {
    val colors = MaterialTheme.colorScheme

    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.SpaceEvenly,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CircularControlButton(
            icon = Icons.Filled.Close,
            label = "Clear",
            containerColor = colors.surface.copy(alpha = 0.7f),
            contentColor = colors.onSurface,
            size = 52.dp,
            onClick = onClear,
        )

        CircularControlButton(
            icon = Icons.AutoMirrored.Filled.VolumeUp,
            label = "Speak",
            containerColor = if (isSpeakEnabled) colors.primary else colors.surface.copy(alpha = 0.7f),
            contentColor = if (isSpeakEnabled) colors.onPrimary else colors.onSurfaceVariant,
            size = 68.dp,
            iconSize = 30.dp,
            onClick = onSpeak,
            enabled = isSpeakEnabled,
        )

        CircularControlButton(
            icon = Icons.Filled.FlipCameraAndroid,
            label = "Flip",
            containerColor = colors.surface.copy(alpha = 0.7f),
            contentColor = colors.onSurface,
            size = 52.dp,
            onClick = onFlip,
        )
    }
}

@Composable
private fun CircularControlButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    containerColor: Color,
    contentColor: Color,
    size: Dp,
    onClick: () -> Unit,
    enabled: Boolean = true,
    iconSize: Dp = 24.dp,
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        FloatingActionButton(
            onClick = { if (enabled) onClick() },
            modifier = Modifier.size(size),
            shape = CircleShape,
            containerColor = containerColor,
            contentColor = contentColor,
            elevation = FloatingActionButtonDefaults.elevation(defaultElevation = 0.dp),
        ) {
            Icon(
                imageVector = icon,
                contentDescription = label,
                modifier = Modifier.size(iconSize),
                tint = contentColor,
            )
        }
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}
