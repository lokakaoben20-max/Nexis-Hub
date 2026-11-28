package com.nexishub.app.screens

import android.Manifest
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.DirectionsWalk
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Description
import androidx.compose.material.icons.rounded.Error
import androidx.compose.material.icons.rounded.Forum
import androidx.compose.material.icons.rounded.Gavel
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.Notifications
import androidx.compose.material.icons.rounded.NotificationsOff
import androidx.compose.material.icons.rounded.Payments
import androidx.compose.material.icons.rounded.PhoneAndroid
import androidx.compose.material.icons.rounded.PhoneIphone
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.app.NotificationManagerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.nexishub.app.AppModel
import com.nexishub.app.LocalApp
import com.nexishub.app.data.AppDevice
import com.nexishub.app.data.CatalogService
import com.nexishub.app.data.DevicePlatform
import com.nexishub.app.data.DrcPhone
import com.nexishub.app.data.LegalDocument
import com.nexishub.app.data.LegalDocumentKey
import com.nexishub.app.data.LegalText
import com.nexishub.app.data.Mission
import com.nexishub.app.data.MissionStatus
import com.nexishub.app.data.Profile
import com.nexishub.app.ui.FlowLoading
import com.nexishub.app.ui.FlowScaffold
import com.nexishub.app.ui.InfoNote
import com.nexishub.app.ui.InitialsAvatar
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.NoteKind
import com.nexishub.app.ui.OutlineButton
import com.nexishub.app.ui.PaymentPill
import com.nexishub.app.ui.Pill
import com.nexishub.app.ui.PillTone
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.ServiceTile
import com.nexishub.app.ui.body
import com.nexishub.app.ui.clock
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.pick
import com.nexishub.app.ui.place
import com.nexishub.app.ui.stamp
import com.nexishub.app.ui.title
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.Instant
import java.util.Locale

// Écrans ouverts depuis le profil : mes informations, mes téléphones,
// notifications, aide et litiges, conditions, devenir prestataire.

/** « 20/11/2026 » (« 11/20/2026 » en anglais). */
fun AppModel.longDate(date: LocalDate): String =
    date.format(DateTimeFormatter.ofPattern(if (language == "en") "MM/dd/yyyy" else "dd/MM/yyyy", Locale.ROOT))

fun AppModel.longDate(time: Instant): String = longDate(time.atZone(ZoneId.systemDefault()).toLocalDate())

/** « aujourd'hui 1 h 30 » : l'heure seule se lirait comme une durée. */
fun AppModel.lastSeen(time: Instant): String =
    if (time.atZone(ZoneId.systemDefault()).toLocalDate() == LocalDate.now()) "${t("today").lowercase()} ${clock(time)}" else stamp(time)

@Composable
private fun Heading(text: String) {
    val p = LocalPalette.current
    Text(text, style = body(16, FontWeight.SemiBold, p.ink), modifier = Modifier.padding(top = 4.dp).semantics { heading() })
}

// Mes informations

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileInfoScreen() {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var profile by remember { mutableStateOf<Profile?>(null) }
    var firstName by remember { mutableStateOf("") }
    var lastName by remember { mutableStateOf("") }
    var commune by remember { mutableStateOf("") }
    var communeMenu by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        attempt { app.repository.profile() }?.let {
            profile = it
            firstName = it.firstName
            lastName = it.lastName
            commune = it.commune
        }
    }
    val me = profile ?: return FlowLoading(app.t("myInfo"))
    val first = firstName.trim()
    val last = lastName.trim()
    val changed = first != me.firstName || last != me.lastName || commune != me.commune
    val ready = changed && first.isNotEmpty() && last.isNotEmpty() && commune.isNotEmpty()
    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedBorderColor = Nexis.brand, unfocusedBorderColor = p.line,
        focusedContainerColor = p.surface, unfocusedContainerColor = p.surface,
    )
    FlowScaffold(
        app.t("myInfo"), onBack = flow::back,
        bottom = {
            PrimaryButton(app.t("infoSave"), {
                busy = true
                scope.launch {
                    try {
                        app.repository.updateProfile(firstName, lastName, commune)
                        app.dataChanged()
                        flow.back()
                        flow.say(app.t("infoSaved"))
                    } catch (cancel: CancellationException) {
                        throw cancel
                    } catch (_: Exception) {
                        busy = false
                        failed = true
                    }
                }
            }, enabled = ready, loading = busy)
        },
    ) {
        Box(Modifier.fillMaxWidth().padding(vertical = 10.dp), contentAlignment = Alignment.Center) {
            InitialsAvatar((first.take(1) + last.take(1)).uppercase(), 84.dp)
        }
        OutlinedTextField(
            value = firstName, onValueChange = { firstName = it; failed = false }, enabled = !busy, singleLine = true,
            label = { Text(app.t("signupFirstName")) }, textStyle = body(16, color = p.ink), shape = RoundedCornerShape(16.dp),
            colors = fieldColors, modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = lastName, onValueChange = { lastName = it; failed = false }, enabled = !busy, singleLine = true,
            label = { Text(app.t("signupLastName")) }, textStyle = body(16, color = p.ink), shape = RoundedCornerShape(16.dp),
            colors = fieldColors, modifier = Modifier.fillMaxWidth(),
        )
        ExposedDropdownMenuBox(expanded = communeMenu, onExpandedChange = { if (!busy) communeMenu = it }) {
            OutlinedTextField(
                value = commune, onValueChange = {}, readOnly = true, enabled = !busy,
                label = { Text(app.t("commune")) },
                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(communeMenu) },
                textStyle = body(16, color = p.ink), shape = RoundedCornerShape(16.dp), colors = fieldColors,
                modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable),
            )
            ExposedDropdownMenu(expanded = communeMenu, onDismissRequest = { communeMenu = false }) {
                app.repository.communes.forEach { item ->
                    DropdownMenuItem(text = { Text(item) }, onClick = {
                        commune = item
                        communeMenu = false
                    })
                }
            }
        }
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(app.t("phone"), style = body(13, color = p.muted))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("+243 ${DrcPhone.parse(me.phone).formatted}", style = body(16, color = p.ink), modifier = Modifier.weight(1f))
                Pill(PillTone.OK, app.t("infoPhoneVerified"), Icons.Rounded.VerifiedUser)
            }
            Text(app.t("infoPhoneLocked"), style = body(13, color = p.muted))
        }
        if (failed) Text(app.t("infoFailed"), style = body(14, color = Nexis.danger))
    }
}

// Mes appareils

@Composable
fun DevicesScreen() {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var devices by remember { mutableStateOf<List<AppDevice>?>(null) }
    var confirming by remember { mutableStateOf<AppDevice?>(null) }
    var busy by remember { mutableStateOf<Int?>(null) }
    LaunchedEffect(app.revision) { devices = attempt { app.repository.devices() } }
    val shown = devices ?: return FlowLoading(app.t("myDevices"))
    val others = shown.filter { !it.isCurrent }
    FlowScaffold(app.t("myDevices"), onBack = flow::back) {
        Heading(app.t("devicesThis"))
        shown.filter { it.isCurrent }.forEach { DeviceCard(it) }
        if (others.isNotEmpty()) {
            Spacer(Modifier.height(2.dp))
            Heading(app.t("devicesOthers"))
            others.forEach { device ->
                DeviceCard(device) {
                    OutlineButton(app.t("devicesSignOut"), { confirming = device }, enabled = busy == null)
                }
            }
            InfoNote(app.t("devicesNotMe"), NoteKind.DANGER, Icons.Rounded.Security)
        }
        InfoNote(app.t("devicesMoneyHint"), icon = Icons.Rounded.Lock)
    }
    confirming?.let { device ->
        AlertDialog(
            onDismissRequest = { confirming = null },
            title = { Text(app.t("devicesSignOutTitle", "name" to device.label), style = title(18, color = p.ink)) },
            text = { Text(app.t("devicesSignOutText"), style = body(15, color = p.ink)) },
            confirmButton = {
                TextButton(onClick = {
                    confirming = null
                    busy = device.id
                    scope.launch {
                        try {
                            app.repository.signOutDevice(device.id)
                            app.dataChanged()
                            flow.say(app.t("devicesSignedOut", "name" to device.label))
                        } catch (cancel: CancellationException) {
                            throw cancel
                        } catch (_: Exception) {
                            flow.say(app.t("actionFailed"))
                        } finally {
                            busy = null
                        }
                    }
                }) { Text(app.t("devicesSignOut"), color = Nexis.danger) }
            },
            dismissButton = { TextButton(onClick = { confirming = null }) { Text(app.t("close")) } },
            containerColor = p.surface,
        )
    }
}

@Composable
private fun DeviceCard(device: AppDevice, actions: @Composable () -> Unit = {}) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val hours = device.moneyHoursLeft()
    Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(44.dp).background(p.soft, RoundedCornerShape(13.dp)), contentAlignment = Alignment.Center) {
                Icon(
                    if (device.platform == DevicePlatform.IOS) Icons.Rounded.PhoneIphone else Icons.Rounded.PhoneAndroid,
                    contentDescription = null, tint = p.softInk, modifier = Modifier.size(22.dp),
                )
            }
            Column(Modifier.weight(1f).padding(start = 12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(device.label, style = body(15, FontWeight.Bold, p.ink))
                Text(app.t("devicesAdded", "date" to app.longDate(device.addedAt)), style = body(13, color = p.muted))
                if (!device.isCurrent && device.lastSeenAt != null) {
                    Text(app.t("devicesLastSeen", "when" to app.lastSeen(device.lastSeenAt)), style = body(13, color = p.muted))
                }
            }
        }
        if (hours > 0) Pill(PillTone.WARN, app.plural("devicesMoneyIn", hours), Icons.Rounded.Schedule)
        actions()
    }
}

// Notifications

private fun notificationsAllowed(context: Context): Boolean = NotificationManagerCompat.from(context).areNotificationsEnabled()

/** L'autorisation réelle du téléphone, et ce que NexisHub envoie. Les
 * messages sur l'argent et la sécurité ne se règlent pas un par un. */
@Composable
fun NotificationSettingsScreen() {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val context = LocalContext.current
    var allowed by remember { mutableStateOf(notificationsAllowed(context)) }
    var asked by remember { mutableStateOf(false) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) allowed = notificationsAllowed(context)
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    val askPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        asked = true
        allowed = notificationsAllowed(context)
    }
    val kinds = listOf(
        "notifQuotes" to Icons.Rounded.Description,
        "notifMission" to Icons.AutoMirrored.Rounded.DirectionsWalk,
        "notifMoney" to Icons.Rounded.Payments,
        "notifDisputes" to Icons.Rounded.Gavel,
        "notifSecurity" to Icons.Rounded.Security,
    )
    FlowScaffold(app.t("notifications"), onBack = flow::back) {
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.semantics(mergeDescendants = true) { }) {
                Box(
                    Modifier.size(44.dp).background(
                        if (allowed) pick(0xFFE3F5EA, 0xFF12301F) else pick(0xFFFDECEA, 0xFF3A1715), RoundedCornerShape(13.dp),
                    ),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        if (allowed) Icons.Rounded.Notifications else Icons.Rounded.NotificationsOff, contentDescription = null,
                        tint = if (allowed) Nexis.ok else Nexis.danger, modifier = Modifier.size(22.dp),
                    )
                }
                Column(Modifier.weight(1f).padding(start = 12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(app.t(if (allowed) "notifAllowed" else "notifOff"), style = body(15, FontWeight.Bold, p.ink))
                    Text(app.t(if (allowed) "notifAllowedSub" else "notifOffSub"), style = body(13, color = p.muted))
                }
            }
            if (!allowed) {
                // Android 13 et plus : on demande une fois ; ensuite, les réglages.
                val canAsk = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !asked
                PrimaryButton(app.t(if (canAsk) "notifAllow" else "notifOpenSettings"), {
                    if (canAsk) {
                        askPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                    } else {
                        context.startActivity(
                            Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                                .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName),
                        )
                    }
                })
            }
        }
        Heading(app.t("notifWhatTitle"))
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(horizontal = 16.dp)) {
            kinds.forEachIndexed { index, (key, icon) ->
                Row(Modifier.padding(vertical = 13.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(icon, contentDescription = null, tint = p.accent, modifier = Modifier.size(20.dp))
                    Text(app.t(key), style = body(15, color = p.ink), modifier = Modifier.padding(start = 14.dp))
                }
                if (index < kinds.lastIndex) HorizontalDivider(color = p.line)
            }
        }
        InfoNote(app.t("notifAlwaysHint"), icon = Icons.Rounded.Lock)
    }
}

// Aide et litiges

@Composable
fun HelpScreen() {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    var disputes by remember { mutableStateOf<List<Mission>?>(null) }
    var open by remember { mutableStateOf<Int?>(null) }
    LaunchedEffect(app.revision) {
        disputes = attempt { app.repository.missions() }?.filter { it.status == MissionStatus.DISPUTED }
    }
    val questions = listOf(
        "faqPaidQ" to "faqPaidA", "faqReportQ" to "faqReportA", "faqContestQ" to "faqContestA",
        "faqSettleQ" to "faqSettleA", "faqDeviceQ" to "faqDeviceA",
    )
    FlowScaffold(
        app.t("helpDisputes"), onBack = flow::back,
        bottom = { PrimaryButton(app.t("writeNexis"), { flow.comingSoon = app.t("writeNexis") }, icon = Icons.Rounded.Forum) },
    ) {
        Heading(app.t("helpMyDisputes"))
        disputes?.let { list ->
            if (list.isEmpty()) {
                Text(app.t("helpNoDispute"), style = body(15, color = p.muted), textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(14.dp))
            }
            list.forEach { mission ->
                Row(
                    Modifier.fillMaxWidth().nexisCard(p).clickable(role = Role.Button) { flow.push(MissionRoute.DisputeCase(mission.id)) }
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    ServiceTile(mission, 44.dp)
                    Column(Modifier.weight(1f).padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(app.place(mission), style = body(15, FontWeight.Bold, p.ink))
                        mission.providerName?.let { Text(it, style = body(13, color = p.muted)) }
                        PaymentPill(mission.payment)
                    }
                    Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, contentDescription = null, tint = p.muted)
                }
            }
        }
        Heading(app.t("helpQuestions"))
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(horizontal = 16.dp)) {
            questions.forEachIndexed { index, (question, answer) ->
                val expanded = open == index
                Column(
                    Modifier.fillMaxWidth().toggleable(expanded, role = Role.Button) { open = if (expanded) null else index }
                        .padding(vertical = 13.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(app.t(question), style = body(15, FontWeight.SemiBold, p.ink), modifier = Modifier.weight(1f))
                        Icon(
                            Icons.AutoMirrored.Rounded.KeyboardArrowRight, contentDescription = null, tint = p.accent,
                            modifier = Modifier.padding(start = 8.dp).rotate(if (expanded) 90f else 0f),
                        )
                    }
                    if (expanded) Text(app.t(answer), style = body(15, color = p.muted))
                }
                if (index < questions.lastIndex) HorizontalDivider(color = p.line)
            }
        }
    }
}

// Conditions d'utilisation

fun AppModel.legalTitle(key: LegalDocumentKey): String = when (key) {
    LegalDocumentKey.CGU -> t("legalCgu")
    LegalDocumentKey.PROVIDER_TERMS -> t("legalProviderTerms")
    LegalDocumentKey.ORG_TERMS -> t("orgTermsTitle")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LegalScreen() {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    var documents by remember { mutableStateOf<List<LegalDocument>?>(null) }
    var reading by remember { mutableStateOf<LegalDocumentKey?>(null) }
    LaunchedEffect(app.revision) { documents = attempt { app.repository.legalDocuments() } }
    val shown = documents ?: return FlowLoading(app.t("legalTerms"))
    FlowScaffold(app.t("legalTerms"), onBack = flow::back) {
        shown.forEach { document ->
            Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(app.legalTitle(document.key), style = body(15, FontWeight.Bold, p.ink))
                Text(app.t("termsVersion", "date" to app.longDate(document.version)), style = body(13, color = p.muted))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    val accepted = document.acceptedAt
                    if (accepted != null) {
                        Pill(PillTone.OK, app.t("legalAcceptedOn", "date" to app.longDate(accepted)), Icons.Rounded.Check)
                    } else {
                        Pill(PillTone.WARN, app.t("legalToAccept"), Icons.Rounded.Error)
                    }
                    Spacer(Modifier.weight(1f))
                    TextButton(onClick = { reading = document.key }) {
                        Text(app.t("legalRead"), style = body(15, FontWeight.SemiBold, p.accent))
                    }
                }
            }
        }
    }
    reading?.let { key -> LegalReader(key) { reading = null } }
}

/** Le texte exact de la version en vigueur. Tant qu'aucune version n'est
 * publiée (aperçu), l'écran le dit. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LegalReader(key: LegalDocumentKey, onClose: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var text by remember { mutableStateOf<LegalText?>(null) }
    LaunchedEffect(key) { text = attempt { app.repository.legalText(key) } }
    ModalBottomSheet(onDismissRequest = onClose, containerColor = p.surface) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 20.dp, end = 20.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(app.legalTitle(key), style = title(18, color = p.ink), modifier = Modifier.semantics { heading() })
            text?.let {
                Text(app.t("termsVersion", "date" to app.longDate(it.version)), style = body(13, color = p.muted))
                Text(it.text ?: app.t("signupDemoTerms"), style = body(16, color = p.ink))
            }
            TextButton(onClick = onClose, modifier = Modifier.align(Alignment.End)) { Text(app.t("close")) }
        }
    }
}

// Devenir prestataire

/** Services, réalisations (facultatif), communes, pièce d'identité, conditions. */
private const val BECOME_STEPS = 5

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun BecomeProviderScreen() {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var step by remember {
        mutableStateOf(
            when (app.capture) {
                in IdentityDemo.codes -> 4
                PortfolioDemo.STEP -> 2
                else -> 1
            },
        )
    }
    var catalog by remember { mutableStateOf(emptyList<CatalogService>()) }
    var services by remember { mutableStateOf(if (app.capture == PortfolioDemo.STEP) setOf("plomberie", "electricite") else emptySet()) }
    var works by remember { mutableStateOf(if (app.capture == PortfolioDemo.STEP) PortfolioDemo.draft(listOf("plomberie")) else PortfolioDraft()) }
    var communes by remember { mutableStateOf(emptySet<String>()) }
    var identity by remember { mutableStateOf(IdentityDraft()) }
    var accepted by remember { mutableStateOf(false) }
    var readingTerms by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    var sent by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { catalog = attempt { app.repository.serviceCatalog() }.orEmpty() }
    // Le retour revient à l'étape d'avant tant que la demande n'est pas partie.
    BackHandler(enabled = step > 1 && !sent && !busy) { step -= 1 }
    if (sent) {
        FlowScaffold(app.t("becomeProvider"), onBack = { flow.restart(null) }, bottom = {
            PrimaryButton(app.t("back"), { flow.restart(null) })
        }) {
            Column(
                Modifier.fillMaxWidth().padding(top = 30.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Box(Modifier.size(96.dp).background(pick(0xFFE3F5EA, 0xFF12301F), CircleShape), contentAlignment = Alignment.Center) {
                    Icon(Icons.Rounded.CheckCircle, contentDescription = null, tint = Nexis.ok, modifier = Modifier.size(42.dp))
                }
                Text(app.t("becomeSentTitle"), style = title(21, color = p.ink), modifier = Modifier.padding(top = 12.dp))
                Text(app.t("becomeSentText"), style = body(15, color = p.muted), textAlign = TextAlign.Center)
            }
        }
        return
    }
    val ready = when (step) {
        1 -> services.isNotEmpty()
        2 -> true
        3 -> communes.isNotEmpty()
        4 -> identity.capture != null
        else -> accepted
    }
    FlowScaffold(
        app.t("becomeProvider"), onBack = { if (step > 1) step -= 1 else flow.back() },
        bottom = {
            val label = when {
                step == BECOME_STEPS -> "becomeSend"
                step == 2 && works.isEmpty -> "worksSkip"
                else -> "nextStep"
            }
            PrimaryButton(app.t(label), {
                if (step < BECOME_STEPS) {
                    step += 1
                } else {
                    val capture = identity.capture ?: return@PrimaryButton
                    busy = true
                    failed = false
                    scope.launch {
                        try {
                            val chosen = catalog.map { it.id }.filter { it in services }
                            app.repository.applyAsProvider(
                                chosen, communes.sorted(), capture, works.portfolio(chosen),
                                if (accepted) app.repository.providerTermsVersion else null,
                            )
                            app.dataChanged()
                            sent = true
                        } catch (cancel: CancellationException) {
                            throw cancel
                        } catch (_: Exception) {
                            failed = true
                        } finally {
                            busy = false
                        }
                    }
                }
            }, enabled = ready, loading = busy)
        },
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(app.t("becomeStep", "step" to step.toString(), "total" to BECOME_STEPS.toString()), style = body(13, FontWeight.SemiBold, p.accent))
            LinearProgressIndicator(
                progress = { step / BECOME_STEPS.toFloat() }, color = Nexis.brand, trackColor = p.soft,
                modifier = Modifier.fillMaxWidth().clearAndSetSemantics { },
            )
        }
        when (step) {
            1 -> {
                Text(app.t("becomeIntro"), style = body(15, color = p.muted))
                StepHeading(app.t("becomeServices"), app.t("becomeServicesHint"))
                catalog.forEach { item ->
                    CheckRow(item.label(app.language), item.id in services, { ServiceTile(item, 38.dp) }) {
                        services = if (item.id in services) services - item.id else services + item.id
                    }
                }
            }
            2 -> {
                StepHeading(app.t("becomeWorks"), app.t("becomeWorksHint"))
                PortfolioEditor(catalog.filter { it.id in services }, works) { works = it }
                InfoNote(app.t("worksDemoNote"), NoteKind.VIOLET)
            }
            3 -> {
                StepHeading(app.t("becomeCommunes"), app.t("becomeCommunesHint"))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    app.repository.communes.forEach { commune ->
                        ToggleChip(commune, commune in communes) {
                            communes = if (commune in communes) communes - commune else communes + commune
                        }
                    }
                }
            }
            4 -> {
                StepHeading(app.t("becomeIdentity"), null)
                IdentityStep(identity) { identity = it }
            }
            else -> {
                StepHeading(app.t("legalProviderTerms"), null)
                Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(app.t("termsVersion", "date" to app.longDate(app.repository.providerTermsVersion)), style = body(13, color = p.muted))
                    TextButton(onClick = { readingTerms = true }) {
                        Text(app.t("becomeReadTerms"), style = body(15, FontWeight.SemiBold, p.accent))
                    }
                    HorizontalDivider(color = p.line)
                    Row(
                        Modifier.fillMaxWidth().toggleable(accepted, enabled = !busy, role = Role.Checkbox) { accepted = it },
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(checked = accepted, onCheckedChange = null, colors = CheckboxDefaults.colors(checkedColor = Nexis.brand))
                        Text(app.t("becomeAcceptTerms"), style = body(15, color = p.ink), modifier = Modifier.padding(start = 10.dp))
                    }
                }
            }
        }
        if (failed) Text(app.t("becomeFailed"), style = body(14, color = Nexis.danger))
    }
    if (readingTerms) LegalReader(LegalDocumentKey.PROVIDER_TERMS) { readingTerms = false }
}

@Composable
private fun StepHeading(text: String, hint: String?) {
    val p = LocalPalette.current
    Column(Modifier.padding(top = 4.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(text, style = title(19, color = p.ink), modifier = Modifier.semantics { heading() })
        if (hint != null) Text(hint, style = body(14, color = p.muted))
    }
}

/** Ligne à cocher (plusieurs choix possibles). */
@Composable
private fun CheckRow(text: String, selected: Boolean, leading: @Composable () -> Unit, onToggle: () -> Unit) {
    val p = LocalPalette.current
    val shape = RoundedCornerShape(16.dp)
    Row(
        Modifier.fillMaxWidth().clip(shape).background(p.surface, shape)
            .border(if (selected) 2.dp else 0.5.dp, if (selected) Nexis.brand else p.line, shape)
            .toggleable(selected, role = Role.Checkbox) { onToggle() }
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        leading()
        Text(text, style = body(15, if (selected) FontWeight.SemiBold else FontWeight.Medium, p.ink), modifier = Modifier.weight(1f).padding(horizontal = 12.dp))
        Checkbox(checked = selected, onCheckedChange = null, colors = CheckboxDefaults.colors(checkedColor = Nexis.brand))
    }
}

/** Puce à cocher (communes). */
@Composable
private fun ToggleChip(label: String, selected: Boolean, onToggle: () -> Unit) {
    val p = LocalPalette.current
    Row(
        Modifier.clip(CircleShape).background(if (selected) p.soft else p.surface, CircleShape)
            .border(if (selected) 1.5.dp else 1.dp, if (selected) Nexis.brand else p.line, CircleShape)
            .toggleable(selected, role = Role.Checkbox) { onToggle() }
            .padding(horizontal = 13.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        if (selected) Icon(Icons.Rounded.Check, contentDescription = null, tint = p.accent, modifier = Modifier.size(14.dp))
        Text(label, style = body(14, FontWeight.SemiBold, if (selected) p.accent else p.ink))
    }
}
