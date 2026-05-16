package com.gestura.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.navigation.NavController
import android.Manifest
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import com.gestura.app.data.settings.ThemeMode
import com.gestura.app.data.microphone.MicrophoneInputManager
import com.gestura.app.data.microphone.MicrophoneInput
import com.gestura.app.navigation.Screen
import com.gestura.app.viewmodel.AppSettingsViewModel
import kotlinx.coroutines.launch
import androidx.compose.ui.platform.LocalContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    navController: NavController,
    viewModel: AppSettingsViewModel,
) {
    val colors = MaterialTheme.colorScheme
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    val micManager = remember { MicrophoneInputManager(context) }
    val micState by micManager.state.collectAsState()
    var showMicInputDialog by remember { mutableStateOf(false) }

    var showThemeDialog by remember { mutableStateOf(false) }
    var showLanguageDialog by remember { mutableStateOf(false) }
    var showCameraPermissionDialog by remember { mutableStateOf(false) }
    var showMicrophonePermissionDialog by remember { mutableStateOf(false) }
    var showBackendDialog by remember { mutableStateOf(false) }

    Scaffold(
        containerColor = colors.background,
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = { Text("Settings", color = colors.onBackground) },
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
            SettingsSectionTitle("Preferences")
            SettingsCard {
                SettingsSwitchRow(
                    title = "Notifications",
                    subtitle = "Lesson reminders and progress updates",
                    checked = uiState.notificationsEnabled,
                    onCheckedChange = viewModel::setNotificationsEnabled,
                )
                SettingsActionRow(
                    title = "Theme",
                    subtitle = uiState.themeMode.label,
                    onClick = { showThemeDialog = true },
                )
                SettingsActionRow(
                    title = "Language",
                    subtitle = uiState.language,
                    onClick = { showLanguageDialog = true },
                )
            }

            SettingsSectionTitle("Privacy & Device")
            SettingsCard {
                SettingsActionRow(
                    title = "Camera permissions",
                    subtitle = uiState.cameraPermissionStatus,
                    onClick = { showCameraPermissionDialog = true },
                )
                SettingsActionRow(
                    title = "Microphone permissions",
                    subtitle = "Checked on device",
                    onClick = { showMicrophonePermissionDialog = true },
                )
                SettingsActionRow(
                    title = "Microphone input",
                    subtitle = when (micState.selectedInput) {
                        MicrophoneInput.SYSTEM_DEFAULT -> "System default"
                        MicrophoneInput.PHONE_MIC -> "Phone microphone"
                        MicrophoneInput.EXTERNAL_MIC -> micState.externalMicName ?: "External microphone"
                    },
                    onClick = { showMicInputDialog = true },
                )
                SettingsActionRow(
                    title = "Backend / AI settings",
                    subtitle = uiState.backendMode,
                    onClick = { showBackendDialog = true },
                )
            }

            SettingsSectionTitle("App")
            SettingsCard {
                SettingsActionRow(
                    title = "About app",
                    subtitle = "Version, licenses, privacy policy",
                    onClick = { navController.navigate(Screen.About.route) },
                )
            }
        }
    }

    if (showThemeDialog) {
        SelectionDialog(
            title = "Choose theme",
            options = ThemeMode.entries.map { it.label },
            selected = uiState.themeMode.label,
            onDismiss = { showThemeDialog = false },
            onSelect = { label ->
                val mode = ThemeMode.entries.first { it.label == label }
                viewModel.setThemeMode(mode)
                showThemeDialog = false
                scope.launch { snackbarHostState.showSnackbar("Theme set to ${mode.label}") }
            },
        )
    }

    if (showLanguageDialog) {
        SelectionDialog(
            title = "Choose language",
            options = listOf("English", "French", "Spanish"),
            selected = uiState.language,
            onDismiss = { showLanguageDialog = false },
            onSelect = {
                viewModel.setLanguage(it)
                showLanguageDialog = false
                scope.launch { snackbarHostState.showSnackbar("Language set to $it") }
            },
        )
    }

    if (showCameraPermissionDialog) {
        PermissionDialog(
            title = "Camera Permission",
            description = "Camera access is required for sign detection.",
            isGranted = isCameraPermissionGranted(context),
            onOpenSettings = { openAppSettings(context) },
            onDismiss = { showCameraPermissionDialog = false },
        )
    }

    if (showMicrophonePermissionDialog) {
        PermissionDialog(
            title = "Microphone Permission",
            description = "Microphone access is required for voice-to-sign translation.",
            isGranted = isMicrophonePermissionGranted(context),
            onOpenSettings = { openAppSettings(context) },
            onDismiss = { showMicrophonePermissionDialog = false },
        )
    }

    if (showMicInputDialog) {
        MicrophoneInputDialog(
            currentInput = micState.selectedInput,
            isExternalMicConnected = micState.isExternalMicConnected,
            externalMicName = micState.externalMicName,
            onSelect = { input ->
                micManager.setSelectedMicrophone(input)
                showMicInputDialog = false
            },
            onDismiss = { showMicInputDialog = false },
        )
    }

    if (showBackendDialog) {
        SelectionDialog(
            title = "Backend / AI mode",
            options = listOf("Cloud AI", "On-device AI", "Hybrid"),
            selected = uiState.backendMode,
            onDismiss = { showBackendDialog = false },
            onSelect = {
                viewModel.setBackendMode(it)
                showBackendDialog = false
                scope.launch { snackbarHostState.showSnackbar("Backend mode set to $it") }
            },
        )
    }
}

@Composable
private fun SettingsSectionTitle(title: String) {
    Text(title, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelLarge)
}

@Composable
private fun SettingsCard(content: @Composable () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Card(
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = colors.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(modifier = Modifier.padding(4.dp)) { content() }
    }
}

@Composable
private fun SettingsSwitchRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    SettingsRowShell(onClick = { onCheckedChange(!checked) }) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, color = colors.onSurface)
            Text(subtitle, color = colors.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
private fun SettingsActionRow(
    title: String,
    subtitle: String,
    onClick: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    SettingsRowShell(onClick = onClick) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, color = colors.onSurface)
            Text(subtitle, color = colors.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
        Icon(Icons.Filled.ChevronRight, contentDescription = null, tint = colors.onSurfaceVariant)
    }
}

@Composable
private fun SettingsRowShell(
    onClick: () -> Unit,
    content: @Composable androidx.compose.foundation.layout.RowScope.() -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        content = content,
    )
}

@Composable
private fun SelectionDialog(
    title: String,
    options: List<String>,
    selected: String,
    onDismiss: () -> Unit,
    onSelect: (String) -> Unit,
    description: String? = null,
) {
    val colors = MaterialTheme.colorScheme
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!description.isNullOrBlank()) {
                    Text(
                        text = description,
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.onSurfaceVariant,
                    )
                }
                options.forEach { option ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onSelect(option) }
                            .padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = option == selected, onClick = { onSelect(option) })
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(option, color = colors.onSurface)
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
        icon = { Icon(Icons.Filled.Info, contentDescription = null, tint = colors.primary) },
    )
}

@Composable
private fun PermissionDialog(
    title: String,
    description: String,
    isGranted: Boolean,
    onOpenSettings: () -> Unit,
    onDismiss: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    text = description,
                    style = MaterialTheme.typography.bodySmall,
                    color = colors.onSurfaceVariant,
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(
                        imageVector = if (isGranted) Icons.Filled.Info else Icons.Filled.Info,
                        contentDescription = null,
                        tint = if (isGranted) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                        modifier = Modifier.width(20.dp),
                    )
                    Text(
                        text = if (isGranted) "Granted" else "Not granted",
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (isGranted) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onOpenSettings) {
                Text("Open App Settings")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Close")
            }
        },
        icon = { Icon(Icons.Filled.Info, contentDescription = null, tint = colors.primary) },
    )
}

private fun isCameraPermissionGranted(context: Context): Boolean {
    return ContextCompat.checkSelfPermission(
        context,
        Manifest.permission.CAMERA
    ) == android.content.pm.PackageManager.PERMISSION_GRANTED
}

private fun isMicrophonePermissionGranted(context: Context): Boolean {
    return ContextCompat.checkSelfPermission(
        context,
        Manifest.permission.RECORD_AUDIO
    ) == android.content.pm.PackageManager.PERMISSION_GRANTED
}

private fun openAppSettings(context: Context) {
    val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
        data = Uri.parse("package:${context.packageName}")
    }
    context.startActivity(intent)
}

@Composable
private fun MicrophoneInputDialog(
    currentInput: MicrophoneInput,
    isExternalMicConnected: Boolean,
    externalMicName: String?,
    onSelect: (MicrophoneInput) -> Unit,
    onDismiss: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Microphone Input") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (isExternalMicConnected && externalMicName != null) {
                    Text(
                        text = "Detected: $externalMicName",
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.onSurfaceVariant,
                    )
                }
                listOf(
                    MicrophoneInput.SYSTEM_DEFAULT to "System default",
                    MicrophoneInput.PHONE_MIC to "Phone microphone",
                    MicrophoneInput.EXTERNAL_MIC to "External microphone",
                ).forEach { (input, label) ->
                    val isEnabled = input != MicrophoneInput.EXTERNAL_MIC || isExternalMicConnected
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable(enabled = isEnabled) { if (isEnabled) onSelect(input) }
                            .padding(vertical = 4.dp)
                            .alpha(if (isEnabled) 1f else 0.5f),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(
                            selected = input == currentInput,
                            onClick = { if (isEnabled) onSelect(input) },
                            enabled = isEnabled,
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(label, color = colors.onSurface)
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
        icon = { Icon(Icons.Filled.Info, contentDescription = null, tint = colors.primary) },
    )
}

