package com.nexishub.app.screens

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.RectF
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.IntentSenderRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.ArrowForward
import androidx.compose.material.icons.rounded.Badge
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.DirectionsCar
import androidx.compose.material.icons.rounded.DocumentScanner
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.automirrored.rounded.MenuBook
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material.icons.rounded.Replay
import androidx.compose.material.icons.rounded.Sync
import androidx.compose.material.icons.rounded.Videocam
import androidx.compose.material.icons.rounded.Visibility
import androidx.compose.material.icons.rounded.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.google.android.gms.tasks.Task
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult
import com.google.mlkit.vision.face.Face
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetector
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.google.mlkit.vision.face.FaceLandmark
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.TextRecognizer
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import com.nexishub.app.LocalApp
import com.nexishub.app.data.CardCheck
import com.nexishub.app.data.CardSide
import com.nexishub.app.data.CardVerdict
import com.nexishub.app.data.FaceSample
import com.nexishub.app.data.HeadTurn
import com.nexishub.app.data.IdentityCapture
import com.nexishub.app.data.IdentityDocument
import com.nexishub.app.data.ImageHash
import com.nexishub.app.data.MachineZone
import com.nexishub.app.data.SelfieScript
import com.nexishub.app.ui.ChoiceRow
import com.nexishub.app.ui.InfoNote
import com.nexishub.app.ui.LocalPalette
import com.nexishub.app.ui.Nexis
import com.nexishub.app.ui.NoteKind
import com.nexishub.app.ui.OutlineButton
import com.nexishub.app.ui.PrimaryButton
import com.nexishub.app.ui.body
import com.nexishub.app.ui.nexisCard
import com.nexishub.app.ui.rememberReduceMotion
import com.nexishub.app.ui.title
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.UUID
import java.util.concurrent.Executors
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.math.abs
import kotlin.math.max

// Étape « Pièce d'identité » de « Devenir prestataire » : recto puis verso
// de la carte (ou page photo du passeport) par le scanner de documents de ML Kit (import depuis la galerie
// désactivé), puis courte vidéo guidée du visage (CameraX, sans micro). Jamais
// de galerie. ML Kit, sur le téléphone, guide la prise ; c'est l'équipe
// NexisHub qui vérifie la personne.

/** Une face de la pièce, à l'endroit et réduite. */
class CardShot(
    val jpeg: ByteArray,
    val preview: ImageBitmap,
    val hashes: List<Long>,
    val faceFound: Boolean,
    /** Page de passeport : la zone de lecture automatique a été vue. */
    val machineZone: Boolean = false,
)

/** La vidéo du visage, prête à être envoyée. */
class VideoShot(val data: ByteArray, val thumbnail: ImageBitmap?, val seconds: Int, val turns: List<HeadTurn>)

/** Ce qui a été pris jusqu'ici. */
data class IdentityDraft(
    /** Choisie par la personne avant la prise. */
    val document: IdentityDocument? = null,
    /** Recto de la carte, ou page photo du passeport. */
    val recto: CardShot? = null,
    val verso: CardShot? = null,
    val video: VideoShot? = null,
) {
    val pieceDone: Boolean
        get() {
            val document = document ?: return false
            return recto != null && (!document.needsVerso || verso != null)
        }

    val capture: IdentityCapture?
        get() {
            val document = document ?: return null
            val recto = recto ?: return null
            val video = video ?: return null
            if (!pieceDone) return null
            val back = if (document.needsVerso) verso?.jpeg else null
            return IdentityCapture(document, recto.jpeg, back, video.data, video.seconds, video.turns).takeIf { it.isComplete }
        }

    /** Changer de pièce efface les faces déjà prises. */
    fun choose(document: IdentityDocument): IdentityDraft =
        if (document == this.document) this else copy(document = document, recto = null, verso = null)
}

/** Écrans figés pour les captures de la CI (l'émulateur n'a ni le scanner ni
 * une vraie caméra). */
enum class IdentityDemo(val code: String) {
    RECTO("become-identity"),
    WRONG_SIDE("become-wrong-side"),
    VERSO("become-verso"),
    SELFIE("become-selfie"),
    REVIEW("become-review"),
    PASSPORT("become-passport"),
    WRONG_PAGE("become-wrong-page"),
    ;

    companion object {
        fun from(capture: String?): IdentityDemo? = entries.firstOrNull { it.code == capture }
        val codes: Set<String> = entries.map { it.code }.toSet()
    }
}

@Composable
fun IdentityStep(draft: IdentityDraft, onChange: (IdentityDraft) -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val demo = IdentityDemo.from(app.capture)
    var scanning by remember { mutableStateOf<List<CardSide>?>(null) }
    var filming by remember { mutableStateOf(false) }
    LaunchedEffect(demo) {
        when (demo) {
            IdentityDemo.RECTO, IdentityDemo.WRONG_SIDE -> {
                onChange(draft.choose(IdentityDocument.VOTER_CARD))
                scanning = listOf(CardSide.RECTO, CardSide.VERSO)
            }
            IdentityDemo.VERSO -> {
                onChange(draft.choose(IdentityDocument.VOTER_CARD))
                scanning = listOf(CardSide.VERSO)
            }
            IdentityDemo.PASSPORT, IdentityDemo.WRONG_PAGE -> {
                onChange(draft.choose(IdentityDocument.PASSPORT))
                scanning = listOf(CardSide.PASSPORT_PAGE)
            }
            IdentityDemo.SELFIE -> filming = true
            IdentityDemo.REVIEW -> onChange(IdentityDemoImages.draft())
            null -> Unit
        }
    }
    // La pièce : d'abord laquelle, puis recto et verso (ou la page photo du passeport).
    Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionLine(app.t("becomeIdDocument"), app.t("becomeIdDocumentSub"), Icons.Rounded.Badge, draft.pieceDone)
        OrgDropdown(app.t("becomeDocChoose"), IdentityDocument.entries, draft.document, { app.t(it.labelKey) }) {
            onChange(draft.choose(it))
        }
        val document = draft.document
        if (document != null) {
            Text(
                app.t(if (document.needsVerso) "becomeCardSides" else "becomePassportSub"),
                style = body(13, color = p.muted),
            )
            if (draft.recto != null || draft.verso != null) {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    if (document.needsVerso) {
                        FaceThumb(app.t("becomeRecto"), draft.recto, CardSide.RECTO.ratio, Modifier.weight(1f)) { scanning = listOf(CardSide.RECTO) }
                        FaceThumb(app.t("becomeVerso"), draft.verso, CardSide.VERSO.ratio, Modifier.weight(1f)) { scanning = listOf(CardSide.VERSO) }
                    } else {
                        FaceThumb(app.t("becomePhotoPage"), draft.recto, CardSide.PASSPORT_PAGE.ratio, Modifier.weight(1f)) {
                            scanning = listOf(CardSide.PASSPORT_PAGE)
                        }
                    }
                }
            }
            if (!draft.pieceDone) {
                OutlineButton(app.t("becomeScanCard"), {
                    scanning = if (draft.recto == null) document.sides else listOf(CardSide.VERSO)
                }, icon = Icons.Rounded.DocumentScanner)
            }
        }
    }
    // La vidéo du visage.
    Column(Modifier.fillMaxWidth().nexisCard(p).padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(64.dp).clip(CircleShape).background(p.soft), contentAlignment = Alignment.Center) {
                val thumbnail = draft.video?.thumbnail
                if (thumbnail != null) {
                    Image(thumbnail, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                } else {
                    Icon(Icons.Rounded.Videocam, contentDescription = null, tint = p.softInk, modifier = Modifier.size(26.dp))
                }
            }
            Column(Modifier.weight(1f).padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(app.t("becomeSelfie"), style = body(15, FontWeight.Bold, p.ink))
                val video = draft.video
                Text(
                    if (video != null) app.t("becomeVideoDone", "seconds" to video.seconds.toString()) else app.t("becomeSelfieSub"),
                    style = body(13, color = p.muted),
                )
            }
            if (draft.video != null) Icon(Icons.Rounded.CheckCircle, contentDescription = null, tint = Nexis.ok)
        }
        OutlineButton(
            app.t(if (draft.video == null) "becomeRecordVideo" else "becomeRetake"), { filming = true },
            icon = if (draft.video == null) Icons.Rounded.Videocam else Icons.Rounded.Replay,
        )
    }
    InfoNote(app.t("becomeGuideNote"), icon = Icons.Rounded.Visibility)
    InfoNote(app.t("becomeIdentityHint"), icon = Icons.Rounded.Lock)
    InfoNote(app.t("becomeDemoNote"), NoteKind.VIOLET)

    scanning?.let { sides ->
        CardScanScreen(
            sides = sides,
            rectoHash = if (sides.first() == CardSide.VERSO) draft.recto?.hashes?.firstOrNull() else null,
            demo = demo,
            onClose = { scanning = null },
        ) { shots ->
            scanning = null
            onChange(
                draft.copy(
                    recto = shots[CardSide.RECTO] ?: shots[CardSide.PASSPORT_PAGE] ?: draft.recto,
                    verso = shots[CardSide.VERSO] ?: draft.verso,
                ),
            )
        }
    }
    if (filming) {
        SelfieVideoScreen(demo = demo == IdentityDemo.SELFIE, onClose = { filming = false }) { video ->
            filming = false
            onChange(draft.copy(video = video))
        }
    }
}

private val IdentityDocument.labelKey: String
    get() = when (this) {
        IdentityDocument.VOTER_CARD -> "docVoterCard"
        IdentityDocument.DRIVING_LICENCE -> "docDrivingLicence"
        IdentityDocument.PASSPORT -> "docPassport"
    }

private val IdentityDocument.icon: ImageVector
    get() = when (this) {
        IdentityDocument.VOTER_CARD -> Icons.Rounded.Badge
        IdentityDocument.DRIVING_LICENCE -> Icons.Rounded.DirectionsCar
        IdentityDocument.PASSPORT -> Icons.AutoMirrored.Rounded.MenuBook
    }

/** Format de la pièce : carte ID-1 (85,6 × 54 mm) ou page de passeport ID-3 (125 × 88 mm). */
private val CardSide.ratio: Float get() = if (this == CardSide.PASSPORT_PAGE) 125f / 88f else 1.586f

private val CardSide.labelKey: String
    get() = when (this) {
        CardSide.RECTO -> "becomeRecto"
        CardSide.VERSO -> "becomeVerso"
        CardSide.PASSPORT_PAGE -> "becomePhotoPage"
    }

@Composable
private fun SectionLine(heading: String, subtitle: String, icon: ImageVector, done: Boolean) {
    val p = LocalPalette.current
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(64.dp).clip(RoundedCornerShape(14.dp)).background(p.soft), contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = null, tint = p.softInk, modifier = Modifier.size(26.dp))
        }
        Column(Modifier.weight(1f).padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(heading, style = body(15, FontWeight.Bold, p.ink))
            Text(subtitle, style = body(13, color = p.muted))
        }
        if (done) Icon(Icons.Rounded.CheckCircle, contentDescription = null, tint = Nexis.ok)
    }
}

/** Aperçu d'une face, avec « Reprendre ». */
@Composable
private fun FaceThumb(label: String, shot: CardShot?, ratio: Float, modifier: Modifier, onRetake: () -> Unit) {
    val app = LocalApp.current
    val p = LocalPalette.current
    val shape = RoundedCornerShape(12.dp)
    Column(modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Box(
            Modifier.fillMaxWidth().aspectRatio(ratio).clip(shape).background(p.soft).border(0.5.dp, p.line, shape),
            contentAlignment = Alignment.Center,
        ) {
            if (shot != null) {
                Image(shot.preview, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
            } else {
                Icon(Icons.Rounded.Badge, contentDescription = null, tint = p.softInk)
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(label, style = body(13, FontWeight.SemiBold, p.ink), modifier = Modifier.weight(1f))
            if (shot != null) {
                TextButton(onClick = onRetake, modifier = Modifier.semantics { contentDescription = "${app.t("becomeRetake")} · $label" }) {
                    Text(app.t("becomeRetake"), style = body(13, FontWeight.SemiBold, p.accent))
                }
            }
        }
    }
}

// --- Scanner de la carte (ML Kit Document Scanner) ---

private sealed interface ScanState {
    data object Ready : ScanState
    data object Checking : ScanState
    data class Wrong(val verdict: CardVerdict) : ScanState
    data object Taken : ScanState
    data object TurnCard : ScanState
    data object Unavailable : ScanState
}

private fun Context.findActivity(): Activity? {
    var context: Context? = this
    while (context is ContextWrapper) {
        if (context is Activity) return context
        context = context.baseContext
    }
    return null
}

private suspend fun <T> Task<T>.awaitResult(): T = suspendCancellableCoroutine { continuation ->
    addOnSuccessListener { continuation.resume(it) }
    addOnFailureListener { continuation.resumeWithException(it) }
    addOnCanceledListener { continuation.cancel() }
}

private val cardFaces: FaceDetector by lazy {
    FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE)
            .setMinFaceSize(0.08f)
            .build(),
    )
}

/** La grille 9 × 8 en niveaux de gris de l'empreinte. */
private fun grayGrid(bitmap: Bitmap): IntArray {
    val small = Bitmap.createScaledBitmap(bitmap, ImageHash.WIDTH, ImageHash.HEIGHT, true)
    return IntArray(ImageHash.WIDTH * ImageHash.HEIGHT) { i ->
        val color = small.getPixel(i % ImageHash.WIDTH, i / ImageHash.WIDTH)
        val r = (color shr 16) and 0xFF
        val g = (color shr 8) and 0xFF
        val b = color and 0xFF
        (r * 299 + g * 587 + b * 114) / 1000
    }
}

private fun cardHashes(bitmap: Bitmap): List<Long> {
    val grid = grayGrid(bitmap)
    return listOf(ImageHash.dHash(grid), ImageHash.dHash(ImageHash.halfTurn(grid)))
}

private fun rotated(bitmap: Bitmap, degrees: Int): Bitmap =
    if (degrees % 360 == 0) bitmap else Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, Matrix().apply { postRotate(degrees.toFloat()) }, true)

private fun jpeg(bitmap: Bitmap): ByteArray = ByteArrayOutputStream().use { out ->
    bitmap.compress(Bitmap.CompressFormat.JPEG, 80, out)
    out.toByteArray()
}

/** Lit la page scannée (réduite à 1 600 px), cherche un visage dans les quatre
 * sens, la remet à l'endroit, puis efface le fichier du scanner. */
private suspend fun readCard(context: Context, uri: Uri, readsMachineZone: Boolean): CardShot? {
    val bitmap = withContext(Dispatchers.IO) {
        try {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
            var sample = 1
            while (max(bounds.outWidth, bounds.outHeight) / (sample * 2) >= 1600) sample *= 2
            val decoded = context.contentResolver.openInputStream(uri)?.use {
                BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample })
            } ?: return@withContext null
            val longest = max(decoded.width, decoded.height)
            if (longest > 1600) {
                val k = 1600f / longest
                Bitmap.createScaledBitmap(decoded, (decoded.width * k).toInt(), (decoded.height * k).toInt(), true)
            } else {
                decoded
            }
        } finally {
            if (uri.scheme == "file") uri.path?.let { File(it).delete() }
        }
    } ?: return null
    var upright: Bitmap? = null
    for (degrees in listOf(0, 180, 90, 270)) {
        val faces = try {
            cardFaces.process(InputImage.fromBitmap(bitmap, degrees)).awaitResult()
        } catch (cancel: CancellationException) {
            throw cancel
        } catch (_: Exception) {
            emptyList()
        }
        val area = bitmap.width.toFloat() * bitmap.height
        if (faces.any { it.boundingBox.width().toFloat() * it.boundingBox.height() / area >= 0.01f }) {
            upright = rotated(bitmap, degrees)
            break
        }
    }
    val faceFound = upright != null
    val card = upright ?: if (bitmap.height > bitmap.width) rotated(bitmap, 90) else bitmap
    val machineZone = readsMachineZone && hasMachineZone(card)
    return withContext(Dispatchers.Default) { CardShot(jpeg(card), card.asImageBitmap(), cardHashes(card), faceFound, machineZone) }
}

private val pageText: TextRecognizer by lazy { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }

/** Lit les lignes de texte de la page, sur le téléphone, pour y chercher la
 * zone de lecture automatique d'un passeport. Le texte n'est pas gardé. */
private suspend fun hasMachineZone(page: Bitmap): Boolean {
    val text = try {
        pageText.process(InputImage.fromBitmap(page, 0)).awaitResult()
    } catch (cancel: CancellationException) {
        throw cancel
    } catch (_: Exception) {
        return false
    }
    return MachineZone.found(text.textBlocks.flatMap { block -> block.lines.map { it.text } })
}

@Composable
private fun CardScanScreen(
    sides: List<CardSide>,
    rectoHash: Long?,
    demo: IdentityDemo?,
    onClose: () -> Unit,
    onDone: (Map<CardSide, CardShot>) -> Unit,
) {
    val app = LocalApp.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var side by remember { mutableStateOf(if (demo == IdentityDemo.VERSO) CardSide.VERSO else sides.first()) }
    var state by remember {
        mutableStateOf<ScanState>(
            when (demo) {
                IdentityDemo.WRONG_SIDE -> ScanState.Wrong(CardVerdict.SHOW_RECTO_FIRST)
                IdentityDemo.WRONG_PAGE -> ScanState.Wrong(CardVerdict.SHOW_PHOTO_PAGE)
                else -> ScanState.Ready
            },
        )
    }
    var shots by remember {
        mutableStateOf<Map<CardSide, CardShot>>(
            if (demo == IdentityDemo.VERSO) mapOf(CardSide.RECTO to IdentityDemoImages.shot(CardSide.RECTO)) else emptyMap(),
        )
    }
    val scanner = remember {
        GmsDocumentScanning.getClient(
            GmsDocumentScannerOptions.Builder()
                // Jamais de photo choisie dans la galerie.
                .setGalleryImportAllowed(false)
                .setPageLimit(1)
                .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_JPEG)
                .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_BASE)
                .build(),
        )
    }

    fun accept(shot: CardShot) {
        shots = shots + (side to shot)
        state = ScanState.Taken
        scope.launch {
            delay(1_100)
            val next = sides.dropWhile { it != side }.drop(1).firstOrNull()
            if (next == null) {
                onDone(shots)
            } else {
                side = next
                state = ScanState.TurnCard
            }
        }
    }

    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { result ->
        val uri = if (result.resultCode == Activity.RESULT_OK) {
            GmsDocumentScanningResult.fromActivityResultIntent(result.data)?.pages?.firstOrNull()?.imageUri
        } else {
            null
        }
        if (uri == null) {
            state = ScanState.Ready
            return@rememberLauncherForActivityResult
        }
        state = ScanState.Checking
        scope.launch {
            val shot = readCard(context, uri, readsMachineZone = side == CardSide.PASSPORT_PAGE)
            if (shot == null) {
                state = ScanState.Ready
                return@launch
            }
            val recto = if (side == CardSide.VERSO) shots[CardSide.RECTO]?.hashes?.firstOrNull() ?: rectoHash else null
            when (val verdict = CardCheck.verdict(side, shot.faceFound, shot.hashes, recto, shot.machineZone)) {
                CardVerdict.ACCEPTED -> accept(shot)
                else -> state = ScanState.Wrong(verdict)
            }
        }
    }

    fun openScanner() {
        val activity = context.findActivity() ?: return
        scanner.getStartScanIntent(activity)
            .addOnSuccessListener { launcher.launch(IntentSenderRequest.Builder(it).build()) }
            .addOnFailureListener { state = ScanState.Unavailable }
    }

    // Après « Retournez la carte », le scanner s'ouvre seul pour le verso.
    LaunchedEffect(state) {
        if (state == ScanState.TurnCard && demo == null) {
            delay(2_200)
            state = ScanState.Ready
            openScanner()
        }
    }

    FullScreenDark(onClose) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            CloseButton(onClose)
            Spacer(Modifier.weight(1f))
            val index = (sides.indexOf(side).takeIf { it >= 0 } ?: 0) + 1
            Text(
                "$index / ${sides.size}", style = body(13, FontWeight.SemiBold, Color.White),
                modifier = Modifier.clip(CircleShape).background(Color.White.copy(alpha = 0.14f))
                    .padding(horizontal = 12.dp, vertical = 7.dp).clearAndSetSemantics { },
            )
        }
        Text(
            app.t(
                when (side) {
                    CardSide.RECTO -> "scanRectoTitle"
                    CardSide.VERSO -> "scanTurnTitle"
                    CardSide.PASSPORT_PAGE -> "scanPassportTitle"
                },
            ),
            style = title(22, color = Color.White),
            modifier = Modifier.padding(top = 14.dp).semantics { heading() },
        )
        Text(
            app.t(
                when (side) {
                    CardSide.RECTO -> "scanRectoHint"
                    CardSide.VERSO -> "scanVersoHint"
                    CardSide.PASSPORT_PAGE -> "scanPassportHint"
                },
            ),
            style = body(15, color = Color.White.copy(alpha = 0.82f)), modifier = Modifier.padding(top = 6.dp),
        )
        Box(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
            val frameColor = when (state) {
                ScanState.Taken -> Color(0xFF34C759)
                is ScanState.Wrong -> Color(0xFFFF6B5E)
                ScanState.Checking -> Nexis.halo
                else -> Color.White.copy(alpha = 0.9f)
            }
            Box(
                Modifier.fillMaxWidth(0.94f).aspectRatio(side.ratio).border(3.dp, frameColor, RoundedCornerShape(16.dp)).padding(10.dp),
                contentAlignment = Alignment.Center,
            ) {
                val demoCard = remember(side) { specimenBitmap(side, 720).asImageBitmap() }
                Image(demoCard, contentDescription = null, modifier = Modifier.fillMaxSize().graphicsLayer { rotationZ = -2f; alpha = 0.92f })
                if (state == ScanState.TurnCard) TurnCardIcon()
            }
        }
        val message: Pair<String, Color>? = when (val current = state) {
            ScanState.Checking -> app.t("scanChecking") to Color.White
            is ScanState.Wrong -> app.t(
                when (current.verdict) {
                    CardVerdict.STILL_RECTO -> "scanWrongRecto"
                    CardVerdict.SHOW_PHOTO_PAGE -> "scanWrongPage"
                    else -> "scanWrongVerso"
                },
            ) to Color(0xFFFF8A80)
            ScanState.Taken -> app.t(side.labelKey) to Color(0xFF34C759)
            ScanState.Unavailable -> app.t("scanUnavailable") to Color(0xFFFF8A80)
            else -> null
        }
        if (message != null) {
            Row(
                Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Color.Black.copy(alpha = 0.55f))
                    .border(1.dp, Color.White.copy(alpha = 0.16f), RoundedCornerShape(18.dp))
                    .padding(horizontal = 16.dp, vertical = 12.dp)
                    .semantics { liveRegion = LiveRegionMode.Polite },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    when (state) {
                        ScanState.Taken -> Icons.Rounded.CheckCircle
                        is ScanState.Wrong, ScanState.Unavailable -> Icons.Rounded.Warning
                        else -> Icons.Rounded.DocumentScanner
                    },
                    contentDescription = null, tint = message.second,
                )
                Text(message.first, style = body(15, FontWeight.SemiBold, Color.White), modifier = Modifier.padding(start = 10.dp))
            }
        }
        Spacer(Modifier.height(14.dp))
        PrimaryButton(
            app.t(
                when (side) {
                    CardSide.RECTO -> "scanStartRecto"
                    CardSide.VERSO -> "scanStartVerso"
                    CardSide.PASSPORT_PAGE -> "scanStartPassport"
                },
            ),
            { if (demo == null) openScanner() },
            icon = Icons.Rounded.DocumentScanner,
            enabled = state != ScanState.Taken && state != ScanState.TurnCard,
            loading = state == ScanState.Checking,
        )
    }
}

@Composable
private fun TurnCardIcon() {
    val reduceMotion = rememberReduceMotion()
    val turn = rememberInfiniteTransition(label = "retourner")
    val angle by turn.animateFloat(0f, 180f, infiniteRepeatable(tween(900), RepeatMode.Reverse), label = "angle")
    Box(
        Modifier.size(104.dp).graphicsLayer { rotationY = if (reduceMotion) 0f else angle }
            .clip(CircleShape).background(Nexis.brand.copy(alpha = 0.92f)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(Icons.Rounded.Sync, contentDescription = null, tint = Color.White, modifier = Modifier.size(48.dp))
    }
}

/** Écran plein, sombre, pour les prises de vue. */
@Composable
private fun FullScreenDark(onClose: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    Dialog(
        onDismissRequest = onClose,
        properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false),
    ) {
        Column(
            Modifier.fillMaxSize().background(Color(0xFF0B0F14)).statusBarsPadding().navigationBarsPadding()
                .padding(horizontal = 20.dp, vertical = 12.dp),
            content = content,
        )
    }
}

@Composable
private fun CloseButton(onClose: () -> Unit) {
    val app = LocalApp.current
    IconButton(onClick = onClose, modifier = Modifier.clip(CircleShape).background(Color.White.copy(alpha = 0.14f))) {
        Icon(Icons.Rounded.Close, contentDescription = app.t("close"), tint = Color.White)
    }
}

// --- Vidéo du visage (CameraX + ML Kit) ---

/** Caméra avant sans micro : suit les consignes de [SelfieScript] image par
 * image et enregistre la vidéo entre la première et la dernière consigne. */
private class SelfieCamera(
    private val context: Context,
    private val onStatus: (Status) -> Unit,
    private val onVideo: (VideoShot?) -> Unit,
) {
    data class Status(
        val step: SelfieScript.Step,
        val number: Int,
        val recording: Boolean,
        val severalFaces: Boolean,
        val restarted: Boolean,
    )

    private class Take(val file: File)

    private var script = SelfieScript()
    private val analysis = Executors.newSingleThreadExecutor()
    private val main = ContextCompat.getMainExecutor(context)
    private val faces = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
            .build(),
    )
    private val recorder = Recorder.Builder()
        .setQualitySelector(QualitySelector.from(Quality.HD, FallbackStrategy.lowerQualityOrHigherThan(Quality.SD)))
        .setTargetVideoEncodingBitRate(2_000_000)
        .build()
    private val videoCapture = VideoCapture.withOutput(recorder)
    private var recording: Recording? = null
    private var take: Take? = null
    private var thumbnail: ImageBitmap? = null
    @Volatile private var finishing = false
    @Volatile private var released = false
    @Volatile private var pending: Triple<Take, Int, List<HeadTurn>>? = null
    private var provider: ProcessCameraProvider? = null

    val turns: List<HeadTurn> get() = script.turns

    fun bind(provider: ProcessCameraProvider, owner: LifecycleOwner, view: PreviewView) {
        this.provider = provider
        val preview = Preview.Builder().build().also { it.setSurfaceProvider(view.surfaceProvider) }
        val frames = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
            .build()
        frames.setAnalyzer(analysis, ::analyze)
        provider.unbindAll()
        provider.bindToLifecycle(owner, CameraSelector.DEFAULT_FRONT_CAMERA, preview, frames, videoCapture)
    }

    fun release() {
        released = true
        provider?.unbindAll()
        recording?.stop()
        recording = null
        analysis.execute { faces.close() }
        analysis.shutdown()
    }

    private fun analyze(proxy: ImageProxy) {
        if (finishing) {
            proxy.close()
            return
        }
        val bitmap = rotated(proxy.toBitmap(), proxy.imageInfo.rotationDegrees)
        val time = proxy.imageInfo.timestamp / 1e9
        proxy.close()
        val found = try {
            Tasks.await(faces.process(InputImage.fromBitmap(bitmap, 0)))
        } catch (_: Exception) {
            emptyList()
        }
        val sample = sample(found, bitmap.width, bitmap.height)
        val event = script.feed(sample, time)
        when (event) {
            SelfieScript.Event.START_RECORDING -> start(bitmap)
            SelfieScript.Event.RESTART -> discard()
            SelfieScript.Event.FINISHED -> finish()
            else -> Unit
        }
        val status = Status(script.step, script.number, take != null, script.severalFaces, event == SelfieScript.Event.RESTART)
        main.execute { onStatus(status) }
    }

    private fun sample(found: List<Face>, width: Int, height: Int): FaceSample {
        if (found.size != 1) return FaceSample(found.size)
        val face = found.first()
        val box = face.boundingBox
        val nose = face.getLandmark(FaceLandmark.NOSE_BASE)?.position
        val offset = if (nose != null && box.width() > 0) (nose.x - box.exactCenterX()) / box.width() else 0f
        // Angle Y de ML Kit : positif vers la droite de l'image, comme le nez.
        // S'ils ne disent pas le même sens, l'angle n'est pas retenu.
        val y = face.headEulerAngleY
        val agrees = abs(y) < 10f || (y > 0) == (offset > 0)
        return FaceSample(
            faceCount = 1,
            centerX = box.exactCenterX().toDouble() / width,
            centerY = box.exactCenterY().toDouble() / height,
            width = box.width().toDouble() / width,
            turnDegrees = if (agrees) abs(y).toDouble() else 0.0,
            noseOffset = offset.toDouble(),
        )
    }

    private fun start(frame: Bitmap) {
        discard()
        // La vignette montre la personne comme elle se voyait (en miroir).
        thumbnail = Bitmap.createBitmap(frame, 0, 0, frame.width, frame.height, Matrix().apply { postScale(-1f, 1f) }, true)
            .asImageBitmap()
        val current = Take(File(context.cacheDir, "nexis-visage-${UUID.randomUUID()}.mp4"))
        take = current
        main.execute {
            // Sans withAudioEnabled() : la vidéo n'a pas de son, le micro n'est jamais ouvert.
            recording = recorder.prepareRecording(context, FileOutputOptions.Builder(current.file).build())
                .start(main) { event -> if (event is VideoRecordEvent.Finalize) finalize(current, event) }
        }
    }

    private fun finish() {
        val current = take ?: return
        finishing = true
        pending = Triple(current, script.seconds, script.turns)
        main.execute {
            recording?.stop()
            recording = null
        }
    }

    private fun finalize(current: Take, event: VideoRecordEvent.Finalize) {
        val wanted = pending
        if (released || wanted == null || wanted.first !== current) {
            current.file.delete()
            return
        }
        pending = null
        val bytes = if (!event.hasError() || event.error == VideoRecordEvent.Finalize.ERROR_SOURCE_INACTIVE) {
            runCatching { current.file.readBytes() }.getOrNull()
        } else {
            null
        }
        current.file.delete()
        if (bytes == null || bytes.isEmpty()) {
            // La vidéo n'a pas pu être lue : les consignes reprennent au début.
            if (!analysis.isShutdown) {
                analysis.execute {
                    script = SelfieScript()
                    take = null
                    finishing = false
                }
            }
            onVideo(null)
        } else {
            onVideo(VideoShot(bytes, thumbnail, wanted.second, wanted.third))
        }
    }

    /** Abandonne l'enregistrement en cours ; son fichier est effacé à la fin. */
    private fun discard() {
        take = null
        main.execute {
            recording?.stop()
            recording = null
        }
    }
}

@Composable
private fun SelfieVideoScreen(demo: Boolean, onClose: () -> Unit, onDone: (VideoShot) -> Unit) {
    val app = LocalApp.current
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val reduceMotion = rememberReduceMotion()
    val scope = rememberCoroutineScope()
    var granted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    var denied by remember { mutableStateOf(false) }
    val hasFront = remember { context.packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_FRONT) }
    var step by remember { mutableStateOf<SelfieScript.Step>(if (demo) SelfieScript.Step.Turn(HeadTurn.LEFT) else SelfieScript.Step.FaceIn) }
    var number by remember { mutableStateOf(if (demo) 2 else 1) }
    var recording by remember { mutableStateOf(demo) }
    var severalFaces by remember { mutableStateOf(false) }
    var tooSlow by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        granted = ok
        denied = !ok
    }
    LaunchedEffect(Unit) { if (!demo && !granted && hasFront) permission.launch(Manifest.permission.CAMERA) }
    val previewView = remember {
        PreviewView(context).apply {
            scaleType = PreviewView.ScaleType.FILL_CENTER
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        }
    }
    if (!demo && granted && hasFront) {
        DisposableEffect(owner) {
            val camera = SelfieCamera(
                context,
                onStatus = { status ->
                    step = status.step
                    number = status.number
                    recording = status.recording
                    severalFaces = status.severalFaces
                    if (status.restarted) {
                        tooSlow = true
                        scope.launch {
                            delay(2_500)
                            tooSlow = false
                        }
                    }
                },
                onVideo = { video ->
                    if (video == null) {
                        failed = true
                        scope.launch {
                            delay(2_500)
                            failed = false
                        }
                    } else {
                        scope.launch {
                            delay(900)
                            onDone(video)
                        }
                    }
                },
            )
            val future = ProcessCameraProvider.getInstance(context)
            future.addListener({ camera.bind(future.get(), owner, previewView) }, ContextCompat.getMainExecutor(context))
            onDispose { camera.release() }
        }
    }
    val instruction = when {
        !hasFront -> app.t("cameraMissing")
        denied -> app.t("cameraDenied")
        failed -> app.t("actionFailed")
        tooSlow -> app.t("selfieTooSlow")
        severalFaces -> app.t("selfieOneFace")
        else -> when (val current = step) {
            SelfieScript.Step.FaceIn -> app.t("selfieFaceIn")
            is SelfieScript.Step.Turn -> app.t(if (current.turn == HeadTurn.LEFT) "selfieTurnLeft" else "selfieTurnRight")
            SelfieScript.Step.LookAhead -> app.t("selfieLookAhead")
            SelfieScript.Step.Done -> app.t("selfieDone")
        }
    }
    val warning = !hasFront || denied || failed || tooSlow || severalFaces
    FullScreenDark(onClose) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            CloseButton(onClose)
            Spacer(Modifier.weight(1f))
            if (recording) {
                Row(
                    Modifier.clip(CircleShape).background(Color.White.copy(alpha = 0.14f)).padding(horizontal = 12.dp, vertical = 7.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.size(9.dp).clip(CircleShape).background(Color(0xFFFF3B30)))
                    Text(app.t("selfieRecording"), style = body(13, FontWeight.SemiBold, Color.White), modifier = Modifier.padding(start = 6.dp))
                }
            }
        }
        Text(
            app.t("selfieTitle"), style = title(19, color = Color.White),
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp).semantics { heading() }, textAlign = TextAlign.Center,
        )
        BoxWithConstraints(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
            val diameter = minOf(maxWidth * 0.8f, maxHeight * 0.9f)
            Box(Modifier.size(diameter).clip(CircleShape).background(Color(0xFF1C2129)), contentAlignment = Alignment.Center) {
                if (demo) {
                    DemoFace(step, reduceMotion)
                } else if (granted && hasFront) {
                    AndroidView({ previewView }, Modifier.fillMaxSize())
                }
            }
            val done = if (step == SelfieScript.Step.Done) 4 else number - 1
            Canvas(Modifier.size(diameter + 22.dp).clearAndSetSemantics { }) {
                val gap = 4f
                for (i in 0 until 4) {
                    drawArc(
                        color = if (i < done) Color(0xFF34C759) else Color.White.copy(alpha = if (recording) 0.45f else 0.28f),
                        startAngle = -90f + i * 90f + gap, sweepAngle = 90f - 2 * gap, useCenter = false,
                        topLeft = Offset(3.dp.toPx(), 3.dp.toPx()), size = Size(size.width - 6.dp.toPx(), size.height - 6.dp.toPx()),
                        style = Stroke(width = 6.dp.toPx(), cap = StrokeCap.Round),
                    )
                }
            }
            val turn = (step as? SelfieScript.Step.Turn)?.turn
            if (turn != null) {
                // La flèche montre le côté vers lequel tourner, dans l'image en miroir.
                Box(
                    Modifier.offset(x = (diameter / 2 + 4.dp) * (if (turn == HeadTurn.LEFT) -1f else 1f))
                        .size(58.dp).clip(CircleShape).background(Nexis.brand).clearAndSetSemantics { },
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        if (turn == HeadTurn.LEFT) Icons.AutoMirrored.Rounded.ArrowBack else Icons.AutoMirrored.Rounded.ArrowForward,
                        contentDescription = null, tint = Color.White, modifier = Modifier.size(30.dp),
                    )
                }
            }
        }
        Column(
            Modifier.fillMaxWidth().padding(bottom = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(app.t("selfieStep", "step" to number.toString(), "total" to "4"), style = body(13, FontWeight.SemiBold, Nexis.halo))
            Text(
                instruction, style = title(23, color = if (warning) Color(0xFFFF8A80) else Color.White), textAlign = TextAlign.Center,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )
            if (step == SelfieScript.Step.FaceIn && !warning) {
                Text(app.t("selfieIntro"), style = body(14, color = Color.White.copy(alpha = 0.78f)), textAlign = TextAlign.Center)
            }
            if (denied) {
                PrimaryButton(app.t("notifOpenSettings"), {
                    context.startActivity(
                        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", context.packageName, null)),
                    )
                })
            }
        }
    }
}

@Composable
private fun DemoFace(step: SelfieScript.Step, reduceMotion: Boolean) {
    val target = when ((step as? SelfieScript.Step.Turn)?.turn) {
        HeadTurn.LEFT -> -28f
        HeadTurn.RIGHT -> 28f
        null -> 0f
    }
    val angle by animateFloatAsState(target, if (reduceMotion) tween(0) else tween(600), label = "tete")
    Box(Modifier.fillMaxSize().background(Color(0xFF2E3440)), contentAlignment = Alignment.BottomCenter) {
        Icon(
            Icons.Rounded.Person, contentDescription = null, tint = Color(0xFF8C99AD),
            modifier = Modifier.fillMaxSize(0.92f).offset(y = 24.dp).graphicsLayer { rotationY = angle },
        )
    }
}

// --- Démonstration (captures de la CI) ---

/** Une pièce d'identité dessinée, sans aucun texte : le recto porte un
 * visage, le verso des lignes et un code, la page du passeport un visage et
 * deux lignes de lecture automatique. */
private fun specimenBitmap(side: CardSide, width: Int): Bitmap {
    val height = (width / side.ratio).toInt()
    val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
    val canvas = android.graphics.Canvas(bitmap)
    val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    val w = width.toFloat()
    val h = height.toFloat()
    val radius = w * 0.045f
    paint.color = 0xFFE3ECF8.toInt()
    canvas.drawRoundRect(RectF(0f, 0f, w, h), radius, radius, paint)
    paint.color = 0xD90A63F0.toInt()
    canvas.save()
    canvas.clipRect(0f, 0f, w, h * 0.16f)
    canvas.drawRoundRect(RectF(0f, 0f, w, h * 0.3f), radius, radius, paint)
    canvas.restore()
    paint.color = 0xFF8FA3BF.toInt()
    fun lines(x: Float, y: Float, length: Float, count: Int) {
        for (i in 0 until count) {
            val top = y + i * h * 0.105f
            val end = x + length * (if (i % 2 == 0) 1f else 0.7f)
            canvas.drawRoundRect(RectF(x, top, end, top + h * 0.045f), h * 0.03f, h * 0.03f, paint)
        }
    }
    if (side != CardSide.VERSO) {
        val passport = side == CardSide.PASSPORT_PAGE
        paint.color = 0xFFB9C9DE.toInt()
        val photo = RectF(w * 0.06f, h * 0.24f, w * 0.32f, h * (if (passport) 0.7f else 0.82f))
        canvas.drawRoundRect(photo, w * 0.02f, w * 0.02f, paint)
        paint.color = 0xFF6F84A3.toInt()
        canvas.drawCircle(photo.centerX(), photo.top + photo.height() * 0.38f, photo.width() * 0.22f, paint)
        canvas.drawRoundRect(
            RectF(photo.left + photo.width() * 0.16f, photo.top + photo.height() * 0.64f, photo.right - photo.width() * 0.16f, photo.bottom + photo.width() * 0.1f),
            photo.width() * 0.3f, photo.width() * 0.3f, paint,
        )
        paint.color = 0xFF8FA3BF.toInt()
        lines(w * 0.38f, h * 0.26f, w * 0.54f, if (passport) 4 else 5)
        if (passport) {
            // Les deux lignes de lecture automatique, dessinées en blocs.
            paint.color = 0xD924344D.toInt()
            for (row in 0 until 2) {
                val top = h * (0.77f + row * 0.1f)
                for (i in 0 until 30) {
                    val left = w * (0.05f + i * 0.03f)
                    canvas.drawRoundRect(RectF(left, top, left + w * 0.024f, top + h * 0.055f), 2f, 2f, paint)
                }
            }
        }
    } else {
        lines(w * 0.06f, h * 0.26f, w * 0.6f, 4)
        paint.color = 0xFFC7D3E3.toInt()
        canvas.drawRoundRect(RectF(w * 0.74f, h * 0.3f, w * 0.94f, h * 0.3f + w * 0.2f), w * 0.015f, w * 0.015f, paint)
        paint.color = 0xFF24344D.toInt()
        var x = w * 0.06f
        var i = 0
        while (x < w * 0.66f) {
            val bar = w * (if (i % 3 == 0) 0.008f else 0.004f)
            canvas.drawRect(x, h * 0.72f, x + bar, h * 0.92f, paint)
            x += bar + w * 0.008f
            i += 1
        }
    }
    return bitmap
}

/** Images de démonstration (dessinées par l'app, pas des photos). */
private object IdentityDemoImages {
    fun shot(side: CardSide): CardShot {
        val bitmap = specimenBitmap(side, 856)
        return CardShot(jpeg(bitmap), bitmap.asImageBitmap(), cardHashes(bitmap), side != CardSide.VERSO, side == CardSide.PASSPORT_PAGE)
    }

    fun draft(): IdentityDraft = IdentityDraft(
        document = IdentityDocument.VOTER_CARD,
        recto = shot(CardSide.RECTO),
        verso = shot(CardSide.VERSO),
        video = VideoShot("aperçu".toByteArray(), null, 7, listOf(HeadTurn.LEFT, HeadTurn.RIGHT)),
    )
}
