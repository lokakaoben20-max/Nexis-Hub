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
import androidx.compose.material.icons.automirrored.rounded.ListAlt
import androidx.compose.material.icons.outlined.AccountBalanceWallet
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.Home
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

    val items = listOf(
        Triple(app.t("navHome"), Icons.Rounded.Home, Icons.Outlined.Home),
        Triple(app.t("navMissions"), Icons.AutoMirrored.Rounded.ListAlt, Icons.AutoMirrored.Rounded.ListAlt),
        Triple(app.t("navWallet"), Icons.Rounded.AccountBalanceWallet, Icons.Outlined.AccountBalanceWallet),
        Triple(app.t("navProfile"), Icons.Rounded.AccountCircle, Icons.Outlined.AccountCircle),
    )
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
            if (tab <= 1) {
                ExtendedFloatingActionButton(
                    onClick = { picking = true },
                    icon = { Icon(Icons.Rounded.Add, contentDescription = null) },
                    text = { Text(app.t("requestService"), style = body(15, FontWeight.SemiBold)) },
                    containerColor = Nexis.brand,
                    contentColor = Color.White,
                    shape = RoundedCornerShape(20.dp),
                )
            }
        },
    ) { padding ->
        Box(Modifier.padding(bottom = padding.calculateBottomPadding())) {
            when (tab) {
                0 -> HomeTab(onPick = { picking = true }, onTab = { tab = it }, onComingSoon = { comingSoon = it })
                1 -> MissionsTab(onComingSoon = { comingSoon = it })
                2 -> WalletTab()
                else -> ProfileTab(onComingSoon = { comingSoon = it })
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
private fun HomeTab(onPick: () -> Unit, onTab: (Int) -> Unit, onComingSoon: (String) -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var profile by remember { mutableStateOf<Profile?>(null) }
    var wallet by remember { mutableStateOf(Wallet.EMPTY) }
    var missions by remember { mutableStateOf(emptyList<Mission>()) }
    var showDone by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(app.revision) {
        profile = app.repository.profile()
        wallet = app.repository.wallet()
        missions = app.repository.missions()
    }
    val greeting = profile?.let {
        app.t(if (LocalTime.now().hour < 12) "helloHome" else "eveningHome", "name" to it.firstName)
    } ?: "Nexis Hub"
    val list = if (showDone) missions.filter { it.status == MissionStatus.COMPLETED } else missions.filter { it.isActive }
    val shown = 2

    TabScaffold(greeting) { padding ->
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
                            MissionList(list.take(shown), p) { onComingSoon(app.t("followMission")) }
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

@Composable
private fun MissionsTab(onComingSoon: (String) -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var missions by remember { mutableStateOf(emptyList<Mission>()) }
    var showDone by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(app.revision) { missions = app.repository.missions() }
    val list = if (showDone) missions.filter { it.status == MissionStatus.COMPLETED } else missions.filter { it.isActive }
    TabScaffold(app.t("myMissions")) { padding ->
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item { OngoingDoneSwitch(showDone) { showDone = it } }
            item {
                if (list.isEmpty()) Text(app.t("noMissions"), style = body(15, color = p.muted))
                else MissionList(list, p) { onComingSoon(app.t("followMission")) }
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
    val p = LocalPalette.current
    var profile by remember { mutableStateOf<Profile?>(null) }
    LaunchedEffect(app.revision) { profile = app.repository.profile() }
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
                                app.t("clientBadge"), style = body(12, FontWeight.SemiBold, p.softInk),
                                modifier = Modifier.background(p.soft, CircleShape).padding(horizontal = 10.dp, vertical = 3.dp),
                            )
                        }
                    }
                }
            }
            item {
                SettingsGroup(p, listOf(
                    app.t("myInfo") to app.t("myInfoSub"),
                    app.t("notifications") to app.t("notificationsSub"),
                    app.t("myDevices") to app.plural("devicesCount", 1),
                    app.t("helpDisputes") to app.t("helpDisputesSub"),
                ), onComingSoon)
            }
            item { SettingsGroup(p, listOf(app.t("becomeProvider") to app.t("becomeProviderSub")), onComingSoon) }
            item { SettingsGroup(p, listOf(app.t("legalTerms") to null, app.t("legalPrivacy") to null), onComingSoon) }
            item {
                TextButton(onClick = { app.signOut() }, modifier = Modifier.fillMaxWidth()) {
                    Text(app.t("signOut"), style = body(16, FontWeight.SemiBold, Nexis.danger))
                }
            }
        }
    }
}

@Composable
private fun SettingsGroup(p: NexisPalette, rows: List<Pair<String, String?>>, onOpen: (String) -> Unit) {
    Column(Modifier.fillMaxWidth().nexisCard(p)) {
        rows.forEachIndexed { index, (heading, sub) ->
            ListItem(
                headlineContent = { Text(heading, style = body(16, color = p.ink)) },
                supportingContent = if (sub != null) {
                    { Text(sub, style = body(13, color = p.muted)) }
                } else {
                    null
                },
                colors = ListItemDefaults.colors(containerColor = Color.Transparent),
                modifier = Modifier.clickable { onOpen(heading) },
            )
            if (index < rows.lastIndex) HorizontalDivider(Modifier.padding(start = 16.dp), color = p.line)
        }
    }
}
