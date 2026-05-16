package com.gestura.app.data.api

import com.gestura.app.data.model.TranslateRequest
import com.gestura.app.data.model.TranslateResponse
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.POST
import java.util.concurrent.TimeUnit

interface GesturaApi {

    @POST("translate")
    suspend fun translate(@Body request: TranslateRequest): TranslateResponse

    companion object {
        // 10.0.2.2 maps to the host machine's localhost inside the Android emulator
        private const val BASE_URL = "http://172.16.0.87:8000/"

        fun create(): GesturaApi {
            val logger = HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BODY
            }

            val client = OkHttpClient.Builder()
                .addInterceptor(logger)
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .build()

            return Retrofit.Builder()
                .baseUrl(BASE_URL)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(GesturaApi::class.java)
        }
    }
}
