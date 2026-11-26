package com.nexishub.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.HourglassTop
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.rounded.ListAlt
import androidx.compose.material.icons.outlined.AccountBalanceWallet
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import com.nexishub.app.data.ProviderStatus
import com.nexishub.app.data.AppNotification
import androidx.compose.material.icons.rounded.AccountBalanceWallet
import androidx.compose.material.icons.rounded.AccountCircle
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.Apps
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.MoreHoriz
import androidx.compose.material.icons.rounded.Shield
import androidx.compose.material.icons.automirrored.rounded.Undo
import androidx.compose.material.icons.rounded.Upload
import androidx.compose.material.icons.rounded.Visibility
import androidx.compose.material.icons.rounded.VisibilityOff
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LargeTopAppBar
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import android.os.SystemClock
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.input.pointer.pointerInput
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.nexishub.app.AppModel
import com.nexishub.app.Capture
import com.nexishub.app.LocalApp
import com.nexishub.app.data.Currency
import com.nexishub.app.data.DrcPhone
import com.nexishub.app.data.Mission
import com.nexishub.app.data.MissionStatus
import com.nexishub.app.data.Money
import com.nexishub.app.data.Movement
import com.nexishub.app.data.MovementKind
import com.nexishub.app.data.PaymentState
import com.nexishub.app.data.Profile
import com.nexishub.app.data.Wallet
import com.nexishub.app.ui.InfoNote
import com.nexishub.app.ui.ComingSoonContent
import com.nexishub.app.ui.InitialsAvatar
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.MissionRow
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.NexisPalette
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.body
import com.nexishub.app.ui.day
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.paymentLabel
import com.nexishub.app.ui.title
import java.time.LocalTime

/** Les quatre onglets dans la barre de navigation Material 3 et
 * « Demander un service », l'action principale, en bouton flottant. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun Shell(start: Capture?) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var tab by rememberSaveable { mutableIntStateOf(start?.tab ?: 0) }
    var picking by remember { mutableStateOf(start?.picker == true) }
    var comingSoon by remember { mutableStateOf<String?>(null) }
    val flow = remember { MissionFlow() }
    // Captures de la CI : l'espace et l'écran de mission demandés.
    LaunchedEffect(Unit) {
        if (start?.provider == true) app.providerSpace = true
        MissionRoute.forCapture(app.capture)?.let { flow.path.addAll(it) }
    }
    // Changer d'espace ramène à son accueil.
    var shownSpace by remember { mutableStateOf(app.providerSpace) }
    if (shownSpace != app.providerSpace) {
        shownSpace = app.providerSpace
        tab = 0
    }
    LaunchedEffect(app.requestedTab) {
        app.requestedTab?.let {
            tab = it
            app.requestedTab = null
        }
    }
    // Côté prestataire, rien à demander : pas de bouton « + ».
    val showFab = tab <= 1 && !app.providerSpace
    // « Demander un service » reste un « + » compact. Il s'ouvre quelques
    // secondes pour se présenter : de temps en temps quand la personne a déjà
    // des missions (sinon la carte de l'accueil porte déjà ce bouton), et dès
    // qu'elle tape plusieurs fois dans le vide, comme si elle cherchait quoi faire.
    var hasMissions by rememberSaveable { mutableStateOf(false) }
    var fabOpen by remember { mutableStateOf(false) }
    var hintsShown by rememberSaveable { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()
    var hintJob by remember { mutableStateOf<Job?>(null) }
    val confusedTaps = remember { ConfusedTapDetector() }
    fun openFabFor(durationMs: Long) {
        hintJob?.cancel()
        hintJob = scope.launch {
            fabOpen = true
            try { delay(durationMs) } finally { fabOpen = false }
        }
    }
    LaunchedEffect(showFab, hasMissions) {
        if (!showFab || !hasMissions) return@LaunchedEffect
        delay(FAB_FIRST_HINT_MS)
        while (hintsShown < FAB_MAX_HINTS) {
            hintsShown++
            openFabFor(FAB_HINT_SHOWN_MS)
            delay(FAB_HINT_SHOWN_MS + FAB_HINT_EVERY_MS)
        }
    }

    val items = listOf(
        Triple(app.t("navHome"), Icons.Rounded.Home, Icons.Outlined.Home),
        Triple(app.t("navMissions"), Icons.AutoMirrored.Rounded.ListAlt, Icons.AutoMirrored.Rounded.ListAlt),
        Triple(app.t("navWallet"), Icons.Rounded.AccountBalanceWallet, Icons.Outlined.AccountBalanceWallet),
        Triple(app.t("navProfile"), Icons.Rounded.AccountCircle, Icons.Outlined.AccountCircle),
    )
    MissionFlowHost(flow) {
        Scaffold(
            containerColor = p.bg,
            bottomBar = {
                NavigationBar(containerColor = p.surface) {
                    items.forEachIndexed { index, (label, selected, idle) ->
                        NavigationBarItem(
                            selected = tab == index,
                            onClick = { tab = index },
                            icon = { Icon(if (tab == index) selected else idle, contentDescription = null) },
                            label = { Text(label, style = body(12, if (tab == index) FontWeight.SemiBold else FontWeight.Medium), maxLines = 1) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = p.accent, selectedTextColor = p.accent,
                                indicatorColor = p.soft, unselectedIconColor = p.muted, unselectedTextColor = p.muted,
                            ),
                        )
                    }
                }
            },
            floatingActionButton = {
                if (showFab) {
                    ExtendedFloatingActionButton(
                        onClick = { picking = true },
                        expanded = fabOpen,
                        icon = { Icon(Icons.Rounded.Add, contentDescription = if (fabOpen) null else app.t("requestService")) },
                        text = { Text(app.t("requestService"), style = body(15, FontWeight.SemiBold)) },
                        containerColor = Nexis.brand,
                        contentColor = Color.White,
                        shape = RoundedCornerShape(20.dp),
                    )
                }
            },
        ) { padding ->
            Box(
                Modifier.padding(bottom = padding.calculateBottomPadding())
                    // Seules les touches qui ne tombent sur aucun bouton arrivent ici.
                    .pointerInput(showFab) {
                        detectTapGestures {
                            if (showFab && confusedTaps.onTap(SystemClock.uptimeMillis())) openFabFor(FAB_CONFUSED_SHOWN_MS)
                        }
                    },
            ) {
                when {
                    tab == 0 && app.providerSpace -> ProviderHomeTab(onTab = { tab = it })
                    tab == 0 -> HomeTab(
                        onPick = { picking = true }, onTab = { tab = it }, onComingSoon = { comingSoon = it },
                        onMissions = { hasMissions = it },
                    )
                    tab == 1 && app.providerSpace -> ProviderMissionsTab()
                    tab == 1 -> MissionsTab(onMissions = { hasMissions = it })
                    tab == 2 -> WalletTab()
                    else -> ProfileTab(onComingSoon = { comingSoon = it })
                }
            }
        }
    }
    if (picking) {
        ServicePickerSheet(onDismiss = { picking = false }, onRequested = { picking = false; tab = 1 })
    }
    comingSoon?.let { heading ->
        ModalBottomSheet(onDismissRequest = { comingSoon = null }, containerColor = p.surface) {
            ComingSoonContent(heading) { comingSoon = null }
        }
    }
}

/** Quand « Demander un service » s'ouvre pour se présenter : la première
 * fois quelques secondes après l'arrivée, puis toutes les 90 secondes, au
 * plus quatre fois par ouverture de l'app. */
private const val FAB_FIRST_HINT_MS = 5_000L
private const val FAB_HINT_SHOWN_MS = 3_500L
private const val FAB_HINT_EVERY_MS = 90_000L
private const val FAB_MAX_HINTS = 4
private const val FAB_CONFUSED_SHOWN_MS = 4_000L

/** Repère les touches « dans le vide » répétées : trois touches qui ne
 * tombent sur aucun bouton en moins de quatre secondes. */
class ConfusedTapDetector(private val taps: Int = 3, private val windowMs: Long = 4_000L) {
    private val recent = ArrayDeque<Long>()

    /** Vrai quand cette touche complète une série ; la série repart alors de zéro. */
    fun onTap(nowMs: Long): Boolean {
        recent.addLast(nowMs)
        while (recent.isNotEmpty() && nowMs - recent.first() > windowMs) recent.removeFirst()
        if (recent.size < taps) return false
        recent.clear()
        return true
    }
}

/** Grand titre en Unbounded qui se replie au défilement. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TabScaffold(heading: String, actions: @Composable () -> Unit = {}, content: @Composable (PaddingValues) -> Unit) {
    val p = LocalPalette.current
    val scroll = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()
    Scaffold(
        modifier = Modifier.nestedScroll(scroll.nestedScrollConnection),
        containerColor = p.bg,
        topBar = {
            LargeTopAppBar(
                title = { Text(heading, maxLines = 1) },
                actions = { actions() },
                colors = TopAppBarDefaults.largeTopAppBarColors(containerColor = p.bg, scrolledContainerColor = p.surface),
                scrollBehavior = scroll,
            )
        },
        contentWindowInsets = androidx.compose.foundation.layout.WindowInsets(0),
        content = content,
    )
}

// Accueil

@Composable
private fun HomeTab(onPick: () -> Unit, onTab: (Int) -> Unit, onComingSoon: (String) -> Unit, onMissions: (Boolean) -> Unit) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    var profile by remember { mutableStateOf<Profile?>(null) }
    var wallet by remember { mutableStateOf(Wallet.EMPTY) }
    var missions by remember { mutableStateOf(emptyList<Mission>()) }
    var showDone by rememberSaveable { mutableStateOf(false) }
    var notifications by remember { mutableStateOf(emptyList<AppNotification>()) }
    var showNotifications by remember { mutableStateOf(false) }
    LaunchedEffect(app.revision) {
        profile = app.repository.profile()
        wallet = app.repository.wallet()
        missions = app.repository.missions()
        onMissions(missions.isNotEmpty())
        notifications = app.repository.notifications()
    }
    val greeting = profile?.let {
        app.t(if (LocalTime.now().hour < 12) "helloHome" else "eveningHome", "name" to it.firstName)
    } ?: "NexisHub"
    val list = if (showDone) missions.filter { it.status == MissionStatus.COMPLETED } else missions.filter { it.isActive }
    val shown = 2

    TabScaffold(
        greeting,
        actions = {
            // La cloche : un point rouge quand une notification n'a pas été lue.
            IconButton(onClick = { showNotifications = true }) {
                BadgedBox(badge = { if (notifications.any { !it.read }) Badge(containerColor = Nexis.danger) }) {
                    Icon(Icons.Outlined.Notifications, contentDescription = app.t("notifications"), tint = p.ink)
                }
            }
            // Le rond du profil (initiales tant qu'il n'y a pas de photo) mène à l'onglet Profil.
            profile?.let { me ->
                IconButton(
                    onClick = { onTab(3) },
                    modifier = Modifier.padding(end = 8.dp).semantics { contentDescription = app.t("navProfile") },
                ) { InitialsAvatar(me.initials, size = 34.dp) }
            }
        },
    ) { padding ->
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(22.dp),
        ) {
            item { WalletCard(wallet) }
            item {
                Row(Modifier.fillMaxWidth()) {
                    QuickAction(Icons.Rounded.Apps, app.t("actionServices"), onPick)
                    QuickAction(Icons.Rounded.Download, app.t("actionDeposit")) { onComingSoon(app.t("actionDeposit")) }
                    QuickAction(Icons.Rounded.Upload, app.t("actionWithdraw")) { onComingSoon(app.t("actionWithdraw")) }
                    QuickAction(Icons.Rounded.History, app.t("actionHistory")) { onTab(2) }
                    QuickAction(Icons.Rounded.MoreHoriz, app.t("actionMore")) { onComingSoon(app.t("actionMore")) }
                }
            }
            if (missions.isEmpty()) {
                item {
                    Column(
                        Modifier.fillMaxWidth().nexisCard(p).padding(22.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(14.dp),
                    ) {
                        Text(app.t("firstRequestTitle"), style = title(20, color = p.ink), textAlign = TextAlign.Center)
                        Text(app.t("pickServiceHint"), style = body(15, color = p.muted), textAlign = TextAlign.Center)
                        PrimaryButton(app.t("requestService"), onPick, icon = Icons.Rounded.Add)
                    }
                }
            } else {
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(app.t("lastServices"), style = title(18, color = p.ink))
                        OngoingDoneSwitch(showDone) { showDone = it }
                        if (list.isEmpty()) {
                            Text(app.t("noMissions"), style = body(15, color = p.muted), modifier = Modifier.padding(vertical = 12.dp))
                        } else {
                            MissionList(list.take(shown), p) { flow.open(it, app) }
                            if (list.size > shown) {
                                TextButton(onClick = { onTab(1) }, modifier = Modifier.fillMaxWidth()) {
                                    Text(app.t("seeMissions", "count" to list.size.toString()), style = body(15, FontWeight.SemiBold))
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    if (showNotifications) NotificationsSheet(notifications) { showNotifications = false }
}

@Composable
private fun MissionList(missions: List<Mission>, p: NexisPalette, onOpen: (Mission) -> Unit) {
    Column(Modifier.nexisCard(p)) {
        missions.forEachIndexed { index, mission ->
            MissionRow(mission, Modifier.fillMaxWidth().clickable { onOpen(mission) }.padding(horizontal = 16.dp, vertical = 12.dp))
            if (index < missions.lastIndex) HorizontalDivider(Modifier.padding(start = 74.dp), color = p.line)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun OngoingDoneSwitch(showDone: Boolean, onChange: (Boolean) -> Unit) {
    val app = LocalApp.current
    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
        listOf(false to app.t("tabOngoing"), true to app.t("tabDone")).forEachIndexed { index, (value, label) ->
            SegmentedButton(
                selected = showDone == value,
                onClick = { onChange(value) },
                shape = SegmentedButtonDefaults.itemShape(index, 2),
                label = { Text(label, style = body(14, FontWeight.SemiBold)) },
            )
        }
    }
}

@Composable
private fun androidx.compose.foundation.layout.RowScope.QuickAction(icon: ImageVector, label: String, onClick: () -> Unit) {
    val p = LocalPalette.current
    Column(
        Modifier.weight(1f).clip(RoundedCornerShape(16.dp)).clickable(role = Role.Button, onClickLabel = label, onClick = onClick).padding(vertical = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Box(Modifier.size(54.dp).background(p.soft, RoundedCornerShape(18.dp)), contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = null, tint = p.accent, modifier = Modifier.size(22.dp))
        }
        Text(label, style = body(12, FontWeight.Medium, p.ink), textAlign = TextAlign.Center, maxLines = 2)
    }
}

/** La carte du portefeuille, partagée par l'accueil et l'onglet
 * Portefeuille : devise au choix, montants masquables, et l'explication
 * de l'argent bloqué pour les missions en cours. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WalletCard(wallet: Wallet) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var explaining by remember { mutableStateOf(false) }
    fun shown(money: Money?) = if (app.amountsHidden) "••••" else app.money(money ?: Money(0, app.walletCurrency))
    val shape = RoundedCornerShape(28.dp)
    Column(
        Modifier.fillMaxWidth().shadow(18.dp, shape, spotColor = Nexis.brand).background(Nexis.brandGradient, shape).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(app.t("available"), style = body(14, FontWeight.Medium, Color.White.copy(alpha = 0.85f)), modifier = Modifier.weight(1f))
            Row(Modifier.clip(CircleShape).background(Color.White.copy(alpha = 0.16f))) {
                for ((currency, label) in listOf(Currency.CDF to "FC", Currency.USD to "USD")) {
                    val selected = app.walletCurrency == currency
                    Text(
                        label,
                        style = body(13, FontWeight.SemiBold, if (selected) Nexis.brand else Color.White),
                        modifier = Modifier.clip(CircleShape)
                            .background(if (selected) Color.White else Color.Transparent)
                            .clickable(role = Role.Tab) { app.walletCurrency = currency }
                            .padding(horizontal = 12.dp, vertical = 6.dp),
                    )
                }
            }
            IconButton(onClick = { app.amountsHidden = !app.amountsHidden }) {
                Icon(
                    if (app.amountsHidden) Icons.Rounded.VisibilityOff else Icons.Rounded.Visibility,
                    contentDescription = if (app.amountsHidden) app.t("showAmounts") else app.t("hideAmounts"),
                    tint = Color.White,
                )
            }
        }
        Text(shown(wallet.available[app.walletCurrency]), style = title(32, color = Color.White), maxLines = 1)
        val secured = wallet.secured[app.walletCurrency]
        if (secured != null && !secured.isZero) {
            Row(
                Modifier.clip(CircleShape).background(Color.White.copy(alpha = 0.16f))
                    .clickable(onClickLabel = app.t("heldWhy")) { explaining = true }
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(Icons.Rounded.Shield, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
                Text(app.t("heldForMissions", "amount" to shown(secured)), style = body(13, FontWeight.Medium, Color.White))
                Icon(Icons.Rounded.Info, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
            }
        }
    }
    if (explaining) {
        ModalBottomSheet(onDismissRequest = { explaining = false }, containerColor = p.surface) {
            Column(Modifier.padding(horizontal = 24.dp).padding(bottom = 32.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(app.t("heldWhy"), style = title(18, color = p.ink))
                Text(app.t("heldTip"), style = body(16, color = p.ink))
                Text(app.t("walletExplanation"), style = body(14, color = p.muted))
                PrimaryButton(app.t("ok"), { explaining = false }, Modifier.padding(top = 8.dp))
            }
        }
    }
}

// Missions

/** Les notifications : la liste, ou un écran vide tant qu'il n'y en a pas. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NotificationsSheet(items: List<AppNotification>, onDismiss: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = p.bg,
    ) {
        Column(Modifier.fillMaxSize().padding(horizontal = 18.dp)) {
            Text(app.t("notifications"), style = title(24, color = p.ink), modifier = Modifier.padding(top = 4.dp, bottom = 16.dp))
            if (items.isEmpty()) {
                Column(
                    Modifier.fillMaxWidth().padding(top = 72.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    Box(Modifier.size(72.dp).clip(CircleShape).background(p.soft), contentAlignment = Alignment.Center) {
                        Icon(Icons.Outlined.Notifications, contentDescription = null, tint = p.accent, modifier = Modifier.size(34.dp))
                    }
                    Text(app.t("noMissions"), style = body(16, color = p.muted), textAlign = TextAlign.Center)
                }
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(bottom = 32.dp)) {
                    items(items, key = { it.id }) { item ->
                        Column(
                            Modifier.fillMaxWidth().nexisCard(p)
                                .background(if (item.read) Color.Transparent else p.soft, RoundedCornerShape(20.dp))
                                .padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Text(item.title, style = body(15, FontWeight.SemiBold, p.ink))
                            Text(item.message, style = body(14, color = p.muted))
                            Text(app.day(item.at), style = body(12, color = p.muted))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MissionsTab(onMissions: (Boolean) -> Unit) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    var missions by remember { mutableStateOf(emptyList<Mission>()) }
    var showDone by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(app.revision) {
        missions = app.repository.missions()
        onMissions(missions.isNotEmpty())
    }
    val list = if (showDone) missions.filter { it.status == MissionStatus.COMPLETED } else missions.filter { it.isActive }
    TabScaffold(app.t("myMissions")) { padding ->
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item { OngoingDoneSwitch(showDone) { showDone = it } }
            item {
                if (list.isEmpty()) Text(app.t("noMissions"), style = body(15, color = p.muted))
                else MissionList(list, p) { flow.open(it, app) }
            }
        }
    }
}

// Portefeuille

@Composable
private fun WalletTab() {
    val app = LocalApp.current
    val p = LocalPalette.current
    var wallet by remember { mutableStateOf(Wallet.EMPTY) }
    var movements by remember { mutableStateOf(emptyList<Movement>()) }
    LaunchedEffect(app.revision) {
        wallet = app.repository.wallet()
        movements = app.repository.movements()
    }
    TabScaffold(app.t("navWallet")) { padding ->
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item { WalletCard(wallet) }
            item { Text(app.t("recentMovements"), style = title(18, color = p.ink), modifier = Modifier.padding(top = 6.dp)) }
            item {
                if (movements.isEmpty()) {
                    Text(app.t("noMissions"), style = body(15, color = p.muted))
                } else {
                    Column(Modifier.nexisCard(p)) {
                        movements.forEachIndexed { index, movement ->
                            MovementRow(movement, app, p)
                            if (index < movements.lastIndex) HorizontalDivider(Modifier.padding(start = 70.dp), color = p.line)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MovementRow(movement: Movement, app: AppModel, p: NexisPalette) {
    val tint = when (movement.state) {
        PaymentState.SECURED -> p.accent
        PaymentState.REFUNDED, PaymentState.AVAILABLE -> Nexis.ok
        PaymentState.BLOCKED -> Nexis.danger
        else -> p.muted
    }
    val icon = when (movement.kind) {
        MovementKind.PAYMENT -> Icons.Rounded.Shield
        MovementKind.REFUND -> Icons.AutoMirrored.Rounded.Undo
        MovementKind.RELEASE -> Icons.Rounded.CheckCircle
        MovementKind.DEPOSIT -> Icons.Rounded.Download
        MovementKind.WITHDRAWAL -> Icons.Rounded.Upload
    }
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(40.dp).background(tint.copy(alpha = 0.12f), CircleShape), contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(18.dp))
        }
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Text(movement.label, style = body(15, FontWeight.SemiBold, p.ink))
            Text(listOfNotNull(app.day(movement.at), app.paymentLabel(movement.state)).joinToString(" · "), style = body(13, color = p.muted))
        }
        val positive = movement.amount.minorUnits > 0
        Text(
            if (app.amountsHidden) "•••" else (if (positive) "+" else "") + app.money(movement.amount),
            style = title(14, color = if (positive) Nexis.ok else p.ink),
        )
    }
}

// Profil

@Composable
private fun ProfileTab(onComingSoon: (String) -> Unit) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    var profile by remember { mutableStateOf<Profile?>(null) }
    var devicesCount by remember { mutableStateOf(1) }
    LaunchedEffect(app.revision) {
        profile = app.repository.profile()
        devicesCount = attempt { app.repository.devices() }?.size ?: 1
    }
    TabScaffold(app.t("navProfile"), actions = { LanguageMenu() }) { padding ->
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            profile?.let { me ->
                item {
                    Row(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        InitialsAvatar(me.initials)
                        Spacer(Modifier.width(16.dp))
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text("${me.firstName} ${me.lastName}", style = title(19, color = p.ink))
                            Text("+243 ${DrcPhone.parse(me.phone).formatted} · ${me.commune}", style = body(14, color = p.muted))
                            Text(
                                app.t(
                                    when {
                                        me.providerStatus == ProviderStatus.PENDING -> "providerPending"
                                        app.providerSpace -> "spaceProvider"
                                        else -> "clientBadge"
                                    },
                                ),
                                style = body(12, FontWeight.SemiBold, p.softInk),
                                modifier = Modifier.background(p.soft, CircleShape).padding(horizontal = 10.dp, vertical = 3.dp),
                            )
                        }
                    }
                }
            }
            if (profile?.providerStatus == ProviderStatus.PENDING) {
                item { InfoNote(app.t("providerPendingHint"), icon = Icons.Rounded.HourglassTop) }
            }
            if (profile?.isProvider == true) item { SpaceSwitch() }
            item {
                SettingsGroup(p, listOf(
                    SettingsRow(app.t("myInfo"), app.t("myInfoSub")) { flow.push(MissionRoute.ProfileInfo) },
                    SettingsRow(app.t("notifications"), app.t("notificationsSub")) { flow.push(MissionRoute.NotificationSettings) },
                    SettingsRow(app.t("myDevices"), app.plural("devicesCount", devicesCount)) { flow.push(MissionRoute.Devices) },
                    SettingsRow(app.t("securityRow"), app.t("securityRowSub")) { flow.push(MissionRoute.Security) },
                    SettingsRow(app.t("helpDisputes"), app.t("helpDisputesSub")) { flow.push(MissionRoute.Help) },
                ))
            }
            if (profile != null && profile?.providerStatus == null) {
                item {
                    SettingsGroup(p, listOf(
                        SettingsRow(app.t("becomeProvider"), app.t("becomeProviderSub")) { flow.push(MissionRoute.BecomeProvider) },
                    ))
                }
            }
            item {
                SettingsGroup(p, listOf(
                    SettingsRow(app.t("legalTerms"), null) { flow.push(MissionRoute.Legal) },
                    SettingsRow(app.t("legalPrivacy"), null) { onComingSoon(app.t("legalPrivacy")) },
                ))
            }
            item {
                TextButton(onClick = { app.signOut() }, modifier = Modifier.fillMaxWidth()) {
                    Text(app.t("signOut"), style = body(16, FontWeight.SemiBold, Nexis.danger))
                }
            }
        }
    }
}

private class SettingsRow(val heading: String, val sub: String?, val onOpen: () -> Unit)

@Composable
private fun SettingsGroup(p: NexisPalette, rows: List<SettingsRow>) {
    Column(Modifier.fillMaxWidth().nexisCard(p)) {
        rows.forEachIndexed { index, row ->
            ListItem(
                headlineContent = { Text(row.heading, style = body(16, color = p.ink)) },
                supportingContent = row.sub?.let { sub -> { Text(sub, style = body(13, color = p.muted)) } },
                trailingContent = {
                    Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, contentDescription = null, tint = p.muted)
                },
                colors = ListItemDefaults.colors(containerColor = Color.Transparent),
                modifier = Modifier.clickable(role = Role.Button, onClick = row.onOpen),
            )
            if (index < rows.lastIndex) HorizontalDivider(Modifier.padding(start = 16.dp), color = p.line)
        }
    }
}
