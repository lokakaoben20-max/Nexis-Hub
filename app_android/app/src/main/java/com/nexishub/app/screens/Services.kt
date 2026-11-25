package com.nexishub.app.screens

import androidx.compose.animation.AnimatedContent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.EditNote
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Shield
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.nexishub.app.LocalApp
import com.nexishub.app.data.CatalogService
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.NewBadge
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.ServiceTile
import com.nexishub.app.ui.body
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.title
import kotlinx.coroutines.launch

private sealed interface PickerStep {
    data object Grid : PickerStep
    data class Request(val item: CatalogService) : PickerStep
    data object Describe : PickerStep
}

/** « Quel service ? » : le catalogue publié par le serveur, en grille,
 * avec recherche, dans une feuille Material 3. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ServicePickerSheet(onDismiss: () -> Unit, onRequested: () -> Unit) {
    val p = LocalPalette.current
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var step by remember { mutableStateOf<PickerStep>(PickerStep.Grid) }
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = state, containerColor = p.bg) {
        AnimatedContent(targetState = step, label = "picker") { current ->
            when (current) {
                PickerStep.Grid -> ServiceGrid(onClose = onDismiss, onPick = { step = PickerStep.Request(it) }, onDescribe = { step = PickerStep.Describe })
                is PickerStep.Request -> RequestForm(current.item, onBack = { step = PickerStep.Grid }, onDone = onRequested)
                PickerStep.Describe -> DescribeForm(onBack = { step = PickerStep.Grid }, onDone = onDismiss)
            }
        }
    }
}

@Composable
private fun SheetHeader(heading: String, onBack: (() -> Unit)?, onClose: (() -> Unit)?) {
    val app = LocalApp.current
    val p = LocalPalette.current
    Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        if (onBack != null) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = app.t("back")) }
        } else {
            Box(Modifier.size(48.dp))
        }
        Text(heading, style = title(18, color = p.ink), textAlign = TextAlign.Center, modifier = Modifier.weight(1f))
        if (onClose != null) {
            IconButton(onClick = onClose) { Icon(Icons.Rounded.Close, contentDescription = app.t("close")) }
        } else {
            Box(Modifier.size(48.dp))
        }
    }
}

@Composable
private fun ServiceGrid(onClose: () -> Unit, onPick: (CatalogService) -> Unit, onDescribe: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var catalog by remember { mutableStateOf(emptyList<CatalogService>()) }
    var query by remember { mutableStateOf("") }
    LaunchedEffect(Unit) { catalog = app.repository.serviceCatalog() }
    val needle = query.trim()
    // La recherche accepte le nom affiché et le nom d'origine du catalogue.
    val filtered = if (needle.isEmpty()) catalog else catalog.filter {
        it.label(app.language).contains(needle, ignoreCase = true) || it.baseName.contains(needle, ignoreCase = true)
    }
    Column(Modifier.fillMaxHeight(0.92f)) {
        SheetHeader(app.t("whichService"), onBack = null, onClose = onClose)
        LazyVerticalGrid(
            columns = GridCells.Adaptive(minSize = 100.dp),
            contentPadding = PaddingValues(start = 18.dp, end = 18.dp, bottom = 32.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(app.t("pickServiceHint"), style = body(15, color = p.muted))
                    OutlinedTextField(
                        value = query, onValueChange = { query = it },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = { Text(app.t("searchService")) },
                        leadingIcon = { Icon(Icons.Rounded.Search, contentDescription = null) },
                        singleLine = true, shape = RoundedCornerShape(28.dp), textStyle = body(16, color = p.ink),
                    )
                    if (filtered.isEmpty()) Text(app.t("noServiceMatches"), style = body(15, color = p.muted))
                }
            }
            items(filtered, key = { it.id }) { item -> ServiceCell(item) { onPick(item) } }
            item(span = { GridItemSpan(maxLineSpan) }) {
                Row(
                    Modifier.fillMaxWidth().nexisCard(p).clickable(role = Role.Button, onClick = onDescribe).padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.size(44.dp).background(p.soft, RoundedCornerShape(14.dp)), contentAlignment = Alignment.Center) {
                        Icon(Icons.Rounded.EditNote, contentDescription = null, tint = p.accent)
                    }
                    Column(Modifier.weight(1f).padding(horizontal = 14.dp)) {
                        Text(app.t("cantFindService"), style = body(15, FontWeight.SemiBold, p.ink))
                        Text(app.t("cantFindHint"), style = body(13, color = p.muted))
                    }
                    Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, contentDescription = null, tint = p.muted)
                }
            }
        }
    }
}

@Composable
private fun ServiceCell(item: CatalogService, onClick: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val shape = RoundedCornerShape(20.dp)
    Column(
        Modifier.heightIn(min = 112.dp).background(p.surface, shape).border(0.5.dp, p.line, shape)
            .clickable(role = Role.Button, onClick = onClick).padding(vertical = 12.dp, horizontal = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box {
            ServiceTile(item, 52.dp)
            if (item.isNew) Box(Modifier.align(Alignment.TopEnd).padding(start = 30.dp)) { NewBadge() }
        }
        Text(item.label(app.language), style = body(13, FontWeight.SemiBold, p.ink), textAlign = TextAlign.Center, maxLines = 2)
    }
}

/** Demande pour un service du catalogue : commune et besoin. Rien n'est
 * payé à cette étape ; dans l'aperçu, la demande est une simulation. */
@Composable
private fun RequestForm(item: CatalogService, onBack: () -> Unit, onDone: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var commune by remember { mutableStateOf<String?>(null) }
    var text by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var saved by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val trimmed = text.trim()
    val valid = commune != null && trimmed.length in 10..500

    Column(Modifier.fillMaxHeight(0.92f).imePadding()) {
        SheetHeader(app.t("requestService"), onBack = onBack, onClose = null)
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                ServiceTile(item, 48.dp)
                Text(item.label(app.language), style = title(18, color = p.ink), modifier = Modifier.padding(start = 14.dp))
            }
            CommuneField(commune, app.repository.communes) { commune = it }
            OutlinedTextField(
                value = text, onValueChange = { text = it.take(500) },
                modifier = Modifier.fillMaxWidth().heightIn(min = 140.dp),
                label = { Text(app.t("describeTextLabel")) },
                placeholder = { Text(app.t("describeTextHint")) },
                supportingText = { Text("${trimmed.length}/500") },
                shape = RoundedCornerShape(16.dp), textStyle = body(16, color = p.ink),
            )
            InfoLine(Icons.Rounded.Info, app.t("serviceRequestDemo"))
            InfoLine(Icons.Rounded.Shield, app.t("serviceRequestNoPay"))
            if (failed) Text(app.t("requestNotSent"), style = body(14, color = Nexis.danger))
        }
        Box(Modifier.navigationBarsPadding().padding(horizontal = 20.dp, vertical = 8.dp)) {
            PrimaryButton(app.t("sendRequest"), enabled = valid && !sending, onClick = {
                val chosen = commune ?: return@PrimaryButton
                sending = true
                failed = false
                scope.launch {
                    runCatching { app.repository.requestService(item.id, chosen, trimmed) }
                        .onSuccess { app.dataChanged(); saved = true }
                        .onFailure { failed = true }
                    sending = false
                }
            })
        }
    }
    if (saved) {
        AlertDialog(
            onDismissRequest = onDone,
            title = { Text(app.t("serviceRequestSaved")) },
            text = { Text(app.t("serviceRequestSavedText"), style = body(15)) },
            confirmButton = { TextButton(onClick = onDone) { Text(app.t("ok")) } },
        )
    }
}

/** « Décrire mon besoin » : une demande libre transmise à l'équipe. */
@Composable
private fun DescribeForm(onBack: () -> Unit, onDone: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val scope = rememberCoroutineScope()
    var heading by remember { mutableStateOf("") }
    var text by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var sent by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val valid = heading.isNotBlank() && text.trim().length >= 10

    Column(Modifier.fillMaxHeight(0.92f).imePadding()) {
        SheetHeader(app.t("describeNeed"), onBack = onBack, onClose = null)
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(app.t("describeLead"), style = body(15, color = p.muted))
            OutlinedTextField(
                value = heading, onValueChange = { heading = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text(app.t("describeTypeLabel")) }, placeholder = { Text(app.t("describeTypeHint")) },
                singleLine = true, shape = RoundedCornerShape(16.dp), textStyle = body(16, color = p.ink),
            )
            OutlinedTextField(
                value = text, onValueChange = { text = it.take(500) },
                modifier = Modifier.fillMaxWidth().heightIn(min = 140.dp),
                label = { Text(app.t("describeTextLabel")) }, placeholder = { Text(app.t("describeTextHint")) },
                shape = RoundedCornerShape(16.dp), textStyle = body(16, color = p.ink),
            )
            InfoLine(Icons.Rounded.Shield, app.t("describeNoPay"))
            if (failed) Text(app.t("requestNotSent"), style = body(14, color = Nexis.danger))
        }
        Box(Modifier.navigationBarsPadding().padding(horizontal = 20.dp, vertical = 8.dp)) {
            PrimaryButton(app.t("sendRequest"), enabled = valid && !sending, onClick = {
                sending = true
                scope.launch {
                    runCatching { app.repository.sendFreeRequest(heading, text) }
                        .onSuccess { sent = true }
                        .onFailure { failed = true }
                    sending = false
                }
            })
        }
    }
    if (sent) {
        AlertDialog(
            onDismissRequest = onDone,
            title = { Text(app.t("requestSent")) },
            text = { Text(app.t("requestSentText"), style = body(15)) },
            confirmButton = { TextButton(onClick = onDone) { Text(app.t("backHome")) } },
        )
    }
}
