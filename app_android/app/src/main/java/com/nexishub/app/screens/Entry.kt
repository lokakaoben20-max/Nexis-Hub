package com.nexishub.app.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.Chat
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Language
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.Sms
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LargeTopAppBar
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nexishub.app.Capture
import com.nexishub.app.LocalApp
import com.nexishub.app.R
import com.nexishub.app.data.CodeChannel
import com.nexishub.app.data.DrcPhone
import com.nexishub.app.data.Service
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.ServiceTile
import com.nexishub.app.ui.body
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.title
import java.time.format.DateTimeFormatter

/** Étapes du parcours d'entrée. */
sealed interface EntryStep {
    data class Phone(val login: Boolean) : EntryStep
    data class Code(val phone: String, val channel: CodeChannel, val login: Boolean) : EntryStep
    data class Signup(val phone: String) : EntryStep
}

@Composable
fun EntryFlow(start: Capture?) {
    val stack = remember {
        mutableStateListOf<EntryStep>().apply {
            when (start) {
                Capture.PHONE -> add(EntryStep.Phone(login = false))
                Capture.SIGNUP -> add(EntryStep.Signup("+243991112222"))
                else -> Unit
            }
        }
    }
    BackHandler(enabled = stack.isNotEmpty()) { stack.removeAt(stack.lastIndex) }
    val back: () -> Unit = { stack.removeAt(stack.lastIndex) }
    when (val step = stack.lastOrNull()) {
        null -> WelcomeScreen(onStart = { stack.add(EntryStep.Phone(login = false)) }, onLogin = { stack.add(EntryStep.Phone(login = true)) })
        is EntryStep.Phone -> PhoneScreen(step.login, back) { phone, channel -> stack.add(EntryStep.Code(phone, channel, step.login)) }
        is EntryStep.Code -> CodeScreen(step, back, onSignup = { stack.add(EntryStep.Signup(step.phone)) }, onChangeNumber = back)
        is EntryStep.Signup -> SignupScreen(step.phone, back)
    }
}

// Bienvenue

@Composable
private fun WelcomeScreen(onStart: () -> Unit, onLogin: () -> Unit) {
    val app = LocalApp.current
    Box(Modifier.fillMaxSize().background(Nexis.heroGradient)) {
        Column(
            Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(horizontal = 24.dp).padding(bottom = 12.dp),
        ) {
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.End) {
                LanguageMenu(onBrand = true)
            }
            Spacer(Modifier.weight(1f))
            Image(
                painterResource(R.drawable.logo_blanc), contentDescription = "Nexis Hub",
                modifier = Modifier.height(44.dp),
            )
            Text(app.t("slogan"), style = title(30, color = Color.White), modifier = Modifier.padding(top = 28.dp))
            Text(app.t("welcomeIntro"), style = body(17, color = Color.White.copy(alpha = 0.88f)), modifier = Modifier.padding(top = 12.dp))
            VerifiedStrip(Modifier.padding(top = 28.dp))
            Spacer(Modifier.weight(1f))
            androidx.compose.material3.Button(
                onClick = onStart,
                modifier = Modifier.fillMaxWidth().height(56.dp),
                shape = CircleShape,
                colors = androidx.compose.material3.ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = Nexis.brand),
            ) { Text(app.t("start"), style = body(16, FontWeight.SemiBold)) }
            Spacer(Modifier.height(12.dp))
            OutlinedButton(
                onClick = onLogin,
                modifier = Modifier.fillMaxWidth().height(56.dp),
                shape = CircleShape,
                border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = 0.6f)),
                colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(contentColor = Color.White),
            ) { Text(app.t("haveAccount"), style = body(16, FontWeight.SemiBold)) }
        }
    }
}

@Composable
private fun VerifiedStrip(modifier: Modifier = Modifier) {
    val app = LocalApp.current
    Row(
        modifier.fillMaxWidth().semantics(mergeDescendants = true) { contentDescription = app.t("verifiedProvider") },
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        for (service in listOf(Service.PLOMBERIE, Service.ELECTRICITE, Service.NETTOYAGE)) {
            Column(
                Modifier.weight(1f)
                    .background(Color.White.copy(alpha = 0.14f), RoundedCornerShape(20.dp))
                    .border(0.5.dp, Color.White.copy(alpha = 0.3f), RoundedCornerShape(20.dp))
                    .padding(vertical = 14.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                ServiceTile(service, size = 40.dp)
                Text(service.label(app.language), style = body(12, FontWeight.SemiBold, Color.White), maxLines = 1)
                Icon(Icons.Rounded.Verified, contentDescription = null, tint = Color.White.copy(alpha = 0.9f), modifier = Modifier.size(16.dp))
            }
        }
    }
}

/** Pastille de langue : FR, LN ou EN, et un menu des trois langues. */
@Composable
fun LanguageMenu(onBrand: Boolean = false) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var open by remember { mutableStateOf(false) }
    Box {
        TextButton(onClick = { open = true }) {
            Icon(Icons.Rounded.Language, contentDescription = app.t("language"), tint = if (onBrand) Color.White else p.ink)
            Spacer(Modifier.width(6.dp))
            Text(app.language.uppercase(), style = body(14, FontWeight.SemiBold, if (onBrand) Color.White else p.ink))
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            for ((code, name) in listOf("fr" to "Français", "ln" to "Lingála", "en" to "English")) {
                DropdownMenuItem(
                    text = { Text(name, style = body(15)) },
                    onClick = { app.language = code; open = false },
                    trailingIcon = { if (code == app.language) Icon(Icons.Rounded.CheckCircle, null, tint = p.accent) },
                )
            }
        }
    }
}

/** Écran à grand titre (Unbounded) avec retour, contenu défilant et
 * bouton principal en bas. */
@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun FormScreen(
    heading: String,
    onBack: (() -> Unit)?,
    bottom: @Composable () -> Unit = {},
    content: @Composable () -> Unit,
) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val scroll = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()
    Scaffold(
        modifier = Modifier.nestedScroll(scroll.nestedScrollConnection),
        containerColor = p.bg,
        topBar = {
            LargeTopAppBar(
                title = { Text(heading, maxLines = 2) },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = app.t("back")) }
                    }
                },
                colors = TopAppBarDefaults.largeTopAppBarColors(containerColor = p.bg, scrolledContainerColor = p.bg),
                scrollBehavior = scroll,
            )
        },
        bottomBar = {
            Box(Modifier.navigationBarsPadding().imePadding().padding(horizontal = 20.dp, vertical = 8.dp)) { bottom() }
        },
    ) { padding ->
        Column(
            Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) { content() }
    }
}

// Numéro

@Composable
private fun PhoneScreen(login: Boolean, onBack: () -> Unit, onSent: (String, CodeChannel) -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val channels = app.repository.codeChannels
    var phone by rememberSaveable { mutableStateOf("") }
    var channel by remember { mutableStateOf(channels.firstOrNull()) }
    val parsed = DrcPhone.parse(phone)
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }

    FormScreen(
        heading = if (login) app.t("signInTitle") else app.t("yourNumber"),
        onBack = onBack,
        bottom = {
            PrimaryButton(app.t("receiveCode"), onClick = { channel?.let { onSent(parsed.e164, it) } }, enabled = parsed.isValid && channel != null)
        },
    ) {
        Text(app.t("yourNumberIntro"), style = body(15, color = p.muted))
        OutlinedTextField(
            value = parsed.formatted,
            onValueChange = { phone = DrcPhone.parse(it).digits },
            modifier = Modifier.fillMaxWidth().focusRequester(focus),
            label = { Text(app.t("phone")) },
            prefix = { Text("🇨🇩 +243  ", style = body(17, FontWeight.SemiBold, p.ink)) },
            placeholder = { Text("81 234 5678") },
            textStyle = body(17, FontWeight.Medium, p.ink),
            singleLine = true,
            isError = !parsed.prefixKnown,
            supportingText = { if (!parsed.prefixKnown) Text(app.t("numberNotCongolese")) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            shape = RoundedCornerShape(16.dp),
        )
        Text(app.t("receiveCodeBy"), style = body(13, FontWeight.SemiBold, p.muted))
        Column(Modifier.nexisCard(p)) {
            if (channels.isEmpty()) {
                Text(app.t("noCodeChannel"), style = body(14, color = p.muted), modifier = Modifier.padding(16.dp))
            }
            channels.forEach { item ->
                val (icon, color, name, sub) = when (item) {
                    CodeChannel.WHATSAPP -> Quad(Icons.AutoMirrored.Rounded.Chat, Color(0xFF25D366), "WhatsApp", app.t("whatsappSub"))
                    CodeChannel.TELEGRAM -> Quad(Icons.AutoMirrored.Rounded.Send, Color(0xFF229ED9), "Telegram", app.t("telegramSub"))
                    CodeChannel.SMS -> Quad(Icons.Rounded.Sms, p.muted, "SMS", app.t("smsSub"))
                }
                Row(
                    Modifier.fillMaxWidth()
                        .selectable(selected = channel == item, role = Role.RadioButton, onClick = { channel = item })
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    Box(Modifier.size(36.dp).background(color, RoundedCornerShape(10.dp)), contentAlignment = Alignment.Center) {
                        Icon(icon, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                    }
                    Column(Modifier.weight(1f)) {
                        Text(name, style = body(16, FontWeight.SemiBold, p.ink))
                        Text(sub, style = body(13, color = p.muted))
                    }
                    if (channel == item) Icon(Icons.Rounded.CheckCircle, contentDescription = null, tint = p.accent)
                }
            }
        }
    }
}

private data class Quad(val icon: ImageVector, val color: Color, val name: String, val sub: String)

// Code

@Composable
private fun CodeScreen(step: EntryStep.Code, onBack: () -> Unit, onSignup: () -> Unit, onChangeNumber: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var code by remember { mutableStateOf("") }
    var noAccount by remember { mutableStateOf(false) }
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }

    /** Démonstration : tout code à 6 chiffres est accepté. */
    fun verified() {
        when {
            app.repository.openAccount(step.phone) -> app.signIn()
            step.login -> noAccount = true
            else -> onSignup()
        }
    }

    val number = "+243 " + DrcPhone.parse(step.phone).formatted
    val sent = when (step.channel) {
        CodeChannel.SMS -> app.t("codeSentBySms", "phone" to number)
        CodeChannel.WHATSAPP -> app.t("codeSentTo", "channel" to "WhatsApp", "phone" to number)
        CodeChannel.TELEGRAM -> app.t("codeSentTo", "channel" to "Telegram", "phone" to number)
    }
    FormScreen(heading = app.t("enterCode"), onBack = onBack) {
        Text(sent, style = body(15, color = p.muted))
        OutlinedTextField(
            value = code,
            onValueChange = { value ->
                code = value.filter { it.isDigit() }.take(6)
                if (code.length == 6) verified()
            },
            modifier = Modifier.fillMaxWidth().focusRequester(focus),
            label = { Text(app.t("enterCode")) },
            textStyle = title(24, color = p.ink).copy(letterSpacing = 8.sp),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
            shape = RoundedCornerShape(16.dp),
        )
        InfoLine(Icons.Rounded.Schedule, app.t("codeHint"))
        InfoLine(Icons.Rounded.Lock, app.t("neverAskCode"))
    }
    if (noAccount) {
        AlertDialog(
            onDismissRequest = { noAccount = false },
            title = { Text(app.t("noAccountTitle")) },
            text = { Text(app.t("noAccountHint"), style = body(15)) },
            confirmButton = { TextButton(onClick = { noAccount = false; onSignup() }) { Text(app.t("signupCreateProfile")) } },
            dismissButton = { TextButton(onClick = { noAccount = false; onChangeNumber() }) { Text(app.t("changeLoginNumber")) } },
        )
    }
}

@Composable
fun InfoLine(icon: ImageVector, text: String) {
    val p = LocalPalette.current
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(icon, contentDescription = null, tint = p.muted, modifier = Modifier.size(18.dp))
        Text(text, style = body(13, color = p.muted))
    }
}

// Inscription

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SignupScreen(phone: String, onBack: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val repo = app.repository
    var firstName by rememberSaveable { mutableStateOf("") }
    var lastName by rememberSaveable { mutableStateOf("") }
    var commune by rememberSaveable { mutableStateOf<String?>(null) }
    var accepted by rememberSaveable { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    var readingTerms by remember { mutableStateOf(false) }
    val complete = firstName.isNotBlank() && lastName.isNotBlank() && commune != null && accepted
    val termsDate = repo.signupTermsVersion.format(DateTimeFormatter.ofPattern("dd/MM/yyyy", app.locale))

    FormScreen(
        heading = app.t("signupTitle"),
        onBack = onBack,
        bottom = {
            PrimaryButton(app.t("signupCreateProfile"), enabled = complete, onClick = {
                val created = repo.registerClient(phone, firstName, lastName, commune ?: "", if (accepted) repo.signupTermsVersion else null)
                if (created) app.signIn() else failed = true
            })
        },
    ) {
        Text(app.t("signupDemoNotice"), style = body(14, color = p.muted))
        OutlinedTextField(firstName, { firstName = it; failed = false }, Modifier.fillMaxWidth(),
            label = { Text(app.t("signupFirstName")) }, singleLine = true, shape = RoundedCornerShape(16.dp), textStyle = body(16, color = p.ink))
        OutlinedTextField(lastName, { lastName = it; failed = false }, Modifier.fillMaxWidth(),
            label = { Text(app.t("signupLastName")) }, singleLine = true, shape = RoundedCornerShape(16.dp), textStyle = body(16, color = p.ink))
        CommuneField(commune, repo.communes) { commune = it; failed = false }
        Column(Modifier.nexisCard(p).padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(app.t("legalTerms"), style = title(15, color = p.ink))
            Text(app.t("termsVersion", "date" to termsDate), style = body(13, color = p.muted))
            TextButton(onClick = { readingTerms = true }) { Text(app.t("signupReadTerms"), style = body(15, FontWeight.SemiBold)) }
            Row(
                Modifier.fillMaxWidth().clickable(role = Role.Checkbox) { accepted = !accepted },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Checkbox(checked = accepted, onCheckedChange = null)
                Spacer(Modifier.width(8.dp))
                Text(app.t("signupAcceptTerms"), style = body(15, color = p.ink))
            }
        }
        if (failed) Text(app.t("signupFailed"), style = body(14, color = Nexis.danger))
    }
    if (readingTerms) {
        ModalBottomSheet(onDismissRequest = { readingTerms = false }, containerColor = p.surface) {
            Column(Modifier.padding(horizontal = 24.dp).padding(bottom = 32.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(app.t("legalTerms"), style = title(20, color = p.ink))
                Text(app.t("termsVersion", "date" to termsDate), style = body(13, color = p.muted))
                Text(app.t("signupDemoTerms"), style = body(16, color = p.ink))
            }
        }
    }
}

/** Choix de la commune parmi les 24 communes de Kinshasa. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CommuneField(value: String?, communes: List<String>, onPick: (String) -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var open by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }) {
        OutlinedTextField(
            value = value ?: "",
            onValueChange = {},
            readOnly = true,
            label = { Text(app.t("commune")) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = open) },
            modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable),
            shape = RoundedCornerShape(16.dp),
            textStyle = body(16, color = p.ink),
        )
        ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            communes.forEach { item ->
                DropdownMenuItem(text = { Text(item, style = body(15)) }, onClick = { onPick(item); open = false })
            }
        }
    }
}
