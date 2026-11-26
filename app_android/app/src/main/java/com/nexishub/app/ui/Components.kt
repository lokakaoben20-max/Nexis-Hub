package com.nexishub.app.ui

import android.provider.Settings
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Construction
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nexishub.app.AppModel
import com.nexishub.app.LocalApp
import com.nexishub.app.R
import com.nexishub.app.data.CatalogService
import com.nexishub.app.data.Mission
import com.nexishub.app.data.MissionStatus
import com.nexishub.app.data.PaymentState
import com.nexishub.app.data.Service
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Pastille de service : pictogramme Phosphor bleu sur carré blanc bordé
 * (direction B choisie par Ben). Quand `tour` change, le carré montre un à
 * un les autres objets de son service, puis revient à l'icône principale. */
@Composable
fun ServiceTile(icons: List<Int>, size: Dp = 46.dp, tour: Int = 0, delayMs: Long = 0) {
    val p = LocalPalette.current
    val reduceMotion = rememberReduceMotion()
    var index by remember(icons) { mutableIntStateOf(0) }
    LaunchedEffect(tour) {
        if (tour == 0 || icons.size < 2 || reduceMotion) return@LaunchedEffect
        try {
            delay(delayMs)
            for (next in 1 until icons.size) {
                index = next
                delay(TOUR_STEP_MS)
            }
        } finally {
            // Feuille fermée pendant le tour : on revient à l'icône principale.
            index = 0
        }
    }
    val shape = RoundedCornerShape(size * 0.32f)
    Box(
        modifier = Modifier
            .size(size)
            .background(p.surface, shape)
            .border(1.dp, p.tileLine, shape)
            .clearAndSetSemantics { },
        contentAlignment = Alignment.Center,
    ) {
        AnimatedContent(
            targetState = index,
            transitionSpec = {
                (fadeIn(tween(840)) + scaleIn(tween(840), initialScale = 0.6f)) togetherWith
                    (fadeOut(tween(840)) + scaleOut(tween(840), targetScale = 1.25f))
            },
            label = "pictogramme",
        ) { shown ->
            Icon(painterResource(icons[shown]), contentDescription = null, tint = p.accent, modifier = Modifier.size(size * 0.5f))
        }
    }
}

/** Durée d'affichage de chaque objet pendant le tour. */
const val TOUR_STEP_MS = 3_500L

@Composable
fun ServiceTile(item: CatalogService, size: Dp = 46.dp, tour: Int = 0, delayMs: Long = 0) =
    ServiceTile(Pictogrammes.icons(item), size, tour, delayMs)

@Composable
fun ServiceTile(mission: Mission, size: Dp = 46.dp) {
    val item = mission.catalogService
    if (item != null) ServiceTile(item, size) else ServiceTile(Pictogrammes.icons(mission.service), size)
}

@Composable
fun ServiceTile(service: Service, size: Dp = 46.dp) = ServiceTile(Pictogrammes.icons(service), size)

/** « Supprimer les animations » d'Android : les pictogrammes restent fixes. */
@Composable
fun rememberReduceMotion(): Boolean {
    val context = LocalContext.current
    return remember {
        Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    }
}

/** Attente Nexis : les pictogrammes des services se relaient au lieu d'un
 * rond qui tourne (choix de Ben du 2026-11-25). Avec « Supprimer les
 * animations », la première icône reste fixe. */
@Composable
fun PictoLoader(label: String, size: Dp = 24.dp, color: Color = Color.White) {
    val reduceMotion = rememberReduceMotion()
    var index by remember { mutableIntStateOf(0) }
    LaunchedEffect(reduceMotion) {
        if (reduceMotion) return@LaunchedEffect
        while (isActive) {
            delay(LOADER_STEP_MS)
            index = (index + 1) % LOADER_ICONS.size
        }
    }
    Box(
        Modifier.size(size).clearAndSetSemantics {
            contentDescription = label
            liveRegion = LiveRegionMode.Polite
        },
        contentAlignment = Alignment.Center,
    ) {
        AnimatedContent(
            targetState = index,
            transitionSpec = {
                (fadeIn(tween(350)) + scaleIn(tween(350), initialScale = 0.55f)) togetherWith
                    (fadeOut(tween(350)) + scaleOut(tween(350), targetScale = 1.25f))
            },
            label = "chargement",
        ) { shown ->
            Icon(painterResource(LOADER_ICONS[shown]), contentDescription = null, tint = color, modifier = Modifier.size(size))
        }
    }
}

/** Les icônes principales des services, dans l'ordre du catalogue. */
val LOADER_ICONS = listOf(
    R.drawable.ph_wrench, R.drawable.ph_lightning, R.drawable.ph_snowflake, R.drawable.ph_laptop, R.drawable.ph_pen_nib,
    R.drawable.ph_scissors, R.drawable.ph_broom, R.drawable.ph_plant, R.drawable.ph_paint_roller, R.drawable.ph_truck,
)
const val LOADER_STEP_MS = 700L

/** « Nouveau » : petite pastille rouge de la maquette. */
@Composable
fun NewBadge() {
    val app = LocalApp.current
    Text(
        app.t("newBadge"),
        style = body(10, FontWeight.Bold, Color.White),
        modifier = Modifier.background(Nexis.newBadge, CircleShape).padding(horizontal = 6.dp, vertical = 2.dp),
    )
}

/** Bouton principal de l'écran, pleine largeur. */
@Composable
fun PrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    icon: ImageVector? = null,
    loading: Boolean = false,
) {
    Button(
        onClick = onClick,
        enabled = enabled && !loading,
        modifier = modifier.fillMaxWidth().height(56.dp),
        shape = CircleShape,
        colors = if (loading) {
            // Pendant l'attente, le bouton garde son bleu : seuls les pictogrammes bougent.
            ButtonDefaults.buttonColors(
                containerColor = Nexis.brand, contentColor = Color.White,
                disabledContainerColor = Nexis.brand, disabledContentColor = Color.White,
            )
        } else {
            ButtonDefaults.buttonColors(containerColor = Nexis.brand, contentColor = Color.White)
        },
    ) {
        if (loading) {
            PictoLoader(label = text, size = 24.dp)
            return@Button
        }
        if (icon != null) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(8.dp))
        }
        Text(text, style = body(16, FontWeight.SemiBold))
    }
}

/** Carte de contenu : surface pleine, bord fin. */
fun Modifier.nexisCard(palette: NexisPalette, radius: Dp = 22.dp): Modifier {
    val shape = RoundedCornerShape(radius)
    return this.clip(shape).background(palette.surface, shape).border(0.5.dp, palette.line, shape)
}

fun MissionStatus.tint(palette: NexisPalette): Color = when (this) {
    MissionStatus.PENDING, MissionStatus.QUOTED, MissionStatus.AWAITING_CONFIRMATION -> Nexis.wait
    MissionStatus.CONFIRMED, MissionStatus.IN_PROGRESS -> palette.accent
    MissionStatus.COMPLETED -> Nexis.ok
    MissionStatus.CANCELLED -> palette.muted
    MissionStatus.DISPUTED -> Nexis.danger
}

fun AppModel.statusLabel(mission: Mission): String = when (mission.status) {
    MissionStatus.PENDING -> t("statusPending")
    MissionStatus.QUOTED -> t("statusQuoted", "count" to mission.quotesCount.toString())
    MissionStatus.CONFIRMED -> t("statusConfirmed")
    MissionStatus.IN_PROGRESS -> t("statusInProgress", "name" to (mission.providerName ?: ""))
    MissionStatus.AWAITING_CONFIRMATION -> t("statusAwaiting")
    MissionStatus.COMPLETED -> t("statusCompleted")
    MissionStatus.CANCELLED -> t("statusCancelled")
    MissionStatus.DISPUTED -> t("statusDisputed")
}

fun AppModel.paymentLabel(state: PaymentState): String? = when (state) {
    PaymentState.NONE -> null
    PaymentState.SECURED -> t("paySecured")
    PaymentState.RELEASED -> t("payReleased")
    PaymentState.REFUNDED -> t("payRefunded")
    PaymentState.BLOCKED -> t("payBlocked")
    PaymentState.AVAILABLE -> t("payAvailable")
}

/** « Aujourd'hui », « Hier », sinon la date en chiffres (les noms de mois
 * en lingala ne sont pas encore relus). */
fun AppModel.day(instant: Instant): String {
    val date = instant.atZone(ZoneId.systemDefault()).toLocalDate()
    val today = LocalDate.now()
    return when (date) {
        today -> t("today")
        today.minusDays(1) -> t("yesterday")
        else -> date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy", locale))
    }
}

@Composable
fun MissionRow(mission: Mission, modifier: Modifier = Modifier) {
    val app = LocalApp.current
    val p = LocalPalette.current
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        ServiceTile(mission, 44.dp)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(mission.serviceName(app.language), style = body(16, FontWeight.SemiBold, p.ink), modifier = Modifier.weight(1f))
                mission.amount?.let {
                    Text(if (app.amountsHidden) "•••" else app.money(it), style = title(14, color = p.ink))
                }
            }
            Text("${mission.commune} · ${mission.reference}", style = body(13, color = p.muted))
            Row(verticalAlignment = Alignment.CenterVertically) {
                val tint = mission.status.tint(p)
                Box(Modifier.size(7.dp).background(tint, CircleShape))
                Spacer(Modifier.width(6.dp))
                Text(app.statusLabel(mission), style = body(13, FontWeight.Medium, tint))
                app.paymentLabel(mission.payment)?.let {
                    Text(" · $it", style = body(13, color = p.muted), maxLines = 1)
                }
            }
        }
    }
}

/** Écran pas encore construit dans l'app native : on le dit, sans faire
 * semblant (« Bientôt dans l'app »). */
@Composable
fun ComingSoonContent(heading: String, onClose: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    Column(
        Modifier.fillMaxWidth().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Box(Modifier.size(64.dp).background(p.soft, CircleShape), contentAlignment = Alignment.Center) {
            Icon(Icons.Rounded.Construction, contentDescription = null, tint = p.accent, modifier = Modifier.size(30.dp))
        }
        Text(heading, style = title(20, color = p.ink), textAlign = TextAlign.Center)
        Text(app.t("comingSoonText"), style = body(15, color = p.muted), textAlign = TextAlign.Center)
        PrimaryButton(app.t("ok"), onClose, Modifier.padding(top = 8.dp))
    }
}

@Composable
fun InitialsAvatar(initials: String, size: Dp = 64.dp) {
    Box(
        Modifier.size(size).clip(CircleShape).background(Nexis.brandGradient).clearAndSetSemantics { },
        contentAlignment = Alignment.Center,
    ) {
        Text(initials, style = title((size.value * 0.34f).toInt(), color = Color.White))
    }
}
