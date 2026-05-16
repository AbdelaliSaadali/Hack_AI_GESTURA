package com.gestura.app.components

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.gestura.app.navigation.Screen

@Composable
fun ProfileMenu(
    expanded: Boolean,
    onDismissRequest: () -> Unit,
    onNavigate: (String) -> Unit,
    onLogoutComingSoon: () -> Unit,
    modifier: Modifier = Modifier,
) {
    DropdownMenu(
        expanded = expanded,
        onDismissRequest = onDismissRequest,
        modifier = modifier,
    ) {
        DropdownMenuItem(
            text = { Text("Profile") },
            leadingIcon = { Icon(Icons.Filled.Person, contentDescription = null) },
            onClick = { onNavigate(Screen.Profile.route) },
        )
        DropdownMenuItem(
            text = { Text("Settings") },
            leadingIcon = { Icon(Icons.Filled.Settings, contentDescription = null) },
            onClick = { onNavigate(Screen.Settings.route) },
        )
        DropdownMenuItem(
            text = { Text("Help & Support") },
            leadingIcon = { Icon(Icons.Filled.HelpOutline, contentDescription = null) },
            onClick = { onNavigate(Screen.Help.route) },
        )
        DropdownMenuItem(
            text = { Text("About") },
            leadingIcon = { Icon(Icons.Filled.Info, contentDescription = null) },
            onClick = { onNavigate(Screen.About.route) },
        )
        DropdownMenuItem(
            text = { Text("Logout") },
            leadingIcon = { Icon(Icons.Filled.Logout, contentDescription = null) },
            enabled = false,
            onClick = { onLogoutComingSoon() },
        )
    }
}
