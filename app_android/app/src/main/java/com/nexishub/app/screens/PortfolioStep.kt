package com.nexishub.app.screens

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.LinearGradient
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Shader
import android.media.ExifInterface
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AddPhotoAlternate
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.MarkEmailUnread
import androidx.compose.material.icons.rounded.School
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Cancel
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material.icons.rounded.Visibility
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
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
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.nexishub.app.LocalApp
import com.nexishub.app.data.CatalogService
import com.nexishub.app.data.Portfolio
import com.nexishub.app.data.PortfolioRequest
import com.nexishub.app.data.ProofReview
import com.nexishub.app.data.samePhotos
import com.nexishub.app.data.WorkProof
import com.nexishub.app.ui.FlowScaffold
import com.nexishub.app.ui.InfoNote
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.NoteKind
import com.nexishub.app.ui.OutlineButton
import com.nexishub.app.ui.Pill
import com.nexishub.app.ui.PillTone
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.ServiceTile
import com.nexishub.app.ui.body
import com.nexishub.app.ui.nexisCard
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.util.UUID
import kotlin.math.max

// Preuves de réalisations : étape facultative de « Devenir prestataire » et
// écran « Mes réalisations » du profil. L'équipe NexisHub les revoit, puis les
// photos d'un service approuvé sont montrées aux clients (« Voir ses
// réalisations » sur les devis). Les diplômes restent vus par l'équipe
// seulement. La galerie est permise ici, et seulement ici : ce sont des
// travaux déjà faits (la pièce d'identité et la vidéo restent sans galerie).

/** Une photo choisie, réduite, prête à être envoyée. */
class ProofPhoto(val jpeg: ByteArray, val preview: ImageBitmap, val id: String = UUID.randomUUID().toString())

/** Ce qui est en cours de saisie. */
data class PortfolioDraft(
    val photos: Map<String, List<ProofPhoto>> = emptyMap(),
    val notes: Map<String, String> = emptyMap(),
    val certificates: List<ProofPhoto> = emptyList(),
    /** Ce qui a été envoyé, avec la décision de l'équipe. */
    val sent: Portfolio = Portfolio(),
) {
    val isEmpty: Boolean get() = photos.values.all { it.isEmpty() } && certificates.isEmpty()

    /** La décision de l'équipe sur un service, tant que ses photos et sa
     * phrase n'ont pas été changées ici (sinon elles seront revues). */
    fun review(serviceId: String): ProofReview? {
        val work = sent.works.firstOrNull { it.serviceId == serviceId } ?: return null
        val unchanged = samePhotos(photos[serviceId].orEmpty().map { it.jpeg }, work.photos) &&
            notes[serviceId].orEmpty().trim() == work.note
        return if (unchanged) work.review else null
    }

    val certificatesVerified: Boolean
        get() = sent.certificatesVerified && samePhotos(certificates.map { it.jpeg }, sent.certificates)

    /** Les preuves à envoyer, dans l'ordre des services. */
    fun portfolio(services: List<String>): Portfolio = Portfolio(
        services.map { id -> WorkProof(id, photos[id].orEmpty().map { it.jpeg }, notes[id].orEmpty()) },
        certificates.map { it.jpeg },
    ).cleaned

    companion object {
        /** Reprend ce qui a déjà été envoyé. */
        fun of(portfolio: Portfolio): PortfolioDraft {
            fun photo(data: ByteArray) = BitmapFactory.decodeByteArray(data, 0, data.size)?.let { ProofPhoto(data, it.asImageBitmap()) }
            return PortfolioDraft(
                photos = portfolio.works.associate { work -> work.serviceId to work.photos.mapNotNull(::photo) },
                notes = portfolio.works.associate { it.serviceId to it.note },
                certificates = portfolio.certificates.mapNotNull(::photo),
                sent = portfolio,
            )
        }
    }
}

/** Lit la photo choisie, la remet à l'endroit, la réduit à 1 600 px et la
 * réencode en JPEG : les métadonnées (lieu, appareil, date) disparaissent. */
private suspend fun prepareProof(context: Context, uri: Uri): ProofPhoto? = withContext(Dispatchers.IO) {
    try {
        val resolver = context.contentResolver
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return@withContext null
        var sample = 1
        while (max(bounds.outWidth, bounds.outHeight) / (sample * 2) >= 1600) sample *= 2
        val decoded = resolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample })
        } ?: return@withContext null
        val degrees = resolver.openInputStream(uri)?.use {
            when (ExifInterface(it).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
                ExifInterface.ORIENTATION_ROTATE_90 -> 90
                ExifInterface.ORIENTATION_ROTATE_180 -> 180
                ExifInterface.ORIENTATION_ROTATE_270 -> 270
                else -> 0
            }
        } ?: 0
        val scale = minOf(1f, 1600f / max(decoded.width, decoded.height))
        val matrix = Matrix().apply {
            postScale(scale, scale)
            postRotate(degrees.toFloat())
        }
        val upright = Bitmap.createBitmap(decoded, 0, 0, decoded.width, decoded.height, matrix, true)
        val jpeg = ByteArrayOutputStream().use { out ->
            upright.compress(Bitmap.CompressFormat.JPEG, 80, out)
            out.toByteArray()
        }
        ProofPhoto(jpeg, upright.asImageBitmap())
    } catch (cancel: CancellationException) {
        throw cancel
    } catch (_: Exception) {
        null
    }
}

@Composable
fun PortfolioEditor(services: List<CatalogService>, draft: PortfolioDraft, onChange: (PortfolioDraft) -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    var failed by remember { mutableStateOf(false) }
    InfoNote(app.t("worksPrivacy"), icon = Icons.Rounded.Lock)
    services.forEach { service ->
        ProofCard(
            title = service.label(app.language), subtitle = null, status = reviewStatus(draft.review(service.id)),
            maxPhotos = Portfolio.MAX_PHOTOS,
            photos = draft.photos[service.id].orEmpty(),
            onPhotos = { onChange(draft.copy(photos = draft.photos + (service.id to it))) },
            note = draft.notes[service.id].orEmpty(),
            onNote = { onChange(draft.copy(notes = draft.notes + (service.id to it))) },
            onFailed = { failed = it },
        ) { ServiceTile(service, 38.dp) }
    }
    ProofCard(
        title = app.t("worksCertificates"), subtitle = app.t("worksCertificatesSub"),
        status = if (draft.certificatesVerified) ProofStatus(PillTone.OK, Icons.Rounded.Verified, app.t("worksCertificatesVerified")) else null,
        maxPhotos = Portfolio.MAX_CERTIFICATES,
        photos = draft.certificates, onPhotos = { onChange(draft.copy(certificates = it)) },
        note = null, onNote = null, onFailed = { failed = it },
    ) {
        Box(Modifier.size(38.dp).clip(RoundedCornerShape(10.dp)).background(p.soft), contentAlignment = Alignment.Center) {
            Icon(Icons.Rounded.School, contentDescription = null, tint = p.softInk, modifier = Modifier.size(20.dp))
        }
    }
    if (failed) Text(app.t("worksPhotoFailed"), style = body(14, color = Nexis.danger))
}

class ProofStatus(val tone: PillTone, val icon: ImageVector, val text: String)

@Composable
private fun reviewStatus(review: ProofReview?): ProofStatus? {
    val app = LocalApp.current
    return when (review) {
        ProofReview.PENDING -> ProofStatus(PillTone.WAIT, Icons.Rounded.Schedule, app.t("worksReviewPending"))
        ProofReview.APPROVED -> ProofStatus(PillTone.OK, Icons.Rounded.Visibility, app.t("worksReviewApproved"))
        ProofReview.REJECTED -> ProofStatus(PillTone.BAD, Icons.Rounded.Cancel, app.t("worksReviewRejected"))
        null -> null
    }
}

/** Les photos d'un service (ou les attestations), choisies dans la galerie. */
@Composable
private fun ProofCard(
    title: String,
    subtitle: String?,
    status: ProofStatus?,
    maxPhotos: Int,
    photos: List<ProofPhoto>,
    onPhotos: (List<ProofPhoto>) -> Unit,
    note: String?,
    onNote: ((String) -> Unit)?,
    onFailed: (Boolean) -> Unit,
    leading: @Composable () -> Unit,
) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(false) }
    // Sélecteur de photos du système : aucune autorisation demandée, seulement des images.
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(Portfolio.MAX_PHOTOS)) { uris ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        loading = true
        scope.launch {
            val room = maxPhotos - photos.size
            val read = uris.take(room).map { prepareProof(context, it) }
            onFailed(read.any { it == null })
            onPhotos(photos + read.filterNotNull())
            loading = false
        }
    }
    Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            leading()
            Column(Modifier.weight(1f).padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(title, style = body(15, FontWeight.Bold, p.ink))
                if (subtitle != null) Text(subtitle, style = body(13, color = p.muted))
            }
            Text(app.t("worksCount", "count" to photos.size.toString(), "max" to maxPhotos.toString()), style = body(12, FontWeight.SemiBold, p.muted))
        }
        if (status != null) Pill(status.tone, status.text, status.icon)
        if (photos.isNotEmpty()) {
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                photos.forEach { photo ->
                    Box(Modifier.size(76.dp).clip(RoundedCornerShape(12.dp))) {
                        Image(photo.preview, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.size(76.dp))
                        IconButton(
                            onClick = { onPhotos(photos.filterNot { it.id == photo.id }) },
                            modifier = Modifier.align(Alignment.TopEnd).size(32.dp),
                        ) {
                            Box(Modifier.size(22.dp).clip(CircleShape).background(Color.Black.copy(alpha = 0.55f)), contentAlignment = Alignment.Center) {
                                Icon(Icons.Rounded.Close, contentDescription = app.t("worksRemove"), tint = Color.White, modifier = Modifier.size(14.dp))
                            }
                        }
                    }
                }
            }
        }
        OutlineButton(
            app.t("worksAddPhotos"),
            { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
            icon = Icons.Rounded.AddPhotoAlternate,
            enabled = photos.size < maxPhotos && !loading,
        )
        if (note != null && onNote != null) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(app.t("worksNote"), style = body(13, FontWeight.SemiBold, p.ink))
                OutlinedTextField(
                    value = note,
                    onValueChange = { onNote(it.take(Portfolio.MAX_NOTE)) },
                    placeholder = { Text(app.t("worksNoteExample"), style = body(15, color = p.muted)) },
                    textStyle = body(15, color = p.ink),
                    maxLines = 3,
                    shape = RoundedCornerShape(12.dp),
                    colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Nexis.brand, unfocusedBorderColor = p.line),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}

// --- Mes réalisations (profil) ---

@Composable
fun PortfolioScreen() {
    val app = LocalApp.current
    val flow = LocalFlow.current
    val scope = rememberCoroutineScope()
    val demo = app.capture == PortfolioDemo.PROFILE
    var services by remember { mutableStateOf(emptyList<CatalogService>()) }
    var draft by remember { mutableStateOf(PortfolioDraft()) }
    var request by remember { mutableStateOf<PortfolioRequest?>(null) }
    var busy by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    var saved by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        val catalog = attempt { app.repository.serviceCatalog() }.orEmpty()
        if (demo) {
            services = catalog.filter { it.id == "plomberie" || it.id == "electricite" }
            request = PortfolioRequest(listOf("electricite"), java.time.LocalDate.now())
            // La plomberie a déjà été approuvée : les clients la voient.
            val demoDraft = PortfolioDemo.draft(listOf("plomberie"))
            val sent = demoDraft.portfolio(listOf("plomberie"))
            draft = demoDraft.copy(sent = Portfolio(sent.works.map { it.withReview(ProofReview.APPROVED) }, sent.certificates))
        } else {
            val chosen = attempt { app.repository.providerServices() }.orEmpty()
            services = catalog.filter { it.id in chosen }
            draft = PortfolioDraft.of(attempt { app.repository.portfolio() } ?: Portfolio())
            request = attempt { app.repository.portfolioRequest() }
        }
    }
    FlowScaffold(app.t("myWorks"), onBack = { flow.back() }, bottom = {
        PrimaryButton(app.t("worksSave"), {
            busy = true
            failed = false
            saved = false
            scope.launch {
                try {
                    app.repository.sendPortfolio(draft.portfolio(services.map { it.id }))
                    request = null
                    saved = true
                    app.dataChanged()
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (_: Exception) {
                    failed = true
                } finally {
                    busy = false
                }
            }
        }, enabled = !busy && !demo, loading = busy)
    }) {
        request?.let { asked ->
            val names = asked.services.mapNotNull { id -> services.firstOrNull { it.id == id }?.label(app.language) }
            InfoNote(app.t("worksRequested", "services" to names.joinToString(", ")), icon = Icons.Rounded.MarkEmailUnread)
        }
        PortfolioEditor(services, draft) { draft = it }
        if (saved) InfoNote(app.t("worksSaved"), icon = Icons.Rounded.CheckCircle)
        if (failed) Text(app.t("actionFailed"), style = body(14, color = Nexis.danger))
        InfoNote(app.t("worksDemoNote"), NoteKind.VIOLET)
    }
}

// --- Démonstration (captures de la CI) ---

/** `become-portfolio` (étape de la demande) et `portfolio` (profil, avec une
 * demande de l'équipe). */
object PortfolioDemo {
    const val STEP = "become-portfolio"
    const val PROFILE = "portfolio"

    /** Photos dessinées par l'app (pas de vraies photos). */
    fun draft(services: List<String>): PortfolioDraft {
        val shades = listOf(0xFF9FB6D6.toInt(), 0xFFB9C9DE.toInt(), 0xFF8FA3BF.toInt())
        val photos = shades.map { shade ->
            val bitmap = Bitmap.createBitmap(240, 240, Bitmap.Config.ARGB_8888)
            val canvas = android.graphics.Canvas(bitmap)
            val paint = Paint(Paint.ANTI_ALIAS_FLAG)
            paint.shader = LinearGradient(0f, 0f, 0f, 240f, 0xFFD6E4F5.toInt(), shade, Shader.TileMode.CLAMP)
            canvas.drawRect(0f, 0f, 240f, 240f, paint)
            paint.shader = null
            paint.color = 0xB324344D.toInt()
            canvas.drawRoundRect(60f, 70f, 180f, 170f, 18f, 18f, paint)
            val jpeg = ByteArrayOutputStream().use { out ->
                bitmap.compress(Bitmap.CompressFormat.JPEG, 80, out)
                out.toByteArray()
            }
            ProofPhoto(jpeg, bitmap.asImageBitmap())
        }
        return PortfolioDraft(
            photos = services.associateWith { photos },
            notes = services.associateWith { "Limete, 2025" },
        )
    }
}
