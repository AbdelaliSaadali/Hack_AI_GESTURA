package com.gestura.app.data.microphone

import android.content.Context
import android.content.SharedPreferences
import android.media.AudioDeviceInfo
import android.media.AudioManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class MicrophoneInput(val value: String) {
    SYSTEM_DEFAULT("system_default"),
    PHONE_MIC("phone_mic"),
    EXTERNAL_MIC("external_mic"),
}

data class MicrophoneInputState(
    val selectedInput: MicrophoneInput = MicrophoneInput.SYSTEM_DEFAULT,
    val isExternalMicConnected: Boolean = false,
    val externalMicName: String? = null,
)

class MicrophoneInputManager(private val context: Context) {
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val prefs: SharedPreferences = context.getSharedPreferences("mic_input_prefs", Context.MODE_PRIVATE)

    private val _state = MutableStateFlow(MicrophoneInputState())
    val state: StateFlow<MicrophoneInputState> = _state.asStateFlow()

    init {
        // Load saved preference
        val saved = prefs.getString("selected_mic_input", MicrophoneInput.SYSTEM_DEFAULT.value)
        val selectedInput = MicrophoneInput.entries.find { it.value == saved } ?: MicrophoneInput.SYSTEM_DEFAULT
        
        updateState(selectedInput = selectedInput)
    }

    fun detectExternalMicrophones() {
        val audioDevices = audioManager.getDevices(AudioManager.GET_DEVICES_INPUTS)
        
        val externalMics = audioDevices.filter { device ->
            val type = device.type
            type == AudioDeviceInfo.TYPE_USB_DEVICE ||
            type == AudioDeviceInfo.TYPE_USB_HEADSET ||
            type == AudioDeviceInfo.TYPE_WIRED_HEADSET ||
            type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
        }
        
        val isConnected = externalMics.isNotEmpty()
        val externalMicName = externalMics.firstOrNull()?.productName?.toString()
        
        val currentState = _state.value
        
        // If external mic disconnected and was selected, fallback to system default
        if (!isConnected && currentState.selectedInput == MicrophoneInput.EXTERNAL_MIC) {
            updateState(
                selectedInput = MicrophoneInput.SYSTEM_DEFAULT,
                isExternalMicConnected = false,
                externalMicName = null
            )
        } else {
            updateState(
                selectedInput = if (currentState.selectedInput == MicrophoneInput.EXTERNAL_MIC && !isConnected) {
                    MicrophoneInput.SYSTEM_DEFAULT
                } else {
                    currentState.selectedInput
                },
                isExternalMicConnected = isConnected,
                externalMicName = externalMicName
            )
        }
    }

    fun setSelectedMicrophone(input: MicrophoneInput) {
        if (input == MicrophoneInput.EXTERNAL_MIC && !_state.value.isExternalMicConnected) {
            return // Cannot select external mic if not connected
        }
        updateState(selectedInput = input)
        prefs.edit().putString("selected_mic_input", input.value).apply()
    }

    private fun updateState(
        selectedInput: MicrophoneInput = _state.value.selectedInput,
        isExternalMicConnected: Boolean = _state.value.isExternalMicConnected,
        externalMicName: String? = _state.value.externalMicName,
    ) {
        _state.value = MicrophoneInputState(
            selectedInput = selectedInput,
            isExternalMicConnected = isExternalMicConnected,
            externalMicName = externalMicName,
        )
    }
}


