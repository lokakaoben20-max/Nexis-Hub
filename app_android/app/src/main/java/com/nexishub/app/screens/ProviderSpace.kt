package com.nexishub.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Chat
import androidx.compose.material.icons.rounded.ArrowDropDown
import androidx.compose.material.icons.rounded.CalendarToday
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.NearMe
import androidx.compose.material.icons.rounded.Phone
import androidx.compose.material.icons.rounded.Place
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SelectableDates
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.TimePicker
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nexishub.app.AppModel
import com.nexishub.app.LocalApp
import com.nexishub.app.data.Currency
import com.nexishub.app.data.Money
import com.nexishub.app.data.PaymentState
import com.nexishub.app.data.PresenceResult
import com.nexishub.app.data.Profile
import com.nexishub.app.data.ProviderHome
import com.nexishub.app.data.ProviderJob
import com.nexishub.app.data.ProviderRequest
import com.nexishub.app.data.ProviderStep
import com.nexishub.app.ui.FlowLoading
import com.nexishub.app.ui.FlowScaffold
import com.nexishub.app.ui.InfoNote
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.NoteKind
import com.nexishub.app.ui.OutlineButton
import com.nexishub.app.ui.PaymentPill
import com.nexishub.app.ui.PersonHeader
import com.nexishub.app.ui.PhotoSlot
import com.nexishub.app.ui.Pill
import com.nexishub.app.ui.PillTone
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.RoundIconButton
import com.nexishub.app.ui.SectionTitle
import com.nexishub.app.ui.ServiceTile
import com.nexishub.app.ui.StepItem
import com.nexishub.app.ui.StepList
import com.nexishub.app.ui.StepState
import com.nexishub.app.ui.body
import com.nexishub.app.ui.clock
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.pick
import com.nexishub.app.ui.slot
import com.nexishub.app.ui.title
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZoneOffset

// Espace prestataire, repris des écrans Flutter
// (app_mobile/lib/screens/provider) : accueil « En service », demandes,
// envoi d'un devis et déroulé d'une mission payée.

// Prix tapé

object PriceInput {
    private val francs = Regex("^\\d{1,9}$")
    private val dollars = Regex("^(\\d{1,7})(?:\\.(\\d{1,2}))?$")

    /** Lit le prix tapé : des francs entiers, ou des dollars avec au plus
     * deux décimales. Rien de lisible ou zéro : pas de prix. Même règle que
     * l'app Flutter (`parsePrice`) ; le serveur revérifie. */
    fun parse(text: String, currency: Currency): Money? {
        val clean = text.filterNot { it.isWhitespace() }.replace(',', '.')
        if (clean.isEmpty()) return null
        return when (currency) {
            Currency.CDF -> {
                if (!francs.matches(clean)) return null
                val value = clean.toLong()
                if (value > 0) Money(value, Currency.CDF) else null
            }
            Currency.USD -> {
                val match = dollars.matchEntire(clean) ?: return null
                val cents = match.groupValues[1].toLong() * 100 + match.groupValues[2].padEnd(2, '0').toLong()
                if (cents > 0) Money(cents, Currency.USD) else null
            }
        }
    }

    /** Ce que le champ garde pendant la frappe : les francs groupés par
     * milliers (« 25 000 »), les dollars avec leur virgule. */
    fun typed(text: String, currency: Currency): String = when (currency) {
        Currency.CDF -> {
            val digits = text.filter { it in '0'..'9' }.take(9)
            buildString {
                digits.forEachIndexed { index, digit ->
                    if (index > 0 && (digits.length - index) % 3 == 0) append(' ')
                    append(digit)
                }
            }
        }
        Currency.USD -> text.filter { it in '0'..'9' || it == '.' || it == ',' }.take(10)
    }
}

// Client / Prestataire

/** Passe de l'espace client à l'espace prestataire (même compte). */
@Composable
fun SpaceSwitch() {
    val app = LocalApp.current
    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
        listOf(false to app.t("spaceClient"), true to app.t("spaceProvider")).forEachIndexed { index, (value, label) ->
            SegmentedButton(
                selected = app.providerSpace == value,
                onClick = { app.providerSpace = value },
                shape = SegmentedButtonDefaults.itemShape(index, 2),
                label = { Text(label, style = body(14, FontWeight.SemiBold)) },
            )
        }
    }
}

/** « Limete et Gombe », « Limete, Gombe et Ngaliema ». */
fun AppModel.communesList(communes: List<String>): String = when (communes.size) {
    0 -> ""
    1 -> communes.first()
    else -> t("andList", "head" to communes.dropLast(1).joinToString(", "), "last" to communes.last())
}

fun AppModel.requestAge(at: Instant): String {
    val minutes = Duration.between(at, Instant.now()).toMinutes().coerceAtLeast(0)
    return if (minutes < 60) t("minutesAgo", "count" to minutes.toString()) else t("hoursAgo", "count" to (minutes / 60).toString())
}

fun AppModel.jobStatus(job: ProviderJob): String {
    val name = job.clientFirstName
    return when {
        ProviderStep.FINISHED in job.steps -> t("jobWaitingClient", "name" to name)
        ProviderStep.ARRIVED in job.steps -> t("jobOnSite")
        job.arrivalSignaled -> t("jobArrivalPending", "name" to name)
        ProviderStep.LEFT_HOME in job.steps -> t("jobOnTheWay")
        else -> t("jobToStart")
    }
}

// 11. Accueil prestataire

@Composable
fun ProviderHomeTab(onTab: (Int) -> Unit) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var home by remember { mutableStateOf<ProviderHome?>(null) }
    var profile by remember { mutableStateOf<Profile?>(null) }
    var saving by remember { mutableStateOf(false) }
    LaunchedEffect(app.revision) {
        home = attempt { app.repository.providerHome() }
        profile = attempt { app.repository.profile() }
    }
    val greeting = profile?.let {
        app.t(if (LocalTime.now().hour < 12) "helloHome" else "eveningHome", "name" to it.firstName)
    } ?: "NexisHub"
    TabScaffold(greeting) { padding ->
        val shown = home
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item { SpaceSwitch() }
            if (shown == null) return@LazyColumn
            item {
                Row(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(9.dp).background(if (shown.inService) Nexis.ok else Color(0xFFC9D0DB), CircleShape))
                    Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                        Text(app.t(if (shown.inService) "inService" else "offService"), style = body(15, FontWeight.Bold, p.ink))
                        Text(
                            if (shown.inService) app.t("inServiceSub", "communes" to app.communesList(shown.communes)) else app.t("offServiceSub"),
                            style = body(13, color = p.muted),
                        )
                    }
                    Switch(
                        checked = shown.inService,
                        enabled = !saving,
                        onCheckedChange = { value ->
                            saving = true
                            scope.launch {
                                try {
                                    app.repository.setInService(value)
                                    app.dataChanged()
                                } catch (cancel: CancellationException) {
                                    throw cancel
                                } catch (_: Exception) {
                                    flow.say(app.t("actionFailed"))
                                } finally {
                                    saving = false
                                }
                            }
                        },
                        colors = SwitchDefaults.colors(checkedTrackColor = Nexis.ok),
                        modifier = Modifier.semantics { contentDescription = app.t("inService") },
                    )
                }
            }
            item { ProviderMoneyCard(shown) }
            item {
                Row(Modifier.fillMaxWidth().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(app.t("newRequests"), style = title(17, color = p.ink), modifier = Modifier.weight(1f))
                    TextButton(onClick = { onTab(1) }) { Text(app.t("seeAll"), style = body(14, FontWeight.SemiBold, p.accent)) }
                }
            }
            when {
                !shown.inService -> item { InfoNote(app.t("offServiceHint")) }
                shown.requests.isEmpty() -> item { EmptyLine(app.t("noRequests")) }
                else -> items(shown.requests, key = { "r${it.missionId}" }) { RequestCard(it) }
            }
            if (shown.jobs.isNotEmpty()) {
                item { Text(app.t("jobsInProgress"), style = title(17, color = p.ink), modifier = Modifier.padding(top = 6.dp)) }
                items(shown.jobs, key = { "j${it.missionId}" }) { JobCard(it) }
            }
        }
    }
}

@Composable
private fun ProviderMoneyCard(home: ProviderHome) {
    val app = LocalApp.current
    val shape = RoundedCornerShape(24.dp)
    Column(
        Modifier.fillMaxWidth().background(
            androidx.compose.ui.graphics.Brush.linearGradient(
                0f to Nexis.halo, 0.45f to Nexis.gradientStart, 1f to Nexis.gradientEnd,
            ),
            shape,
        ).padding(18.dp).semantics(mergeDescendants = true) { },
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(
            "${app.t("available")} · ${if (home.available.currency == Currency.CDF) "FC" else "USD"}",
            style = body(13, color = Color.White.copy(alpha = 0.85f)),
        )
        Text(if (app.amountsHidden) "•••" else app.money(home.available), style = title(28, color = Color.White), maxLines = 1)
        Row(Modifier.padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Rounded.VerifiedUser, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(8.dp))
            Text(
                app.t("securedUntilConfirm", "amount" to (if (app.amountsHidden) "•••" else app.money(home.secured))),
                style = body(13, color = Color.White),
            )
        }
    }
}

@Composable
private fun EmptyLine(text: String) {
    val p = LocalPalette.current
    Text(text, style = body(15, color = p.muted), textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(16.dp))
}

// Missions côté prestataire

@Composable
fun ProviderMissionsTab() {
    val app = LocalApp.current
    val p = LocalPalette.current
    var home by remember { mutableStateOf<ProviderHome?>(null) }
    LaunchedEffect(app.revision) { home = attempt { app.repository.providerHome() } }
    TabScaffold(app.t("myMissions")) { padding ->
        val shown = home
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            if (shown == null) return@LazyColumn
            item { Text(app.t("jobsInProgress"), style = title(17, color = p.ink)) }
            if (shown.jobs.isEmpty()) item { EmptyLine(app.t("noMissions")) }
            items(shown.jobs, key = { "j${it.missionId}" }) { JobCard(it) }
            item { Text(app.t("newRequests"), style = title(17, color = p.ink), modifier = Modifier.padding(top = 6.dp)) }
            if (shown.requests.isEmpty()) item { EmptyLine(app.t("noRequests")) }
            items(shown.requests, key = { "r${it.missionId}" }) { RequestCard(it) }
        }
    }
}

// Cartes

/** Une demande de client : « Nouveau » et le bouton « Envoyer un devis » les
 * dix premières minutes, l'âge ensuite. */
@Composable
private fun RequestCard(request: ProviderRequest) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val fresh = Duration.between(request.receivedAt, Instant.now()).toMinutes() < 10 && !request.quoted
    Column(
        Modifier.fillMaxWidth().nexisCard(p)
            .clickable(enabled = !request.quoted, role = Role.Button) { flow.push(MissionRoute.SendQuote(request.missionId)) }
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ServiceTile(request.service, 44.dp)
            Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                Text(
                    "${request.service.label(app.language)} · ${request.commune}",
                    style = body(15, FontWeight.Bold, p.ink), maxLines = 1, overflow = TextOverflow.Ellipsis,
                )
                Text(request.summary, style = body(13, color = p.muted), maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            when {
                request.quoted -> Pill(PillTone.OK, app.t("quoteSentPill"), Icons.Rounded.Check)
                fresh -> Text(
                    app.t("newPill"),
                    style = body(11, FontWeight.Bold, Nexis.ok),
                    modifier = Modifier.background(pick(0xFFE3F5EA, 0xFF16351F), CircleShape).padding(horizontal = 8.dp, vertical = 3.dp),
                )
                else -> Pill(PillTone.WAIT, app.requestAge(request.receivedAt), Icons.Rounded.Schedule)
            }
        }
        if (fresh) PrimaryButton(app.t("sendAQuote"), { flow.push(MissionRoute.SendQuote(request.missionId)) })
    }
}

/** Une mission payée, côté prestataire : où elle en est. */
@Composable
private fun JobCard(job: ProviderJob) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    Row(
        Modifier.fillMaxWidth().nexisCard(p).clickable(role = Role.Button) { flow.push(MissionRoute.Job(job.missionId)) }.padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        ServiceTile(job.service, 44.dp)
        Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
            Text(
                "${job.service.label(app.language)} · ${job.commune}",
                style = body(15, FontWeight.Bold, p.ink), maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            Text(app.jobStatus(job), style = body(13, color = p.muted), maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        PaymentPill(PaymentState.SECURED, app.money(job.amount))
    }
}

// 12. Envoyer un devis

@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
fun SendQuoteScreen(missionId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var request by remember { mutableStateOf<ProviderRequest?>(null) }
    var price by remember { mutableStateOf("") }
    var currency by remember { mutableStateOf(Currency.CDF) }
    var currencyMenu by remember { mutableStateOf(false) }
    var slot by remember { mutableStateOf<Instant?>(null) }
    var custom by remember { mutableStateOf<Instant?>(null) }
    var pickingDay by remember { mutableStateOf(false) }
    var pickedDay by remember { mutableStateOf<LocalDate?>(null) }
    var busy by remember { mutableStateOf(false) }
    LaunchedEffect(app.revision) { if (!busy) request = attempt { app.repository.providerRequest(missionId) } }
    val shown = request ?: return FlowLoading(app.t("sendAQuote"))
    val parsed = PriceInput.parse(price, currency)
    val ready = parsed != null && slot != null && !shown.quoted
    val slots = shown.slotChoices + listOfNotNull(custom)
    FlowScaffold(
        app.t("sendAQuote"), onBack = flow::back, subtitle = "${shown.service.label(app.language)} · ${shown.commune}",
        bottom = {
            PrimaryButton(app.t("sendTheQuote"), {
                val money = parsed ?: return@PrimaryButton
                val chosen = slot ?: return@PrimaryButton
                busy = true
                scope.launch {
                    try {
                        app.repository.sendQuote(missionId, money, chosen)
                        app.dataChanged()
                        flow.back()
                        flow.say(app.t("quoteSentToast"))
                    } catch (cancel: CancellationException) {
                        throw cancel
                    } catch (_: Exception) {
                        busy = false
                        flow.say(app.t("quoteFailed"))
                    }
                }
            }, enabled = ready, loading = busy)
        },
    ) {
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(shown.description, style = body(15, color = p.ink))
            if (shown.photos > 0) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    repeat(minOf(shown.photos, 3)) {
                        PhotoSlot(Icons.Rounded.Image, app.plural("photosCount", shown.photos)) {
                            flow.comingSoon = app.plural("photosCount", shown.photos)
                        }
                    }
                }
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill(PillTone.WAIT, shown.wanted, Icons.Rounded.CalendarToday)
                Pill(PillTone.WAIT, shown.commune, Icons.Rounded.Place)
            }
        }
        SectionTitle(app.t("yourPrice"))
        OutlinedTextField(
            value = price,
            onValueChange = { price = PriceInput.typed(it, currency) },
            enabled = !busy,
            label = { Text(app.t("priceAsked")) },
            placeholder = { Text("0", style = title(22, color = p.muted)) },
            textStyle = title(22, color = p.ink),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = if (currency == Currency.CDF) KeyboardType.Number else KeyboardType.Decimal),
            trailingIcon = {
                Box {
                    TextButton(onClick = { currencyMenu = true }, enabled = !busy) {
                        Text(if (currency == Currency.CDF) "FC" else "USD", style = body(15, FontWeight.SemiBold, p.muted))
                        Icon(Icons.Rounded.ArrowDropDown, contentDescription = app.t("changeCurrency"), tint = p.muted)
                    }
                    DropdownMenu(expanded = currencyMenu, onDismissRequest = { currencyMenu = false }) {
                        for ((value, label) in listOf(Currency.CDF to "FC", Currency.USD to "USD")) {
                            DropdownMenuItem(text = { Text(label) }, onClick = {
                                if (value != currency) price = ""
                                currency = value
                                currencyMenu = false
                            })
                        }
                    }
                }
            },
            shape = RoundedCornerShape(16.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Nexis.brand, unfocusedBorderColor = p.line,
                focusedContainerColor = p.surface, unfocusedContainerColor = p.surface,
            ),
            modifier = Modifier.fillMaxWidth(),
        )
        SectionTitle(app.t("yourSlot"))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            slots.forEach { choice ->
                SlotChip(app.slot(choice, capital = true), selected = slot == choice, enabled = !busy) { slot = choice }
            }
            SlotChip(app.t("otherSlot"), selected = false, enabled = !busy) { pickingDay = true }
        }
    }
    if (pickingDay) {
        val today = LocalDate.now()
        val dayState = rememberDatePickerState(
            selectableDates = object : SelectableDates {
                override fun isSelectableDate(utcTimeMillis: Long): Boolean {
                    val day = Instant.ofEpochMilli(utcTimeMillis).atZone(ZoneOffset.UTC).toLocalDate()
                    return !day.isBefore(today) && !day.isAfter(today.plusDays(60))
                }
            },
        )
        DatePickerDialog(
            onDismissRequest = { pickingDay = false },
            confirmButton = {
                TextButton(onClick = {
                    pickedDay = dayState.selectedDateMillis?.let { Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate() }
                    pickingDay = false
                }) { Text(app.t("confirmCode")) }
            },
            dismissButton = { TextButton(onClick = { pickingDay = false }) { Text(app.t("close")) } },
        ) { DatePicker(dayState) }
    }
    pickedDay?.let { day ->
        val timeState = rememberTimePickerState(initialHour = 9, initialMinute = 0, is24Hour = app.language != "en")
        AlertDialog(
            onDismissRequest = { pickedDay = null },
            title = { Text(app.t("yourSlot")) },
            text = { TimePicker(timeState) },
            confirmButton = {
                TextButton(onClick = {
                    val chosen = day.atTime(timeState.hour, timeState.minute).atZone(ZoneId.systemDefault()).toInstant()
                    if (chosen.isAfter(Instant.now())) {
                        custom = chosen
                        slot = chosen
                    }
                    pickedDay = null
                }) { Text(app.t("confirmCode")) }
            },
            dismissButton = { TextButton(onClick = { pickedDay = null }) { Text(app.t("close")) } },
        )
    }
}

@Composable
private fun SlotChip(label: String, selected: Boolean, enabled: Boolean, onClick: () -> Unit) {
    val p = LocalPalette.current
    val shape = RoundedCornerShape(12.dp)
    Text(
        label,
        style = body(14, FontWeight.SemiBold, if (selected) p.accent else p.ink),
        modifier = Modifier.clip(shape).background(if (selected) p.soft else p.surface, shape)
            .border(if (selected) 1.5.dp else 1.dp, if (selected) Nexis.brand else p.line, shape)
            .clickable(enabled = enabled, role = Role.RadioButton, onClick = onClick)
            .padding(horizontal = 13.dp, vertical = 9.dp),
    )
}

// 13. Mission côté prestataire

/** L'arrivée suit la règle du serveur : « Je suis arrivé » ne confirme rien
 * seul. Le client confirme sur son téléphone, ou le prestataire tape son
 * code de présence (cinq essais au plus). */
@Composable
fun ProviderJobScreen(missionId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var job by remember { mutableStateOf<ProviderJob?>(null) }
    var busy by remember { mutableStateOf(false) }
    var code by remember { mutableStateOf("") }
    var codeError by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(app.revision) { job = attempt { app.repository.providerJob(missionId) } }
    val shown = job ?: return FlowLoading(app.t("jobTitle"))
    fun perform(action: suspend () -> Unit) {
        busy = true
        scope.launch {
            try {
                action()
                app.dataChanged()
            } catch (cancel: CancellationException) {
                throw cancel
            } catch (_: Exception) {
                flow.say(app.t("actionFailed"))
            } finally {
                busy = false
            }
        }
    }
    val name = shown.clientFirstName
    val steps = shown.steps
    val arrived = ProviderStep.ARRIVED in steps
    val finished = ProviderStep.FINISHED in steps
    val waitingArrival = shown.arrivalSignaled && !arrived
    val current = ProviderStep.entries.firstOrNull { it !in steps } ?: ProviderStep.FINISHED
    fun item(heading: String, step: ProviderStep, sub: String? = null) = StepItem(
        heading, sub, steps[step]?.let { app.clock(it) },
        when {
            step in steps -> StepState.DONE
            step == current -> StepState.NOW
            else -> StepState.TODO
        },
    )
    val repo = app.repository
    FlowScaffold(
        app.t("jobTitle"), onBack = flow::back, subtitle = "${shown.service.label(app.language)} · ${shown.commune}",
        bottom = {
            when {
                finished || waitingArrival -> Unit
                arrived -> PrimaryButton(app.t("btnFinished"), { perform { repo.finishJob(missionId) } }, icon = Icons.Rounded.Check, loading = busy)
                ProviderStep.LEFT_HOME in steps ->
                    PrimaryButton(app.t("btnArrived"), { perform { repo.signalArrival(missionId) } }, icon = Icons.Rounded.Place, loading = busy)
                else -> PrimaryButton(app.t("btnLeave"), { perform { repo.leaveForJob(missionId) } }, icon = Icons.Rounded.NearMe, loading = busy)
            }
            OutlineButton(app.t("callClient", "name" to name), { flow.comingSoon = app.t("callClient", "name" to name) }, icon = Icons.Rounded.Phone)
        },
    ) {
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            PersonHeader(shown.clientInitials, shown.clientColor, shown.clientName, subtitle = shown.place) {
                RoundIconButton(Icons.AutoMirrored.Rounded.Chat, app.t("messageLabel")) { flow.comingSoon = app.t("messageLabel") }
            }
            PaymentPill(PaymentState.SECURED, app.t("securedAmount", "amount" to app.money(shown.amount)))
        }
        if (!finished) {
            Row(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(38.dp).background(p.soft, CircleShape), contentAlignment = Alignment.Center) {
                    Icon(Icons.Rounded.NearMe, contentDescription = null, tint = p.softInk, modifier = Modifier.size(17.dp))
                }
                Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                    Text(app.t("shareLocation"), style = body(15, FontWeight.Bold, p.ink))
                    Text(app.t("shareLocationSub", "name" to name), style = body(13, color = p.muted))
                }
                Switch(
                    checked = shown.sharing,
                    enabled = !busy,
                    onCheckedChange = { value -> perform { repo.setSharing(missionId, value) } },
                    colors = SwitchDefaults.colors(checkedTrackColor = Nexis.ok),
                    modifier = Modifier.semantics { contentDescription = app.t("shareLocation") },
                )
            }
        }
        Box(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp)) {
            StepList(
                listOf(
                    item(app.t("pStepPaid"), ProviderStep.CLIENT_PAID),
                    item(app.t("pStepLeft"), ProviderStep.LEFT_HOME),
                    item(
                        app.t(if (arrived) "pStepOnSite" else "pStepArrive"), ProviderStep.ARRIVED,
                        when {
                            arrived -> app.t("arrivalConfirmed")
                            waitingArrival -> app.t("arrivalWaitingSub", "name" to name)
                            else -> null
                        },
                    ),
                    item(app.t("pStepDone"), ProviderStep.FINISHED),
                ),
            )
        }
        if (waitingArrival) {
            InfoNote(app.t("arrivalWaiting", "name" to name))
            if (shown.codeAttemptsLeft > 0) {
                Column(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(app.t("presenceCode"), style = body(15, FontWeight.SemiBold, p.ink))
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedTextField(
                            value = code,
                            onValueChange = { code = it.filter { c -> c in '0'..'9' }.take(4) },
                            enabled = !busy,
                            singleLine = true,
                            placeholder = { Text("••••", style = title(22, color = p.muted)) },
                            textStyle = title(22, color = p.ink).copy(letterSpacing = 8.sp),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.weight(1f).semantics { contentDescription = app.t("presenceCode") },
                        )
                        PrimaryButton(
                            app.t("confirmCode"),
                            {
                                val entered = code
                                perform {
                                    val result = repo.enterPresenceCode(missionId, entered)
                                    val after = repo.providerJob(missionId)
                                    code = ""
                                    codeError = when (result) {
                                        PresenceResult.CONFIRMED -> null
                                        PresenceResult.WRONG_CODE -> app.plural("wrongCode", after.codeAttemptsLeft)
                                        PresenceResult.LOCKED -> app.t("codeLocked", "name" to name)
                                    }
                                }
                            },
                            Modifier.width(130.dp),
                            enabled = code.length == 4,
                            loading = busy,
                        )
                    }
                    codeError?.let { Text(it, style = body(13, FontWeight.SemiBold, Nexis.danger)) }
                }
            } else {
                InfoNote(app.t("codeLocked", "name" to name), NoteKind.DANGER, Icons.Rounded.Lock)
            }
        }
        if (finished) InfoNote(app.t("finishedNote", "name" to name), NoteKind.VIOLET)
    }
}
