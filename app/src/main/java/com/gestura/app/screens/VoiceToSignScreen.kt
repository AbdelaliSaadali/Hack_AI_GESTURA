package com.gestura.app.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gestura.app.components.ExternalMicDetectedBanner
import com.gestura.app.components.MicrophoneInputSelector
import com.gestura.app.data.microphone.MicrophoneInput
import com.gestura.app.ui.theme.*
import java.util.concurrent.Executors

@Composable
fun VoiceToSignScreen(
    viewModel: VoiceToSignViewModel = viewModel(),
    bottomPadding: Dp = 0.dp
) {
    val uiState by viewModel.uiState.collectAsState()
    val isCameraMode = false
    val colors = MaterialTheme.colorScheme

    var lensFacing by remember { mutableIntStateOf(CameraSelector.LENS_FACING_FRONT) }

    // Microphone input state
    val micManager = viewModel.getMicrophoneInputManager()
    val micState by micManager.state.collectAsState()
    var showMicDetectedBanner by remember { mutableStateOf(false) }
    
    LaunchedEffect(micState.isExternalMicConnected) {
        if (micState.isExternalMicConnected && micState.selectedInput != MicrophoneInput.EXTERNAL_MIC) {
            showMicDetectedBanner = true
        }
    }

    // Audio permission handling
    val context = LocalContext.current
    var hasAudioPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context, Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasAudioPermission = granted
        if (granted) viewModel.startListening()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background)
            .statusBarsPadding()
            .padding(horizontal = 20.dp)
            .padding(top = 16.dp, bottom = bottomPadding + 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Box(
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                text = "Voice to Sign",
                style = MaterialTheme.typography.headlineLarge,
                color = colors.onBackground,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.align(Alignment.CenterStart),
            )

            NoiseCancelToggleButton(
                checked = uiState.isNoiseCancelEnabled,
                onCheckedChange = viewModel::setNoiseCancelEnabled,
                modifier = Modifier.align(Alignment.CenterEnd),
            )
        }

        // External Microphone Detected Banner
        ExternalMicDetectedBanner(
            visible = showMicDetectedBanner,
            onUseExternalMic = {
                micManager.setSelectedMicrophone(MicrophoneInput.EXTERNAL_MIC)
                showMicDetectedBanner = false
            },
            onDismiss = { showMicDetectedBanner = false },
        )

        // Microphone Input Selector (only shown if external mic is connected)
        if (micState.isExternalMicConnected) {
            MicrophoneInputSelector(
                currentInput = micState.selectedInput.value,
                isExternalMicConnected = micState.isExternalMicConnected,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp),
            )
        }

        // ── Main Content Area ──
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Sign Animation Area (Output)
            SignAnimationArea(
                uiState = uiState,
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(if (isCameraMode) 1f else 2f),
                isCameraMode = isCameraMode
            )

            // Lip Reading Input Area (Visible only in Camera mode)
            if (isCameraMode) {
                LipReadingCameraPanel(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1.2f),
                    lensFacing = lensFacing,
                    onFlipCamera = {
                        lensFacing = if (lensFacing == CameraSelector.LENS_FACING_FRONT) {
                            CameraSelector.LENS_FACING_BACK
                        } else {
                            CameraSelector.LENS_FACING_FRONT
                        }
                    }
                )
            }
        }

        // ── Error message ──
        AnimatedVisibility(visible = uiState.error != null) {
            uiState.error?.let { errorMsg ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = Error.copy(alpha = 0.1f)),
                    shape = RoundedCornerShape(12.dp),
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Icon(
                            Icons.Filled.ErrorOutline,
                            contentDescription = null,
                            tint = Error,
                            modifier = Modifier.size(18.dp),
                        )
                        Text(
                            text = errorMsg,
                            style = MaterialTheme.typography.bodySmall,
                            color = Error,
                        )
                    }
                }
            }
        }

        // ── Gloss chips ──
        AnimatedVisibility(visible = uiState.glosses.isNotEmpty()) {
            GlossChipsRow(
                glosses = uiState.glosses,
                currentIndex = if (uiState.isPlaying) uiState.currentSignIndex else -1,
            )
        }

        // ── Transcription / Lip Reading Status Card ──
        TranscriptionCard(
            transcription = uiState.transcription,
            isListening = uiState.isListening,
            isTranslating = uiState.isTranslating,
            playbackStatus = uiState.playbackStatus,
            isCameraMode = isCameraMode,
            onMicClick = {
                if (uiState.isListening) {
                    viewModel.stopListening()
                } else if (hasAudioPermission) {
                    viewModel.startListening()
                } else {
                    permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                }
            },
        )
    }
}

// ──────────────────────────────────────────────
// Noise cancellation toggle (glass style)
// ──────────────────────────────────────────────
@Composable
private fun NoiseCancelToggleButton(
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = MaterialTheme.colorScheme
    val isDark = isSystemInDarkTheme()

    val offContainer = if (isDark) {
        Color.White.copy(alpha = 0.08f)
    } else {
        colors.surfaceVariant.copy(alpha = 0.85f)
    }
    val onContainer = if (isDark) {
        colors.primary.copy(alpha = 0.26f)
    } else {
        colors.primary.copy(alpha = 0.12f)
    }
    val borderColor = when {
        checked && !isDark -> colors.primary.copy(alpha = 0.18f)
        isDark -> Color.White.copy(alpha = 0.22f)
        else -> colors.outline.copy(alpha = 0.72f)
    }
    val contentColor = when {
        checked -> colors.primary
        isDark -> colors.onSurfaceVariant
        else -> colors.onSurface
    }
    val elevation = when {
        isDark -> 4.dp
        checked -> 2.dp
        else -> 3.dp
    }

    Surface(
        modifier = modifier,
        onClick = { onCheckedChange(!checked) },
        shape = RoundedCornerShape(50.dp),
        color = if (checked) onContainer else offContainer,
        contentColor = contentColor,
        border = androidx.compose.foundation.BorderStroke(1.dp, borderColor),
        shadowElevation = elevation,
        tonalElevation = 0.dp,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 18.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            Icon(
                imageVector = Icons.Filled.GraphicEq,
                contentDescription = null,
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text(
                text = "Noise Cancelation",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Medium,
            )
        }
    }
}

// ──────────────────────────────────────────────
// Sign Animation Area (Avatar/Skeleton output)
// ──────────────────────────────────────────────
@Composable
private fun SignAnimationArea(
    uiState: VoiceToSignUiState,
    modifier: Modifier = Modifier,
    isCameraMode: Boolean = false
) {
    val colors = MaterialTheme.colorScheme
    val currentGloss = if (uiState.isPlaying && uiState.signs.isNotEmpty()) {
        uiState.signs.getOrNull(uiState.currentSignIndex)?.gloss ?: ""
    } else ""

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(24.dp))
            .background(colors.surfaceVariant)
            .border(
                width = 1.dp,
                color = colors.outline.copy(alpha = 0.5f),
                shape = RoundedCornerShape(24.dp),
            ),
        contentAlignment = Alignment.Center,
    ) {
        when {
            uiState.fingerspellLetter != null -> {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                    modifier = Modifier.fillMaxSize(),
                ) {
                    if (currentGloss.isNotEmpty()) {
                        Text(
                            text = currentGloss,
                            style = MaterialTheme.typography.titleMedium,
                            color = colors.primary,
                            fontWeight = FontWeight.Bold,
                        )
                        Spacer(Modifier.height(16.dp))
                    }
                    Text(
                        text = uiState.fingerspellLetter,
                        style = MaterialTheme.typography.displayLarge.copy(fontSize = if (isCameraMode) 56.sp else 80.sp),
                        color = colors.onSurface,
                        fontWeight = FontWeight.Bold,
                        textAlign = TextAlign.Center,
                    )
                }
            }

            uiState.currentFrame.isNotEmpty() -> {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    if (currentGloss.isNotEmpty()) {
                        Text(
                            text = currentGloss,
                            style = MaterialTheme.typography.titleMedium,
                            color = colors.primary,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(top = 12.dp, bottom = 4.dp),
                        )
                    }
                    SkeletonCanvas(
                        frame = uiState.currentFrame,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(12.dp),
                    )
                }
            }

            else -> {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                    modifier = Modifier.padding(20.dp)
                ) {
                    Icon(
                        imageVector = Icons.Filled.Accessibility,
                        contentDescription = "Sign Avatar",
                        tint = colors.primary.copy(alpha = 0.4f),
                        modifier = Modifier.size(if (isCameraMode) 48.dp else 64.dp),
                    )
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = "Sign Language Avatar",
                        style = MaterialTheme.typography.titleMedium,
                        color = colors.onSurfaceVariant,
                        textAlign = TextAlign.Center
                    )
                    Text(
                        text = if (isCameraMode) "Waiting for lip-read text..." else "Waiting for voice input...",
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.onSurfaceVariant.copy(alpha = 0.7f),
                        textAlign = TextAlign.Center
                    )
                }
            }
        }
    }
}

// ──────────────────────────────────────────────
// Lip Reading Camera Panel
// ──────────────────────────────────────────────
@Composable
private fun LipReadingCameraPanel(
    modifier: Modifier = Modifier,
    lensFacing: Int,
    onFlipCamera: () -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val cameraProviderFuture = remember { ProcessCameraProvider.getInstance(context) }

    // Use a long-lived executor
    val analysisExecutor = remember { Executors.newSingleThreadExecutor() }
    DisposableEffect(Unit) {
        onDispose { analysisExecutor.shutdown() }
    }

    var hasPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasPermission = granted
    }

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(24.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .border(
                width = 1.dp,
                color = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f),
                shape = RoundedCornerShape(24.dp),
            ),
        contentAlignment = Alignment.Center
    ) {
        if (!hasPermission) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.padding(24.dp)
            ) {
                Icon(
                    Icons.Filled.VideocamOff,
                    contentDescription = null,
                    modifier = Modifier.size(40.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "Camera required for lip reading",
                    style = MaterialTheme.typography.bodySmall,
                    textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(12.dp))
                Button(
                    onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) },
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("Grant Permission", style = MaterialTheme.typography.labelMedium)
                }
            }
        } else {
            // CameraX Preview - Use key to force recreation on lensFacing change
            key(lensFacing) {
                AndroidView(
                    factory = { ctx ->
                        val previewView = PreviewView(ctx)
                        cameraProviderFuture.addListener({
                            val cameraProvider = cameraProviderFuture.get()

                            val preview = Preview.Builder().build().also {
                                it.setSurfaceProvider(previewView.surfaceProvider)
                            }

                            val imageAnalysis = ImageAnalysis.Builder()
                                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                                .build()

                            imageAnalysis.setAnalyzer(analysisExecutor) { imageProxy ->
                                // TODO: Future Lip-Reading ML Implementation
                                imageProxy.close()
                            }

                            val cameraSelector = CameraSelector.Builder()
                                .requireLensFacing(lensFacing)
                                .build()

                            try {
                                cameraProvider.unbindAll()
                                if (cameraProvider.hasCamera(cameraSelector)) {
                                    cameraProvider.bindToLifecycle(
                                        lifecycleOwner,
                                        cameraSelector,
                                        preview,
                                        imageAnalysis
                                    )
                                } else {
                                    // Fallback to other camera if selected one is missing
                                    val fallback = if (lensFacing == CameraSelector.LENS_FACING_FRONT)
                                        CameraSelector.DEFAULT_BACK_CAMERA else CameraSelector.DEFAULT_FRONT_CAMERA
                                    cameraProvider.bindToLifecycle(
                                        lifecycleOwner,
                                        fallback,
                                        preview,
                                        imageAnalysis
                                    )
                                }
                            } catch (e: Exception) {
                                e.printStackTrace()
                            }
                        }, ContextCompat.getMainExecutor(ctx))
                        previewView
                    },
                    modifier = Modifier.fillMaxSize()
                )
            }

            // Flip Camera Button
            Box(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(12.dp)
            ) {
                SmallFloatingActionButton(
                    onClick = onFlipCamera,
                    containerColor = Color.Black.copy(alpha = 0.5f),
                    contentColor = Color.White,
                    shape = CircleShape,
                ) {
                    Icon(Icons.Filled.FlipCameraAndroid, contentDescription = "Flip Camera", modifier = Modifier.size(20.dp))
                }
            }

            // Status label
            Surface(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 12.dp),
                color = Color.Black.copy(alpha = 0.6f),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(
                    text = "Lip reading ready",
                    color = Color.White,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

// ──────────────────────────────────────────────
// Skeleton Canvas
// ──────────────────────────────────────────────
@Composable
private fun SkeletonCanvas(
    frame: List<List<Float>>,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier) {
        val w = size.width
        val h = size.height

        fun lm(index: Int): Offset? {
            if (index >= frame.size) return null
            val point = frame[index]
            if (point.size < 2) return null
            if (point[0] == 0f && point[1] == 0f && (point.size < 3 || point[2] == 0f)) {
                return null
            }
            val x = point[0].coerceIn(0f, 1f)
            val y = point[1].coerceIn(0f, 1f)
            return Offset(x * w, y * h)
        }

        val bodyColor = Primary
        val bodyStroke = 4f

        val bodyConnections = listOf(
            11 to 12, 11 to 13, 13 to 15, 12 to 14, 14 to 16,
            11 to 23, 12 to 24, 23 to 24, 23 to 25, 25 to 27, 24 to 26, 26 to 28,
        )

        for ((a, b) in bodyConnections) {
            val pA = lm(a) ?: continue
            val pB = lm(b) ?: continue
            drawLine(bodyColor, pA, pB, strokeWidth = bodyStroke, cap = StrokeCap.Round)
        }

        val bodyJoints = listOf(11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28)
        for (idx in bodyJoints) {
            val p = lm(idx) ?: continue
            drawCircle(bodyColor, radius = 6f, center = p)
        }

        val nose = lm(0)
        val leftShoulder = lm(11)
        val rightShoulder = lm(12)
        if (nose != null && leftShoulder != null && rightShoulder != null) {
            val shoulderDist = (rightShoulder - leftShoulder).getDistance()
            val headRadius = shoulderDist * 0.35f
            drawCircle(
                color = bodyColor,
                radius = headRadius,
                center = nose,
                style = androidx.compose.ui.graphics.drawscope.Stroke(width = bodyStroke),
            )
        }

        val handConnections = listOf(
            0 to 1, 1 to 2, 2 to 3, 3 to 4, 0 to 5, 5 to 6, 6 to 7, 7 to 8,
            0 to 9, 9 to 10, 10 to 11, 11 to 12, 0 to 13, 13 to 14, 14 to 15, 15 to 16,
            0 to 17, 17 to 18, 18 to 19, 19 to 20, 5 to 9, 9 to 13, 13 to 17,
        )

        drawHand(frame, 33, handConnections, PrimaryLight, 3.5f, 2.5f, w, h)
        drawHand(frame, 54, handConnections, Accent, 3.5f, 2.5f, w, h)

        val faceColor = TextMuted.copy(alpha = 0.3f)
        val faceEnd = minOf(frame.size, 180)
        for (i in 75 until faceEnd) {
            val p = lm(i) ?: continue
            drawCircle(faceColor, radius = 1.5f, center = p)
        }
    }
}

private fun DrawScope.drawHand(
    frame: List<List<Float>>,
    offset: Int,
    connections: List<Pair<Int, Int>>,
    color: Color,
    dotRadius: Float,
    lineStroke: Float,
    canvasW: Float,
    canvasH: Float,
) {
    fun handLm(relIdx: Int): Offset? {
        val absIdx = offset + relIdx
        if (absIdx >= frame.size) return null
        val pt = frame[absIdx]
        if (pt[0] == 0f && pt[1] == 0f && (pt.size < 3 || pt[2] == 0f)) return null
        val x = pt[0].coerceIn(0f, 1f)
        val y = pt[1].coerceIn(0f, 1f)
        return Offset(x * canvasW, y * canvasH)
    }

    for ((a, b) in connections) {
        val pA = handLm(a) ?: continue
        val pB = handLm(b) ?: continue
        drawLine(color, pA, pB, strokeWidth = lineStroke, cap = StrokeCap.Round)
    }

    for (i in 0 until 21) {
        val p = handLm(i) ?: continue
        drawCircle(color, radius = dotRadius, center = p)
    }
}

@Composable
private fun GlossChipsRow(
    glosses: List<String>,
    currentIndex: Int,
) {
    val colors = MaterialTheme.colorScheme
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        glosses.forEachIndexed { index, gloss ->
            val isCurrent = index == currentIndex
            val isPast = index < currentIndex
            Surface(
                shape = RoundedCornerShape(8.dp),
                color = when {
                    isCurrent -> colors.primary
                    isPast -> colors.secondary.copy(alpha = 0.18f)
                    else -> colors.surface
                },
                tonalElevation = if (isCurrent) 4.dp else 0.dp,
            ) {
                Text(
                    text = gloss,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Normal,
                    color = if (isCurrent) colors.onPrimary else if (isPast) colors.secondary else colors.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun TranscriptionCard(
    transcription: String,
    isListening: Boolean,
    isTranslating: Boolean,
    playbackStatus: String,
    isCameraMode: Boolean,
    onMicClick: () -> Unit,
) {
    Box {
        ElevatedCard(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.elevatedCardColors(
                containerColor = MaterialTheme.colorScheme.surface,
            ),
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = if (isCameraMode) "Lip Reading" else "Transcription",
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    if (isListening && !isCameraMode) {
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Listening...",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = if (transcription.isNotBlank()) {
                        transcription
                    } else if (isCameraMode) {
                        "Detected words will appear here..."
                    } else {
                        "Your speech will appear here..."
                    },
                    style = MaterialTheme.typography.bodyLarge,
                    color = if (transcription.isNotBlank()) {
                        MaterialTheme.colorScheme.onSurface
                    } else {
                        MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                    },
                )

                if (playbackStatus.isNotBlank()) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Surface(
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.08f),
                        shape = RoundedCornerShape(10.dp),
                    ) {
                        Text(
                            text = playbackStatus,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                    }
                }
            }
        }

        // FAB is only for Microphone mode
        if (!isCameraMode) {
            PulsingMicFab(
                isListening = isListening,
                onClick = onMicClick,
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .offset(x = (-12).dp, y = (-12).dp),
            )
        }
    }
}

@Composable
private fun PulsingMicFab(
    isListening: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = MaterialTheme.colorScheme
    val infiniteTransition = rememberInfiniteTransition(label = "mic_pulse")
    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = if (isListening) 1.25f else 1.15f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = if (isListening) 500 else 800, easing = EaseInOut),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "mic_scale",
    )
    val alpha by infiniteTransition.animateFloat(
        initialValue = if (isListening) 0.5f else 0.3f,
        targetValue = 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = if (isListening) 500 else 800, easing = EaseInOut),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "mic_glow",
    )

    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .size(64.dp)
                .scale(scale)
                .clip(CircleShape)
                .background(
                    if (isListening) colors.error.copy(alpha = alpha)
                    else colors.primary.copy(alpha = alpha)
                ),
        )
        FloatingActionButton(
            onClick = onClick,
            modifier = Modifier.size(52.dp),
            shape = CircleShape,
            containerColor = if (isListening) colors.error else colors.primary,
            contentColor = colors.onPrimary,
        ) {
            Icon(
                imageVector = if (isListening) Icons.Filled.Stop else Icons.Filled.Mic,
                contentDescription = if (isListening) "Listening..." else "Start recording",
                modifier = Modifier.size(26.dp),
                tint = colors.onPrimary,
            )
        }
    }
}
