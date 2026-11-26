package com.nexishub.app.screens

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.StartOffset
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.offset
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.heading
import com.nexishub.app.ui.NexisPalette
import com.nexishub.app.ui.Pictogrammes
import com.nexishub.app.ui.rememberReduceMotion
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.Description
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.TopAppBar
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.text.input.KeyboardCapitalization
import com.nexishub.app.ui.pick
import kotlinx.coroutines.delay
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
import androidx.compose.runtime.rememberCoroutineScope
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
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.ServiceTile
import com.nexishub.app.ui.body
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.title
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

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
                Capture.CODE -> {
                    add(EntryStep.Phone(login = false))
                    add(EntryStep.Code("+243991112222", CodeChannel.WHATSAPP, login = false))
                }
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
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(bottom = 12.dp)) {
            Row(
                Modifier.fillMaxWidth().padding(start = 20.dp, end = 8.dp, top = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Image(
                    painterResource(R.drawable.logo_blanc), contentDescription = "Nexis Hub",
                    modifier = Modifier.height(17.dp).semantics { heading() },
                )
                Spacer(Modifier.weight(1f))
                LanguageMenu(onBrand = true)
            }
            Constellation(Modifier.weight(1f).fillMaxWidth().padding(vertical = 12.dp))
            Column(Modifier.padding(horizontal = 24.dp)) {
                Text(app.t("slogan"), style = title(28, color = Color.White))
                Text(app.t("welcomeIntro"), style = body(16, color = Color.White.copy(alpha = 0.9f)), modifier = Modifier.padding(top = 12.dp))
                Spacer(Modifier.height(32.dp))
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
                    colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(
                        containerColor = Color.White.copy(alpha = 0.14f), contentColor = Color.White,
                    ),
                ) { Text(app.t("haveAccount"), style = body(16, FontWeight.SemiBold)) }
            }
        }
    }
}

/** Un carré de la Constellation, aux mesures de la maquette (écran de 390 de large). */
private data class Spot(val service: String, val x: Float, val y: Float, val size: Float, val angle: Float, val periodMs: Int)

private val SPOTS = listOf(
    Spot("plomberie", 30f, 30f, 74f, -6f, 7_000),
    Spot("climatisation", 150f, 6f, 58f, 4f, 6_200),
    Spot("coiffure", 262f, 42f, 82f, 7f, 7_800),
    Spot("electricite", 84f, 146f, 60f, 5f, 6_600),
    Spot("nettoyage", 186f, 120f, 86f, -4f, 7_400),
    Spot("demenagement", 296f, 172f, 58f, -7f, 6_000),
    Spot("informatique", 24f, 240f, 56f, 3f, 7_200),
    Spot("peinture", 122f, 248f, 66f, -3f, 6_800),
)
private const val DESIGN_WIDTH = 390f
private const val DESIGN_HEIGHT = 320f

/** Bienvenue « Constellation » (maquette A1 choisie par Ben le 2026-11-25) :
 * des carrés de services blancs, penchés, qui flottent lentement. À
 * l'ouverture de l'app, chacun fait une fois le tour de ses objets (même
 * rythme que « Quel service ? »), puis revient à son icône. Avec
 * « Supprimer les animations », rien ne bouge. */
@Composable
private fun Constellation(modifier: Modifier = Modifier) {
    val reduceMotion = rememberReduceMotion()
    // Un seul tour par ouverture de l'app, pas à chaque retour en arrière.
    var tour by rememberSaveable { mutableIntStateOf(0) }
    LaunchedEffect(Unit) { if (tour == 0) tour = 1 }
    val floating = rememberInfiniteTransition(label = "flottement")
    // Carrés blancs et icônes bleues, même en mode sombre : ils sont posés sur le bleu.
    CompositionLocalProvider(LocalPalette provides NexisPalette.Light) {
        BoxWithConstraints(modifier.clearAndSetSemantics { }) {
            val k = minOf(maxWidth.value / DESIGN_WIDTH, maxHeight.value / DESIGN_HEIGHT)
            val left = (maxWidth.value - DESIGN_WIDTH * k) / 2
            val top = (maxHeight.value - DESIGN_HEIGHT * k) / 2
            SPOTS.forEachIndexed { i, spot ->
                val lift by floating.animateFloat(
                    initialValue = 0f,
                    targetValue = if (reduceMotion) 0f else -9f,
                    animationSpec = infiniteRepeatable(
                        tween(spot.periodMs / 2, easing = FastOutSlowInEasing),
                        RepeatMode.Reverse,
                        initialStartOffset = StartOffset(i * 600),
                    ),
                    label = "flottement $i",
                )
                Box(
                    Modifier
                        .offset(x = (left + spot.x * k).dp, y = (top + spot.y * k).dp)
                        .graphicsLayer {
                            translationY = lift * k * density
                            rotationZ = spot.angle
                        }
                        .shadow((14 * k).dp, RoundedCornerShape((spot.size * k * 0.32f).dp), ambientColor = Nexis.navy, spotColor = Nexis.navy),
                ) {
                    ServiceTile(
                        Pictogrammes.byService[spot.service] ?: Pictogrammes.fallback,
                        size = (spot.size * k).dp,
                        tour = tour,
                        delayMs = 1_000L + i * 400L,
                    )
                }
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

/** Cadre des écrans d'entrée (maquettes A2 à A4) : retour à gauche, langue
 * à droite, titre dans le contenu, bouton d'action en bas. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FormScreen(
    heading: String,
    onBack: (() -> Unit)?,
    intro: String? = null,
    bottom: @Composable () -> Unit = {},
    content: @Composable () -> Unit,
) {
    val app = LocalApp.current
    val p = LocalPalette.current
    Scaffold(
        containerColor = p.bg,
        topBar = {
            TopAppBar(
                title = {},
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(
                            onClick = onBack,
                            modifier = Modifier.padding(start = 6.dp).size(44.dp)
                                .background(p.surface, CircleShape).border(1.dp, p.line, CircleShape),
                        ) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = app.t("back"), tint = p.ink) }
                    }
                },
                actions = { Box(Modifier.padding(end = 12.dp)) { LanguageMenu() } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = p.bg, scrolledContainerColor = p.bg),
            )
        },
        bottomBar = {
            Box(Modifier.navigationBarsPadding().imePadding().padding(horizontal = 20.dp, vertical = 8.dp)) { bottom() }
        },
    ) { padding ->
        Column(
            Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState())
                .padding(start = 20.dp, end = 20.dp, top = 8.dp, bottom = 24.dp),
        ) {
            Text(heading, style = title(28, color = p.ink), modifier = Modifier.semantics { this.heading() })
            if (intro != null) Text(intro, style = body(15, color = p.muted), modifier = Modifier.padding(top = 8.dp))
            content()
        }
    }
}

/** Carte blanche aux coins de 20, comme dans les maquettes. */
@Composable
private fun EntryCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    val p = LocalPalette.current
    Column(modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(p.surface)) { content() }
}

@Composable
private fun EntryLabel(text: String, modifier: Modifier = Modifier) {
    val p = LocalPalette.current
    Text(text, style = body(13, FontWeight.SemiBold, p.muted), modifier = modifier)
}

private val CodeChannel.displayName: String
    get() = when (this) {
        CodeChannel.WHATSAPP -> "WhatsApp"
        CodeChannel.TELEGRAM -> "Telegram"
        CodeChannel.SMS -> "SMS"
    }

// Numéro (A2)

@Composable
private fun PhoneScreen(login: Boolean, onBack: () -> Unit, onSent: (String, CodeChannel) -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val channels = app.repository.codeChannels
    var phone by rememberSaveable { mutableStateOf("") }
    var channel by remember { mutableStateOf(channels.firstOrNull()) }
    var sending by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val parsed = DrcPhone.parse(phone)
    val focus = remember { FocusRequester() }
    val interaction = remember { MutableInteractionSource() }
    val focused by interaction.collectIsFocusedAsState()
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }

    FormScreen(
        heading = if (login) app.t("signInTitle") else app.t("yourNumber"),
        onBack = onBack,
        intro = app.t("yourNumberIntro"),
        bottom = {
            PrimaryButton(
                app.t("receiveCode"),
                enabled = parsed.isValid && channel != null,
                loading = sending,
                onClick = {
                    val chosen = channel
                    if (chosen != null && parsed.isValid && !sending) {
                        val number = parsed.e164
                        sending = true
                        failed = false
                        // Le serveur envoie le code ; on n'avance qu'une fois l'envoi confirmé.
                        scope.launch {
                            try {
                                app.repository.sendCode(number, chosen)
                                onSent(number, chosen)
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                failed = true
                            } finally {
                                sending = false
                            }
                        }
                    }
                },
            )
        },
    ) {
        EntryLabel(app.t("phone"), Modifier.padding(top = 24.dp))
        val shape = RoundedCornerShape(18.dp)
        Row(
            Modifier.padding(top = 8.dp).fillMaxWidth()
                .then(if (focused) Modifier.border(4.dp, Nexis.brand.copy(alpha = 0.12f), RoundedCornerShape(22.dp)).padding(4.dp) else Modifier.padding(4.dp))
                .height(60.dp).clip(shape).background(p.surface, shape)
                .border(if (focused) 2.dp else 1.dp, if (focused) Nexis.brand else p.line, shape)
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("🇨🇩", style = body(20), modifier = Modifier.clearAndSetSemantics { })
            Text("+243", style = body(17, FontWeight.SemiBold, p.ink))
            Box(Modifier.width(1.dp).height(26.dp).background(p.line))
            Box(Modifier.weight(1f), contentAlignment = Alignment.CenterStart) {
                if (phone.isEmpty()) Text("81 234 5678", style = body(19, FontWeight.Medium, p.muted))
                BasicTextField(
                    value = parsed.formatted,
                    onValueChange = { phone = DrcPhone.parse(it).digits },
                    enabled = !sending,
                    singleLine = true,
                    textStyle = body(19, FontWeight.Medium, p.ink),
                    cursorBrush = SolidColor(Nexis.brand),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                    interactionSource = interaction,
                    modifier = Modifier.fillMaxWidth().focusRequester(focus).semantics { contentDescription = app.t("phone") },
                )
            }
        }
        if (!parsed.prefixKnown) {
            Text(app.t("numberNotCongolese"), style = body(13, color = Nexis.danger), modifier = Modifier.padding(top = 8.dp))
        }
        EntryLabel(app.t("receiveCodeBy"), Modifier.padding(top = 26.dp))
        EntryCard(Modifier.padding(top = 8.dp)) {
            if (channels.isEmpty()) {
                Text(app.t("noCodeChannel"), style = body(14, color = p.muted), modifier = Modifier.padding(16.dp))
            }
            channels.forEachIndexed { index, item ->
                val (icon, color, sub) = when (item) {
                    CodeChannel.WHATSAPP -> Triple(Icons.AutoMirrored.Rounded.Chat, Color(0xFF25D366), app.t("whatsappSub"))
                    CodeChannel.TELEGRAM -> Triple(Icons.AutoMirrored.Rounded.Send, Color(0xFF229ED9), app.t("telegramSub"))
                    CodeChannel.SMS -> Triple(Icons.Rounded.Sms, Color(0xFF5B667A), app.t("smsSub"))
                }
                Row(
                    Modifier.fillMaxWidth()
                        .selectable(selected = channel == item, enabled = !sending, role = Role.RadioButton, onClick = { channel = item })
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    Box(Modifier.size(38.dp).background(color, RoundedCornerShape(11.dp)), contentAlignment = Alignment.Center) {
                        Icon(icon, contentDescription = null, tint = Color.White, modifier = Modifier.size(20.dp))
                    }
                    Column(Modifier.weight(1f)) {
                        Text(item.displayName, style = body(16, FontWeight.SemiBold, p.ink))
                        Text(sub, style = body(13, color = p.muted))
                    }
                    if (channel == item) {
                        Icon(Icons.Rounded.CheckCircle, contentDescription = null, tint = Nexis.brand, modifier = Modifier.size(26.dp))
                    } else {
                        Box(Modifier.padding(2.dp).size(22.dp).border(2.dp, pick(0xFFC9D0DB, 0xFF3A4A66), CircleShape))
                    }
                }
                if (index < channels.lastIndex) HorizontalDivider(Modifier.padding(start = 68.dp), color = p.line)
            }
        }
        if (failed) Text(app.t("actionFailed"), style = body(14, color = Nexis.danger), modifier = Modifier.padding(top = 12.dp))
    }
}

// Code (A3)

/** Délai avant de pouvoir redemander un code : 60 s (choix de Ben). */
private const val RESEND_DELAY = 60

@Composable
private fun CodeScreen(step: EntryStep.Code, onBack: () -> Unit, onSignup: () -> Unit, onChangeNumber: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var code by remember { mutableStateOf("") }
    var channel by remember { mutableStateOf(step.channel) }
    var noAccount by remember { mutableStateOf(false) }
    var left by remember { mutableIntStateOf(RESEND_DELAY) }
    var round by remember { mutableIntStateOf(0) }
    var resending by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf<String?>(null) }
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
    // Le compte à rebours repart à chaque nouvel envoi.
    LaunchedEffect(round) {
        left = RESEND_DELAY
        while (left > 0) {
            delay(1_000)
            left -= 1
        }
    }
    LaunchedEffect(notice) {
        val shown = notice ?: return@LaunchedEffect
        delay(2_500)
        if (notice == shown) notice = null
    }

    /** Démonstration : tout code à 6 chiffres est accepté. */
    fun verified() {
        when {
            app.repository.openAccount(step.phone) -> app.signIn()
            step.login -> noAccount = true
            else -> onSignup()
        }
    }

    fun send(target: CodeChannel, text: String) {
        resending = true
        scope.launch {
            try {
                app.repository.sendCode(step.phone, target)
                code = ""
                channel = target
                round += 1
                notice = text
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                notice = app.t("actionFailed")
            } finally {
                resending = false
            }
        }
    }

    val number = "+243 " + DrcPhone.parse(step.phone).formatted
    val sent = if (channel == CodeChannel.SMS) {
        app.t("codeSentBySms", "phone" to number)
    } else {
        app.t("codeSentTo", "channel" to channel.displayName, "phone" to number)
    }
    Box(Modifier.fillMaxSize()) {
        FormScreen(heading = app.t("enterCode"), onBack = onBack, intro = sent) {
            Box(Modifier.padding(top = 20.dp)) {
                Row(Modifier.fillMaxWidth().clearAndSetSemantics { }, horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                    repeat(6) { index ->
                        val shape = RoundedCornerShape(14.dp)
                        val current = index == code.length
                        Box(
                            Modifier.weight(1f).height(58.dp).clip(shape).background(p.surface, shape)
                                .border(if (current) 2.dp else 1.dp, if (current) Nexis.brand else p.line, shape),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(code.getOrNull(index)?.toString().orEmpty(), style = title(24, color = p.ink))
                        }
                    }
                }
                BasicTextField(
                    value = code,
                    onValueChange = { value ->
                        code = value.filter { it.isDigit() }.take(6)
                        if (code.length == 6) verified()
                    },
                    singleLine = true,
                    textStyle = body(1, color = Color.Transparent),
                    cursorBrush = SolidColor(Color.Transparent),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    modifier = Modifier.matchParentSize().focusRequester(focus).semantics { contentDescription = app.t("enterCode") },
                )
            }
            Column(Modifier.padding(top = 20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                InfoLine(Icons.Rounded.Schedule, app.t("codeHint"))
                InfoLine(Icons.Rounded.VerifiedUser, app.t("neverAskCode"))
            }
            Row(Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                TextButton(
                    onClick = { send(channel, app.t("codeResentToast", "channel" to channel.displayName)) },
                    enabled = left == 0 && !resending,
                ) {
                    Text(
                        if (left == 0) app.t("resendNow") else app.t("resendIn", "time" to "%d:%02d".format(left / 60, left % 60)),
                        style = body(14, if (left == 0) FontWeight.SemiBold else FontWeight.Normal, if (left == 0) p.accent else p.muted),
                    )
                }
                Spacer(Modifier.weight(1f))
                TextButton(onClick = onChangeNumber) { Text(app.t("changeLoginNumber"), style = body(14, FontWeight.SemiBold, p.accent)) }
            }
            app.repository.codeChannels.filter { it != channel }.forEach { other ->
                TextButton(
                    onClick = { send(other, app.t("codeSentToast", "channel" to other.displayName)) },
                    enabled = !resending,
                ) { Text(app.t("receiveInstead", "channel" to other.displayName), style = body(14, FontWeight.SemiBold, p.accent)) }
            }
        }
        notice?.let {
            Text(
                it, style = body(15, FontWeight.Medium, Color.White),
                modifier = Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 24.dp, start = 24.dp, end = 24.dp)
                    .background(Nexis.navy.copy(alpha = 0.94f), CircleShape).padding(horizontal = 18.dp, vertical = 12.dp)
                    .semantics { liveRegion = LiveRegionMode.Polite },
            )
        }
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

// Inscription (A4)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SignupScreen(phone: String, onBack: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val repo = app.repository
    var firstName by rememberSaveable { mutableStateOf("") }
    var lastName by rememberSaveable { mutableStateOf("") }
    var commune by rememberSaveable { mutableStateOf<String?>(null) }
    var communeMenu by remember { mutableStateOf(false) }
    var accepted by rememberSaveable { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    var readingTerms by remember { mutableStateOf(false) }
    val complete = firstName.isNotBlank() && lastName.isNotBlank() && commune != null && accepted
    val termsDate = repo.signupTermsVersion.format(DateTimeFormatter.ofPattern("dd/MM/yyyy", app.locale))

    @Composable
    fun FieldRow(label: String, value: @Composable () -> Unit) {
        Row(Modifier.fillMaxWidth().height(54.dp).padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(label, style = body(14, color = p.muted), modifier = Modifier.width(84.dp).clearAndSetSemantics { })
            Box(Modifier.weight(1f), contentAlignment = Alignment.CenterStart) { value() }
        }
    }

    @Composable
    fun NameField(label: String, value: String, onChange: (String) -> Unit) {
        FieldRow(label) {
            if (value.isEmpty()) Text(label, style = body(16, FontWeight.Medium, p.muted))
            BasicTextField(
                value = value, onValueChange = onChange, singleLine = true,
                textStyle = body(16, FontWeight.Medium, p.ink), cursorBrush = SolidColor(Nexis.brand),
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Words),
                modifier = Modifier.fillMaxWidth().semantics { contentDescription = label },
            )
        }
    }

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
        Row(
            Modifier.padding(top = 12.dp).background(pick(0xFFE6F4EC, 0xFF12301F), CircleShape).padding(horizontal = 11.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Icon(Icons.Rounded.CheckCircle, contentDescription = null, tint = Nexis.ok, modifier = Modifier.size(16.dp))
            Text(
                app.t("numberVerified", "phone" to "+243 " + DrcPhone.parse(phone).formatted),
                style = body(13, FontWeight.SemiBold, Nexis.ok),
            )
        }
        EntryCard(Modifier.padding(top = 22.dp)) {
            NameField(app.t("signupFirstName"), firstName) { firstName = it; failed = false }
            HorizontalDivider(Modifier.padding(start = 16.dp), color = p.line)
            NameField(app.t("signupLastName"), lastName) { lastName = it; failed = false }
            HorizontalDivider(Modifier.padding(start = 16.dp), color = p.line)
            Box {
                Row(
                    Modifier.fillMaxWidth().clickable(role = Role.Button) { communeMenu = true }
                        .semantics(mergeDescendants = true) { },
                ) {
                    FieldRow(app.t("commune")) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(commune ?: "—", style = body(16, FontWeight.Medium, if (commune == null) p.muted else p.ink), modifier = Modifier.weight(1f))
                            Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, contentDescription = app.t("commune"), tint = p.muted)
                        }
                    }
                }
                DropdownMenu(expanded = communeMenu, onDismissRequest = { communeMenu = false }) {
                    repo.communes.forEach { item ->
                        DropdownMenuItem(text = { Text(item, style = body(15)) }, onClick = {
                            commune = item
                            communeMenu = false
                            failed = false
                        })
                    }
                }
            }
        }
        EntryCard(Modifier.padding(top = 16.dp)) {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(Modifier.size(38.dp).background(p.soft, RoundedCornerShape(11.dp)), contentAlignment = Alignment.Center) {
                    Icon(Icons.Rounded.Description, contentDescription = null, tint = Nexis.brand, modifier = Modifier.size(21.dp))
                }
                Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                    Text(app.t("legalTerms"), style = body(15, FontWeight.SemiBold, p.ink))
                    Text(app.t("termsVersion", "date" to termsDate), style = body(13, color = p.muted))
                }
                TextButton(onClick = { readingTerms = true }) {
                    Text(app.t("signupReadTerms"), style = body(14, FontWeight.SemiBold, p.accent))
                }
            }
            HorizontalDivider(Modifier.padding(start = 16.dp), color = p.line)
            Row(
                Modifier.fillMaxWidth().height(54.dp).toggleable(accepted, role = Role.Switch) { accepted = it }
                    .padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(app.t("signupAcceptTerms"), style = body(15, color = p.ink), modifier = Modifier.weight(1f))
                Switch(checked = accepted, onCheckedChange = null, colors = SwitchDefaults.colors(checkedTrackColor = Nexis.brand))
            }
        }
        if (failed) Text(app.t("signupFailed"), style = body(14, color = Nexis.danger), modifier = Modifier.padding(top = 12.dp))
        Text(app.t("signupDemoNotice"), style = body(13, color = p.muted), modifier = Modifier.padding(top = 16.dp))
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
