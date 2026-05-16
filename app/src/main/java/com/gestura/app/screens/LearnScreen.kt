package com.gestura.app.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.gestura.app.components.LessonCard
import com.gestura.app.navigation.Screen
import com.gestura.app.viewmodel.LearnViewModel
import androidx.compose.ui.platform.LocalContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LearnScreen(
    navController: NavController,
    viewModel: LearnViewModel,
    bottomPadding: Dp = 0.dp
) {
    val uiState by viewModel.uiState.collectAsState()
    val colors = MaterialTheme.colorScheme
    val context = LocalContext.current

    // load real lessons from assets once
    LaunchedEffect(Unit) {
        viewModel.loadFromRepository(context)
    }

    Scaffold(
        containerColor = colors.background,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "Learning Portal",
                            style = MaterialTheme.typography.titleLarge,
                            color = colors.onBackground,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            text = "Choose a lesson to continue",
                            style = MaterialTheme.typography.bodySmall,
                            color = colors.onSurfaceVariant,
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = colors.background),
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(
                start = 16.dp, 
                end = 16.dp, 
                top = 16.dp, 
                bottom = bottomPadding + 16.dp // Adjust for bottom navigation
            ),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(uiState.lessons, key = { it.id }) { lesson ->
                val progress = uiState.progressByLessonId[lesson.id] ?: viewModel.getProgress(lesson.id)
                LessonCard(
                    lesson = lesson,
                    progress = progress,
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        if (lesson.unlocked) {
                            navController.navigate("${Screen.Learning.route}/${lesson.id}")
                        }
                    },
                )
            }
        }
    }
}
