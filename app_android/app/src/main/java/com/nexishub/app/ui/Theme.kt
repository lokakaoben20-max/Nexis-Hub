package com.nexishub.app.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nexishub.app.R

/** Identité Nexis (AGENTS.md, choix de Ben du 2026-11-23) : bleu vif
 * #0A63F0, marine #021937, monogramme blanc, Unbounded pour les titres et
 * les montants, Inter pour tout le texte. Mêmes valeurs que
 * app_mobile/lib/ui/theme.dart. */
object Nexis {
    val brand = Color(0xFF0A63F0)
    val navy = Color(0xFF021937)
    val halo = Color(0xFF0A8CFF)
    val gradientStart = Color(0xFF0870EE)
    val gradientEnd = Color(0xFF0350E6)
    val ok = Color(0xFF1E8A4C)
    val danger = Color(0xFFC62828)
    val wait = Color(0xFFB26A00)
    /** Pastille « Nouveau » de la maquette. */
    val newBadge = Color(0xFFE5484D)

    val brandGradient = Brush.linearGradient(listOf(gradientStart, gradientEnd))
    val heroGradient = Brush.verticalGradient(listOf(halo, gradientEnd))
}

/** Couleurs qui suivent le thème clair ou sombre (NexisPalette de Flutter). */
@Immutable
data class NexisPalette(
    val bg: Color,
    val surface: Color,
    val ink: Color,
    val muted: Color,
    val line: Color,
    val soft: Color,
    val softInk: Color,
    /** Bleu lisible sur le fond du thème. */
    val accent: Color,
) {
    companion object {
        val Light = NexisPalette(
            bg = Color(0xFFF6F8FB), surface = Color.White, ink = Nexis.navy,
            muted = Color(0xFF5B667A), line = Color(0xFFE3E8F0), soft = Color(0xFFE8F0FE),
            softInk = Nexis.brand, accent = Nexis.brand,
        )
        val Dark = NexisPalette(
            bg = Color(0xFF0B1424), surface = Color(0xFF121E33), ink = Color(0xFFEAF0FA),
            muted = Color(0xFF9AA7BD), line = Color(0xFF22314B), soft = Color(0xFF1A2B4D),
            softInk = Color(0xFF8DB4FF), accent = Color(0xFF5B8CFF),
        )
    }
}

val LocalPalette = staticCompositionLocalOf { NexisPalette.Light }

/** Unbounded et Inter sont des polices variables : chaque graisse pose la
 * valeur de son axe « wght », comme l'app Flutter (fontVariations). */
@OptIn(ExperimentalTextApi::class)
private fun variable(res: Int, vararg weights: Int): FontFamily = FontFamily(
    weights.map { w ->
        Font(res, FontWeight(w), variationSettings = FontVariation.Settings(FontVariation.weight(w)))
    },
)

val Unbounded = variable(R.font.unbounded, 400, 500, 600, 700)
val Inter = variable(R.font.inter, 400, 500, 600, 700)
val NexisServices = FontFamily(Font(R.font.nexis_services))

/** Raccourcis de la charte : `title` en Unbounded, `body` en Inter. */
fun title(size: Int, weight: FontWeight = FontWeight.SemiBold, color: Color = Color.Unspecified) =
    TextStyle(fontFamily = Unbounded, fontWeight = weight, fontSize = size.sp, lineHeight = (size * 1.2).sp, color = color)

fun body(size: Int, weight: FontWeight = FontWeight.Normal, color: Color = Color.Unspecified) =
    TextStyle(fontFamily = Inter, fontWeight = weight, fontSize = size.sp, lineHeight = (size * 1.4).sp, color = color)

private val typography = Typography().let { base ->
    base.copy(
        displayLarge = base.displayLarge.copy(fontFamily = Unbounded),
        displayMedium = base.displayMedium.copy(fontFamily = Unbounded),
        displaySmall = base.displaySmall.copy(fontFamily = Unbounded),
        headlineLarge = base.headlineLarge.copy(fontFamily = Unbounded, fontWeight = FontWeight.SemiBold),
        headlineMedium = base.headlineMedium.copy(fontFamily = Unbounded, fontWeight = FontWeight.SemiBold),
        headlineSmall = base.headlineSmall.copy(fontFamily = Unbounded, fontWeight = FontWeight.SemiBold),
        titleLarge = base.titleLarge.copy(fontFamily = Unbounded, fontWeight = FontWeight.SemiBold),
        titleMedium = base.titleMedium.copy(fontFamily = Inter, fontWeight = FontWeight.SemiBold),
        titleSmall = base.titleSmall.copy(fontFamily = Inter, fontWeight = FontWeight.SemiBold),
        bodyLarge = base.bodyLarge.copy(fontFamily = Inter),
        bodyMedium = base.bodyMedium.copy(fontFamily = Inter),
        bodySmall = base.bodySmall.copy(fontFamily = Inter),
        labelLarge = base.labelLarge.copy(fontFamily = Inter, fontWeight = FontWeight.SemiBold),
        labelMedium = base.labelMedium.copy(fontFamily = Inter, fontWeight = FontWeight.Medium),
        labelSmall = base.labelSmall.copy(fontFamily = Inter, fontWeight = FontWeight.Medium),
    )
}

private val shapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(22.dp),
    extraLarge = RoundedCornerShape(28.dp),
)

@Composable
fun NexisTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val palette = if (dark) NexisPalette.Dark else NexisPalette.Light
    val colors = if (dark) {
        darkColorScheme(
            primary = palette.accent, onPrimary = Color.White,
            primaryContainer = palette.soft, onPrimaryContainer = palette.softInk,
            secondaryContainer = palette.soft, onSecondaryContainer = palette.softInk,
            background = palette.bg, onBackground = palette.ink,
            surface = palette.bg, onSurface = palette.ink,
            surfaceContainerLowest = palette.surface, surfaceContainerLow = palette.surface,
            surfaceContainer = palette.surface, surfaceContainerHigh = palette.surface,
            onSurfaceVariant = palette.muted, outline = palette.line, outlineVariant = palette.line,
            error = Color(0xFFFF8A80),
        )
    } else {
        lightColorScheme(
            primary = Nexis.brand, onPrimary = Color.White,
            primaryContainer = palette.soft, onPrimaryContainer = palette.softInk,
            secondaryContainer = palette.soft, onSecondaryContainer = palette.softInk,
            background = palette.bg, onBackground = palette.ink,
            surface = palette.bg, onSurface = palette.ink,
            surfaceContainerLowest = palette.surface, surfaceContainerLow = palette.surface,
            surfaceContainer = palette.surface, surfaceContainerHigh = palette.surface,
            onSurfaceVariant = palette.muted, outline = palette.line, outlineVariant = palette.line,
            error = Nexis.danger,
        )
    }
    androidx.compose.runtime.CompositionLocalProvider(LocalPalette provides palette) {
        MaterialTheme(colorScheme = colors, typography = typography, shapes = shapes, content = content)
    }
}
