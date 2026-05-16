package com.gestura.app.screens

import android.app.Application
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.gestura.app.data.api.GesturaApi
import com.gestura.app.data.microphone.MicrophoneInputManager
import com.gestura.app.data.semantic.SemanticMatcher
import com.gestura.app.data.model.SignItem
import com.gestura.app.data.model.TranslateRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

data class VoiceToSignUiState(
    val isListening: Boolean = false,
    val isNoiseCancelEnabled: Boolean = false,
    val transcription: String = "",
    val glosses: List<String> = emptyList(),
    val signs: List<SignItem> = emptyList(),
    val isTranslating: Boolean = false,
    val isPlaying: Boolean = false,
    val currentSignIndex: Int = 0,
    val currentFrameIndex: Int = 0,
    /** The current frame's 180 landmarks – each landmark is [x, y, z]. */
    val currentFrame: List<List<Float>> = emptyList(),
    /** Non-null when a fingerspell letter is being displayed. */
    val fingerspellLetter: String? = null,
    val error: String? = null,
    val matchedVideoIds: List<String> = emptyList(),
    val matchedFbxPaths: List<String> = emptyList(),
    val playbackQueue: List<SignPlaybackItem> = emptyList(),
    val playbackStatus: String = "",
    val currentPlaybackIndex: Int = -1,
    val currentPlaybackItem: SignPlaybackItem? = null,
)

data class SignPlaybackItem(
    val originalWord: String,
    val matchedWord: String?,
    val videoId: String?,
    val assetPath: String?,
    val isKnown: Boolean,
)

class VoiceToSignViewModel(application: Application) : AndroidViewModel(application) {

    private val api = GesturaApi.create()
    private val micManager = MicrophoneInputManager(application)

    private val _uiState = MutableStateFlow(VoiceToSignUiState())
    val uiState: StateFlow<VoiceToSignUiState> = _uiState.asStateFlow()

    private var speechRecognizer: SpeechRecognizer? = null
    private var animationJob: Job? = null
    private var playbackJob: Job? = null
    private val semanticMatcher = SemanticMatcher()

    private val stopWords = setOf(
        "i", "me", "my", "the", "a", "an", "is", "am", "are", "was", "were", "to", "of", "it", "and"
    )

    init {
        // Detect external microphones on init
        micManager.detectExternalMicrophones()
        // Load semantic assets in background
        viewModelScope.launch {
            semanticMatcher.loadFromAssets(getApplication())
        }
    }

    // ── Speech Recognition ──────────────────────────────────────────

    fun setNoiseCancelEnabled(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(isNoiseCancelEnabled = enabled)
        Log.d(SPEECH_MODE_TAG, "NoiseCancel: ${if (enabled) "ON" else "OFF"}")
    }

    fun getMicrophoneInputManager() = micManager

    fun startListening() {
        val context = getApplication<Application>()
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            _uiState.value = _uiState.value.copy(error = "Speech recognition not available")
            return
        }

        // Cancel any running animation
        animationJob?.cancel()
        playbackJob?.cancel()

        speechRecognizer?.destroy()
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
            setRecognitionListener(GesturaSpeechListener())
        }

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)

            if (_uiState.value.isNoiseCancelEnabled) {
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 1500)
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 800)
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 500)
            }
        }

        Log.d(SPEECH_MODE_TAG, "NoiseCancel: ${if (_uiState.value.isNoiseCancelEnabled) "ON" else "OFF"}")

        _uiState.value = _uiState.value.copy(
            isListening = true,
            error = null,
            transcription = "",
            glosses = emptyList(),
            signs = emptyList(),
            isPlaying = false,
            currentFrame = emptyList(),
            fingerspellLetter = null,
            playbackQueue = emptyList(),
            playbackStatus = "",
            currentPlaybackIndex = -1,
            currentPlaybackItem = null,
            matchedVideoIds = emptyList(),
            matchedFbxPaths = emptyList(),
        )
        speechRecognizer?.startListening(intent)
    }

    fun stopListening() {
        speechRecognizer?.stopListening()
        _uiState.value = _uiState.value.copy(isListening = false)
    }

    // ── Backend API call ────────────────────────────────────────────

    private fun translateText(text: String) {
        if (text.isBlank()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isTranslating = true, error = null)
            try {
                val response = api.translate(TranslateRequest(text = text))
                if (response.success && response.signs.isNotEmpty()) {
                    _uiState.value = _uiState.value.copy(
                        isTranslating = false,
                        glosses = response.glosses,
                        signs = response.signs,
                    )
                    // Start the frame-by-frame animation loop
                    startAnimationLoop(response.signs)
                } else {
                    _uiState.value = _uiState.value.copy(
                        isTranslating = false,
                        glosses = response.glosses,
                        signs = emptyList(),
                        error = if (response.signs.isEmpty()) "No sign data found" else null,
                    )
                }
            } catch (e: Exception) {
                Log.e(TAG, "Translation API error", e)
                _uiState.value = _uiState.value.copy(
                    isTranslating = false,
                    error = "Connection failed: ${e.localizedMessage}",
                )
            }
        }
    }

    // ── Skeleton / Fingerspell Animation Loop ───────────────────────

    private fun startAnimationLoop(signs: List<SignItem>) {
        animationJob?.cancel()
        animationJob = viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isPlaying = true, currentSignIndex = 0)

            for ((signIdx, sign) in signs.withIndex()) {
                _uiState.value = _uiState.value.copy(
                    currentSignIndex = signIdx,
                    currentFrameIndex = 0,
                    fingerspellLetter = null,
                    currentFrame = emptyList(),
                )

                when (sign.type) {
                    "skeleton" -> {
                        if (sign.found && sign.frames.isNotEmpty()) {
                            for ((frameIdx, frame) in sign.frames.withIndex()) {
                                _uiState.value = _uiState.value.copy(
                                    currentFrameIndex = frameIdx,
                                    currentFrame = frame,
                                    fingerspellLetter = null,
                                )
                                delay(SKELETON_FRAME_DELAY_MS)
                            }
                        } else {
                            // Sign not found – show gloss text briefly
                            _uiState.value = _uiState.value.copy(
                                fingerspellLetter = sign.gloss,
                            )
                            delay(FINGERSPELL_LETTER_DELAY_MS * sign.gloss.length)
                        }
                    }

                    "fingerspell" -> {
                        // Show each letter for 500ms
                        for (ch in sign.gloss) {
                            _uiState.value = _uiState.value.copy(
                                fingerspellLetter = ch.toString(),
                                currentFrame = emptyList(),
                            )
                            delay(FINGERSPELL_LETTER_DELAY_MS)
                        }
                    }

                    else -> {
                        // Unknown type – just show gloss briefly
                        _uiState.value = _uiState.value.copy(
                            fingerspellLetter = sign.gloss,
                        )
                        delay(FINGERSPELL_LETTER_DELAY_MS * sign.gloss.length)
                    }
                }
            }

            // Animation finished
            _uiState.value = _uiState.value.copy(
                isPlaying = false,
                fingerspellLetter = null,
            )
        }
    }

    // ── Cleanup ─────────────────────────────────────────────────────

    override fun onCleared() {
        super.onCleared()
        animationJob?.cancel()
        playbackJob?.cancel()
        speechRecognizer?.destroy()
    }

    private suspend fun buildPlaybackQueue(sentence: String): List<SignPlaybackItem> = withContext(Dispatchers.IO) {
        val tokens = sentence
            .lowercase(Locale.US)
            .split(Regex("[^\\p{L}\\p{N}']+"))
            .map { it.trim() }
            .filter { it.isNotBlank() }

        val queue = ArrayList<SignPlaybackItem>()

        for (token in tokens) {
            if (token in stopWords) continue

            val matchedWord = semanticMatcher.findBestMatch(token)
            if (matchedWord == null) {
                queue.add(
                    SignPlaybackItem(
                        originalWord = token,
                        matchedWord = null,
                        videoId = null,
                        assetPath = null,
                        isKnown = false,
                    )
                )
                continue
            }

            val videoId = semanticMatcher.findVideoIdForWord(matchedWord)
            if (videoId.isNullOrBlank()) {
                queue.add(
                    SignPlaybackItem(
                        originalWord = token,
                        matchedWord = matchedWord,
                        videoId = null,
                        assetPath = null,
                        isKnown = false,
                    )
                )
                continue
            }

            queue.add(
                SignPlaybackItem(
                    originalWord = token,
                    matchedWord = matchedWord,
                    videoId = videoId,
                    assetPath = "upper_body_trimmed/${videoId}_upper.fbx",
                    isKnown = true,
                )
            )
        }

        queue
    }

    private suspend fun assetExists(assetPath: String): Boolean = withContext(Dispatchers.IO) {
        try {
            getApplication<Application>().assets.open(assetPath).use { }
            true
        } catch (_: Exception) {
            false
        }
    }

    private fun startPlaybackQueue(queue: List<SignPlaybackItem>) {
        playbackJob?.cancel()
        playbackJob = viewModelScope.launch {
            if (queue.isEmpty()) {
                _uiState.value = _uiState.value.copy(
                    isPlaying = false,
                    playbackQueue = emptyList(),
                    playbackStatus = "No available signs found",
                    currentPlaybackIndex = -1,
                    currentPlaybackItem = null,
                )
                return@launch
            }

            _uiState.value = _uiState.value.copy(
                isPlaying = true,
                playbackQueue = queue,
                currentPlaybackIndex = 0,
                currentPlaybackItem = queue.firstOrNull(),
                playbackStatus = "",
            )

            for ((index, item) in queue.withIndex()) {
                _uiState.value = _uiState.value.copy(
                    currentPlaybackIndex = index,
                    currentPlaybackItem = item,
                )

                if (!item.isKnown) {
                    val status = "Sign unavailable: ${item.originalWord}"
                    _uiState.value = _uiState.value.copy(playbackStatus = status)
                    Log.d(TAG, status)
                    delay(UNKNOWN_SIGN_STATUS_DELAY_MS)
                    continue
                }

                val displayWord = item.matchedWord ?: item.originalWord
                if (!item.matchedWord.isNullOrBlank() &&
                    item.matchedWord.lowercase(Locale.US).trim() != item.originalWord.lowercase(Locale.US).trim()
                ) {
                    val synonymStatus = "${item.originalWord} → $displayWord"
                    _uiState.value = _uiState.value.copy(playbackStatus = synonymStatus)
                    Log.d("Matcher", "input=${item.originalWord} → $displayWord")
                    delay(SYNONYM_STATUS_DELAY_MS)
                }

                val assetPath = item.assetPath
                val fileExists = assetPath != null && assetExists(assetPath)
                if (!fileExists) {
                    val missingStatus = "Animation file missing: $displayWord"
                    _uiState.value = _uiState.value.copy(playbackStatus = missingStatus)
                    Log.d(TAG, missingStatus)
                    delay(MISSING_ASSET_STATUS_DELAY_MS)
                    continue
                }

                val playingStatus = "Playing: ${displayWord.uppercase(Locale.US)}"
                _uiState.value = _uiState.value.copy(playbackStatus = playingStatus)
                Log.d(TAG, playingStatus)
                if (assetPath != null) {
                    Log.d(TAG, "video_id=${item.videoId}")
                    Log.d(TAG, "assetPath=$assetPath")
                }
                delay(KNOWN_SIGN_PLAYBACK_MS)
            }

            _uiState.value = _uiState.value.copy(
                isPlaying = false,
                playbackStatus = "Translation complete",
                currentPlaybackItem = null,
            )
        }
    }

    // ── SpeechRecognizer Listener ───────────────────────────────────

    private inner class GesturaSpeechListener : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {}
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            _uiState.value = _uiState.value.copy(isListening = false)
        }

        override fun onError(error: Int) {
            val message = when (error) {
                SpeechRecognizer.ERROR_NO_MATCH -> "No speech detected"
                SpeechRecognizer.ERROR_NETWORK -> "Network error"
                SpeechRecognizer.ERROR_AUDIO -> "Audio error"
                else -> "Recognition error ($error)"
            }
            _uiState.value = _uiState.value.copy(
                isListening = false,
                error = message,
            )
        }

        override fun onResults(results: Bundle?) {
            val noiseCancelEnabled = _uiState.value.isNoiseCancelEnabled
            val text = results
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()
                .orEmpty()

            val wordCount = text
                .trim()
                .split(Regex("\\s+"))
                .filter { it.isNotBlank() }
                .size

            val shouldIgnoreForNoiseCancel = noiseCancelEnabled && wordCount <= 2
            if (!shouldIgnoreForNoiseCancel) {
                _uiState.value = _uiState.value.copy(
                    isListening = false,
                    transcription = text,
                )

                viewModelScope.launch {
                    val queue = buildPlaybackQueue(text)
                    val videoIds = queue.mapNotNull { it.videoId }
                    val fbxPaths = queue.mapNotNull { it.assetPath }
                    val finalStatus = if (queue.isEmpty()) "No available signs found" else ""

                    _uiState.value = _uiState.value.copy(
                        matchedVideoIds = videoIds,
                        matchedFbxPaths = fbxPaths,
                        playbackQueue = queue,
                        playbackStatus = finalStatus,
                        currentPlaybackIndex = if (queue.isEmpty()) -1 else 0,
                        currentPlaybackItem = queue.firstOrNull(),
                    )

                    startPlaybackQueue(queue)
                }

                // Automatically call the backend API with the transcribed text
                if (text.isNotBlank()) {
                    translateText(text)
                }
            } else {
                // Keep last valid transcription when noise-cancel filter ignores short speech
                _uiState.value = _uiState.value.copy(isListening = false)
            }

            if (noiseCancelEnabled) {
                // Continuous listening mode when noise cancellation is enabled.
                viewModelScope.launch {
                    delay(120)
                    startListening()
                }
            }
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val partial = partialResults
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()
                .orEmpty()

            if (partial.isNotBlank()) {
                _uiState.value = _uiState.value.copy(transcription = partial)
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    companion object {
        private const val TAG = "VoiceToSignVM"
        private const val SPEECH_MODE_TAG = "SpeechMode"
        private const val SKELETON_FRAME_DELAY_MS = 80L
        private const val FINGERSPELL_LETTER_DELAY_MS = 500L
        private const val KNOWN_SIGN_PLAYBACK_MS = 1100L
        private const val SYNONYM_STATUS_DELAY_MS = 350L
        private const val UNKNOWN_SIGN_STATUS_DELAY_MS = 900L
        private const val MISSING_ASSET_STATUS_DELAY_MS = 900L
    }
}
