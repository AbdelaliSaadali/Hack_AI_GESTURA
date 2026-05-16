package com.gestura.app.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.media3.common.util.UnstableApi
import androidx.compose.material3.ExperimentalMaterial3Api

@OptIn(UnstableApi::class)
@Composable
fun ReferenceBottomSheet(
    title: String,
    videoId: String?,
    referenceAssetPath: String?,
    instruction: String,
    onClose: () -> Unit,
    onPractice: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
        Text(title, style = MaterialTheme.typography.titleLarge)
        Spacer(modifier = Modifier.height(8.dp))
        Text(text = "video id: ${videoId ?: "N/A"}", style = MaterialTheme.typography.bodySmall)
        Spacer(modifier = Modifier.height(12.dp))
        
        // Show video player if MP4 exists
        if (referenceAssetPath != null && referenceAssetPath.endsWith(".mp4")) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(300.dp)
            ) {
                AssetVideoPlayer(referenceAssetPath)
            }
        } else {
            Text(text = "Reference video unavailable", style = MaterialTheme.typography.bodySmall)
        }
        
        Spacer(modifier = Modifier.height(12.dp))
        Text(instruction, style = MaterialTheme.typography.bodyMedium)
        Spacer(modifier = Modifier.height(16.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            TextButton(onClick = onClose) { Text("Close") }
            Spacer(modifier = Modifier.width(8.dp))
            Button(onClick = onPractice) { Text("Practice this sign") }
        }
    }
}

