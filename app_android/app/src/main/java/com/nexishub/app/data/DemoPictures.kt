package com.nexishub.app.data

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Shader
import java.io.ByteArrayOutputStream

/** Photos dessinées par l'app pour l'aperçu (pas de vraies photos de
 * travaux) : un dégradé et une forme, en JPEG. */
object DemoPictures {
    fun jpeg(shade: Int = 0xFF9FB6D6.toInt(), round: Boolean = false): ByteArray {
        // Tests sur la JVM : android.graphics n'y dessine rien.
        val bitmap = Bitmap.createBitmap(240, 240, Bitmap.Config.ARGB_8888) ?: return ByteArray(0)
        val canvas = Canvas(bitmap)
        val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        paint.shader = LinearGradient(0f, 0f, 0f, 240f, 0xFFD6E4F5.toInt(), shade, Shader.TileMode.CLAMP)
        canvas.drawRect(0f, 0f, 240f, 240f, paint)
        paint.shader = null
        paint.color = 0xB324344D.toInt()
        if (round) canvas.drawCircle(120f, 120f, 52f, paint) else canvas.drawRoundRect(60f, 70f, 180f, 170f, 18f, 18f, paint)
        return ByteArrayOutputStream().use { out ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, 80, out)
            out.toByteArray()
        }
    }
}
