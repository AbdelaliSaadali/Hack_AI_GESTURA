package com.gestura.app.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.ContactSupport
import androidx.compose.material.icons.filled.Help
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
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
fun HelpScreen(navController: NavController) {
    val colors = MaterialTheme.colorScheme
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    Scaffold(
        containerColor = colors.background,
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = { Text("Help & Support", color = colors.onBackground) },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Back", tint = colors.onBackground)
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
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("FAQs", style = MaterialTheme.typography.titleLarge, color = colors.onSurface, fontWeight = FontWeight.SemiBold)
                    HelpActionButton(Icons.Filled.Help, "How do I start translating?", "Open a learning or translation screen") {
                        scope.launch { snackbarHostState.showSnackbar("App guide coming soon") }
                    }
                    HelpActionButton(Icons.Filled.MenuBook, "How do lessons work?", "Track progress in the Learn tab") {
                        scope.launch { snackbarHostState.showSnackbar("Lesson guide coming soon") }
                    }
                }
            }

            Card(
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(containerColor = colors.surface),
            ) {
                Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Contact", style = MaterialTheme.typography.titleLarge, color = colors.onSurface, fontWeight = FontWeight.SemiBold)
                    HelpActionButton(Icons.Filled.ContactSupport, "Contact support", "Email: support@gestura.app") {
                        scope.launch { snackbarHostState.showSnackbar("Support contact placeholder") }
                    }
                    HelpActionButton(Icons.Filled.BugReport, "Report a problem", "Send logs and feedback") {
                        scope.launch { snackbarHostState.showSnackbar("Problem report placeholder") }
                    }
                    HelpActionButton(Icons.Filled.Chat, "App tutorial", "Quick walkthrough and tips") {
                        scope.launch { snackbarHostState.showSnackbar("Tutorial coming soon") }
                    }
                }
            }
        }
    }
}

@Composable
private fun HelpActionButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme

    Button(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Icon(icon, contentDescription = null, tint = colors.onPrimary)
        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
        Column(modifier = Modifier.weight(1f), horizontalAlignment = Alignment.Start) {
            Text(title, color = colors.onPrimary, fontWeight = FontWeight.SemiBold)
            Text(subtitle, color = colors.onPrimary.copy(alpha = 0.85f), style = MaterialTheme.typography.bodySmall)
        }
    }
}
