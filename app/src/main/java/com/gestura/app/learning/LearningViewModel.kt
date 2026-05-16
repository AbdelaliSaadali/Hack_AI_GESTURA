package com.gestura.app.learning

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.gestura.app.learning.models.LearningCourse
import com.gestura.app.learning.models.LearningSign
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class LearningUiState(
    val courses: List<LearningCourse> = emptyList(),
    val currentCourse: LearningCourse? = null,
    val currentIndex: Int = 0,
    val playingStatus: String = "",
    val practiceStatus: String = "",
    val completedPerCourse: Map<String, Int> = emptyMap(),
    val streak: Int = 0
)

class LearningViewModel(application: Application) : AndroidViewModel(application) {
    private val repo = LearningRepository(application)
    private val _uiState = MutableStateFlow(LearningUiState())
    val uiState: StateFlow<LearningUiState> = _uiState.asStateFlow()
    private val evaluator: PracticeEvaluator = MockPracticeEvaluator()

    init {
        viewModelScope.launch {
            repo.loadAssets()
            val courses = repo.buildCourses()
            _uiState.value = _uiState.value.copy(courses = courses)
        }
    }

    fun openCourse(courseId: String) {
        viewModelScope.launch {
            val course = repo.getCourseById(courseId)
            if (course != null) {
                _uiState.value = _uiState.value.copy(currentCourse = course, currentIndex = 0)
            }
        }
    }

    fun nextSign() {
        val course = _uiState.value.currentCourse ?: return
        val idx = _uiState.value.currentIndex
        if (idx + 1 < course.signs.size) {
            _uiState.value = _uiState.value.copy(currentIndex = idx + 1)
        } else {
            // finished
            _uiState.value = _uiState.value.copy(playingStatus = "Translation complete")
        }
    }

    fun playSign(sign: LearningSign) {
        _uiState.value = _uiState.value.copy(playingStatus = "Playing: ${sign.word.uppercase()}")
    }

    fun startPractice(target: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(practiceStatus = "Recording")
            val result = evaluator.evaluate(target)
            _uiState.value = _uiState.value.copy(practiceStatus = result.feedbackMessage)
        }
    }
}

