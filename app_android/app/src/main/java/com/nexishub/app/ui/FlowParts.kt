package com.nexishub.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.Undo
import androidx.compose.material.icons.rounded.AccountBalanceWallet
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.Star
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.nexishub.app.AppModel
import com.nexishub.app.LocalApp
import com.nexishub.app.data.Mission
import com.nexishub.app.data.MobileOperator
import com.nexishub.app.data.PaymentState
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import kotlin.math.ceil

// Pièces communes aux écrans de mission (suivi, devis, paiement, litige,
// espace prestataire). Mêmes couleurs que l'app Flutter (ui/common.dart,
// ui/parts.dart), posées dans le style Android validé.

// Dates et heures

private val weekdays = mapOf(
    "fr" to listOf("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
    "ln" to listOf(
        "mokɔlɔ ya yambo", "mokɔlɔ ya mibale", "mokɔlɔ ya misato", "mokɔlɔ ya minei",
        "mokɔlɔ ya mitano", "mposɔ", "lomingo",
    ),
    "en" to listOf("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
)
private val shortWeekdays = mapOf(
    "fr" to listOf("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."),
    "en" to listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
)

/** « 9 h », « 8 h 41 » ; en anglais « 9 am », « 8:41 am ». */
fun clockText(time: Instant, language: String, zone: ZoneId = ZoneId.systemDefault()): String {
    val local = time.atZone(zone)
    val hour = local.hour
    val minute = local.minute
    val mm = minute.toString().padStart(2, '0')
    if (language == "en") {
        val h = if (hour % 12 == 0) 12 else hour % 12
        val suffix = if (hour < 12) "am" else "pm"
        return if (minute == 0) "$h $suffix" else "$h:$mm $suffix"
    }
    return if (minute == 0) "$hour h" else "$hour h $mm"
}

/** Jours entiers qui restent avant `until` (au moins 1 tant que ce n'est
 * pas passé, 0 ensuite). */
fun daysLeft(until: Instant, now: Instant = Instant.now()): Int {
    val left = Duration.between(now, until)
    if (left.isNegative || left.isZero) return 0
    return ceil(left.toMinutes() / (24.0 * 60)).toInt()
}

fun AppModel.clock(time: Instant): String = clockText(time, language)

/** « samedi 9 h » (ou « Samedi 9 h »). */
fun AppModel.slot(time: Instant, capital: Boolean = false): String {
    val days = weekdays[language] ?: weekdays.getValue("fr")
    val text = "${days[time.atZone(ZoneId.systemDefault()).dayOfWeek.value - 1]} ${clock(time)}"
    return if (capital) text.replaceFirstChar { it.uppercase() } else text
}

/** « 13 h » aujourd'hui, sinon « sam. 13 h » (le lingala garde le jour entier). */
fun AppModel.stamp(time: Instant): String {
    val local = time.atZone(ZoneId.systemDefault())
    if (local.toLocalDate() == LocalDate.now()) return clock(time)
    val days = shortWeekdays[language] ?: weekdays[language] ?: weekdays.getValue("fr")
    return "${days[local.dayOfWeek.value - 1]} ${clock(time)}"
}

/** « 4,9 » (« 4.9 » en anglais). */
fun AppModel.rating(value: Double): String {
    val text = String.format(java.util.Locale.ROOT, "%.1f", value)
    return if (language == "en") text else text.replace('.', ',')
}

/** « Plomberie · Gombe ». */
fun AppModel.place(mission: Mission): String = "${mission.serviceName(language)} · ${mission.commune}"

// Couleurs claires et sombres

@Composable
@ReadOnlyComposable
fun pick(light: Long, dark: Long): Color = Color(if (LocalPalette.current == NexisPalette.Dark) dark else light)

// Pastilles

enum class PillTone(val light: Pair<Long, Long>, val dark: Pair<Long, Long>) {
    SECURED(0xFFE8F0FE to 0xFF0A3D9E, 0xFF1A2B4D to 0xFF8DB4FF),
    OK(0xFFE3F5EA to 0xFF17663A, 0xFF12301F to 0xFF5BD08A),
    INFO(0xFFECECF8 to 0xFF3B3E80, 0xFF22234A to 0xFFB3B5F2),
    WARN(0xFFFFF1D6 to 0xFF7A4E00, 0xFF33270D to 0xFFF2C661),
    WAIT(0xFFEEF1F5 to 0xFF4E5B70, 0xFF1A2740 to 0xFFA9B4C6),
    BAD(0xFFFDECEA to 0xFFB42318, 0xFF3A1715 to 0xFFFF8A80),
}

@Composable
fun Pill(tone: PillTone, text: String, icon: ImageVector? = null) {
    val dark = LocalPalette.current == NexisPalette.Dark
    val (background, foreground) = if (dark) tone.dark else tone.light
    Row(
        Modifier.background(Color(background), CircleShape).padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        if (icon != null) Icon(icon, contentDescription = null, tint = Color(foreground), modifier = Modifier.size(13.dp))
        Text(text, style = body(12, FontWeight.SemiBold, Color(foreground)), maxLines = 1)
    }
}

/** L'état de l'argent, avec sa couleur de la charte. */
@Composable
fun PaymentPill(state: PaymentState, text: String? = null) {
    val app = LocalApp.current
    val (icon, tone) = when (state) {
        PaymentState.SECURED -> Icons.Rounded.VerifiedUser to PillTone.SECURED
        PaymentState.RELEASED -> Icons.Rounded.CheckCircle to PillTone.OK
        PaymentState.REFUNDED -> Icons.AutoMirrored.Rounded.Undo to PillTone.INFO
        PaymentState.BLOCKED -> Icons.Rounded.Lock to PillTone.BAD
        PaymentState.AVAILABLE -> Icons.Rounded.AccountBalanceWallet to PillTone.OK
        PaymentState.NONE -> Icons.Rounded.Schedule to PillTone.WAIT
    }
    Pill(tone, text ?: app.paymentLabel(state).orEmpty(), icon)
}

// Notes

enum class NoteKind { INFO, VIOLET, DANGER }

/** Encadré d'information (bleu), de décision (violet) ou d'argent bloqué (rouge). */
@Composable
fun InfoNote(text: String, kind: NoteKind = NoteKind.INFO, icon: ImageVector = Icons.Rounded.Info) {
    val (background, foreground) = when (kind) {
        NoteKind.INFO -> pick(0xFFE8F0FE, 0xFF1A2B4D) to pick(0xFF0A3D9E, 0xFF8DB4FF)
        NoteKind.VIOLET -> pick(0xFFECECF8, 0xFF22234A) to pick(0xFF3B3E80, 0xFFB3B5F2)
        NoteKind.DANGER -> pick(0xFFFFF6F5, 0xFF3A1715) to pick(0xFF7A3A33, 0xFFFFB4AB)
    }
    Row(
        Modifier.fillMaxWidth().background(background, RoundedCornerShape(16.dp)).padding(14.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(icon, contentDescription = null, tint = foreground, modifier = Modifier.size(18.dp))
        Text(text, style = body(14, color = foreground), modifier = Modifier.weight(1f))
    }
}

// Personnes

/** Rond coloré à initiales (couleur donnée par le serveur). */
@Composable
fun PersonAvatar(initials: String, color: Long, size: Dp = 44.dp) {
    Box(Modifier.size(size).background(Color(color), CircleShape).clearAndSetSemantics { }, contentAlignment = Alignment.Center) {
        Text(initials, style = body((size.value / 3).toInt(), FontWeight.Bold, Color.White))
    }
}

/** « ★ 4,9 (128) ». */
@Composable
fun Stars(rating: Double, reviews: Int) {
    val app = LocalApp.current
    val p = LocalPalette.current
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(3.dp)) {
        Icon(Icons.Rounded.Star, contentDescription = null, tint = Color(0xFFE3A008), modifier = Modifier.size(15.dp))
        Text("${app.rating(rating)} ($reviews)", style = body(13, FontWeight.SemiBold, p.ink))
    }
}

/** Une personne et sa note, avec des boutons ronds à droite. */
@Composable
fun PersonHeader(
    initials: String,
    color: Long,
    name: String,
    rating: Double? = null,
    reviews: Int? = null,
    subtitle: String? = null,
    trailing: @Composable RowScope.() -> Unit = {},
) {
    val p = LocalPalette.current
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        PersonAvatar(initials, color)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(name, style = body(15, FontWeight.Bold, p.ink))
            if (rating != null && reviews != null) Stars(rating, reviews)
            if (subtitle != null) {
                Text(subtitle, style = body(13, color = p.muted), maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        trailing()
    }
}

/** Bouton rond bleu clair (appeler, écrire). */
@Composable
fun RoundIconButton(icon: ImageVector, label: String, size: Dp = 42.dp, onClick: () -> Unit) {
    val p = LocalPalette.current
    Box(
        Modifier.size(size).clip(CircleShape).background(p.soft)
            .clickable(role = Role.Button, onClickLabel = label, onClick = onClick)
            .semantics { this.contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = p.softInk, modifier = Modifier.size(size * 0.45f))
    }
}

// Étapes

enum class StepState { DONE, NOW, TODO }

data class StepItem(val title: String, val sub: String? = null, val time: String? = null, val state: StepState)

/** Frise des étapes : points bleus pleins pour les étapes faites, point
 * entouré pour l'étape en cours, trait bleu entre les faites. */
@Composable
fun StepList(items: List<StepItem>) {
    val p = LocalPalette.current
    val grey = pick(0xFFE3E7EE, 0xFF22314B)
    Column {
        items.forEachIndexed { index, item ->
            Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min).semantics(mergeDescendants = true) { }) {
                Column(Modifier.width(22.dp).fillMaxHeight(), horizontalAlignment = Alignment.CenterHorizontally) {
                    StepDot(item.state, p)
                    if (index < items.lastIndex) {
                        Box(Modifier.width(2.dp).weight(1f).background(if (item.state == StepState.DONE) Nexis.brand else grey))
                    }
                }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f).padding(top = 1.dp, bottom = if (index < items.lastIndex) 16.dp else 0.dp)) {
                    Text(
                        item.title,
                        style = body(
                            15, if (item.state == StepState.TODO) FontWeight.Medium else FontWeight.Bold,
                            if (item.state == StepState.TODO) pick(0xFF8A94A6, 0xFF7D8AA3) else p.ink,
                        ),
                    )
                    if (item.sub != null) Text(item.sub, style = body(13, color = p.muted))
                }
                if (item.time != null) {
                    Text(item.time, style = body(12, FontWeight.Medium, p.muted), modifier = Modifier.padding(start = 10.dp, top = 2.dp))
                }
            }
        }
    }
}

@Composable
private fun StepDot(state: StepState, p: NexisPalette) {
    when (state) {
        StepState.DONE -> Box(Modifier.size(22.dp).background(Nexis.brand, CircleShape), contentAlignment = Alignment.Center) {
            Icon(Icons.Rounded.Check, contentDescription = null, tint = Color.White, modifier = Modifier.size(13.dp))
        }
        StepState.NOW -> Box(
            Modifier.size(22.dp).background(p.surface, CircleShape).border(2.dp, Nexis.brand, CircleShape),
            contentAlignment = Alignment.Center,
        ) { Box(Modifier.size(8.dp).background(Nexis.brand, CircleShape)) }
        StepState.TODO -> Box(
            Modifier.size(22.dp).background(p.surface, CircleShape).border(2.dp, pick(0xFFC9D0DB, 0xFF3A4A66), CircleShape),
        )
    }
}

// Choix

/** Rond de choix unique (opérateur, raison du litige). */
@Composable
fun RadioDot(selected: Boolean) {
    Box(
        Modifier.size(22.dp).border(
            if (selected) 6.dp else 2.dp,
            if (selected) Nexis.brand else pick(0xFFC9D0DB, 0xFF3A4A66),
            CircleShape,
        ),
    )
}

/** Ligne de choix dans une carte, bordée de bleu quand elle est choisie. */
@Composable
fun ChoiceRow(
    title: String,
    selected: Boolean,
    onClick: () -> Unit,
    subtitle: String? = null,
    enabled: Boolean = true,
    leading: @Composable () -> Unit = {},
) {
    val p = LocalPalette.current
    val shape = RoundedCornerShape(16.dp)
    Row(
        Modifier.fillMaxWidth().clip(shape).background(p.surface, shape)
            .border(if (selected) 2.dp else 0.5.dp, if (selected) Nexis.brand else p.line, shape)
            .selectable(selected = selected, enabled = enabled, role = Role.RadioButton, onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        leading()
        Column(Modifier.weight(1f)) {
            Text(title, style = body(15, if (selected) FontWeight.SemiBold else FontWeight.Medium, p.ink))
            if (subtitle != null) Text(subtitle, style = body(13, color = p.muted))
        }
        RadioDot(selected)
    }
}

/** Pastille de l'opérateur : une lettre en attendant l'accord des
 * opérateurs pour leurs logos. */
@Composable
fun OperatorBadge(operator: MobileOperator) {
    val (letter, color) = when (operator) {
        MobileOperator.MPESA -> "M" to 0xFFE60000
        MobileOperator.ORANGE -> "O" to 0xFFFF7900
        MobileOperator.AIRTEL -> "A" to 0xFFED1C24
    }
    Box(
        Modifier.size(40.dp).background(Color(color), RoundedCornerShape(12.dp)).clearAndSetSemantics { },
        contentAlignment = Alignment.Center,
    ) { Text(letter, style = body(14, FontWeight.ExtraBold, Color.White)) }
}

/** Case photo. L'envoi et l'affichage des photos arrivent avec le serveur :
 * en attendant, la case le dit au lieu de faire semblant. */
@Composable
fun PhotoSlot(icon: ImageVector, label: String, onClick: () -> Unit) {
    val shape = RoundedCornerShape(14.dp)
    Box(
        Modifier.size(64.dp).clip(shape)
            .background(Brush.linearGradient(listOf(pick(0xFFDDE6F0, 0xFF223047), pick(0xFFC8D4E2, 0xFF1A263A))), shape)
            .clickable(role = Role.Button, onClickLabel = label, onClick = onClick)
            .semantics { this.contentDescription = label },
        contentAlignment = Alignment.Center,
    ) { Icon(icon, contentDescription = null, tint = Color(0xFF7B8AA0), modifier = Modifier.size(22.dp)) }
}

/** Bouton bordé (« Signaler un problème », « Appeler Esther »). */
@Composable
fun OutlineButton(text: String, onClick: () -> Unit, enabled: Boolean = true, icon: ImageVector? = null) {
    val p = LocalPalette.current
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.fillMaxWidth().height(52.dp),
        shape = CircleShape,
        border = BorderStroke(1.dp, pick(0xFFD5DBE5, 0xFF2D3D5A)),
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = null, tint = p.ink, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
        }
        Text(text, style = body(16, FontWeight.SemiBold, p.ink))
    }
}

/** Ligne « libellé · montant » des cartes de confirmation et de décision. */
@Composable
fun AmountRow(label: String, amount: String, color: Color) {
    val p = LocalPalette.current
    Row(Modifier.fillMaxWidth().semantics(mergeDescendants = true) { }, verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = body(16, FontWeight.Bold, p.ink), modifier = Modifier.weight(1f))
        Text(amount, style = title(16, color = color))
    }
}

/** « Plomberie · Gombe » à gauche, le créneau à droite, puis un trait. */
@Composable
fun PlaceLine(place: String, slot: String?) {
    val p = LocalPalette.current
    Row(Modifier.fillMaxWidth()) {
        Text(place, style = body(14, color = p.muted), modifier = Modifier.weight(1f))
        if (slot != null) Text(slot, style = body(14, FontWeight.SemiBold, p.ink))
    }
    HorizontalDivider(color = p.line)
}

// Cadre des écrans de mission

/** Barre de titre avec retour, contenu qui défile, boutons d'action en bas. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FlowScaffold(
    heading: String,
    onBack: (() -> Unit)?,
    subtitle: String? = null,
    bottom: (@Composable ColumnScope.() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val app = LocalApp.current
    val p = LocalPalette.current
    Scaffold(
        containerColor = p.bg,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(heading, style = body(17, FontWeight.SemiBold, p.ink), maxLines = 1)
                        if (subtitle != null) Text(subtitle, style = body(12, color = p.muted), maxLines = 1)
                    }
                },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = app.t("back"), tint = p.ink)
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = p.bg, scrolledContainerColor = p.surface),
            )
        },
        bottomBar = {
            if (bottom != null) {
                Column(
                    Modifier.fillMaxWidth().background(p.bg).navigationBarsPadding().imePadding()
                        .padding(horizontal = 18.dp, vertical = 10.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    content = bottom,
                )
            }
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState())
                .padding(start = 18.dp, end = 18.dp, top = 6.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
            content = content,
        )
    }
}

/** Attente de lecture : les pictogrammes se relaient au milieu de l'écran. */
@Composable
fun FlowLoading(label: String) {
    val p = LocalPalette.current
    Box(Modifier.fillMaxSize().background(p.bg), contentAlignment = Alignment.Center) {
        PictoLoader(label = label, size = 40.dp, color = p.accent)
    }
}

/** Titre de section des écrans de mission. */
@Composable
fun SectionTitle(text: String) {
    val p = LocalPalette.current
    Text(text, style = body(16, FontWeight.SemiBold, p.ink), modifier = Modifier.padding(top = 4.dp))
}

/** Gros titre centré sous un rond (confirmation, décision). */
@Composable
fun CenteredHeading(heading: String, text: String, badge: @Composable () -> Unit) {
    val p = LocalPalette.current
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Box(Modifier.padding(vertical = 12.dp)) { badge() }
        Text(heading, style = title(20, color = p.ink), textAlign = TextAlign.Center)
        Text(text, style = body(15, color = p.muted), textAlign = TextAlign.Center)
    }
}
