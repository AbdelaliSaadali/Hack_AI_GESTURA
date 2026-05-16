package com.gestura.app.viewmodel

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gestura.app.data.FakeLessonRepository
import com.gestura.app.data.LessonDifficulty
import com.gestura.app.data.Lesson
import com.gestura.app.data.LessonSign
import com.gestura.app.data.LessonProgress
import com.gestura.app.learning.LearningRepository
import com.gestura.app.learning.MockPracticeEvaluator
import com.gestura.app.learning.PracticeResult
import com.gestura.app.learning.PracticeStatus
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class LearnUiState(
    val lessons: List<Lesson> = emptyList(),
    val selectedLessonId: String? = null,
    val currentSignIndex: Int = 0,
    val progressByLessonId: Map<String, LessonProgress> = emptyMap(),
    val streakCount: Int = 12,
)

class LearnViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(LearnUiState())
    val uiState: StateFlow<LearnUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<String>()
    val events: SharedFlow<String> = _events.asSharedFlow()

    init {
        // initialize with fake lessons; real assets can be loaded later via loadFromRepository(context)
        val lessons = FakeLessonRepository.getLessons()
        val progress = lessons.associate { lesson ->
            lesson.id to LessonProgress(
                lessonId = lesson.id,
                completedSigns = 0,
                totalSigns = lesson.signs.size,
                isCompleted = false,
            )
        }

        _uiState.value = LearnUiState(
            lessons = lessons,
            progressByLessonId = progress,
        )
    }

    // Load real lessons from assets using LearningRepository. Call from Compose with LocalContext.
    fun loadFromRepository(context: Context) {
        viewModelScope.launch {
            try {
                val repo = LearningRepository(context)
                repo.loadAssets()
                val courses = repo.buildCourses()
                // map LearningCourse -> Lesson
                val lessons = courses.map { course ->
                    val signs: List<LessonSign> = course.signs.mapIndexed { idx, s ->
                        LessonSign(
                            id = "${course.id}_$idx",
                            word = s.word.replaceFirstChar { ch -> ch.uppercaseChar() },
                            instruction = s.instruction,
                            referenceLabel = s.videoId,
                            videoId = s.videoId,
                            referenceAssetPath = s.referenceAssetPath
                        )
                    }
                    val diff = when (course.difficulty) {
                        "Starter" -> LessonDifficulty.Beginner
                        "Beginner" -> LessonDifficulty.Beginner
                        "Intermediate" -> LessonDifficulty.Intermediate
                        else -> LessonDifficulty.Intermediate
                    }
                    Lesson(
                        id = course.id,
                        title = course.title,
                        description = course.description,
                        signs = signs,
                        difficulty = diff,
                        unlocked = course.isUnlocked,
                        tag = course.difficulty
                    )
                }

                val progress = lessons.associate { lesson ->
                    lesson.id to LessonProgress(
                        lessonId = lesson.id,
                        completedSigns = 0,
                        totalSigns = lesson.signs.size,
                        isCompleted = false,
                    )
                }

                _uiState.update {
                    it.copy(lessons = lessons, progressByLessonId = progress)
                }
            } catch (e: Exception) {
                // keep existing fake lessons on error
                _events.emit("Failed to load courses: ${e.localizedMessage}")
            }
        }
    }

    private val evaluator = MockPracticeEvaluator()

    fun startPractice(targetWord: String) {
        viewModelScope.launch {
            _events.emit("Practice started for $targetWord")
            val result: PracticeResult = evaluator.evaluate(targetWord)
            // show feedback
            _events.emit(result.feedbackMessage)

            // if correct, update progress for selected lesson
            if (result.status == PracticeStatus.Correct) {
                val lessonId = _uiState.value.selectedLessonId ?: return@launch
                val lesson = getLessonById(lessonId) ?: return@launch
                val prev = _uiState.value.progressByLessonId[lessonId]
                val newCompleted = (prev?.completedSigns ?: 0) + 1
                updateProgress(lesson, completedSigns = newCompleted, isCompleted = newCompleted >= lesson.signs.size)
                // increase streak
                _uiState.update { it.copy(streakCount = it.streakCount + 1) }
            }
        }
    }

    fun selectLesson(lessonId: String) {
        val lesson = _uiState.value.lessons.firstOrNull { it.id == lessonId }
        if (lesson == null) {
            emitEvent("Lesson not found")
            return
        }
        if (!lesson.unlocked) {
            emitEvent("This lesson is locked")
            return
        }

        val progress = _uiState.value.progressByLessonId[lessonId]
        val index = when {
            progress == null -> 0
            progress.totalSigns == 0 -> 0
            progress.isCompleted -> (progress.totalSigns - 1).coerceAtLeast(0)
            else -> progress.completedSigns.coerceAtMost((progress.totalSigns - 1).coerceAtLeast(0))
        }

        _uiState.update {
            it.copy(
                selectedLessonId = lessonId,
                currentSignIndex = index,
            )
        }
    }

    fun nextSign() {
        val state = _uiState.value
        val lesson = getSelectedLesson(state) ?: return
        val lastIndex = lesson.signs.lastIndex
        if (lastIndex < 0) return

        if (state.currentSignIndex < lastIndex) {
            val nextIndex = state.currentSignIndex + 1
            updateProgress(
                lesson = lesson,
                completedSigns = (nextIndex + 1).coerceAtMost(lesson.signs.size),
                isCompleted = nextIndex == lastIndex,
            )
            _uiState.update { it.copy(currentSignIndex = nextIndex) }
            if (nextIndex == lastIndex) emitEvent("Last sign reached")
            return
        }

        updateProgress(
            lesson = lesson,
            completedSigns = lesson.signs.size,
            isCompleted = true,
        )
        emitEvent("Lesson complete")
    }

    fun restartLesson() {
        val lesson = getSelectedLesson(_uiState.value) ?: return
        updateProgress(lesson, completedSigns = 0, isCompleted = false)
        _uiState.update { it.copy(currentSignIndex = 0) }
        emitEvent("Lesson restarted")
    }

    fun markLessonComplete() {
        val lesson = getSelectedLesson(_uiState.value) ?: return
        updateProgress(lesson, completedSigns = lesson.signs.size, isCompleted = true)
        _uiState.update { it.copy(currentSignIndex = lesson.signs.lastIndex.coerceAtLeast(0)) }
        emitEvent("Marked as complete")
    }

    fun onWatchLearnClicked() {
        emitEvent("Reference video player coming soon")
    }

    fun showLessonInfo() {
        val lesson = getSelectedLesson(_uiState.value) ?: return
        emitEvent("${lesson.title}: ${lesson.description}")
    }

    fun getLessonById(lessonId: String): Lesson? {
        return _uiState.value.lessons.firstOrNull { it.id == lessonId }
    }

    fun getSelectedLesson(state: LearnUiState = _uiState.value): Lesson? {
        return state.selectedLessonId?.let { id ->
            state.lessons.firstOrNull { it.id == id }
        }
    }

    fun getCurrentSign(state: LearnUiState = _uiState.value) = getSelectedLesson(state)
        ?.signs
        ?.getOrNull(state.currentSignIndex)

    fun getProgress(lessonId: String): LessonProgress {
        val lesson = getLessonById(lessonId)
        return _uiState.value.progressByLessonId[lessonId]
            ?: LessonProgress(
                lessonId = lessonId,
                completedSigns = 0,
                totalSigns = lesson?.signs?.size ?: 0,
                isCompleted = false,
            )
    }

    private fun updateProgress(
        lesson: Lesson,
        completedSigns: Int,
        isCompleted: Boolean,
    ) {
        _uiState.update { state ->
            val boundedCompleted = completedSigns.coerceIn(0, lesson.signs.size)
            val updated = state.progressByLessonId.toMutableMap().apply {
                put(
                    lesson.id,
                    LessonProgress(
                        lessonId = lesson.id,
                        completedSigns = boundedCompleted,
                        totalSigns = lesson.signs.size,
                        isCompleted = isCompleted,
                    )
                )
            }
            state.copy(progressByLessonId = updated)
        }
    }

    private fun emitEvent(message: String) {
        viewModelScope.launch {
            _events.emit(message)
        }
    }
}

