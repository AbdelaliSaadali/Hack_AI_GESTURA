package com.gestura.app.learning

import android.content.Context
import android.util.Log

object AssetUtils {
    private const val TAG = "LearningAssets"
    
    fun findReferenceVideoAsset(context: Context, videoId: String, word: String): String? {
        val candidates = listOf(
            "videos/$videoId.mp4",
            "videos/$word.mp4",
            "learning/$videoId.mp4",
            "learning/$word.mp4",
            "raw_videos/$videoId.mp4",
            "raw_videos/$word.mp4"
        )
        for (p in candidates) {
            Log.d(TAG, "Checking video path: $p")
            try {
                context.assets.open(p).close()
                Log.d(TAG, "Found video path: $p")
                return p
            } catch (e: Exception) {
                // continue
            }
        }
        Log.d(TAG, "No reference video found for $word / $videoId")
        return null
    }
}

