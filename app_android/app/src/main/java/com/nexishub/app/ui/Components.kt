package com.nexishub.app.ui

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
import androidx.compose.material.icons.rounded.FormatPaint
import androidx.compose.material.icons.rounded.LocalShipping
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nexishub.app.AppModel
import com.nexishub.app.LocalApp
import com.nexishub.app.data.CatalogService
import com.nexishub.app.data.Mission
import com.nexishub.app.data.MissionStatus
import com.nexishub.app.data.PaymentState
import com.nexishub.app.data.Service
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Pastille de service (série B validée) : pictogramme blanc sur carré
 * arrondi de la couleur du service, avec l'ombre colorée des maquettes. */
@Composable
fun ServiceTile(color: Color, service: Service?, fallback: ImageVector = Icons.Rounded.AutoAwesome, size: Dp = 46.dp) {
    val shape = RoundedCornerShape(size * 0.32f)
    Box(
        modifier = Modifier
            .size(size)
            .shadow(size * 0.22f, shape, ambientColor = color, spotColor = color)
            .background(color, shape)
            .clearAndSetSemantics { },
        contentAlignment = Alignment.Center,
    ) {
        if (service != null) {
            Text(service.glyph, style = androidx.compose.ui.text.TextStyle(fontFamily = NexisServices, fontSize = (size.value * 0.565f).sp, color = Color.White))
        } else {
            Icon(fallback, contentDescription = null, tint = Color.White, modifier = Modifier.size(size * 0.48f))
        }
    }
}

@Composable
fun ServiceTile(item: CatalogService, size: Dp = 46.dp) =
    ServiceTile(Color(item.color), item.service, fallbackIcon(item.id), size)

@Composable
fun ServiceTile(mission: Mission, size: Dp = 46.dp) {
    val item = mission.catalogService
    if (item != null) ServiceTile(item, size) else ServiceTile(Color(mission.service.color), mission.service, size = size)
}

fun fallbackIcon(id: String): ImageVector = when (id) {
    "peinture" -> Icons.Rounded.FormatPaint
    "demenagement" -> Icons.Rounded.LocalShipping
    else -> Icons.Rounded.AutoAwesome
}

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
fun PrimaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, icon: ImageVector? = null) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.fillMaxWidth().height(56.dp),
        shape = CircleShape,
        colors = ButtonDefaults.buttonColors(containerColor = Nexis.brand, contentColor = Color.White),
    ) {
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
