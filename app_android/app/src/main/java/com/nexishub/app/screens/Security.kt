package com.nexishub.app.screens

import android.content.Context
import android.content.ContextWrapper
import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.AnimationVector1D
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.Backspace
import androidx.compose.material.icons.rounded.Fingerprint
import androidx.compose.material.icons.rounded.GppGood
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.LockReset
import androidx.compose.material.icons.rounded.Password
import androidx.compose.material.icons.rounded.Shield
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import com.nexishub.app.LocalApp
import com.nexishub.app.MoneyGate
import com.nexishub.app.data.AppSecurity
import com.nexishub.app.data.BiometricResult
import com.nexishub.app.data.CodeRules
import com.nexishub.app.data.Profile
import com.nexishub.app.ui.FlowScaffold
import com.nexishub.app.ui.InfoNote
import com.nexishub.app.ui.InitialsAvatar
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.body
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.title
import kotlin.math.sin
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// Code NexisHub et empreinte : création juste après l'inscription (ou la
// connexion sur un nouveau téléphone), verrou à l'ouverture, et confirmation
// avant chaque sortie d'argent. C'est le téléphone qui reconnaît la
// personne : l'app ne reçoit qu'un oui ou un non.

// Création du code

private enum class ProtectPhase { CREATE, CONFIRM, BIOMETRICS, DONE }

@Composable
fun ProtectScreen() {
    val app = LocalApp.current
    val p = LocalPalette.current
    val activity = LocalContext.current.findFragmentActivity()
    val scope = rememberCoroutineScope()
    val shake = remember { Animatable(0f) }
    var phase by remember {
        // Code déjà créé (capture de la CI) : on reprend à l'empreinte.
        mutableStateOf(
            when {
                !app.security.hasCode -> ProtectPhase.CREATE
                app.security.biometryAvailable -> ProtectPhase.BIOMETRICS
                else -> ProtectPhase.DONE
            },
        )
    }
    var first by remember { mutableStateOf("") }
    var entry by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    var enabling by remember { mutableStateOf(false) }

    fun refuse(text: String) {
        message = text
        scope.launch { shake.shakeOnce() }
    }

    LaunchedEffect(phase) {
        if (phase == ProtectPhase.DONE) {
            delay(1_200)
            app.finishingProtection = false
        }
    }
    BackHandler {
        if (phase == ProtectPhase.CONFIRM) {
            phase = ProtectPhase.CREATE
            first = ""
            entry = ""
        } else {
            activity?.moveTaskToBack(true)
        }
    }

    Box(Modifier.fillMaxSize().background(p.bg).statusBarsPadding().navigationBarsPadding()) {
        when (phase) {
            ProtectPhase.CREATE, ProtectPhase.CONFIRM -> Column(
                Modifier.fillMaxSize().padding(horizontal = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                val creating = phase == ProtectPhase.CREATE
                CodeHeader(
                    Icons.Rounded.Shield,
                    app.t(if (creating) "protectTitle" else "protectConfirmTitle"),
                    app.t(if (creating) "protectIntro" else "protectConfirmIntro"),
                    Modifier.padding(top = 28.dp),
                )
                CodeDots(entry.length, failed = message != null && entry.isEmpty(), shake.value, Modifier.padding(top = 28.dp))
                CodeMessage(message)
                Spacer(Modifier.weight(1f))
                if (creating) {
                    Text(
                        app.t("protectAdvice"), style = body(13, color = p.muted), textAlign = TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 0.dp).padding(bottom = 18.dp),
                    )
                }
                CodePad(entry, onEntry = { entry = it }, modifier = Modifier.padding(bottom = 20.dp)) { code ->
                    entry = ""
                    if (phase == ProtectPhase.CREATE) {
                        if (CodeRules.isWeak(code)) {
                            refuse(app.t("protectWeak"))
                        } else {
                            first = code
                            message = null
                            phase = ProtectPhase.CONFIRM
                        }
                    } else if (code == first) {
                        app.finishingProtection = true
                        app.security.setCode(code)
                        first = ""
                        message = null
                        phase = if (app.security.biometryAvailable) ProtectPhase.BIOMETRICS else ProtectPhase.DONE
                    } else {
                        first = ""
                        phase = ProtectPhase.CREATE
                        refuse(app.t("protectMismatch"))
                    }
                }
            }
            ProtectPhase.BIOMETRICS -> Column(
                Modifier.fillMaxSize().padding(horizontal = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                val method = app.t("bioFingerprint")
                Spacer(Modifier.weight(1f))
                Box(
                    Modifier.size(112.dp).background(p.soft, RoundedCornerShape(32.dp)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Rounded.Fingerprint, contentDescription = null, tint = Nexis.brand, modifier = Modifier.size(60.dp))
                }
                Text(
                    app.t("protectBioTitle", "method" to method), style = title(24, color = p.ink), textAlign = TextAlign.Center,
                    modifier = Modifier.padding(top = 28.dp).semantics { heading() },
                )
                Text(
                    app.t("protectBioText"), style = body(15, color = p.muted), textAlign = TextAlign.Center,
                    modifier = Modifier.padding(top = 12.dp),
                )
                Spacer(Modifier.weight(1f))
                PrimaryButton(
                    app.t("protectBioOn", "method" to method),
                    onClick = {
                        enabling = true
                        scope.launch {
                            app.security.enableBiometrics(activity, app.t("protectBioTitle", "method" to method), app.t("lockUseCode"))
                            enabling = false
                            phase = ProtectPhase.DONE
                        }
                    },
                    icon = Icons.Rounded.Fingerprint,
                    loading = enabling,
                )
                TextButton(
                    onClick = { phase = ProtectPhase.DONE },
                    enabled = !enabling,
                    modifier = Modifier.padding(top = 6.dp, bottom = 12.dp).heightIn(min = 48.dp),
                ) {
                    Text(app.t("protectBioLater"), style = body(16, FontWeight.SemiBold, p.accent))
                }
            }
            ProtectPhase.DONE -> Column(
                Modifier.fillMaxSize().padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Icon(Icons.Rounded.GppGood, contentDescription = null, tint = Nexis.ok, modifier = Modifier.size(72.dp))
                Text(
                    app.t("protectDone"), style = title(20, color = p.ink), textAlign = TextAlign.Center,
                    modifier = Modifier.padding(top = 18.dp).semantics { liveRegion = LiveRegionMode.Polite },
                )
            }
        }
    }
}

// Verrou

/** Posé sur toute l'app quand elle revient après au moins une minute. */
@Composable
fun LockScreen() {
    val app = LocalApp.current
    val p = LocalPalette.current
    val activity = LocalContext.current.findFragmentActivity()
    val scope = rememberCoroutineScope()
    val shake = remember { Animatable(0f) }
    var profile by remember { mutableStateOf<Profile?>(null) }
    var entry by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    var forgot by remember { mutableStateOf(false) }
    var blocked by remember { mutableStateOf(false) }
    val security = app.security
    val method = app.t("bioFingerprint")

    suspend fun tryBiometrics() {
        when (security.unlockWithBiometrics(activity, app.t("lockPrompt"), app.t("lockUseCode"))) {
            BiometricResult.OK -> {
                app.locked = false
            }
            BiometricResult.CHANGED -> {
                message = app.t("lockBioChanged", "method" to method.replaceFirstChar { it.uppercase() })
            }
            BiometricResult.FAILED -> Unit
        }
    }

    LaunchedEffect(Unit) {
        profile = attempt { app.repository.profile() }
        if (security.failures >= CodeRules.MAX_FAILURES) {
            blocked = true
        } else if (app.capture == null && security.biometricsOn) {
            tryBiometrics()
        }
    }
    // Le retour ne montre pas l'app derrière le verrou.
    BackHandler { activity?.moveTaskToBack(true) }

    Column(
        Modifier.fillMaxSize().background(p.bg).blockTouches().statusBarsPadding().navigationBarsPadding()
            .padding(horizontal = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Column(
            Modifier.padding(top = 36.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            InitialsAvatar(profile?.initials.orEmpty(), size = 64.dp)
            Text(
                profile?.let { app.t("hello", "name" to it.firstName) } ?: "NexisHub",
                style = title(22, color = p.ink), textAlign = TextAlign.Center,
                modifier = Modifier.semantics { heading() },
            )
            Text(app.t("lockPrompt"), style = body(15, color = p.muted), textAlign = TextAlign.Center)
        }
        CodeDots(entry.length, failed = message != null && entry.isEmpty(), shake.value, Modifier.padding(top = 28.dp))
        CodeMessage(message)
        Spacer(Modifier.weight(1f))
        CodePad(
            entry, onEntry = { entry = it },
            biometrics = security.biometricsOn,
            biometricsLabel = app.t("lockUseBio", "method" to method),
            onBiometrics = { scope.launch { tryBiometrics() } },
        ) { code ->
            entry = ""
            when (val result = security.check(code)) {
                AppSecurity.Check.Ok -> {
                    message = null
                    app.locked = false
                }
                is AppSecurity.Check.Wrong -> {
                    message = app.plural("lockWrong", result.left)
                    scope.launch { shake.shakeOnce() }
                }
                AppSecurity.Check.Blocked -> {
                    blocked = true
                }
            }
        }
        TextButton(onClick = { forgot = true }, modifier = Modifier.padding(top = 8.dp, bottom = 12.dp).heightIn(min = 48.dp)) {
            Text(app.t("lockForgot"), style = body(15, FontWeight.SemiBold, p.accent))
        }
    }

    if (forgot) {
        AlertDialog(
            onDismissRequest = { forgot = false },
            title = { Text(app.t("lockForgot")) },
            text = { Text(app.t("lockForgotText")) },
            confirmButton = {
                TextButton(onClick = { forgot = false; app.signOut() }) {
                    Text(app.t("lockForgotAction"), color = Nexis.danger)
                }
            },
            dismissButton = { TextButton(onClick = { forgot = false }) { Text(app.t("cancel")) } },
        )
    }
    if (blocked) {
        AlertDialog(
            onDismissRequest = {},
            title = { Text(app.t("lockBlockedTitle")) },
            text = { Text(app.t("lockBlockedText")) },
            confirmButton = { TextButton(onClick = { blocked = false; app.signOut() }) { Text(app.t("ok")) } },
        )
    }
}

// Avant une sortie d'argent

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GateSheet(gate: MoneyGate) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val activity = LocalContext.current.findFragmentActivity()
    val scope = rememberCoroutineScope()
    val shake = remember { Animatable(0f) }
    val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var entry by remember(gate) { mutableStateOf("") }
    var message by remember(gate) { mutableStateOf<String?>(null) }
    val security = app.security
    val method = app.t("bioFingerprint")

    suspend fun tryBiometrics() {
        when (security.unlockWithBiometrics(activity, gate.reason, app.t("lockUseCode"))) {
            BiometricResult.OK -> app.finishGate(true)
            BiometricResult.CHANGED -> {
                message = app.t("lockBioChanged", "method" to method.replaceFirstChar { it.uppercase() })
            }
            BiometricResult.FAILED -> Unit
        }
    }

    LaunchedEffect(gate) {
        if (app.capture == null && security.biometricsOn) tryBiometrics()
    }

    ModalBottomSheet(onDismissRequest = { app.finishGate(false) }, sheetState = sheet, containerColor = p.bg) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 20.dp).navigationBarsPadding(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                app.t("guardTitle"), style = title(20, color = p.ink), textAlign = TextAlign.Center,
                modifier = Modifier.semantics { heading() },
            )
            Text(
                gate.reason, style = body(16, FontWeight.SemiBold, p.accent), textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 8.dp),
            )
            CodeDots(entry.length, failed = message != null && entry.isEmpty(), shake.value, Modifier.padding(top = 26.dp))
            CodeMessage(message)
            CodePad(
                entry, onEntry = { entry = it },
                biometrics = security.biometricsOn,
                biometricsLabel = app.t("lockUseBio", "method" to method),
                onBiometrics = { scope.launch { tryBiometrics() } },
                modifier = Modifier.padding(top = 12.dp),
            ) { code ->
                entry = ""
                when (val result = security.check(code)) {
                    AppSecurity.Check.Ok -> app.finishGate(true)
                    is AppSecurity.Check.Wrong -> {
                        message = app.plural("lockWrong", result.left)
                        scope.launch { shake.shakeOnce() }
                    }
                    AppSecurity.Check.Blocked -> {
                        // Le verrou montre « Trop d'essais » puis déconnecte.
                        app.finishGate(false)
                        app.locked = true
                    }
                }
            }
            TextButton(onClick = { app.finishGate(false) }, modifier = Modifier.padding(vertical = 8.dp).heightIn(min = 48.dp)) {
                Text(app.t("cancel"), style = body(15, FontWeight.SemiBold, p.accent))
            }
        }
    }
}

// Réglages (profil)

@Composable
fun SecurityScreen() {
    val app = LocalApp.current
    val p = LocalPalette.current
    val flow = LocalFlow.current
    val activity = LocalContext.current.findFragmentActivity()
    val scope = rememberCoroutineScope()
    val security = app.security
    val method = app.t("bioFingerprint")
    var biometricsOn by remember { mutableStateOf(security.biometricsOn) }
    var busy by remember { mutableStateOf(false) }
    var changing by remember { mutableStateOf(false) }

    if (changing) {
        ChangeCode(onBack = { changing = false }) {
            changing = false
            flow.say(app.t("securityCodeChanged"))
        }
        return
    }
    FlowScaffold(app.t("securityRow"), onBack = flow::back) {
        if (security.biometryAvailable) {
            Column(Modifier.nexisCard(p)) {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Rounded.Fingerprint, contentDescription = null, tint = p.accent)
                    Text(
                        app.t("lockUseBio", "method" to method), style = body(16, color = p.ink),
                        modifier = Modifier.weight(1f).padding(horizontal = 12.dp),
                    )
                    Switch(
                        checked = biometricsOn,
                        enabled = !busy,
                        onCheckedChange = { on ->
                            if (!on) {
                                security.disableBiometrics()
                                biometricsOn = false
                            } else {
                                busy = true
                                scope.launch {
                                    biometricsOn = security.enableBiometrics(
                                        activity, app.t("lockUseBio", "method" to method), app.t("lockUseCode"),
                                    )
                                    busy = false
                                }
                            }
                        },
                        colors = SwitchDefaults.colors(checkedTrackColor = Nexis.brand),
                    )
                }
            }
            Text(app.t("securityBioHint", "method" to method), style = body(13, color = p.muted))
        } else {
            InfoNote(app.t("securityNoBio"), icon = Icons.Rounded.Shield)
        }
        Column(Modifier.nexisCard(p).clickable { changing = true }) {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp).heightIn(min = 56.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Rounded.Password, contentDescription = null, tint = p.accent)
                Text(
                    app.t("securityChangeCode"), style = body(16, color = p.ink),
                    modifier = Modifier.weight(1f).padding(horizontal = 12.dp),
                )
            }
        }
        Text(app.t("securityLockNote"), style = body(13, color = p.muted))
    }
}

private enum class ChangePhase { CURRENT, CREATE, CONFIRM }

/** Changer de code : l'actuel d'abord, puis le nouveau deux fois. */
@Composable
private fun ChangeCode(onBack: () -> Unit, onChanged: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    val shake = remember { Animatable(0f) }
    var phase by remember { mutableStateOf(ChangePhase.CURRENT) }
    var first by remember { mutableStateOf("") }
    var entry by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }

    fun refuse(text: String) {
        message = text
        scope.launch { shake.shakeOnce() }
    }

    BackHandler(onBack = onBack)
    Column(
        Modifier.fillMaxSize().background(p.bg).statusBarsPadding().navigationBarsPadding().padding(horizontal = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(Modifier.fillMaxWidth()) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = app.t("back"), tint = p.ink)
            }
        }
        CodeHeader(
            if (phase == ChangePhase.CURRENT) Icons.Rounded.Lock else Icons.Rounded.LockReset,
            when (phase) {
                ChangePhase.CURRENT -> app.t("securityCurrentCode")
                ChangePhase.CREATE -> app.t("securityNewCode")
                ChangePhase.CONFIRM -> app.t("protectConfirmTitle")
            },
            if (phase == ChangePhase.CREATE) app.t("protectAdvice") else null,
            Modifier.padding(top = 8.dp),
        )
        CodeDots(entry.length, failed = message != null && entry.isEmpty(), shake.value, Modifier.padding(top = 26.dp))
        CodeMessage(message)
        Spacer(Modifier.weight(1f))
        CodePad(entry, onEntry = { entry = it }, modifier = Modifier.padding(bottom = 20.dp)) { code ->
            entry = ""
            when (phase) {
                ChangePhase.CURRENT -> when (val result = app.security.check(code)) {
                    AppSecurity.Check.Ok -> {
                        message = null
                        phase = ChangePhase.CREATE
                    }
                    is AppSecurity.Check.Wrong -> refuse(app.plural("lockWrong", result.left))
                    AppSecurity.Check.Blocked -> {
                        app.locked = true
                    }
                }
                ChangePhase.CREATE -> if (CodeRules.isWeak(code)) {
                    refuse(app.t("protectWeak"))
                } else {
                    first = code
                    message = null
                    phase = ChangePhase.CONFIRM
                }
                ChangePhase.CONFIRM -> if (code == first) {
                    app.security.setCode(code)
                    onChanged()
                } else {
                    first = ""
                    phase = ChangePhase.CREATE
                    refuse(app.t("protectMismatch"))
                }
            }
        }
    }
}

// Pièces communes

@Composable
private fun CodeHeader(icon: ImageVector, headline: String, text: String?, modifier: Modifier = Modifier) {
    val p = LocalPalette.current
    Column(modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(Modifier.size(60.dp).background(p.soft, RoundedCornerShape(18.dp)), contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = null, tint = Nexis.brand, modifier = Modifier.size(28.dp))
        }
        Text(headline, style = title(22, color = p.ink), textAlign = TextAlign.Center, modifier = Modifier.semantics { heading() })
        if (text != null) Text(text, style = body(15, color = p.muted), textAlign = TextAlign.Center)
    }
}

/** Six points : pleins pour les chiffres tapés, rouges après une erreur. */
@Composable
private fun CodeDots(filled: Int, failed: Boolean, shake: Float, modifier: Modifier = Modifier) {
    val p = LocalPalette.current
    val label = "$filled / ${CodeRules.LENGTH}"
    Row(
        modifier.offset { IntOffset((8 * sin(shake * Math.PI * 4)).dp.roundToPx(), 0) }
            .semantics { contentDescription = label },
        horizontalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        repeat(CodeRules.LENGTH) { index ->
            val full = index < filled
            Box(
                Modifier.size(14.dp)
                    .background(if (full) Nexis.brand else if (failed) Nexis.danger.copy(alpha = 0.18f) else Color.Transparent, CircleShape)
                    .then(
                        if (full) Modifier else Modifier.border(1.5.dp, if (failed) Nexis.danger else p.muted.copy(alpha = 0.55f), CircleShape),
                    ),
            )
        }
    }
}

@Composable
private fun CodeMessage(text: String?) {
    Text(
        text.orEmpty(), style = body(14, FontWeight.Medium, Nexis.danger), textAlign = TextAlign.Center,
        modifier = Modifier.fillMaxWidth().padding(top = 14.dp).heightIn(min = 40.dp)
            .semantics { liveRegion = LiveRegionMode.Polite },
    )
}

/** Le pavé de chiffres. Le clavier du système n'est pas utilisé : il
 * proposerait de remplir le code à partir des messages. */
@Composable
private fun CodePad(
    entry: String,
    onEntry: (String) -> Unit,
    modifier: Modifier = Modifier,
    biometrics: Boolean = false,
    biometricsLabel: String = "",
    onBiometrics: () -> Unit = {},
    onComplete: (String) -> Unit,
) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val haptics = LocalHapticFeedback.current
    val scope = rememberCoroutineScope()
    fun type(digit: Char) {
        if (entry.length >= CodeRules.LENGTH) return
        haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        val next = entry + digit
        onEntry(next)
        if (next.length == CodeRules.LENGTH) {
            // Laisse voir le dernier point avant de vérifier.
            scope.launch {
                delay(140)
                onComplete(next)
            }
        }
    }
    Column(modifier, verticalArrangement = Arrangement.spacedBy(14.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        listOf("123", "456", "789").forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) { row.forEach { PadKey(it.toString()) { type(it) } } }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            if (biometrics) {
                IconButton(onClick = onBiometrics, modifier = Modifier.size(KEY)) {
                    Icon(Icons.Rounded.Fingerprint, contentDescription = biometricsLabel, tint = p.accent, modifier = Modifier.size(32.dp))
                }
            } else {
                Spacer(Modifier.size(KEY))
            }
            PadKey("0") { type('0') }
            IconButton(
                onClick = { if (entry.isNotEmpty()) onEntry(entry.dropLast(1)) },
                enabled = entry.isNotEmpty(),
                modifier = Modifier.size(KEY),
            ) {
                Icon(
                    Icons.AutoMirrored.Rounded.Backspace, contentDescription = app.t("lockDelete"),
                    tint = if (entry.isEmpty()) p.ink.copy(alpha = 0.3f) else p.ink,
                )
            }
        }
    }
}

private val KEY = 74.dp

@Composable
private fun PadKey(digit: String, onClick: () -> Unit) {
    val p = LocalPalette.current
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    Box(
        Modifier.size(KEY)
            .background(if (pressed) p.soft else p.surface, CircleShape)
            .border(1.dp, p.line, CircleShape)
            .clickable(interactionSource = interaction, indication = null, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(digit, style = title(26, FontWeight.Medium, p.ink))
    }
}

/** Petit tremblement après un code refusé. */
private suspend fun Animatable<Float, AnimationVector1D>.shakeOnce() {
    snapTo(0f)
    animateTo(1f, tween(400))
    snapTo(0f)
}

/** Empêche les touchers de passer à l'écran de dessous. */
fun Modifier.blockTouches(): Modifier = pointerInput(Unit) {
    awaitPointerEventScope {
        while (true) awaitPointerEvent().changes.forEach { it.consume() }
    }
}

/** L'activité de l'app (l'invite d'empreinte en a besoin). */
private tailrec fun Context.findFragmentActivity(): FragmentActivity? = when (this) {
    is FragmentActivity -> this
    is ContextWrapper -> baseContext.findFragmentActivity()
    else -> null
}
