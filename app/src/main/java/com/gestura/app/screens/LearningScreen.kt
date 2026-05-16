package com.gestura.app.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gestura.app.learning.LearningViewModel
import com.gestura.app.learning.models.LearningCourse
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.ui.Alignment
import androidx.compose.ui.text.font.FontWeight

@Composable
fun LearningScreen(
    vm: LearningViewModel = viewModel(),
    onOpenCourse: (String) -> Unit = {}
) {
    val state by vm.uiState.collectAsState()
    val courses = state.courses

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Learning Portal", style = MaterialTheme.typography.headlineLarge)
        Spacer(modifier = Modifier.height(12.dp))
        if (courses.isEmpty()) {
            Text("No courses available", style = MaterialTheme.typography.bodyMedium)
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(courses) { course ->
                    CourseCard(course = course, onClick = { onOpenCourse(course.id); vm.openCourse(course.id) })
                }
            }
        }
    }
}

@Composable
private fun CourseCard(course: LearningCourse, onClick: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(110.dp)
            .clickable(enabled = course.isUnlocked) { onClick() },
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = colors.surface)
    ) {
        Row(modifier = Modifier.fillMaxSize().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(course.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(6.dp))
                Text(course.description, style = MaterialTheme.typography.bodySmall)
                Spacer(modifier = Modifier.height(8.dp))
                LinearProgressIndicator(progress = if (course.signs.isEmpty()) 0f else 0.0f, modifier = Modifier.fillMaxWidth().height(6.dp))
            }
            Icon(Icons.Default.PlayArrow, contentDescription = "Open")
        }
    }
}

