@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package com.nexishub.app.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Description
import androidx.compose.material.icons.rounded.Group
import androidx.compose.material.icons.rounded.HourglassTop
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material.icons.rounded.Phone
import androidx.compose.material.icons.rounded.PersonAdd
import androidx.compose.material.icons.rounded.RadioButtonUnchecked
import androidx.compose.material.icons.rounded.Receipt
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material.icons.rounded.Warning
import androidx.compose.material.icons.rounded.AccountBalanceWallet
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.nexishub.app.AppModel
import com.nexishub.app.LocalApp
import com.nexishub.app.data.DrcPhone
import com.nexishub.app.data.LegalDocumentKey
import com.nexishub.app.data.OrgActivity
import com.nexishub.app.data.OrgDemo
import com.nexishub.app.data.OrgDocKind
import com.nexishub.app.data.OrgDocState
import com.nexishub.app.data.OrgDraft
import com.nexishub.app.data.OrgFunction
import com.nexishub.app.data.OrgLegalForm
import com.nexishub.app.data.OrgStatus
import com.nexishub.app.data.Organization
import com.nexishub.app.data.Profile
import com.nexishub.app.ui.ChoiceRow
import com.nexishub.app.ui.FlowScaffold
import com.nexishub.app.ui.InfoNote
import com.nexishub.app.ui.InitialsAvatar
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.NoteKind
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.OutlineButton
import com.nexishub.app.ui.Pill
import com.nexishub.app.ui.PillTone
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.StepItem
import com.nexishub.app.ui.StepList
import com.nexishub.app.ui.StepState
import com.nexishub.app.ui.body
import com.nexishub.app.ui.clock
import com.nexishub.app.ui.day
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.pick
import com.nexishub.app.ui.title
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import java.time.Instant

// Espace entreprise : création en quatre étapes, puis suivi de la demande
// (envoyée, correction demandée, validée). Mêmes composants que « Devenir
// prestataire ». L'identité ne se vérifie qu'une fois par personne : une
// personne déjà vérifiée n'a rien de plus à envoyer. Les documents sont
// simulés dans l'aperçu ; le serveur validera chaque pièce.

private const val ORG_STEPS = 5

private fun AppModel.functionName(function: OrgFunction): String = when (function) {
    OrgFunction.MANAGER -> t("orgFnManager")
    OrgFunction.DIRECTOR -> t("orgFnDirector")
    OrgFunction.OWNER -> t("orgFnOwner")
    OrgFunction.ACCOUNTANT -> t("orgFnAccountant")
    OrgFunction.OTHER -> t("orgFormOther")
}

private fun AppModel.formName(form: OrgLegalForm): String = when (form) {
    OrgLegalForm.SARL -> "SARL"
    OrgLegalForm.SARLU -> "SARLU"
    OrgLegalForm.SA -> "SA"
    OrgLegalForm.ESTABLISHMENT -> t("orgFormEstablishment")
    OrgLegalForm.OTHER -> t("orgFormOther")
}

private fun AppModel.activityName(activity: OrgActivity): String = when (activity) {
    OrgActivity.ORDERS -> t("orgActOrders")
    OrgActivity.PROVIDES -> t("orgActProvides")
    OrgActivity.BOTH -> t("orgActBoth")
}

private fun AppModel.docTitle(kind: OrgDocKind): String = when (kind) {
    OrgDocKind.RCCM -> "RCCM"
    OrgDocKind.IDNAT -> "IDNAT"
    OrgDocKind.NIF -> "NIF"
}

private fun AppModel.docSubtitle(kind: OrgDocKind): String = when (kind) {
    OrgDocKind.RCCM -> t("orgDocRccm")
    OrgDocKind.IDNAT -> t("orgDocIdnat")
    OrgDocKind.NIF -> t("orgDocNif")
}

/** « Aujourd'hui, 14 h 20 ». */
private fun AppModel.sentStamp(time: Instant): String = "${day(time)}, ${clock(time)}"

@Composable
private fun OrgHeading(text: String, hint: String? = null) {
    val p = LocalPalette.current
    Column(Modifier.padding(top = 4.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(text, style = title(19, color = p.ink), modifier = Modifier.semantics { heading() })
        if (hint != null) Text(hint, style = body(14, color = p.muted))
    }
}

/** Liste déroulante à choix unique (forme juridique, activité, fonction, pièce d'identité). */
@Composable
internal fun <T> OrgDropdown(label: String, options: List<T>, selected: T?, text: (T) -> String, onSelect: (T) -> Unit) {
    val p = LocalPalette.current
    var open by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }) {
        OutlinedTextField(
            value = selected?.let(text) ?: "", onValueChange = {}, readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(open) },
            textStyle = body(16, color = p.ink), shape = RoundedCornerShape(16.dp), colors = orgFieldColors(),
            modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable),
        )
        ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            options.forEach { option ->
                DropdownMenuItem(text = { Text(text(option)) }, onClick = {
                    onSelect(option)
                    open = false
                })
            }
        }
    }
}

/** Bandeau vert (identité déjà vérifiée) ou bleu (à vérifier). */
@Composable
private fun OrgIdentityBanner(done: Boolean, heading: String, text: String) {
    val p = LocalPalette.current
    Row(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(
            Modifier.size(40.dp).background(if (done) pick(0xFFE3F5EA, 0xFF12301F) else p.soft, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                if (done) Icons.Rounded.VerifiedUser else Icons.Rounded.Person, contentDescription = null,
                tint = if (done) Nexis.ok else p.accent, modifier = Modifier.size(22.dp),
            )
        }
        Column(verticalArrangement = Arrangement.spacedBy(3.dp), modifier = Modifier.weight(1f)) {
            Text(heading, style = body(15, FontWeight.Bold, p.ink))
            Text(text, style = body(13, color = p.muted))
        }
    }
}

// Création

@Composable
fun OrgCreateScreen() {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    // 0 = présentation, 1 à 4 = les étapes, puis « Demande envoyée ».
    var step by remember {
        mutableStateOf(
            when (app.capture) {
                "org-step1" -> 1
                "org-rep-unverified" -> 2
                "org-docs" -> 3
                "org-terms" -> 4
                else -> 0
            },
        )
    }
    var draft by remember {
        mutableStateOf(
            when (app.capture) {
                "org-rep-unverified" -> OrgDemo.draft(documents = false)
                "org-docs" -> OrgDemo.draft(documents = false).copy(documents = setOf(OrgDocKind.RCCM, OrgDocKind.IDNAT))
                "org-terms" -> OrgDemo.draft(documents = true)
                else -> OrgDraft()
            },
        )
    }
    var identity by remember { mutableStateOf(IdentityDraft()) }
    var profile by remember { mutableStateOf<Profile?>(null) }
    var accepted by remember { mutableStateOf(false) }
    var readingTerms by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    var sent by remember { mutableStateOf<Organization?>(null) }
    LaunchedEffect(Unit) { profile = attempt { app.repository.profile() } }
    BackHandler(enabled = step > 0 && sent == null && !busy) { step -= 1 }

    sent?.let { org ->
        OrgStatusBody(org)
        return
    }
    val identityVerified = profile?.isIdentityVerified ?: false
    if (step == 0) {
        FlowScaffold(
            app.t("orgTitle"), onBack = flow::back,
            bottom = {
                PrimaryButton(app.t("orgStart"), { step = 1 })
                OutlineButton(app.t("orgLater"), { flow.back() })
            },
        ) {
            Text(app.t("orgIntroTitle"), style = title(22, color = p.ink), modifier = Modifier.semantics { heading() })
            Text(app.t("orgIntroPersonal"), style = body(15, color = p.muted))
            Column(Modifier.fillMaxWidth().nexisCard(p)) {
                OrgBenefit(Icons.Rounded.AccountBalanceWallet, app.t("orgIntroWalletT"), app.t("orgIntroWalletS"))
                HorizontalDivider(Modifier.padding(start = 66.dp), color = p.line)
                OrgBenefit(Icons.Rounded.Group, app.t("orgIntroTeamT"), app.t("orgIntroTeamS"))
                HorizontalDivider(Modifier.padding(start = 66.dp), color = p.line)
                OrgBenefit(Icons.Rounded.Receipt, app.t("orgIntroReceiptsT"), app.t("orgIntroReceiptsS"))
            }
            InfoNote("${app.t("orgIntroPrepareT")} : ${app.t("orgIntroPrepareS")}")
        }
        return
    }
    val ready = when (step) {
        1 -> draft.step1Ready
        2 -> draft.step2Ready(identityVerified, identity.capture != null)
        3 -> draft.step3Ready
        else -> accepted
    }
    FlowScaffold(
        app.t("orgTitle"), onBack = { if (!busy) step -= 1 },
        bottom = {
            PrimaryButton(app.t(if (step == 4) "becomeSend" else "nextStep"), {
                if (step < 4) {
                    step += 1
                } else {
                    busy = true
                    failed = false
                    scope.launch {
                        try {
                            val org = app.repository.createOrganization(
                                draft, if (accepted) app.repository.orgTermsVersion else null,
                                // Une personne déjà vérifiée n'envoie rien de plus.
                                if (draft.representativeIsMe && !identityVerified) identity.capture else null,
                            )
                            app.dataChanged()
                            sent = org
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
            if (step >= 2) OutlineButton(app.t("back"), { step -= 1 }, enabled = !busy)
        },
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(app.t("becomeStep", "step" to step.toString(), "total" to ORG_STEPS.toString()), style = body(13, FontWeight.SemiBold, p.accent))
            LinearProgressIndicator(
                progress = { step / ORG_STEPS.toFloat() }, color = Nexis.brand, trackColor = p.soft,
                modifier = Modifier.fillMaxWidth().clearAndSetSemantics { },
            )
        }
        when (step) {
            1 -> CompanyStep(draft) { draft = it }
            2 -> RepresentativeStep(draft, profile, identityVerified, identity, { draft = it }) { identity = it }
            3 -> DocumentsStep(draft) { draft = it }
            else -> TermsStep(draft, profile, accepted, busy, { accepted = it }, { step = 1 }) { readingTerms = true }
        }
        if (failed) Text(app.t("orgFailed"), style = body(14, color = Nexis.danger))
    }
    if (readingTerms) LegalReader(LegalDocumentKey.ORG_TERMS) { readingTerms = false }
}

@Composable
private fun OrgBenefit(icon: ImageVector, heading: String, text: String) {
    val p = LocalPalette.current
    Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        Box(Modifier.size(40.dp).background(p.soft, RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = null, tint = p.softInk, modifier = Modifier.size(22.dp))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(heading, style = body(15, FontWeight.Bold, p.ink))
            Text(text, style = body(13, color = p.muted))
        }
    }
}

@Composable
private fun orgFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedBorderColor = Nexis.brand, unfocusedBorderColor = LocalPalette.current.line,
    focusedContainerColor = LocalPalette.current.surface, unfocusedContainerColor = LocalPalette.current.surface,
)

@Composable
private fun OrgTextField(
    value: String, label: String, onChange: (String) -> Unit,
    keyboard: KeyboardType = KeyboardType.Text, hint: String? = null,
) {
    val p = LocalPalette.current
    OutlinedTextField(
        value = value, onValueChange = onChange, singleLine = true,
        label = { Text(label) }, placeholder = hint?.let { text -> { Text(text, style = body(15, color = p.muted)) } },
        keyboardOptions = KeyboardOptions(keyboardType = keyboard),
        textStyle = body(16, color = p.ink), shape = RoundedCornerShape(16.dp),
        colors = orgFieldColors(), modifier = Modifier.fillMaxWidth(),
    )
}

// Étape 1 : l'entreprise

@Composable
private fun CompanyStep(draft: OrgDraft, onChange: (OrgDraft) -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var communeMenu by remember { mutableStateOf(false) }
    OrgHeading(app.t("orgStep1Title"))
    OrgTextField(draft.name, app.t("orgName"), { onChange(draft.copy(name = it)) })
    OrgTextField(draft.rccm, "RCCM", { onChange(draft.copy(rccm = it.uppercase())) }, hint = "CD/KIN/RCCM/…")
    OrgTextField(draft.idnat, "IDNAT", { onChange(draft.copy(idnat = it.uppercase())) }, hint = "01-F4300-…")
    OrgTextField(draft.nif, "NIF", { onChange(draft.copy(nif = it.uppercase())) }, hint = "A2512345B")
    OrgTextField(draft.email, app.t("orgEmail"), { onChange(draft.copy(email = it)) }, KeyboardType.Email, "contact@entreprise.cd")
    if (draft.email.isNotEmpty() && !OrgDraft.isEmail(draft.email)) {
        Text(app.t("orgEmailInvalid"), style = body(13, color = Nexis.danger))
    }
    ExposedDropdownMenuBox(expanded = communeMenu, onExpandedChange = { communeMenu = it }) {
        OutlinedTextField(
            value = draft.commune ?: "", onValueChange = {}, readOnly = true,
            label = { Text(app.t("commune")) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(communeMenu) },
            textStyle = body(16, color = p.ink), shape = RoundedCornerShape(16.dp), colors = orgFieldColors(),
            modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable),
        )
        ExposedDropdownMenu(expanded = communeMenu, onDismissRequest = { communeMenu = false }) {
            app.repository.communes.forEach { item ->
                DropdownMenuItem(text = { Text(item) }, onClick = {
                    onChange(draft.copy(commune = item))
                    communeMenu = false
                })
            }
        }
    }
    OrgDropdown(app.t("orgLegalForm"), OrgLegalForm.entries, draft.form, { app.formName(it) }) { onChange(draft.copy(form = it)) }
    OrgDropdown(app.t("orgActivityLabel"), OrgActivity.entries, draft.activity, { app.activityName(it) }) { onChange(draft.copy(activity = it)) }
}

// Étape 2 : le représentant

@Composable
private fun RepresentativeStep(
    draft: OrgDraft, profile: Profile?, identityVerified: Boolean, identity: IdentityDraft,
    onChange: (OrgDraft) -> Unit, onIdentity: (IdentityDraft) -> Unit,
) {
    val app = LocalApp.current
    val p = LocalPalette.current
    OrgHeading(app.t("orgRepTitle"))
    ChoiceRow(
        app.t("orgRepSelf"), draft.representativeIsMe, { onChange(draft.copy(representativeIsMe = true)) },
        subtitle = profile?.let { "${it.firstName} ${it.lastName}" },
    ) { InitialsAvatar(profile?.initials ?: "", 40.dp) }
    ChoiceRow(
        app.t("orgRepOther"), !draft.representativeIsMe, { onChange(draft.copy(representativeIsMe = false)) },
        subtitle = app.t("orgRepOtherSub"),
    ) {
        Box(Modifier.size(40.dp).background(p.soft, CircleShape), contentAlignment = Alignment.Center) {
            Icon(Icons.Rounded.PersonAdd, contentDescription = null, tint = p.softInk, modifier = Modifier.size(22.dp))
        }
    }
    if (!draft.representativeIsMe) {
        OrgTextField(draft.representativePhone, app.t("phone"), { onChange(draft.copy(representativePhone = it)) }, KeyboardType.Phone, "81 234 5678")
    }
    if (draft.representativeIsMe && profile != null) {
        if (identityVerified) {
            OrgIdentityBanner(true, app.t("orgIdVerifiedT"), app.t("orgIdVerifiedS"))
        } else {
            OrgIdentityBanner(false, app.t("orgIdTodoT"), app.t("orgIdTodoS"))
            InfoNote(app.t("orgIdOnce"))
            IdentityStep(identity, onIdentity)
        }
    }
}

// Étape 3 : les documents

@Composable
private fun DocumentsStep(draft: OrgDraft, onChange: (OrgDraft) -> Unit) {
    val app = LocalApp.current
    OrgHeading(app.t("orgDocsTitle"))
    OrgDocKind.entries.forEach { kind ->
        val received = kind in draft.documents
        Box(
            Modifier.toggleable(received, role = Role.Checkbox) {
                onChange(draft.copy(documents = if (received) draft.documents - kind else draft.documents + kind))
            },
        ) { OrgDocRow(kind, if (received) OrgDocState.RECEIVED else OrgDocState.TO_ADD) }
    }
    InfoNote(app.t("orgDocsFormat"))
    InfoNote(app.t("orgDocsNote"))
    InfoNote(app.t("orgDocsDemo"), NoteKind.VIOLET)
}

/** Un document de l'entreprise : sigle, nom, état. */
@Composable
private fun OrgDocRow(kind: OrgDocKind, state: OrgDocState) {
    val app = LocalApp.current
    val p = LocalPalette.current
    Row(
        Modifier.fillMaxWidth().nexisCard(p, 18.dp).padding(14.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(Modifier.size(46.dp).background(p.soft, RoundedCornerShape(14.dp)), contentAlignment = Alignment.Center) {
            Icon(Icons.Rounded.Description, contentDescription = null, tint = p.softInk, modifier = Modifier.size(24.dp))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(app.docTitle(kind), style = body(15, FontWeight.Bold, p.ink))
            Text(app.docSubtitle(kind), style = body(13, color = p.muted))
        }
        when (state) {
            OrgDocState.RECEIVED -> Pill(PillTone.OK, app.t("orgDocReceived"), Icons.Rounded.Check)
            OrgDocState.TO_ADD -> Pill(PillTone.SECURED, app.t("orgDocToAdd"))
            OrgDocState.TO_REDO -> Pill(PillTone.WARN, app.t("orgDocToRedo"), Icons.Rounded.Warning)
        }
    }
}

// Étape 4 : conditions et envoi

@Composable
private fun TermsStep(
    draft: OrgDraft, profile: Profile?, accepted: Boolean, busy: Boolean,
    onAccept: (Boolean) -> Unit, onEdit: () -> Unit, onRead: () -> Unit,
) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val other = draft.functionOther.trim()
    val functionLabel = draft.function?.let { if (it == OrgFunction.OTHER && other.isNotEmpty()) other else app.functionName(it) }
    val representative = if (draft.representativeIsMe) {
        profile?.let { "${it.firstName} ${it.lastName}" }.orEmpty()
    } else {
        "+243 ${DrcPhone.parse(draft.representativePhone).formatted}"
    }
    Column(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(draft.name.ifEmpty { "—" }, style = title(18, color = p.ink), modifier = Modifier.weight(1f))
            TextButton(onClick = onEdit) { Text(app.t("orgEdit"), style = body(15, FontWeight.SemiBold, p.accent)) }
        }
        Text("RCCM ${draft.rccm}", style = body(14, color = p.muted))
        Text(
            if (functionLabel != null) app.t("orgSummaryRep", "name" to representative, "role" to functionLabel.lowercase())
            else "${app.t("orgProfileRep")} : $representative",
            style = body(14, color = p.muted),
        )
        draft.activity?.let { activity ->
            Text(
                app.t(
                    when (activity) {
                        OrgActivity.ORDERS -> "orgSummaryOrders"
                        OrgActivity.PROVIDES -> "orgSummaryProvides"
                        OrgActivity.BOTH -> "orgSummaryBoth"
                    },
                ),
                style = body(14, color = p.muted),
            )
        }
        Text(app.plural("orgDocsCount", draft.documents.size), style = body(14, color = p.muted))
    }
    Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(app.t("orgTermsTitle"), style = body(15, FontWeight.Bold, p.ink))
        Text(app.t("termsVersion", "date" to app.longDate(app.repository.orgTermsVersion)), style = body(13, color = p.muted))
        TextButton(onClick = onRead) { Text(app.t("becomeReadTerms"), style = body(15, FontWeight.SemiBold, p.accent)) }
        HorizontalDivider(color = p.line)
        Row(
            Modifier.fillMaxWidth().toggleable(accepted, enabled = !busy, role = Role.Checkbox) { onAccept(it) },
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = accepted, onCheckedChange = null, colors = CheckboxDefaults.colors(checkedColor = Nexis.brand))
            Text(app.t("orgAccept"), style = body(15, color = p.ink), modifier = Modifier.padding(start = 10.dp))
        }
    }
    InfoNote(app.t("orgReviewNote"), icon = Icons.Rounded.HourglassTop)
}

// Suivi de la demande

/** L'écran du suivi, ouvert depuis le Profil. */
@Composable
fun OrgStatusScreen(orgId: Int) {
    OrgLoader(orgId) { org -> OrgStatusBody(org) }
}

/** Selon l'état : demande envoyée, correction demandée, espace validé. */
@Composable
private fun OrgStatusBody(org: Organization) {
    when (org.status) {
        OrgStatus.REVIEWING -> OrgReviewing(org)
        OrgStatus.CORRECTION -> OrgCorrection(org)
        OrgStatus.OPEN -> OrgApproved(org)
    }
}

@Composable
private fun OrgBadge(icon: ImageVector, tint: androidx.compose.ui.graphics.Color, background: androidx.compose.ui.graphics.Color) {
    Box(Modifier.fillMaxWidth().padding(vertical = 16.dp), contentAlignment = Alignment.Center) {
        Box(Modifier.size(96.dp).background(background, CircleShape), contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(42.dp))
        }
    }
}

@Composable
private fun OrgReviewing(org: Organization) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    FlowScaffold(
        app.t("orgTitle"), onBack = { flow.restart(null) },
        bottom = { PrimaryButton(app.t("orgBackProfile"), { flow.restart(null) }) },
    ) {
        OrgBadge(Icons.Rounded.HourglassTop, p.accent, p.soft)
        Text(app.t("orgSentTitle"), style = title(21, color = p.ink), textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
        Text(
            app.t("orgSentText", "name" to org.shortName), style = body(15, color = p.muted),
            textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth(),
        )
        Column(Modifier.fillMaxWidth().nexisCard(p).padding(16.dp)) {
            StepList(
                listOf(
                    StepItem(app.t("orgSentTitle"), time = app.sentStamp(org.sentAt), state = StepState.DONE),
                    StepItem(app.t("orgTimeReview"), sub = app.t("orgTimeReviewSub"), state = StepState.NOW),
                    StepItem(app.t("orgTimeOpen"), sub = app.t("orgTimeOpenSub"), state = StepState.TODO),
                ),
            )
        }
        InfoNote(app.t("orgSentPersonal"), icon = Icons.Rounded.Person)
    }
}

@Composable
private fun OrgCorrection(org: Organization) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    FlowScaffold(
        app.t("orgTitle"), onBack = { flow.restart(null) },
        bottom = {
            PrimaryButton(app.t("orgFixReplace"), {
                val redo = org.documents.firstOrNull { it.state == OrgDocState.TO_REDO } ?: return@PrimaryButton
                busy = true
                failed = false
                scope.launch {
                    try {
                        app.repository.replaceDocument(org.id, redo.kind)
                        app.dataChanged()
                    } catch (cancel: CancellationException) {
                        throw cancel
                    } catch (_: Exception) {
                        failed = true
                    } finally {
                        busy = false
                    }
                }
            }, enabled = org.documents.any { it.state == OrgDocState.TO_REDO }, loading = busy)
            OutlineButton(app.t("orgFixWrite"), { flow.comingSoon = app.t("orgFixWrite") })
        },
    ) {
        OrgBadge(Icons.Rounded.Warning, Nexis.wait, pick(0xFFFFF1D6, 0xFF33270D))
        Text(app.t("orgFixTitle"), style = title(20, color = p.ink))
        Text(app.t("orgFixKept"), style = body(15, color = p.muted))
        org.documents.forEach { OrgDocRow(it.kind, it.state) }
        org.correctionNote?.let { note ->
            Column(Modifier.fillMaxWidth().background(p.soft, RoundedCornerShape(16.dp)).padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(app.t("orgFixMessage"), style = body(13, FontWeight.SemiBold, p.softInk))
                Text("« $note »", style = body(15, color = p.ink))
            }
        }
        if (failed) Text(app.t("orgFailed"), style = body(14, color = Nexis.danger))
    }
}

@Composable
private fun OrgApproved(org: Organization) {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val p = LocalPalette.current
    FlowScaffold(
        app.t("orgTitle"), onBack = { flow.restart(null) },
        bottom = {
            PrimaryButton(app.t("orgApprovedOpen"), {
                app.openOrgSpace(org.id)
                flow.restart(null)
            })
        },
    ) {
        OrgBadge(Icons.Rounded.VerifiedUser, Nexis.ok, pick(0xFFE3F5EA, 0xFF12301F))
        Text(
            app.t("orgApprovedTitle", "name" to org.shortName), style = title(21, color = p.ink),
            textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth(),
        )
        Text(app.t("orgApprovedText"), style = body(15, color = p.muted), textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
        Column(Modifier.fillMaxWidth().nexisCard(p)) {
            OrgFirstStep(Icons.Rounded.Phone, app.t("orgApprovedNumber")) { flow.push(MissionRoute.OrgNumberAdd(org.id)) }
            HorizontalDivider(Modifier.padding(start = 62.dp), color = p.line)
            OrgFirstStep(Icons.Rounded.PersonAdd, app.t("orgApprovedInvite")) { flow.push(MissionRoute.OrgInvite(org.id)) }
        }
    }
}

@Composable
private fun OrgFirstStep(icon: ImageVector, text: String, onClick: () -> Unit) {
    val p = LocalPalette.current
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(14.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Box(Modifier.size(40.dp).background(p.soft, RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = null, tint = p.softInk, modifier = Modifier.size(22.dp))
        }
        Text(text, style = body(15, FontWeight.SemiBold, p.ink), modifier = Modifier.weight(1f))
    }
}
