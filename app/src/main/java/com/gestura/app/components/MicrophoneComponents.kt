package com.gestura.app.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

@Composable
fun ExternalMicDetectedBanner(
    visible: Boolean,
    onUseExternalMic: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(
        visible = visible,
        enter = slideInVertically(initialOffsetY = { -it }),
        exit = slideOutVertically(targetOffsetY = { -it }),
        modifier = modifier.fillMaxWidth(),
    ) {
        val isDark = isSystemInDarkTheme()
        val backgroundColor = if (isDark) {
            Color.White.copy(alpha = 0.08f)
        } else {
            Color.White.copy(alpha = 0.9f)
        }
        val borderColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.3f)
        val colors = MaterialTheme.colorScheme

        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            shape = RoundedCornerShape(14.dp),
            color = backgroundColor,
            border = androidx.compose.foundation.BorderStroke(1.dp, borderColor),
            shadowElevation = 4.dp,
        ) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(
                        imageVector = Icons.Filled.Mic,
                        contentDescription = null,
                        tint = colors.primary,
                        modifier = Modifier.size(20.dp),
                    )
                    Text(
                        text = "External microphone detected",
                        style = MaterialTheme.typography.labelLarge,
                        color = colors.onSurface,
                        modifier = Modifier.weight(1f),
                    )
                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.size(24.dp),
                    ) {
                        Icon(
                            imageVector = Icons.Filled.Close,
                            contentDescription = "Dismiss",
                            tint = colors.onSurfaceVariant,
                            modifier = Modifier.size(18.dp),
                        )
                    }
                }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(start = 28.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    TextButton(
                        onClick = onUseExternalMic,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text("Use external mic", color = colors.primary)
                    }
                    TextButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(0.8f),
                    ) {
                        Text("Not now", color = colors.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
fun MicrophoneInputSelector(
    currentInput: String,
    isExternalMicConnected: Boolean,
    modifier: Modifier = Modifier,
) {
    if (!isExternalMicConnected) return

    val isDark = isSystemInDarkTheme()
    val colors = MaterialTheme.colorScheme

    val options = listOf(
        "System default" to "system_default",
        "Phone microphone" to "phone_mic",
        "External microphone" to "external_mic",
    )

    Surface(
        modifier = modifier
            .fillMaxWidth()
            .clickable { },
        shape = RoundedCornerShape(50.dp),
        color = if (isDark) {
            Color.White.copy(alpha = 0.08f)
        } else {
            MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.85f)
        },
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            if (isDark) {
                Color.White.copy(alpha = 0.22f)
            } else {
                colors.outline.copy(alpha = 0.72f)
            }
        ),
        shadowElevation = 3.dp,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            Icon(
                imageVector = Icons.Filled.Mic,
                contentDescription = null,
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.size(8.dp))
            val displayLabel = options.find { it.second == currentInput }?.first ?: "System default"
            Text(
                text = displayLabel,
                style = MaterialTheme.typography.labelLarge,
            )
        }
    }
}



