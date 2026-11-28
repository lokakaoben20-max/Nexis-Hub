package com.nexishub.app.screens

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.rounded.PhotoLibrary
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import com.nexishub.app.data.CatalogService
import com.nexishub.app.data.ProviderShowcase
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Chat
import androidx.compose.material.icons.rounded.Balance
import androidx.compose.material.icons.rounded.CalendarToday
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Forum
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.NearMe
import androidx.compose.material.icons.rounded.Phone
import androidx.compose.material.icons.rounded.PhoneAndroid
import androidx.compose.material.icons.rounded.PhotoCamera
import androidx.compose.material.icons.rounded.Place
import androidx.compose.material.icons.rounded.Replay
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.drawscope.scale as scaleBy
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.nexishub.app.AppModel
import com.nexishub.app.LocalApp
import com.nexishub.app.data.Dispute
import com.nexishub.app.data.DisputeOutcome
import com.nexishub.app.data.DisputeReason
import com.nexishub.app.data.Mission
import com.nexishub.app.data.MissionStatus
import com.nexishub.app.data.MobileOperator
import com.nexishub.app.data.PayAccount
import com.nexishub.app.data.PaymentState
import com.nexishub.app.data.Quote
import com.nexishub.app.data.TrackStep
import com.nexishub.app.ui.AmountRow
import com.nexishub.app.ui.CenteredHeading
import com.nexishub.app.ui.ChoiceRow
import com.nexishub.app.ui.ComingSoonContent
import com.nexishub.app.ui.FlowLoading
import com.nexishub.app.ui.FlowScaffold
import com.nexishub.app.ui.InfoNote
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.NoteKind
import com.nexishub.app.ui.OperatorBadge
import com.nexishub.app.ui.OutlineButton
import com.nexishub.app.ui.PaymentPill
import com.nexishub.app.ui.PersonHeader
import com.nexishub.app.ui.PhotoSlot
import com.nexishub.app.ui.Pill
import com.nexishub.app.ui.PillTone
import com.nexishub.app.ui.PlaceLine
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.RoundIconButton
import com.nexishub.app.ui.SectionTitle
import com.nexishub.app.ui.ServiceTile
import com.nexishub.app.ui.StepItem
import com.nexishub.app.ui.StepList
import com.nexishub.app.ui.StepState
import com.nexishub.app.ui.body
import com.nexishub.app.ui.clock
import com.nexishub.app.ui.daysLeft
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.pick
import com.nexishub.app.ui.place
import com.nexishub.app.ui.rememberReduceMotion
import com.nexishub.app.ui.slot
import com.nexishub.app.ui.stamp
import com.nexishub.app.ui.title
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.Instant

// Parcours client d'une mission, repris des écrans Flutter
// (app_mobile/lib/screens/client) : devis, paiement, attente de
// l'opérateur, suivi, confirmation, signalement et litige.

// Navigation

/** Les écrans qu'on ouvre depuis une mission ou depuis le profil. Ils ne
 * portent que des numéros : chaque écran relit le dépôt, jamais une copie
 * gardée. */
sealed interface MissionRoute {
    data class Quotes(val missionId: Int) : MissionRoute
    data class Pay(val missionId: Int, val quoteId: Int) : MissionRoute
    data class Pending(val missionId: Int, val quoteId: Int, val operator: MobileOperator) : MissionRoute
    data class Tracking(val missionId: Int) : MissionRoute
    data class Confirm(val missionId: Int) : MissionRoute
    data class Report(val missionId: Int) : MissionRoute
    data class DisputeCase(val missionId: Int) : MissionRoute
    data class SendQuote(val missionId: Int) : MissionRoute
    data class Job(val missionId: Int) : MissionRoute

    // Écrans ouverts depuis le profil.
    data object ProfileInfo : MissionRoute
    data object Devices : MissionRoute
    data object NotificationSettings : MissionRoute
    data object Help : MissionRoute
    data object Legal : MissionRoute
    data object BecomeProvider : MissionRoute
    data object Security : MissionRoute
    data object Works : MissionRoute
    data object About : MissionRoute

    // Espace entreprise.
    data class OrgTeam(val orgId: Int) : MissionRoute
    data class OrgMemberRights(val orgId: Int, val memberId: Int) : MissionRoute
    data class OrgInvite(val orgId: Int) : MissionRoute
    data object OrgRoles : MissionRoute
    data class OrgNumbers(val orgId: Int) : MissionRoute
    data class OrgNumberAdd(val orgId: Int) : MissionRoute
    data class OrgWithdraw(val orgId: Int) : MissionRoute
    data object OrgCreate : MissionRoute
    data class OrgStatus(val orgId: Int) : MissionRoute

    companion object {
        /** Écrans ouverts d'emblée pour les captures de la CI. */
        fun forCapture(capture: String?): List<MissionRoute>? = when (capture) {
            "tracking" -> listOf(Tracking(51))
            "quotes", SHOWCASE_CAPTURE -> listOf(Quotes(52))
            "pay" -> listOf(Quotes(52), Pay(52, 521))
            "pending" -> listOf(Pending(52, 521, MobileOperator.MPESA))
            "confirm" -> listOf(Tracking(49), Confirm(49))
            "report" -> listOf(Report(51))
            "dispute" -> listOf(DisputeCase(47))
            "decision" -> listOf(DisputeCase(44))
            "request" -> listOf(SendQuote(71))
            "job" -> listOf(Job(61))
            "info" -> listOf(ProfileInfo)
            "devices" -> listOf(Devices)
            "alerts" -> listOf(NotificationSettings)
            "help" -> listOf(Help)
            "legal" -> listOf(Legal)
            "become", PortfolioDemo.STEP -> listOf(BecomeProvider)
            PortfolioDemo.PROFILE, PortfolioDemo.LOCKED -> listOf(Works)
            in IdentityDemo.codes -> listOf(BecomeProvider)
            "security" -> listOf(Security)
            "about" -> listOf(About)
            "org-team" -> listOf(OrgTeam(1))
            "org-member" -> listOf(OrgTeam(1), OrgMemberRights(1, 3))
            "org-invite" -> listOf(OrgTeam(1), OrgInvite(1))
            "org-roles" -> listOf(OrgRoles)
            "org-numbers" -> listOf(OrgNumbers(1))
            "org-number-add" -> listOf(OrgNumbers(1), OrgNumberAdd(1))
            "org-withdraw" -> listOf(OrgWithdraw(1))
            "org-intro", "org-step1", "org-rep-unverified", "org-docs", "org-terms" -> listOf(OrgCreate)
            "org-pending", "org-correction", "org-approved" -> listOf(OrgStatus(1))
            else -> null
        }
    }
}

/** La pile d'écrans de mission, et ce qu'elle montre par-dessus (message
 * bref, « Bientôt dans l'app », mission en attente de devis). */
class MissionFlow {
    val path = mutableStateListOf<MissionRoute>()
    var toast by mutableStateOf<String?>(null)
    var comingSoon by mutableStateOf<String?>(null)
    var pendingNotice by mutableStateOf<Mission?>(null)

    /** Comme l'app Flutter (`openMission`) : l'écran qui suit l'état réel. */
    fun open(mission: Mission, app: AppModel) {
        when (mission.status) {
            MissionStatus.PENDING -> pendingNotice = mission
            MissionStatus.QUOTED -> push(MissionRoute.Quotes(mission.id))
            MissionStatus.CONFIRMED, MissionStatus.IN_PROGRESS, MissionStatus.AWAITING_CONFIRMATION ->
                push(MissionRoute.Tracking(mission.id))
            MissionStatus.DISPUTED -> push(MissionRoute.DisputeCase(mission.id))
            MissionStatus.COMPLETED, MissionStatus.CANCELLED -> comingSoon = app.place(mission)
        }
    }

    fun push(route: MissionRoute) { path.add(route) }

    fun back() { if (path.isNotEmpty()) path.removeAt(path.lastIndex) }

    /** Revient à l'onglet, puis ouvre `route` s'il y en a une. */
    fun restart(route: MissionRoute?) {
        path.clear()
        if (route != null) path.add(route)
    }

    fun say(text: String) { toast = text }
}

val LocalFlow = staticCompositionLocalOf<MissionFlow> { error("MissionFlow absent") }

/** Lit le dépôt ; un refus ou une panne donne `null` (l'écran attend). */
suspend fun <T> attempt(block: suspend () -> T): T? = try {
    block()
} catch (cancel: CancellationException) {
    throw cancel
} catch (_: Exception) {
    null
}

/** Pose les écrans de mission par-dessus les onglets (la barre se range), et
 * leurs messages. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MissionFlowHost(flow: MissionFlow, tabs: @Composable () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    CompositionLocalProvider(LocalFlow provides flow) {
        Box(Modifier.fillMaxSize()) {
            tabs()
            BackHandler(enabled = flow.path.isNotEmpty()) { flow.back() }
            // Profondeur affichée juste avant : avancer glisse depuis la droite.
            val depth = remember { IntArray(1) }
            AnimatedContent(
                targetState = flow.path.lastOrNull(),
                transitionSpec = {
                    val forward = flow.path.size >= depth[0]
                    depth[0] = flow.path.size
                    if (forward) {
                        slideInHorizontally { it / 3 } + fadeIn() togetherWith fadeOut(tween(150))
                    } else {
                        fadeIn(tween(150)) togetherWith slideOutHorizontally { it / 3 } + fadeOut()
                    }
                },
                label = "mission",
            ) { route ->
                if (route != null) {
                    Box(Modifier.fillMaxSize().background(p.bg)) { MissionScreen(route) }
                }
            }
            AnimatedVisibility(
                visible = flow.toast != null,
                enter = slideInVertically { it } + fadeIn(),
                exit = slideOutVertically { it } + fadeOut(),
                modifier = Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 96.dp),
            ) {
                Text(
                    flow.toast.orEmpty(),
                    style = body(15, FontWeight.Medium, Color.White),
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 24.dp)
                        .background(Nexis.navy.copy(alpha = 0.94f), CircleShape)
                        .padding(horizontal = 18.dp, vertical = 12.dp)
                        .semantics { liveRegion = LiveRegionMode.Polite },
                )
            }
        }
    }
    LaunchedEffect(flow.toast) {
        val shown = flow.toast ?: return@LaunchedEffect
        delay(3_500)
        if (flow.toast == shown) flow.toast = null
    }
    flow.comingSoon?.let { heading ->
        ModalBottomSheet(onDismissRequest = { flow.comingSoon = null }, containerColor = p.surface) {
            ComingSoonContent(heading) { flow.comingSoon = null }
        }
    }
    flow.pendingNotice?.let { mission ->
        AlertDialog(
            onDismissRequest = { flow.pendingNotice = null },
            title = { Text(mission.serviceName(app.language), style = title(18, color = p.ink)) },
            text = {
                Text(
                    listOfNotNull(mission.commune, app.t("statusPending"), mission.detail).joinToString("\n"),
                    style = body(15, color = p.ink),
                )
            },
            confirmButton = { TextButton(onClick = { flow.pendingNotice = null }) { Text(app.t("close")) } },
            containerColor = p.surface,
        )
    }
}

@Composable
private fun MissionScreen(route: MissionRoute) {
    when (route) {
        is MissionRoute.Quotes -> QuotesScreen(route.missionId)
        is MissionRoute.Pay -> PayScreen(route.missionId, route.quoteId)
        is MissionRoute.Pending -> PaymentPendingScreen(route.missionId, route.quoteId, route.operator)
        is MissionRoute.Tracking -> TrackingScreen(route.missionId)
        is MissionRoute.Confirm -> ConfirmScreen(route.missionId)
        is MissionRoute.Report -> ReportScreen(route.missionId)
        is MissionRoute.DisputeCase -> DisputeScreen(route.missionId)
        is MissionRoute.SendQuote -> SendQuoteScreen(route.missionId)
        is MissionRoute.Job -> ProviderJobScreen(route.missionId)
        MissionRoute.ProfileInfo -> ProfileInfoScreen()
        MissionRoute.Devices -> DevicesScreen()
        MissionRoute.NotificationSettings -> NotificationSettingsScreen()
        MissionRoute.Help -> HelpScreen()
        MissionRoute.Legal -> LegalScreen()
        MissionRoute.BecomeProvider -> BecomeProviderScreen()
        MissionRoute.Security -> SecurityScreen()
        MissionRoute.Works -> PortfolioScreen()
        MissionRoute.About -> AboutScreen()
        is MissionRoute.OrgTeam -> OrgTeamScreen(route.orgId)
        is MissionRoute.OrgMemberRights -> OrgMemberScreen(route.orgId, route.memberId)
        is MissionRoute.OrgInvite -> OrgInviteScreen(route.orgId)
        MissionRoute.OrgRoles -> OrgRolesScreen()
        is MissionRoute.OrgNumbers -> OrgNumbersScreen(route.orgId)
        MissionRoute.OrgCreate -> OrgCreateScreen()
        is MissionRoute.OrgStatus -> OrgStatusScreen(route.orgId)
        is MissionRoute.OrgNumberAdd -> OrgNumberAddScreen(route.orgId)
        is MissionRoute.OrgWithdraw -> OrgWithdrawScreen(route.orgId)
    }
}

// 6. Suivi

@Composable
private fun TrackingScreen(missionId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    var mission by remember { mutableStateOf<Mission?>(null) }
    LaunchedEffect(app.revision) { mission = attempt { app.repository.mission(missionId) } }
    val shown = mission ?: return FlowLoading(app.t("trackTitle"))
    val name = shown.providerFirstName
    val current = TrackStep.entries.lastOrNull { it in shown.steps }
    val sharing = shown.distanceKm != null && current == TrackStep.ON_THE_WAY
    fun step(heading: String, step: TrackStep, sub: String? = null): StepItem {
        val state = when {
            step !in shown.steps -> StepState.TODO
            step == current && step != TrackStep.CONFIRMED -> StepState.NOW
            else -> StepState.DONE
        }
        return StepItem(heading, sub, shown.steps[step]?.let { app.clock(it) }, state)
    }
    val km = shown.distanceKm?.let { String.format(java.util.Locale.ROOT, "%.1f", it) }
        ?.let { if (app.language == "en") it else it.replace('.', ',') }.orEmpty()
    val confirm: (@Composable ColumnScope.() -> Unit)? = if (shown.status == MissionStatus.AWAITING_CONFIRMATION) {
        { PrimaryButton(app.t("confirmAction"), { flow.push(MissionRoute.Confirm(shown.id)) }) }
    } else {
        null
    }
    FlowScaffold(app.t("trackTitle"), onBack = flow::back, subtitle = app.place(shown), bottom = confirm) {
        Box(Modifier.fillMaxWidth().height(190.dp).clip(RoundedCornerShape(22.dp))) {
            MapSketch(sharing, Modifier.fillMaxSize())
            Row(
                Modifier.padding(12.dp).shadow(2.dp, CircleShape).background(Color.White, CircleShape)
                    .padding(horizontal = 11.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(if (sharing) Icons.Rounded.NearMe else Icons.Rounded.Place, contentDescription = null, tint = Nexis.brand, modifier = Modifier.size(15.dp))
                Text(
                    if (sharing) app.t("distanceAway", "name" to name, "km" to km) else app.t("trackingOff"),
                    style = body(12, FontWeight.SemiBold, Nexis.navy),
                )
            }
        }
        shown.chosen?.let { quote ->
            Box(Modifier.fillMaxWidth().nexisCard(LocalPalette.current).padding(14.dp)) {
                PersonHeader(quote.initials, quote.avatarColor, quote.providerName, quote.rating, quote.reviews) {
                    RoundIconButton(Icons.Rounded.Phone, app.t("callLabel")) { flow.comingSoon = app.t("callLabel") }
                    RoundIconButton(Icons.AutoMirrored.Rounded.Chat, app.t("messageLabel")) { flow.comingSoon = app.t("messageLabel") }
                }
            }
        }
        Box(Modifier.fillMaxWidth().nexisCard(LocalPalette.current).padding(16.dp)) {
            StepList(
                listOf(
                    step(app.t("stepPaid"), TrackStep.PAID, app.t("paySecured")),
                    step(app.t("stepOnTheWay"), TrackStep.ON_THE_WAY, if (sharing) app.t("stepOnTheWaySub") else null),
                    step(app.t("stepOnSite"), TrackStep.ON_SITE),
                    step(app.t("stepWorkDone"), TrackStep.WORK_DONE),
                    step(app.t("stepConfirm", "name" to name), TrackStep.CONFIRMED),
                ),
            )
        }
    }
}

/** Le petit plan de la maquette, dessiné (la vraie carte viendra avec le
 * suivi en direct). Il reste clair dans les deux thèmes, comme une carte. */
@Composable
fun MapSketch(sharing: Boolean, modifier: Modifier = Modifier) {
    Canvas(modifier.clearAndSetSemantics { }) {
        val k = maxOf(size.width / 350f, size.height / 190f)
        translate((size.width - 350f * k) / 2f, (size.height - 190f * k) / 2f) {
            scaleBy(k, k, pivot = Offset.Zero) {
                drawRect(Color(0xFFEAF1F8), size = Size(350f, 190f))
                val river = Path().apply {
                    moveTo(-10f, 150f)
                    cubicTo(60f, 140f, 90f, 170f, 160f, 160f)
                    cubicTo(230f, 150f, 280f, 120f, 360f, 130f)
                }
                drawPath(river, Color(0xFFCFE3F5), style = Stroke(16f, cap = StrokeCap.Round))
                for (l in listOf(
                    floatArrayOf(-10f, 40f, 360f, 70f), floatArrayOf(40f, -10f, 70f, 200f),
                    floatArrayOf(150f, -10f, 170f, 200f), floatArrayOf(260f, -10f, 240f, 200f),
                    floatArrayOf(-10f, 110f, 360f, 100f),
                )) drawLine(Color.White, Offset(l[0], l[1]), Offset(l[2], l[3]), 9f, StrokeCap.Round)
                for (l in listOf(
                    floatArrayOf(100f, -10f, 115f, 200f), floatArrayOf(-10f, 75f, 360f, 88f),
                    floatArrayOf(205f, -10f, 205f, 200f), floatArrayOf(310f, -10f, 300f, 200f),
                )) drawLine(Color.White, Offset(l[0], l[1]), Offset(l[2], l[3]), 4f, StrokeCap.Butt)
                val park = Color(0xFFDDEBD6)
                drawRoundRect(park, Offset(210f, 16f), Size(42f, 40f), CornerRadius(6f))
                drawRoundRect(park, Offset(76f, 118f), Size(30f, 26f), CornerRadius(6f))
                if (sharing) {
                    fun route(points: List<Offset>) = Path().apply {
                        moveTo(points[0].x, points[0].y)
                        points.drop(1).forEach { lineTo(it.x, it.y) }
                    }
                    val stroke = Stroke(5f, cap = StrokeCap.Round, join = StrokeJoin.Round)
                    drawPath(route(listOf(Offset(62f, 128f), Offset(58f, 104f), Offset(160f, 98f), Offset(166f, 70f), Offset(250f, 64f))), Nexis.brand, style = stroke)
                    drawPath(route(listOf(Offset(62f, 128f), Offset(58f, 104f), Offset(120f, 100f))), Color(0xFF9FC2F7), style = stroke)
                }
                // Chez le client.
                drawCircle(Nexis.navy, 12f, Offset(250f, 64f))
                drawCircle(Color.White, 4.5f, Offset(250f, 64f))
                if (sharing) {
                    // Le prestataire, en route.
                    drawCircle(Nexis.brand.copy(alpha = 0.15f), 16f, Offset(120f, 100f))
                    drawCircle(Nexis.brand, 9f, Offset(120f, 100f))
                    drawCircle(Color.White, 9f, Offset(120f, 100f), style = Stroke(3f))
                }
            }
        }
    }
}

// 3. Comparer les devis

@OptIn(ExperimentalLayoutApi::class)
/** Capture de la CI : les réalisations de Prisca, ouvertes depuis les devis. */
const val SHOWCASE_CAPTURE = "showcase"

@Composable
private fun QuotesScreen(missionId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    var mission by remember { mutableStateOf<Mission?>(null) }
    var quotes by remember { mutableStateOf(emptyList<Quote>()) }
    var showcases by remember { mutableStateOf(emptyMap<Int, ProviderShowcase>()) }
    var opened by remember { mutableStateOf<Quote?>(null) }
    LaunchedEffect(app.revision) {
        mission = attempt { app.repository.mission(missionId) }
        quotes = attempt { app.repository.quotes(missionId) }.orEmpty()
        val found = quotes.mapNotNull { quote -> attempt { app.repository.providerShowcase(quote.id) }?.let { quote.id to it } }.toMap()
        showcases = found
        if (app.capture == SHOWCASE_CAPTURE && opened == null) opened = quotes.firstOrNull { it.id in found }
    }
    opened?.let { quote ->
        showcases[quote.id]?.let { ShowcaseSheet(quote, it) { opened = null } }
    }
    val shown = mission ?: return FlowLoading(app.t("compareQuotes"))
    FlowScaffold(app.t("compareQuotes"), onBack = flow::back, subtitle = app.place(shown)) {
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            shown.wanted?.let { Pill(PillTone.WAIT, it, Icons.Rounded.CalendarToday) }
            Pill(PillTone.WAIT, listOfNotNull(shown.commune, shown.detail).joinToString(", "), Icons.Rounded.Place)
        }
        quotes.forEachIndexed { index, quote ->
            QuoteCard(
                quote, best = index == 0 && quotes.size > 1,
                onShowcase = if (quote.id in showcases) ({ opened = quote }) else null,
            ) { flow.push(MissionRoute.Pay(shown.id, quote.id)) }
        }
        InfoNote(app.t("securedUntilDone"), icon = Icons.Rounded.VerifiedUser)
    }
}

@Composable
private fun QuoteCard(quote: Quote, best: Boolean, onShowcase: (() -> Unit)?, onChoose: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val shape = RoundedCornerShape(22.dp)
    Box(Modifier.padding(top = if (best) 8.dp else 0.dp)) {
        Column(
            Modifier.fillMaxWidth().clip(shape).background(p.surface, shape)
                .border(if (best) 2.dp else 0.5.dp, if (best) Nexis.brand else p.line, shape).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            PersonHeader(quote.initials, quote.avatarColor, quote.providerName, quote.rating, quote.reviews) {
                Column(horizontalAlignment = Alignment.End) {
                    Text(app.money(quote.price), style = title(16, color = p.ink))
                    Text(app.slot(quote.slot, capital = true), style = body(12, color = p.muted))
                }
            }
            if (onShowcase != null) {
                TextButton(onClick = onShowcase, contentPadding = PaddingValues(0.dp)) {
                    Icon(Icons.Rounded.PhotoLibrary, contentDescription = null, tint = p.accent, modifier = Modifier.size(18.dp))
                    Text(app.t("showcaseOpen"), style = body(14, FontWeight.SemiBold, p.accent), modifier = Modifier.padding(start = 6.dp))
                }
            }
            val label = app.t("chooseProvider", "name" to quote.firstName)
            if (best) {
                PrimaryButton(label, onChoose)
            } else {
                FilledTonalButton(
                    onClick = onChoose,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    shape = CircleShape,
                    colors = ButtonDefaults.filledTonalButtonColors(containerColor = p.soft, contentColor = p.softInk),
                ) { Text(label, style = body(16, FontWeight.SemiBold)) }
            }
        }
        if (best) {
            Text(
                app.t("bestRated"),
                style = body(11, FontWeight.Bold, Color.White),
                modifier = Modifier.offset(x = 14.dp, y = (-10).dp).background(Nexis.brand, CircleShape)
                    .padding(horizontal = 9.dp, vertical = 3.dp),
            )
        }
    }
}

/** Les réalisations approuvées par l'équipe, vues par le client. Jamais les
 * diplômes : seulement « Diplôme vérifié par NexisHub ». */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun ShowcaseSheet(quote: Quote, showcase: ProviderShowcase, onDismiss: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var catalog by remember { mutableStateOf(emptyList<CatalogService>()) }
    LaunchedEffect(Unit) { catalog = attempt { app.repository.serviceCatalog() }.orEmpty() }
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = state, containerColor = p.bg) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(app.t("showcaseTitle", "name" to quote.firstName), style = title(19, color = p.ink), modifier = Modifier.weight(1f))
                TextButton(onClick = onDismiss) { Text(app.t("close"), style = body(15, FontWeight.SemiBold, p.accent)) }
            }
            PersonHeader(quote.initials, quote.avatarColor, quote.providerName, quote.rating, quote.reviews) {}
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill(PillTone.SECURED, app.t("showcaseChecked"), Icons.Rounded.VerifiedUser)
                if (showcase.certificateVerified) Pill(PillTone.OK, app.t("showcaseCertificate"), Icons.Rounded.Verified)
            }
            showcase.works.forEach { work ->
                Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    catalog.firstOrNull { it.id == work.serviceId }?.let { service ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            ServiceTile(service, 34.dp)
                            Text(service.label(app.language), style = body(15, FontWeight.Bold, p.ink), modifier = Modifier.padding(start = 10.dp))
                        }
                    }
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        work.photos.forEach { data ->
                            val picture = remember(data) { BitmapFactory.decodeByteArray(data, 0, data.size)?.asImageBitmap() }
                            if (picture != null) {
                                Image(
                                    picture, contentDescription = app.t("showcasePhoto"), contentScale = ContentScale.Crop,
                                    modifier = Modifier.size(168.dp).clip(RoundedCornerShape(14.dp)),
                                )
                            }
                        }
                    }
                    if (work.note.isNotEmpty()) Text(work.note, style = body(14, color = p.ink))
                }
            }
        }
    }
}

// 4. Payer

@Composable
private fun PayScreen(missionId: Int, quoteId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    var mission by remember { mutableStateOf<Mission?>(null) }
    var quote by remember { mutableStateOf<Quote?>(null) }
    var accounts by remember { mutableStateOf(emptyList<PayAccount>()) }
    var picked by remember { mutableStateOf<MobileOperator?>(null) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(app.revision) {
        mission = attempt { app.repository.mission(missionId) }
        quote = attempt { app.repository.quotes(missionId) }?.firstOrNull { it.id == quoteId }
        accounts = attempt { app.repository.payAccounts() }.orEmpty()
    }
    val shown = mission
    val chosenQuote = quote
    if (shown == null || chosenQuote == null) return FlowLoading(app.t("payTitle"))
    val chosen = picked ?: accounts.firstOrNull { it.maskedNumber != null }?.operator
    val amount = app.money(chosenQuote.price)
    FlowScaffold(
        app.t("payTitle"), onBack = flow::back,
        bottom = {
            PrimaryButton(
                app.t("payAmount", "amount" to amount),
                {
                    // Le code ou l'empreinte d'abord : sans lui, rien ne part.
                    chosen?.let { operator ->
                        scope.launch {
                            val reason = app.t("guardPay", "amount" to amount, "name" to chosenQuote.firstName)
                            if (app.confirmMoneyOut(reason)) flow.push(MissionRoute.Pending(shown.id, chosenQuote.id, operator))
                        }
                    }
                },
                enabled = chosen != null,
            )
        },
    ) {
        Column(
            Modifier.fillMaxWidth().nexisCard(p).padding(20.dp).semantics(mergeDescendants = true) { },
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            ServiceTile(shown, 54.dp)
            Text(app.place(shown), style = body(16, FontWeight.Bold, p.ink), modifier = Modifier.padding(top = 6.dp))
            Text("${chosenQuote.providerName} · ${app.slot(chosenQuote.slot)}", style = body(14, color = p.muted))
            Text(amount, style = title(30, color = p.accent), maxLines = 1, modifier = Modifier.padding(top = 4.dp))
        }
        SectionTitle(app.t("payWith"))
        accounts.forEach { account ->
            ChoiceRow(
                account.operator.displayName,
                selected = account.operator == chosen,
                onClick = {
                    if (account.maskedNumber == null) flow.comingSoon = app.t("addNumber") else picked = account.operator
                },
                subtitle = account.maskedNumber ?: app.t("addNumber"),
            ) { OperatorBadge(account.operator) }
        }
        InfoNote(app.t("paySecuredNote", "name" to chosenQuote.firstName), icon = Icons.Rounded.VerifiedUser)
    }
}

// En attente de l'opérateur

/** L'app attend la réponse réelle de l'opérateur ; quand il a confirmé,
 * on passe au suivi de la mission. */
@Composable
private fun PaymentPendingScreen(missionId: Int, quoteId: Int, operator: MobileOperator) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val reduceMotion = rememberReduceMotion()
    var quote by remember { mutableStateOf<Quote?>(null) }
    var failed by remember { mutableStateOf(false) }
    val sentAt = remember { Instant.now() }
    // Un seul envoi par écran : rien ne part deux fois si l'écran se redessine.
    LaunchedEffect(Unit) {
        quote = attempt { app.repository.quotes(missionId) }?.firstOrNull { it.id == quoteId }
        if (app.capture == "pending") return@LaunchedEffect
        try {
            val paid = app.repository.pay(missionId, quoteId, operator)
            app.dataChanged()
            flow.restart(MissionRoute.Tracking(paid.id))
        } catch (cancel: CancellationException) {
            throw cancel
        } catch (_: Exception) {
            failed = true
        }
    }
    // Pendant l'attente, le retour ne ferme pas l'écran.
    BackHandler(enabled = !failed) { }
    val pulse = if (reduceMotion) 1f else {
        val transition = rememberInfiniteTransition(label = "attente")
        transition.animateFloat(0.94f, 1.08f, infiniteRepeatable(tween(1_200), RepeatMode.Reverse), label = "halo").value
    }
    FlowScaffold(
        app.t("paymentTitle"), onBack = if (failed) flow::back else null,
        bottom = { OutlineButton(app.t("nothingReceived"), { flow.comingSoon = app.t("nothingReceived") }) },
    ) {
        Box(Modifier.fillMaxWidth().height(180.dp).clearAndSetSemantics { }, contentAlignment = Alignment.Center) {
            Box(
                Modifier.size(180.dp).background(
                    Brush.radialGradient(listOf(Nexis.halo.copy(alpha = 0.22f), Nexis.halo.copy(alpha = 0f))), CircleShape,
                ),
            )
            Box(
                Modifier.size(124.dp).scale(pulse).background(Nexis.halo.copy(alpha = 0.10f), CircleShape)
                    .border(1.5.dp, Nexis.halo.copy(alpha = 0.25f), CircleShape),
            )
            Box(
                Modifier.size(84.dp).shadow(18.dp, RoundedCornerShape(28.dp), spotColor = Nexis.gradientEnd)
                    .background(Nexis.heroGradient, RoundedCornerShape(28.dp)),
                contentAlignment = Alignment.Center,
            ) { Icon(Icons.Rounded.PhoneAndroid, contentDescription = null, tint = Color.White, modifier = Modifier.size(38.dp)) }
        }
        Text(app.t("pendingTitle"), style = title(21, color = p.ink), textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
        Text(
            if (failed) app.t("actionFailed")
            else app.t("pendingText", "operator" to operator.displayName, "amount" to (quote?.let { app.money(it.price) } ?: "")),
            style = body(15, color = if (failed) Nexis.danger else p.muted),
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )
        Box(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp)) {
            StepList(
                listOf(
                    StepItem(app.t("pendingSent", "operator" to operator.displayName), time = app.clock(sentAt), state = StepState.DONE),
                    StepItem(app.t("pendingWaiting"), app.t("pendingWithin"), state = StepState.NOW),
                    StepItem(app.t("pendingSecured"), app.t("pendingNotify", "name" to (quote?.firstName ?: "")), state = StepState.TODO),
                ),
            )
        }
    }
}

// 7. Confirmer que c'est fait

@Composable
private fun ConfirmScreen(missionId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var mission by remember { mutableStateOf<Mission?>(null) }
    var busy by remember { mutableStateOf(false) }
    LaunchedEffect(app.revision) { if (!busy) mission = attempt { app.repository.mission(missionId) } }
    val shown = mission ?: return FlowLoading(app.t("confirmAction"))
    val name = shown.providerFirstName
    FlowScaffold(
        app.t("confirmAction"), onBack = flow::back,
        bottom = {
            PrimaryButton(app.t("yesDone"), {
                scope.launch {
                    // Verser l'argent au prestataire : le code ou l'empreinte d'abord.
                    if (!app.confirmMoneyOut(app.t("guardRelease", "name" to name))) return@launch
                    busy = true
                    try {
                        app.repository.confirmDone(shown.id)
                        app.dataChanged()
                        flow.restart(null)
                        flow.say(app.t("confirmedToast", "name" to name))
                    } catch (cancel: CancellationException) {
                        throw cancel
                    } catch (_: Exception) {
                        busy = false
                        flow.say(app.t("actionFailed"))
                    }
                }
            }, icon = Icons.Rounded.Check, loading = busy)
            OutlineButton(app.t("reportProblem"), { flow.push(MissionRoute.Report(shown.id)) }, enabled = !busy)
        },
    ) {
        CenteredHeading(app.t("confirmQuestion", "name" to name), app.t("confirmText", "name" to name)) {
            Box(
                Modifier.size(108.dp).background(pick(0xFFF1F6FE, 0xFF121E33), CircleShape).padding(10.dp)
                    .background(p.soft, CircleShape),
                contentAlignment = Alignment.Center,
            ) { ServiceTile(shown, 56.dp) }
        }
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            PlaceLine(app.place(shown), shown.chosen?.slot?.let { app.slot(it) })
            shown.amount?.let { AmountRow(app.t("paidTo", "name" to name), app.money(it), p.accent) }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Rounded.VerifiedUser, contentDescription = null, tint = Nexis.brand, modifier = Modifier.size(15.dp))
                Text(app.t("amountFixed"), style = body(12, color = p.muted), modifier = Modifier.padding(start = 6.dp))
            }
        }
        InfoNote(app.t("report48h"), NoteKind.VIOLET)
    }
}

// 25. Signaler un problème

fun AppModel.reasonText(reason: DisputeReason): String = when (reason) {
    DisputeReason.NOT_FINISHED -> t("reasonNotFinished")
    DisputeReason.BAD_WORK -> t("reasonBadWork")
    DisputeReason.NO_SHOW -> t("reasonNoShow")
    DisputeReason.OTHER -> t("reasonOther")
}

private const val REPORT_MAX = 500

@Composable
private fun ReportScreen(missionId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var mission by remember { mutableStateOf<Mission?>(null) }
    var reason by remember { mutableStateOf<DisputeReason?>(null) }
    var text by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    LaunchedEffect(app.revision) { if (!busy) mission = attempt { app.repository.mission(missionId) } }
    val shown = mission ?: return FlowLoading(app.t("reportProblem"))
    val ready = reason != null && text.isNotBlank()
    FlowScaffold(
        app.t("reportProblem"), onBack = flow::back, subtitle = app.place(shown),
        bottom = {
            PrimaryButton(app.t("sendReport"), {
                val chosen = reason ?: return@PrimaryButton
                busy = true
                scope.launch {
                    try {
                        app.repository.reportProblem(missionId, chosen, text)
                        app.dataChanged()
                        flow.restart(MissionRoute.DisputeCase(missionId))
                    } catch (cancel: CancellationException) {
                        throw cancel
                    } catch (_: Exception) {
                        busy = false
                        flow.say(app.t("reportFailed"))
                    }
                }
            }, enabled = ready, loading = busy)
        },
    ) {
        SectionTitle(app.t("whatHappened"))
        DisputeReason.entries.forEach { item ->
            ChoiceRow(app.reasonText(item), selected = reason == item, onClick = { reason = item }, enabled = !busy)
        }
        OutlinedTextField(
            value = text,
            onValueChange = { text = it.take(REPORT_MAX) },
            enabled = !busy,
            placeholder = { Text(app.t("reportHint"), style = body(15, color = p.muted)) },
            textStyle = body(15, color = p.ink),
            minLines = 3,
            maxLines = 6,
            shape = RoundedCornerShape(16.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Nexis.brand, unfocusedBorderColor = p.line,
                focusedContainerColor = p.surface, unfocusedContainerColor = p.surface,
            ),
            modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            PhotoSlot(Icons.Rounded.PhotoCamera, app.t("addPhoto")) { flow.comingSoon = app.t("addPhoto") }
            PhotoSlot(Icons.Rounded.Image, app.t("addPhoto")) { flow.comingSoon = app.t("addPhoto") }
        }
        shown.amount?.let { InfoNote(app.t("reportFrozen", "amount" to app.money(it)), NoteKind.DANGER, Icons.Rounded.Lock) }
    }
}

// 26 et 27. Litige

@Composable
private fun DisputeScreen(missionId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    var mission by remember { mutableStateOf<Mission?>(null) }
    var dispute by remember { mutableStateOf<Dispute?>(null) }
    var loaded by remember { mutableStateOf(false) }
    LaunchedEffect(app.revision) {
        mission = attempt { app.repository.mission(missionId) }
        dispute = attempt { app.repository.dispute(missionId) }
        loaded = true
    }
    val shown = mission
    if (!loaded || shown == null) return FlowLoading(app.t("disputeTitle"))
    val case = dispute
    when {
        case == null -> FlowScaffold(app.t("disputeTitle"), onBack = flow::back) { }
        case.decided -> DecisionView(shown, case)
        else -> OpenDisputeView(shown, case)
    }
}

@Composable
private fun OpenDisputeView(mission: Mission, dispute: Dispute) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val name = mission.providerFirstName
    FlowScaffold(
        app.t("disputeTitle"), onBack = flow::back, subtitle = app.place(mission),
        bottom = {
            PrimaryButton(app.t("writeNexis"), { flow.comingSoon = app.t("writeNexis") }, icon = Icons.Rounded.Forum)
            OutlineButton(app.t("weSettled"), { flow.comingSoon = app.t("weSettled") })
        },
    ) {
        mission.amount?.let { amount ->
            val shape = RoundedCornerShape(20.dp)
            Row(
                Modifier.fillMaxWidth().background(pick(0xFFFFF6F5, 0xFF2A1513), shape)
                    .border(1.dp, pick(0xFFF6D3CF, 0xFF5A2A25), shape).padding(14.dp)
                    .semantics(mergeDescendants = true) { },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(Modifier.size(44.dp).background(pick(0xFFFDE8E6, 0xFF3A1715), CircleShape), contentAlignment = Alignment.Center) {
                    Icon(Icons.Rounded.Lock, contentDescription = null, tint = Color(0xFFA1261B), modifier = Modifier.size(20.dp))
                }
                Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                    Text(app.money(amount), style = title(16, color = p.ink))
                    Text(app.t("nobodyTouches"), style = body(13, color = pick(0xFF7A3A33, 0xFFFFB4AB)))
                }
                PaymentPill(PaymentState.BLOCKED)
            }
        }
        val steps = buildList {
            add(
                StepItem(
                    app.t("youReported"),
                    "${app.reasonText(dispute.reason)} · ${app.plural("photosCount", dispute.photos)}",
                    app.stamp(dispute.openedAt), StepState.DONE,
                ),
            )
            dispute.providerReply?.let { reply ->
                add(
                    StepItem(
                        app.t("providerReplied", "name" to name),
                        if (app.language == "en") "“$reply”" else "« $reply »",
                        dispute.providerRepliedAt?.let { app.stamp(it) }, StepState.DONE,
                    ),
                )
            }
            add(StepItem(app.t("nexisLooking"), app.t("nexisLookingSub"), state = StepState.NOW))
            add(StepItem(app.t("decisionStep"), app.t("decisionStepSub"), state = StepState.TODO))
        }
        Box(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp)) { StepList(steps) }
        InfoNote(app.t("settleHint", "name" to name), NoteKind.VIOLET)
    }
}

/** Décision : remboursé, versé au prestataire ou partagé. Les montants
 * viennent du serveur ; l'argent reste bloqué 3 jours pour contester. */
@Composable
private fun DecisionView(mission: Mission, dispute: Dispute) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val name = mission.providerFirstName
    val outcome = dispute.outcome ?: DisputeOutcome.REFUND
    val left = dispute.contestUntil?.let { daysLeft(it) } ?: 0
    val violet = pick(0xFF494C95, 0xFFB3B5F2)
    val (icon, heading, text) = when (outcome) {
        DisputeOutcome.REFUND -> Triple(Icons.Rounded.Replay, app.t("outcomeRefundTitle"), app.t("outcomeRefundText", "name" to name))
        DisputeOutcome.RELEASE -> Triple(
            Icons.Rounded.CheckCircle, app.t("outcomeReleaseTitle", "name" to name), app.t("outcomeReleaseText", "name" to name),
        )
        DisputeOutcome.SPLIT -> Triple(Icons.Rounded.Balance, app.t("outcomeSplitTitle"), app.t("outcomeSplitText", "name" to name))
    }
    FlowScaffold(
        app.t("disputeOver"), onBack = flow::back,
        bottom = {
            PrimaryButton(app.t("seeWallet"), {
                app.requestedTab = 2
                flow.restart(null)
            })
        },
    ) {
        CenteredHeading(heading, text) {
            Box(
                Modifier.size(108.dp).background(pick(0xFFF4F4FB, 0xFF121E33), CircleShape).padding(10.dp)
                    .background(pick(0xFFECECF8, 0xFF22234A), CircleShape),
                contentAlignment = Alignment.Center,
            ) { Icon(icon, contentDescription = null, tint = violet, modifier = Modifier.size(36.dp)) }
        }
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            PlaceLine(app.place(mission), mission.chosen?.slot?.let { app.slot(it) })
            val client = dispute.clientAmount
            val provider = dispute.providerAmount
            if (outcome != DisputeOutcome.RELEASE && client != null) AmountRow(app.t("toRefundYou"), app.money(client), violet)
            if (outcome == DisputeOutcome.SPLIT && provider != null) {
                AmountRow(app.t("forProvider", "name" to name), app.money(provider), violet)
            }
            if (outcome == DisputeOutcome.RELEASE && provider != null) {
                AmountRow(app.t("paidTo", "name" to name), app.money(provider), violet)
            }
            if (left > 0) {
                Pill(PillTone.BAD, app.plural("blockedDaysLeft", left), Icons.Rounded.Lock)
            } else {
                PaymentPill(if (outcome == DisputeOutcome.RELEASE) PaymentState.RELEASED else PaymentState.REFUNDED)
            }
        }
        if (left > 0) InfoNote(app.plural("contestHint", left), NoteKind.VIOLET)
    }
}
