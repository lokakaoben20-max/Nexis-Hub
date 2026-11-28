@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package com.nexishub.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.Apps
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Group
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.MoreHoriz
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material.icons.rounded.Phone
import androidx.compose.material.icons.rounded.RadioButtonUnchecked
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.Send
import androidx.compose.material.icons.rounded.SwapHoriz
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material.icons.rounded.Upload
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.nexishub.app.AppModel
import com.nexishub.app.LocalApp
import com.nexishub.app.data.Currency
import com.nexishub.app.data.DrcPhone
import com.nexishub.app.data.Mission
import com.nexishub.app.data.MissionStatus
import com.nexishub.app.data.MobileOperator
import com.nexishub.app.data.Money
import com.nexishub.app.data.Movement
import com.nexishub.app.data.OrgMember
import com.nexishub.app.data.OrgMemberStatus
import com.nexishub.app.data.OrgRight
import com.nexishub.app.data.OrgRole
import com.nexishub.app.data.Organization
import com.nexishub.app.data.Profile
import com.nexishub.app.data.WithdrawNumber
import com.nexishub.app.ui.ChoiceRow
import com.nexishub.app.ui.FlowLoading
import com.nexishub.app.ui.FlowScaffold
import com.nexishub.app.ui.InfoNote
import com.nexishub.app.ui.InitialsAvatar
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.MissionRow
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.OperatorBadge
import com.nexishub.app.ui.OutlineButton
import com.nexishub.app.ui.PersonAvatar
import com.nexishub.app.ui.Pill
import com.nexishub.app.ui.PillTone
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.ServiceTile
import com.nexishub.app.ui.body
import com.nexishub.app.ui.clock
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.place
import com.nexishub.app.ui.slot
import com.nexishub.app.ui.tint
import com.nexishub.app.ui.title
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.ZoneId

// L'espace entreprise ouvert : changer d'espace, accueil, missions,
// portefeuille, équipe, invitations, rôles, numéros de retrait et retrait.
// Chaque rôle ne voit que ce que le serveur lui permet : l'app cache ce qui
// est interdit, le serveur le refuse de toute façon.

// Mots communs

fun AppModel.rightText(right: OrgRight): String = when (right) {
    OrgRight.SEE_MISSIONS -> t("orgRightMissions")
    OrgRight.SEE_BALANCE -> t("orgRightBalance")
    OrgRight.SEE_TEAM -> t("orgRightTeam")
    OrgRight.ASSIGN_MISSIONS -> t("orgRightAssign")
    OrgRight.MANAGE_MEMBERS -> t("orgRightMembers")
    OrgRight.MANAGE_NUMBERS -> t("orgRightNumbers")
    OrgRight.WITHDRAW -> t("orgRightWithdraw")
}

/** Ce qu'un rôle peut faire, ligne par ligne. Un intervenant a ses trois
 * phrases ; les autres rôles montrent le tableau des droits. */
fun AppModel.rightLines(role: OrgRole): List<Pair<String, Boolean>> =
    if (role == OrgRole.WORKER) {
        listOf(t("orgRightDoMissions") to true, t("orgRightOwnMissions") to true, t("orgRightNoMoney") to false)
    } else {
        OrgRight.entries.map { rightText(it) to role.can(it) }
    }

fun AppModel.roleName(role: OrgRole): String = when (role) {
    OrgRole.REPRESENTATIVE -> t("orgRoleRepresentative")
    OrgRole.MANAGER -> t("orgRoleManager")
    OrgRole.ACCOUNTANT -> t("orgRoleAccountant")
    OrgRole.WORKER -> t("orgRoleWorker")
}

fun AppModel.roleShort(role: OrgRole): String = when (role) {
    OrgRole.REPRESENTATIVE -> t("orgRoleRepShort")
    OrgRole.MANAGER -> t("orgRoleMgrShort")
    OrgRole.ACCOUNTANT -> t("orgRoleAccShort")
    OrgRole.WORKER -> t("orgRoleWrkShort")
}

/** « Jean Kalala » devient « Jean K. ». */
fun AppModel.shortPerson(name: String): String {
    val words = name.split(" ").filter { it.isNotEmpty() }
    if (words.size < 2) return name
    return "${words.first()} ${words.last().first()}."
}

/** « 99 123 4567 ». */
fun AppModel.numberText(number: String): String = DrcPhone(number).formatted

fun AppModel.memberSubtitle(member: OrgMember): String =
    if (member.role == OrgRole.WORKER && member.service != null) member.service.label(language) else roleName(member.role)

/** Le monogramme d'une entreprise : ses initiales sur le bleu Nexis. */
@Composable
fun OrgMark(name: String, size: androidx.compose.ui.unit.Dp = 44.dp) {
    val initials = Organization.shortName(name).split(" ").filter { it.isNotEmpty() }.take(2)
        .joinToString("") { it.take(1) }.uppercase()
    Box(
        Modifier.size(size).clip(RoundedCornerShape(size * 0.3f)).background(Nexis.brandGradient),
        contentAlignment = Alignment.Center,
    ) { Text(initials, style = title((size.value * 0.34f).toInt(), color = Color.White)) }
}

/** Charge une entreprise, puis dessine `content`. Tant qu'elle n'est pas
 * lue, les pictogrammes se relaient. */
@Composable
fun OrgLoader(orgId: Int, content: @Composable (Organization) -> Unit) {
    val app = LocalApp.current
    var org by remember { mutableStateOf<Organization?>(null) }
    LaunchedEffect(app.revision, orgId) { org = attempt { app.repository.organization(orgId) } }
    val shown = org
    if (shown == null) FlowLoading(app.t("orgTitle")) else content(shown)
}

@Composable
private fun SectionLabel(text: String) {
    val p = LocalPalette.current
    Text(text, style = body(13, FontWeight.SemiBold, p.muted), modifier = Modifier.padding(top = 6.dp))
}

@Composable
private fun FailedText(show: Boolean) {
    val app = LocalApp.current
    if (show) Text(app.t("orgFailed"), style = body(14, color = Nexis.danger))
}

// Changer d'espace

@Composable
fun SpacePickerSheet(onDismiss: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var profile by remember { mutableStateOf<Profile?>(null) }
    var orgs by remember { mutableStateOf(emptyList<Organization>()) }
    LaunchedEffect(Unit) {
        profile = attempt { app.repository.profile() }
        orgs = attempt { app.repository.organizations() }.orEmpty()
    }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = p.bg,
    ) {
        Column(Modifier.padding(horizontal = 18.dp).padding(bottom = 32.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(app.t("orgSwitchTitle"), style = title(20, color = p.ink), modifier = Modifier.padding(bottom = 6.dp))
            ChoiceRow(
                title = app.t("orgSwitchPersonal"), subtitle = app.t("spaceClient"),
                selected = app.orgSpaceId == null && !app.providerSpace,
                onClick = { app.openClientSpace(); onDismiss() },
                leading = { InitialsAvatar(profile?.initials.orEmpty(), size = 40.dp) },
            )
            if (profile?.isProvider == true) {
                ChoiceRow(
                    title = app.t("spaceProvider"), subtitle = app.t("orgSwitchPersonal"),
                    selected = app.orgSpaceId == null && app.providerSpace,
                    onClick = { app.openProviderSpace(); onDismiss() },
                    leading = {
                        Box(Modifier.size(40.dp).background(p.soft, CircleShape), contentAlignment = Alignment.Center) {
                            Icon(Icons.Rounded.Person, contentDescription = null, tint = p.softInk)
                        }
                    },
                )
            }
            orgs.filter { it.isOpen }.forEach { org ->
                ChoiceRow(
                    title = org.name, subtitle = app.roleName(org.myRole),
                    selected = app.orgSpaceId == org.id,
                    onClick = { app.openOrgSpace(org.id); onDismiss() },
                    leading = { OrgMark(org.name, 40.dp) },
                )
            }
        }
    }
}

// Accueil de l'espace

@Composable
fun OrgHomeTab(orgId: Int, onTab: (Int) -> Unit) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    var org by remember { mutableStateOf<Organization?>(null) }
    var missions by remember { mutableStateOf(emptyList<Mission>()) }
    var switching by remember { mutableStateOf(false) }
    LaunchedEffect(app.revision, orgId) {
        org = attempt { app.repository.organization(orgId) }
        missions = attempt { app.repository.orgMissions(orgId) }.orEmpty()
    }
    TabScaffold(
        org?.shortName ?: "NexisHub",
        actions = {
            Row(
                Modifier.padding(end = 12.dp).clip(CircleShape).background(p.soft)
                    .clickable(role = Role.Button) { switching = true }.padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(Icons.Rounded.SwapHoriz, contentDescription = null, tint = p.softInk, modifier = Modifier.size(16.dp))
                Text(app.t("orgChange"), style = body(14, FontWeight.SemiBold, p.softInk))
            }
        },
    ) { padding ->
        val shown = org
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(22.dp),
        ) {
            if (shown == null) return@LazyColumn
            if (shown.can(OrgRight.SEE_BALANCE)) {
                item { WalletCard(shown.wallet, org = true, caption = app.t("orgAvailableCaption")) }
                item {
                    Row(Modifier.fillMaxWidth()) {
                        QuickAction(Icons.Rounded.Apps, app.t("actionServices")) { flow.comingSoon = app.t("actionServices") }
                        if (shown.myRole.can(OrgRight.WITHDRAW)) {
                            QuickAction(Icons.Rounded.Upload, app.t("actionWithdraw")) { flow.push(MissionRoute.OrgWithdraw(shown.id)) }
                        }
                        QuickAction(Icons.Rounded.History, app.t("actionHistory")) { onTab(2) }
                        if (shown.can(OrgRight.SEE_TEAM)) {
                            QuickAction(Icons.Rounded.Group, app.t("orgQuickTeam")) { flow.push(MissionRoute.OrgTeam(shown.id)) }
                        }
                        QuickAction(Icons.Rounded.MoreHoriz, app.t("actionMore")) { flow.comingSoon = app.t("actionMore") }
                    }
                }
            } else {
                item { InfoNote(app.t("orgWorkerPays")) }
            }
            item {
                val list = shown.visible(missions).filter { it.isActive }
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(app.t("orgOngoing"), style = title(18, color = p.ink))
                    if (list.isEmpty()) {
                        Text(app.t("noMissions"), style = body(15, color = p.muted), modifier = Modifier.padding(vertical = 12.dp))
                    } else {
                        Column(Modifier.nexisCard(p)) {
                            list.forEachIndexed { index, mission ->
                                MissionRow(mission, Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp))
                                if (index < list.lastIndex) HorizontalDivider(Modifier.padding(start = 74.dp), color = p.line)
                            }
                        }
                    }
                }
            }
        }
    }
    if (switching) SpacePickerSheet { switching = false }
}

// Missions de l'espace

@Composable
fun OrgMissionsTab(orgId: Int) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var org by remember { mutableStateOf<Organization?>(null) }
    var missions by remember { mutableStateOf(emptyList<Mission>()) }
    var showDone by rememberSaveable { mutableStateOf(false) }
    var assigning by remember { mutableStateOf<Mission?>(null) }
    LaunchedEffect(app.revision, orgId) {
        org = attempt { app.repository.organization(orgId) }
        missions = attempt { app.repository.orgMissions(orgId) }.orEmpty()
        if (app.capture == "org-assign" && assigning == null) assigning = missions.firstOrNull { it.isActive }
    }
    val shown = org
    val seen = shown?.visible(missions) ?: missions
    val list = if (showDone) seen.filter { it.status == MissionStatus.COMPLETED } else seen.filter { it.isActive }
    val all = shown?.can(OrgRight.SEE_MISSIONS) ?: true
    TabScaffold(app.t(if (all) "orgMissionsTitle" else "myMissions")) { padding ->
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    listOf(false to app.t("tabOngoing"), true to app.t("tabDone")).forEachIndexed { index, (value, label) ->
                        SegmentedButton(
                            selected = showDone == value,
                            onClick = { showDone = value },
                            shape = SegmentedButtonDefaults.itemShape(index, 2),
                            label = { Text(label, style = body(14, FontWeight.SemiBold)) },
                        )
                    }
                }
            }
            if (list.isEmpty()) {
                item { Text(app.t("noMissions"), style = body(15, color = p.muted)) }
            }
            list.forEach { mission ->
                item(key = mission.id) {
                    Column(Modifier.fillMaxWidth().nexisCard(p).padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        if (!all) {
                            WorkerMissionRow(mission, shown?.shortName.orEmpty())
                        } else {
                            MissionRow(mission, Modifier.fillMaxWidth())
                            if (shown != null && shown.can(OrgRight.ASSIGN_MISSIONS) && mission.isActive) {
                                AssignLine(mission, shown) { assigning = mission }
                            }
                        }
                    }
                }
            }
            if (!all) item { InfoNote(app.t("orgMineOnly"), icon = Icons.Rounded.Person) }
            if (shown != null && !shown.can(OrgRight.SEE_BALANCE)) item { InfoNote(app.t("orgWorkerPays")) }
        }
    }
    val target = assigning
    if (target != null && shown != null) OrgAssignSheet(shown, target) { assigning = null }
}

/** « Intervenants : Jean K., Paul I. » ; un toucher ouvre le choix. */
@Composable
private fun AssignLine(mission: Mission, org: Organization, onOpen: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val names = org.assignments[mission.id].orEmpty()
        .mapNotNull { id -> org.members.firstOrNull { it.id == id }?.name }
        .map { app.shortPerson(it) }
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(p.soft)
            .clickable(role = Role.Button, onClick = onOpen).padding(horizontal = 12.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(Icons.Rounded.Group, contentDescription = null, tint = p.softInk, modifier = Modifier.size(16.dp))
        Text(
            if (names.isEmpty()) app.t("orgAssignNone") else app.t("orgAssignedLine", "names" to names.joinToString(", ")),
            style = body(13, FontWeight.Medium, p.softInk), modifier = Modifier.weight(1f), maxLines = 2,
        )
        Text(app.t("orgAssignAction"), style = body(13, FontWeight.Bold, p.softInk))
    }
}

/** La mission d'un intervenant : le service, l'état et le créneau. */
@Composable
private fun WorkerMissionRow(mission: Mission, orgName: String) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val at = mission.at
    val whenText = if (at == null) {
        orgName
    } else {
        val today = at.atZone(ZoneId.systemDefault()).toLocalDate() == LocalDate.now()
        (if (today) "${app.t("today")} ${app.clock(at)}" else app.slot(at, capital = true)) + " · " + orgName
    }
    val state = when (mission.status) {
        MissionStatus.IN_PROGRESS -> "tabOngoing"
        MissionStatus.COMPLETED -> "tabDone"
        else -> "orgUpcoming"
    }
    Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        ServiceTile(mission, size = 44.dp)
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(app.place(mission), style = body(16, FontWeight.SemiBold, p.ink))
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Box(Modifier.size(7.dp).background(mission.status.tint(p), CircleShape))
                Text(app.t(state), style = body(13, FontWeight.Medium, mission.status.tint(p)))
            }
            Text(whenText, style = body(13, color = p.muted))
        }
    }
}

/** Choisit qui va sur une mission. Plusieurs personnes possibles, toutes
 * vérifiées ; le client voit le nom de chacune. */
@Composable
private fun OrgAssignSheet(org: Organization, mission: Mission, onDismiss: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var picked by remember { mutableStateOf(org.assignments[mission.id].orEmpty().toSet()) }
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val candidates = org.members.filter { it.role == OrgRole.WORKER || it.service != null }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = p.bg,
    ) {
        Column(
            Modifier.padding(horizontal = 18.dp).padding(bottom = 28.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text(app.t("orgAssignTitle"), style = title(20, color = p.ink))
            Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(app.place(mission), style = body(16, FontWeight.Bold, p.ink))
                Text(app.t("orgAssignWho"), style = body(13, color = p.muted))
            }
            Column(Modifier.nexisCard(p)) {
                candidates.forEachIndexed { index, member ->
                    val ready = member.status == OrgMemberStatus.VERIFIED
                    val on = member.id in picked
                    Row(
                        Modifier.fillMaxWidth()
                            .clickable(enabled = ready, role = Role.Checkbox) { picked = if (on) picked - member.id else picked + member.id }
                            .padding(horizontal = 14.dp, vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        PersonAvatar(member.initials, member.color, 44.dp)
                        Column(Modifier.weight(1f)) {
                            Text(member.name, style = body(15, FontWeight.Bold, if (ready) p.ink else p.muted), maxLines = 1)
                            Text(app.memberSubtitle(member), style = body(13, color = p.muted), maxLines = 1)
                        }
                        if (ready) {
                            Icon(
                                if (on) Icons.Rounded.CheckCircle else Icons.Rounded.RadioButtonUnchecked,
                                contentDescription = null, tint = if (on) p.accent else p.muted,
                            )
                        } else {
                            Pill(PillTone.WARN, app.t("orgMemberToVerify"))
                        }
                    }
                    if (index < candidates.lastIndex) HorizontalDivider(Modifier.padding(start = 70.dp), color = p.line)
                }
            }
            InfoNote(app.t("orgAssignHint"), icon = Icons.Rounded.Group)
            InfoNote(app.t("orgAssignOnlyVerified"), icon = Icons.Rounded.VerifiedUser)
            FailedText(failed)
            PrimaryButton(app.t("orgAssignSave"), {
                scope.launch {
                    busy = true
                    failed = false
                    try {
                        app.repository.assignMembers(org.id, mission.id, org.members.map { it.id }.filter { it in picked })
                        app.dataChanged()
                        onDismiss()
                    } catch (cancel: kotlinx.coroutines.CancellationException) {
                        throw cancel
                    } catch (_: Exception) {
                        failed = true
                    }
                    busy = false
                }
            }, enabled = picked.isNotEmpty(), loading = busy)
        }
    }
}

// Portefeuille de l'espace

@Composable
fun OrgWalletTab(orgId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    var org by remember { mutableStateOf<Organization?>(null) }
    var movements by remember { mutableStateOf(emptyList<Movement>()) }
    LaunchedEffect(app.revision, orgId) {
        org = attempt { app.repository.organization(orgId) }
        movements = attempt { app.repository.orgMovements(orgId) }.orEmpty()
    }
    TabScaffold(app.t("navWallet")) { padding ->
        val shown = org
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            if (shown == null) return@LazyColumn
            if (!shown.can(OrgRight.SEE_BALANCE)) {
                item { InfoNote(app.t("orgWalletLocked"), icon = Icons.Rounded.Lock) }
                return@LazyColumn
            }
            item { WalletCard(shown.wallet, org = true, caption = app.t("orgAvailableCaption")) }
            item {
                if (shown.myRole.can(OrgRight.WITHDRAW)) {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        PrimaryButton(app.t("orgWithdrawCta"), { flow.push(MissionRoute.OrgWithdraw(shown.id)) }, icon = Icons.Rounded.Upload)
                        OutlineButton(app.t("orgNumbersTitle"), { flow.push(MissionRoute.OrgNumbers(shown.id)) })
                    }
                } else {
                    InfoNote(app.t("orgWalletRepOnly"), icon = Icons.Rounded.Lock)
                }
            }
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

// L'équipe

@Composable
fun OrgTeamScreen(orgId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    OrgLoader(orgId) { org ->
        FlowScaffold(
            app.t("orgQuickTeam"), onBack = flow::back,
            bottom = {
                if (org.myRole.can(OrgRight.MANAGE_MEMBERS)) {
                    PrimaryButton(app.t("orgInviteAction"), { flow.push(MissionRoute.OrgInvite(org.id)) }, icon = Icons.Rounded.Person)
                }
                OutlineButton(app.t("orgRolesLink"), { flow.push(MissionRoute.OrgRoles) })
            },
        ) {
            if (org.can(OrgRight.SEE_TEAM)) {
                Column(Modifier.fillMaxWidth().nexisCard(p)) {
                    org.members.forEachIndexed { index, member ->
                        val editable = org.myRole.can(OrgRight.MANAGE_MEMBERS) && member.role != OrgRole.REPRESENTATIVE
                        Row(
                            Modifier.fillMaxWidth()
                                .then(if (editable) Modifier.clickable(role = Role.Button) { flow.push(MissionRoute.OrgMemberRights(org.id, member.id)) } else Modifier)
                                .padding(horizontal = 14.dp, vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            PersonAvatar(member.initials, member.color, 44.dp)
                            Column(Modifier.weight(1f)) {
                                Text(member.name, style = body(15, FontWeight.Bold, p.ink), maxLines = 1)
                                Text(app.memberSubtitle(member), style = body(13, color = p.muted), maxLines = 1)
                            }
                            Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(5.dp)) {
                                if (member.role == OrgRole.REPRESENTATIVE) Pill(PillTone.INFO, app.t("orgRoleRepresentative"))
                                if (member.role != OrgRole.REPRESENTATIVE || member.status != OrgMemberStatus.VERIFIED) {
                                    when (member.status) {
                                        OrgMemberStatus.VERIFIED -> Pill(PillTone.OK, app.t("orgMemberVerified"), Icons.Rounded.VerifiedUser)
                                        OrgMemberStatus.TO_VERIFY -> Pill(PillTone.WARN, app.t("orgMemberToVerify"))
                                        OrgMemberStatus.INVITED -> Pill(PillTone.WAIT, app.t("orgMemberInvited"), Icons.Rounded.Schedule)
                                    }
                                }
                            }
                            if (editable) Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, contentDescription = null, tint = p.muted)
                        }
                        if (index < org.members.lastIndex) HorizontalDivider(Modifier.padding(start = 70.dp), color = p.line)
                    }
                }
                InfoNote(app.t("orgTeamHint"), icon = Icons.Rounded.VerifiedUser)
            } else {
                InfoNote(app.t("orgTeamHidden"), icon = Icons.Rounded.Lock)
            }
        }
    }
}

// Inviter quelqu'un

@Composable
fun OrgInviteScreen(orgId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var phone by remember { mutableStateOf(if (app.capture == "org-invite") "82 000 1122" else "") }
    var role by remember { mutableStateOf(OrgRole.WORKER) }
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val ready = DrcPhone.parse(phone).isValid
    FlowScaffold(
        app.t("orgInviteAction"), onBack = flow::back,
        bottom = {
            PrimaryButton(app.t("orgInviteSend"), {
                scope.launch {
                    busy = true
                    failed = false
                    try {
                        app.repository.inviteMember(orgId, phone, role)
                        app.dataChanged()
                        flow.back()
                        flow.say(app.t("orgInviteSent"))
                    } catch (cancel: kotlinx.coroutines.CancellationException) {
                        throw cancel
                    } catch (_: Exception) {
                        failed = true
                    }
                    busy = false
                }
            }, enabled = ready, icon = Icons.Rounded.Send, loading = busy)
            OutlineButton(app.t("cancel"), flow::back, enabled = !busy)
        },
    ) {
        OutlinedTextField(
            value = phone, onValueChange = { phone = it.filter { c -> c.isDigit() || c == ' ' }.take(14) },
            label = { Text(app.t("phone")) }, prefix = { Text("+243 ") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth(),
        )
        SectionLabel(app.t("orgInviteRole"))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OrgRole.invitable.forEach { item ->
                androidx.compose.material3.FilterChip(
                    selected = role == item, onClick = { role = item },
                    label = { Text(app.roleName(item), style = body(14, FontWeight.SemiBold)) },
                )
            }
        }
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(app.t("orgCanTitle"), style = body(15, FontWeight.Bold, p.ink))
            app.rightLines(role).forEach { (text, allowed) ->
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Icon(
                        if (allowed) Icons.Rounded.CheckCircle else Icons.Rounded.Lock, contentDescription = null,
                        tint = if (allowed) Nexis.ok else p.muted, modifier = Modifier.size(20.dp),
                    )
                    Text(text, style = body(14, color = if (allowed) p.ink else p.muted))
                }
            }
        }
        if (role == OrgRole.MANAGER) InfoNote(app.t("orgRolesManagerNote"))
        FailedText(failed)
    }
}

// Rôles et droits

@Composable
fun OrgRolesScreen() {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    FlowScaffold(app.t("orgRolesTitle"), onBack = flow::back) {
        Text(app.t("orgRolesHint"), style = body(15, color = p.muted))
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp)) {
            Row(Modifier.fillMaxWidth().padding(bottom = 8.dp)) {
                Spacer(Modifier.weight(1f))
                OrgRole.entries.forEach { role ->
                    Text(app.roleShort(role), style = body(11, FontWeight.Bold, p.muted), modifier = Modifier.width(54.dp), textAlign = TextAlign.Center)
                }
            }
            OrgRight.entries.forEach { right ->
                HorizontalDivider(color = p.line)
                Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(app.rightText(right), style = body(14, FontWeight.Medium, p.ink), modifier = Modifier.weight(1f))
                    OrgRole.entries.forEach { role ->
                        Box(Modifier.width(54.dp), contentAlignment = Alignment.Center) {
                            if (role.can(right)) {
                                Icon(Icons.Rounded.CheckCircle, contentDescription = null, tint = p.accent)
                            } else {
                                Text("–", style = body(17, FontWeight.SemiBold, p.muted))
                            }
                        }
                    }
                }
            }
        }
        InfoNote(app.t("orgRolesManagerNote"))
        InfoNote(app.t("orgRolesCustomHint"), icon = Icons.Rounded.Tune)
    }
}

// Droits d'une personne

/** Ce que le représentant laisse voir et faire à une personne de l'équipe.
 * On part des droits proposés pour son rôle, puis on les adapte. */
@Composable
fun OrgMemberScreen(orgId: Int, memberId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    OrgLoader(orgId) { org ->
        val member = org.members.firstOrNull { it.id == memberId }
        if (member == null) {
            FlowLoading(app.t("orgMemberRightsTitle"))
            return@OrgLoader
        }
        val current = member.effectiveRights.filter { it.isEditable }.toSet()
        var rights by remember(member) { mutableStateOf(current) }
        var busy by remember { mutableStateOf(false) }
        var failed by remember { mutableStateOf(false) }
        val editable = org.myRole.can(OrgRight.MANAGE_MEMBERS) && member.role != OrgRole.REPRESENTATIVE
        FlowScaffold(
            app.t("orgMemberRightsTitle"), onBack = flow::back,
            bottom = if (editable) {
                {
                    PrimaryButton(app.t("orgAssignSave"), {
                        scope.launch {
                            busy = true
                            failed = false
                            try {
                                app.repository.setMemberRights(org.id, member.id, rights)
                                app.dataChanged()
                                flow.back()
                                flow.say(app.t("orgMemberSaved"))
                            } catch (cancel: kotlinx.coroutines.CancellationException) {
                                throw cancel
                            } catch (_: Exception) {
                                failed = true
                            }
                            busy = false
                        }
                    }, enabled = rights != current, loading = busy)
                    OutlineButton(app.t("orgMemberDefaults"), { rights = member.role.defaultRights.filter { it.isEditable }.toSet() }, enabled = !busy)
                }
            } else {
                null
            },
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                PersonAvatar(member.initials, member.color, 52.dp)
                Column {
                    Text(member.name, style = title(17, color = p.ink), maxLines = 1)
                    Text(app.memberSubtitle(member), style = body(13, color = p.muted))
                }
            }
            Text(app.t("orgMemberRightsHint", "name" to app.shortPerson(member.name)), style = body(14, color = p.muted))
            Column(Modifier.fillMaxWidth().nexisCard(p)) {
                OrgRight.entries.forEachIndexed { index, right ->
                    if (right.isEditable) {
                        Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(app.rightText(right), style = body(15, FontWeight.Medium, p.ink), modifier = Modifier.weight(1f))
                            Switch(
                                checked = right in rights, enabled = editable && !busy,
                                onCheckedChange = { on -> rights = if (on) rights + right else rights - right },
                            )
                        }
                    } else {
                        Row(
                            Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            Icon(Icons.Rounded.Lock, contentDescription = null, tint = p.muted, modifier = Modifier.size(16.dp))
                            Column {
                                Text(app.rightText(right), style = body(15, FontWeight.Medium, p.muted))
                                Text(app.t("orgMemberFixed"), style = body(12, color = p.muted))
                            }
                        }
                    }
                    if (index < OrgRight.entries.lastIndex) HorizontalDivider(Modifier.padding(start = 14.dp), color = p.line)
                }
            }
            FailedText(failed)
        }
    }
}

// Numéros de retrait

@Composable
fun OrgNumbersScreen(orgId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    OrgLoader(orgId) { org ->
        FlowScaffold(
            app.t("orgNumbersTitle"), onBack = flow::back,
            bottom = {
                if (org.myRole.can(OrgRight.MANAGE_NUMBERS)) {
                    if (org.numbers.size < 4) {
                        PrimaryButton(app.t("orgNumberAdd"), { flow.push(MissionRoute.OrgNumberAdd(org.id)) }, icon = Icons.Rounded.Phone)
                    } else {
                        Text(app.t("orgNumberLimit"), style = body(13, color = p.muted))
                    }
                }
            },
        ) {
            Text(app.t("orgNumbersHint"), style = body(15, color = p.muted))
            Column(Modifier.fillMaxWidth().nexisCard(p)) {
                org.numbers.forEachIndexed { index, number ->
                    Row(
                        Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        OperatorBadge(number.operator)
                        Column(Modifier.weight(1f)) {
                            Text(number.operator.displayName, style = body(15, FontWeight.Bold, p.ink))
                            Text(app.t("orgNumberMerchant", "number" to app.numberText(number.number)), style = body(13, color = p.muted))
                        }
                        if (number.isActive()) {
                            Pill(PillTone.OK, app.t("orgNumberActive"), Icons.Rounded.Check)
                        } else {
                            Pill(PillTone.WAIT, app.t("orgNumberWaiting", "hours" to number.hoursLeft().toString()), Icons.Rounded.Schedule)
                        }
                    }
                    if (index < org.numbers.lastIndex) HorizontalDivider(Modifier.padding(start = 76.dp), color = p.line)
                }
            }
            InfoNote(app.t("orgNumbersNote"), icon = Icons.Rounded.Schedule)
        }
    }
}

/** Ajoute un numéro marchand : choisir l'opérateur, taper le numéro, puis
 * confirmer avec le code ou l'empreinte. Le numéro attend 72 h. */
@Composable
fun OrgNumberAddScreen(orgId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val scope = rememberCoroutineScope()
    var operator by remember { mutableStateOf(MobileOperator.AIRTEL) }
    var number by remember { mutableStateOf(if (app.capture == "org-number-add") "99 123 4567" else "") }
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val parsed = DrcPhone.parse(number)
    FlowScaffold(
        app.t("orgNumberAddTitle"), onBack = flow::back,
        bottom = {
            PrimaryButton(app.t("orgNumberAdd"), {
                scope.launch {
                    busy = true
                    failed = false
                    // Ajouter un numéro de retrait : code NexisHub ou empreinte d'abord.
                    if (!app.confirmMoneyOut(app.t("orgNumberGuard", "number" to "+243 ${parsed.formatted}"))) {
                        busy = false
                        return@launch
                    }
                    try {
                        app.repository.addWithdrawNumber(orgId, operator, parsed.digits)
                        app.dataChanged()
                        flow.back()
                        flow.say(app.t("orgNumberDone"))
                    } catch (cancel: kotlinx.coroutines.CancellationException) {
                        throw cancel
                    } catch (_: Exception) {
                        failed = true
                    }
                    busy = false
                }
            }, enabled = parsed.isValid, loading = busy)
        },
    ) {
        SectionLabel(app.t("orgNumberOperator"))
        MobileOperator.entries.forEach { item ->
            ChoiceRow(
                title = item.displayName, selected = operator == item, onClick = { operator = item },
                leading = { OperatorBadge(item) },
            )
        }
        OutlinedTextField(
            value = number, onValueChange = { number = it.filter { c -> c.isDigit() || c == ' ' }.take(14) },
            label = { Text(app.t("phone")) }, prefix = { Text("+243 ") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth(),
        )
        if (number.isNotEmpty() && !parsed.isValid && parsed.isComplete) {
            Text(app.t("orgNumberInvalid"), style = body(14, color = Nexis.danger))
        }
        InfoNote(app.t("orgNumbersNote"), icon = Icons.Rounded.Schedule)
        FailedText(failed)
    }
}

// Retirer de l'argent

@Composable
fun OrgWithdrawScreen(orgId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    OrgLoader(orgId) { org ->
        var currency by remember { mutableStateOf(Currency.CDF) }
        var amountText by remember { mutableStateOf(if (app.capture == "org-withdraw") "500 000" else "") }
        val usable = org.numbers.filter { it.isActive() }
        var chosen by remember { mutableStateOf(usable.firstOrNull()?.id) }
        var busy by remember { mutableStateOf(false) }
        var failed by remember { mutableStateOf(false) }
        val amount = PriceInput.parse(amountText, currency)
        FlowScaffold(
            app.t("actionWithdraw"), onBack = flow::back,
            bottom = {
                PrimaryButton(app.t("orgWithdrawGo", "amount" to (amount?.let { app.money(it) } ?: "")), {
                    val money = amount ?: return@PrimaryButton
                    val number = usable.firstOrNull { it.id == chosen } ?: return@PrimaryButton
                    scope.launch {
                        busy = true
                        failed = false
                        // Une sortie d'argent : code NexisHub ou empreinte d'abord.
                        val reason = app.t(
                            "orgWithdrawGuard", "amount" to app.money(money), "name" to org.shortName,
                            "operator" to number.operator.displayName,
                        )
                        if (!app.confirmMoneyOut(reason)) {
                            busy = false
                            return@launch
                        }
                        try {
                            app.repository.requestOrgWithdrawal(org.id, money, number.id)
                            app.dataChanged()
                            flow.back()
                            flow.say(app.t("orgWithdrawDone", "amount" to app.money(money)))
                        } catch (cancel: kotlinx.coroutines.CancellationException) {
                            throw cancel
                        } catch (_: Exception) {
                            failed = true
                        }
                        busy = false
                    }
                }, enabled = amount != null && chosen != null, loading = busy)
            },
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(app.t("orgWithdrawAvail"), style = body(14, color = p.muted))
                Text(app.money(org.wallet.available[currency] ?: Money(0, currency)), style = title(26, color = p.ink))
            }
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf(Currency.CDF to "FC", Currency.USD to "USD").forEachIndexed { index, (value, label) ->
                    SegmentedButton(
                        selected = currency == value,
                        onClick = { currency = value; amountText = "" },
                        shape = SegmentedButtonDefaults.itemShape(index, 2),
                        label = { Text(label, style = body(14, FontWeight.SemiBold)) },
                    )
                }
            }
            OutlinedTextField(
                value = amountText, onValueChange = { amountText = PriceInput.typed(it, currency) },
                label = { Text(app.t("orgWithdrawAmount")) }, singleLine = true,
                suffix = { Text(if (currency == Currency.CDF) "FC" else "USD") },
                keyboardOptions = KeyboardOptions(keyboardType = if (currency == Currency.USD) KeyboardType.Decimal else KeyboardType.Number),
                shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth(),
            )
            SectionLabel(app.t("orgWithdrawTo"))
            if (usable.isEmpty()) InfoNote(app.t("orgWithdrawNoNumber"), icon = Icons.Rounded.Schedule)
            usable.forEach { number: WithdrawNumber ->
                ChoiceRow(
                    title = number.operator.displayName,
                    subtitle = app.t("orgNumberMerchant", "number" to app.numberText(number.number)),
                    selected = chosen == number.id, onClick = { chosen = number.id },
                    leading = { OperatorBadge(number.operator) },
                )
            }
            InfoNote(app.t("orgWithdrawConfirm"), icon = Icons.Rounded.Lock)
            FailedText(failed)
        }
    }
}

// Profil de l'espace

/** Le 4e onglet de l'espace entreprise : l'entreprise elle-même
 * (représentant, e-mail), son équipe, ses numéros, À propos, et le retour
 * au compte personnel. */
@Composable
fun OrgProfileTab(orgId: Int) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    var org by remember { mutableStateOf<Organization?>(null) }
    var switching by remember { mutableStateOf(false) }
    LaunchedEffect(app.revision, orgId) { org = attempt { app.repository.organization(orgId) } }
    TabScaffold(app.t("orgProfileCompany")) { padding ->
        val shown = org
        LazyColumn(
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = padding.calculateTopPadding(), bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            if (shown == null) return@LazyColumn
            item {
                Row(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    OrgMark(shown.name, 64.dp)
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(shown.name, style = title(18, color = p.ink))
                        Text("RCCM ${shown.rccm}", style = body(13, color = p.muted))
                        Text(
                            app.t("orgSpaceLabel"),
                            style = body(12, FontWeight.SemiBold, Color.White),
                            modifier = Modifier.background(Nexis.navy, CircleShape).padding(horizontal = 10.dp, vertical = 3.dp),
                        )
                    }
                }
            }
            item {
                Column(Modifier.fillMaxWidth().nexisCard(p).padding(horizontal = 16.dp, vertical = 6.dp)) {
                    InfoLine(app.t("orgProfileRep"), shown.representative)
                    if (shown.email.isNotEmpty()) InfoLine(app.t("orgProfileEmail"), shown.email)
                }
            }
            item {
                val rows = buildList {
                    if (shown.can(OrgRight.SEE_TEAM)) {
                        add(Triple(app.t("orgQuickTeam"), app.roleName(shown.myRole)) { flow.push(MissionRoute.OrgTeam(shown.id)) })
                    }
                    if (shown.myRole.can(OrgRight.MANAGE_NUMBERS)) {
                        add(Triple(app.t("orgNumbersTitle"), null as String?) { flow.push(MissionRoute.OrgNumbers(shown.id)) })
                    }
                    add(Triple(app.t("orgRolesTitle"), null as String?) { flow.push(MissionRoute.OrgRoles) })
                }
                Column(Modifier.fillMaxWidth().nexisCard(p)) {
                    rows.forEachIndexed { index, (heading, sub, action) ->
                        if (index > 0) HorizontalDivider(Modifier.padding(start = 16.dp), color = p.line)
                        OrgRow(heading, sub, action)
                    }
                }
            }
            item {
                Column(Modifier.fillMaxWidth().nexisCard(p)) {
                    OrgRow(app.t("aboutRow"), app.t("aboutRowSub")) { flow.push(MissionRoute.About) }
                }
            }
            item {
                Column(Modifier.fillMaxWidth().nexisCard(p)) {
                    OrgRow(app.t("orgSwitchRow"), null) { switching = true }
                    HorizontalDivider(Modifier.padding(start = 16.dp), color = p.line)
                    OrgRow(app.t("orgBackPersonal"), null) { app.openClientSpace() }
                }
            }
        }
    }
    if (switching) SpacePickerSheet { switching = false }
}

@Composable
private fun InfoLine(label: String, value: String) {
    val p = LocalPalette.current
    Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = body(14, color = p.muted))
        Spacer(Modifier.weight(1f))
        Text(value, style = body(15, FontWeight.Medium, p.ink), textAlign = TextAlign.End)
    }
}

@Composable
private fun OrgRow(heading: String, sub: String?, onOpen: () -> Unit) {
    val p = LocalPalette.current
    ListItem(
        headlineContent = { Text(heading, style = body(16, color = p.ink)) },
        supportingContent = sub?.let { text -> { Text(text, style = body(13, color = p.muted)) } },
        trailingContent = { Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, contentDescription = null, tint = p.muted) },
        colors = ListItemDefaults.colors(containerColor = Color.Transparent),
        modifier = Modifier.clickable(role = Role.Button, onClick = onOpen),
    )
}

// À propos (particuliers et entreprises)

@Composable
fun AboutScreen() {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val context = androidx.compose.ui.platform.LocalContext.current
    val version = remember {
        val info = runCatching { context.packageManager.getPackageInfo(context.packageName, 0) }.getOrNull()
        val code = info?.let { androidx.core.content.pm.PackageInfoCompat.getLongVersionCode(it) } ?: 1L
        "${info?.versionName ?: "1.0"} ($code)"
    }
    FlowScaffold(app.t("aboutRow"), onBack = flow::back) {
        Column(
            Modifier.fillMaxWidth().nexisCard(p).padding(vertical = 22.dp, horizontal = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("NexisHub", style = title(30, color = p.ink))
            Text(app.t("slogan"), style = body(15, FontWeight.Medium, p.muted), textAlign = TextAlign.Center)
            Pill(PillTone.INFO, app.t("aboutVersion", "version" to version))
        }
        Text(app.t("aboutText"), style = body(15, color = p.muted))
        Column(Modifier.fillMaxWidth().nexisCard(p)) {
            OrgRow(app.t("legalTerms"), null) { flow.push(MissionRoute.Legal) }
            HorizontalDivider(Modifier.padding(start = 16.dp), color = p.line)
            OrgRow(app.t("legalPrivacy"), null) { flow.comingSoon = app.t("legalPrivacy") }
        }
    }
}
