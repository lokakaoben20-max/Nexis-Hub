package com.nexishub.app

import android.os.Build
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.nexishub.app.data.AndroidBiometrics
import com.nexishub.app.data.AppSecurity
import com.nexishub.app.data.DemoRepository
import com.nexishub.app.data.KeystoreCodeVault
import com.nexishub.app.data.MemoryCodeVault
import com.nexishub.app.data.Texts
import com.nexishub.app.screens.EntryFlow
import com.nexishub.app.screens.GateSheet
import com.nexishub.app.screens.LockScreen
import com.nexishub.app.screens.ProtectScreen
import com.nexishub.app.screens.blockTouches
import com.nexishub.app.screens.Shell
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.NexisTheme
import com.nexishub.app.ui.PictoLoader
import com.nexishub.app.ui.rememberReduceMotion
import kotlinx.coroutines.delay

/** FragmentActivity : l'invite d'empreinte d'Android (BiometricPrompt) en a besoin. */
class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val texts = Texts(assets.open("textes.json").bufferedReader().use { it.readText() })
        // Captures d'écran de la CI uniquement (version de débogage) :
        // ouvre directement l'écran demandé avec les données fictives.
        val capture = if (BuildConfig.DEBUG) Capture.from(intent.getStringExtra("capture")) else null
        // La liste des apps ouvertes ne montre pas l'écran (soldes, missions).
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) setRecentsScreenshotEnabled(false)
        val security = if (capture != null) {
            AppSecurity(MemoryCodeVault(), AndroidBiometrics(applicationContext))
        } else {
            AppSecurity(KeystoreCodeVault(applicationContext), AndroidBiometrics(applicationContext))
        }
        val app = AppModel(DemoRepository(), texts, security, intent.getStringExtra("language") ?: AppModel.defaultLanguage())
        app.capture = capture?.code
        if (capture?.signedIn == true) app.signIn()
        // L'émulateur n'a pas d'empreinte : les captures font comme si.
        when (capture) {
            null, Capture.PROTECT -> Unit
            Capture.PROTECT_BIO -> {
                security.presetForCapture("482916", biometricsOn = false)
                app.finishingProtection = true
            }
            Capture.LOCK -> {
                security.presetForCapture("482916", biometricsOn = true)
                app.locked = true
            }
            else -> if (capture?.signedIn == true) security.presetForCapture("482916", biometricsOn = true)
        }
        setContent {
            NexisTheme {
                CompositionLocalProvider(LocalApp provides app) {
                    NexisRoot(app, capture)
                }
            }
        }
    }
}

@Composable
fun NexisRoot(app: AppModel, capture: Capture?) {
    val start = remember { capture }
    val reduceMotion = rememberReduceMotion()
    // Le lancement ne revient pas quand la langue ou la session change.
    var launched by rememberSaveable { mutableStateOf(capture != null) }
    LaunchedEffect(Unit) {
        if (!launched) {
            delay(if (reduceMotion) 300L else 1_400L)
            launched = true
        }
    }
    // Hors de l'app au moins une minute : le code est redemandé au retour.
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_STOP -> app.left()
                Lifecycle.Event.ON_START -> app.cameBack()
                else -> Unit
            }
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    val hidden = app.locked || app.covered
    Box(Modifier.fillMaxSize()) {
        // Derrière le verrou, rien n'est lu par TalkBack.
        Box(if (hidden) Modifier.fillMaxSize().clearAndSetSemantics {} else Modifier.fillMaxSize()) {
            Crossfade(targetState = app.signedIn, label = "session") { signedIn ->
                when {
                    !signedIn -> EntryFlow(start)
                    app.needsProtection || app.finishingProtection -> ProtectScreen()
                    else -> Shell(start)
                }
            }
        }
        AnimatedVisibility(visible = app.signedIn && app.locked, enter = fadeIn(), exit = fadeOut()) {
            LockScreen()
        }
        if (app.covered) LaunchScreen()
        AnimatedVisibility(visible = !launched, enter = fadeIn(), exit = fadeOut(tween(450))) {
            LaunchScreen()
        }
        app.gate?.let { GateSheet(it) }
    }
}

/** Prolonge l'écran de démarrage d'Android : les pictogrammes des services
 * se relaient, en blanc sur le bleu Nexis. */
@Composable
private fun LaunchScreen() {
    Box(Modifier.fillMaxSize().background(Nexis.heroGradient).blockTouches(), contentAlignment = Alignment.Center) {
        PictoLoader(label = "Nexis Hub", size = 84.dp)
    }
}

/** Écrans que la CI photographie (voir .github/workflows/apps-natives.yml). */
enum class Capture(
    val signedIn: Boolean,
    val tab: Int? = null,
    val entry: String? = null,
    val picker: Boolean = false,
    val provider: Boolean = false,
) {
    WELCOME(false, entry = "welcome"),
    PHONE(false, entry = "phone"),
    CODE(false, entry = "code"),
    SIGNUP(false, entry = "signup"),
    HOME(true, tab = 0),
    MISSIONS(true, tab = 1),
    WALLET(true, tab = 2),
    PROFILE(true, tab = 3),
    SERVICES(true, tab = 0, picker = true),

    // Écrans de mission (voir MissionRoute.forCapture).
    TRACKING(true, tab = 1),
    QUOTES(true, tab = 1),
    SHOWCASE(true, tab = 1),
    PAY(true, tab = 1),
    PENDING(true, tab = 1),
    CONFIRM(true, tab = 1),
    REPORT(true, tab = 1),
    DISPUTE(true, tab = 1),
    DECISION(true, tab = 1),
    PROVIDER(true, tab = 0, provider = true),
    REQUEST(true, tab = 0, provider = true),
    JOB(true, tab = 0, provider = true),

    // Écrans du profil.
    INFO(true, tab = 3),
    DEVICES(true, tab = 3),
    ALERTS(true, tab = 3),
    HELP(true, tab = 3),
    LEGAL(true, tab = 3),
    BECOME(true, tab = 3),

    // Étape « Pièce d'identité », figée sans caméra (voir IdentityDemo).
    BECOME_IDENTITY(true, tab = 3),
    BECOME_WRONG_SIDE(true, tab = 3),
    BECOME_VERSO(true, tab = 3),
    BECOME_SELFIE(true, tab = 3),
    BECOME_REVIEW(true, tab = 3),
    BECOME_PASSPORT(true, tab = 3),
    BECOME_WRONG_PAGE(true, tab = 3),

    // Preuves de réalisations (voir PortfolioDemo).
    BECOME_PORTFOLIO(true, tab = 3),
    PORTFOLIO(true, tab = 3),
    PORTFOLIO_LOCKED(true, tab = 3),

    // Code NexisHub et empreinte.
    PROTECT(true),
    PROTECT_BIO(true),
    LOCK(true, tab = 0),
    SECURITY(true, tab = 3);

    /** Le nom passé par le script de captures (« become-identity »). */
    val code: String get() = name.lowercase().replace('_', '-')

    companion object {
        fun from(value: String?): Capture? = entries.firstOrNull { it.code == value?.lowercase() }
    }
}
