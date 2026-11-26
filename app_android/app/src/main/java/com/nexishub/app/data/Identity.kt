package com.nexishub.app.data

import kotlin.math.abs
import kotlin.math.roundToInt

// Étape « Pièce d'identité » de « Devenir prestataire » : ce qui est envoyé,
// et les règles qui guident la prise sur le téléphone.
//
// Exception à « pas d'IA avant le lancement » (AGENTS.md, décision de Ben du
// 2026-11-26) : ML Kit, sur le téléphone, guide la prise, rien de plus. Il ne
// valide ni ne refuse personne : c'est l'équipe NexisHub qui vérifie la
// personne. Aucune image ne part vers un service d'IA extérieur.

/** Les pièces acceptées. Une carte se prend recto et verso ; un passeport,
 * seulement la page avec la photo. */
enum class IdentityDocument {
    VOTER_CARD, DRIVING_LICENCE, PASSPORT;

    val needsVerso: Boolean get() = this != PASSPORT

    /** Les faces à prendre, dans l'ordre. */
    val sides: List<CardSide> get() = if (needsVerso) listOf(CardSide.RECTO, CardSide.VERSO) else listOf(CardSide.PASSPORT_PAGE)
}

/** La pièce (une ou deux faces) et la courte vidéo du visage (sans son). */
class IdentityCapture(
    val document: IdentityDocument,
    /** Recto de la carte, ou page photo du passeport. */
    val recto: ByteArray,
    /** Verso de la carte ; absent pour un passeport. */
    val verso: ByteArray?,
    /** Vidéo MP4 (H.264) sans piste audio. */
    val video: ByteArray,
    val videoSeconds: Int,
    /** Ordre des consignes données pendant la vidéo (tiré au sort), pour que
     * l'équipe puisse le comparer à ce qu'elle voit. */
    val headTurns: List<HeadTurn>,
) {
    val isComplete: Boolean
        get() = recto.isNotEmpty() && (if (document.needsVerso) verso?.isNotEmpty() == true else verso == null) &&
            video.isNotEmpty() && videoSeconds > 0 &&
            headTurns.size == 2 && headTurns.toSet() == HeadTurn.entries.toSet()
}

enum class CardSide { RECTO, VERSO, PASSPORT_PAGE }

/** Le sens dans lequel la personne tourne la tête (sa gauche, sa droite). */
enum class HeadTurn { LEFT, RIGHT }

// --- Recto ou verso ---

enum class CardVerdict {
    ACCEPTED,

    /** On attendait le recto et la carte ne porte pas de photo de visage. */
    SHOW_RECTO_FIRST,

    /** On attendait le verso et c'est encore le recto. */
    STILL_RECTO,

    /** On attendait la page photo du passeport et ce n'est pas elle. */
    SHOW_PHOTO_PAGE,
}

object CardCheck {
    /** Écart (bits différents sur 64) en dessous duquel deux prises montrent la même face. */
    const val SAME_SIDE = 10

    /** Écart plus large toléré quand un visage est aussi visible sur la prise. */
    const val SAME_SIDE_WITH_FACE = 20

    /** Le recto porte la photo de la personne. Le verso ne doit pas être la
     * même image que le recto (comparée dans les deux sens de lecture). */
    fun verdict(expected: CardSide, faceFound: Boolean, hashes: List<Long>, rectoHash: Long?, machineZone: Boolean = false): CardVerdict =
        when (expected) {
            // Passeport : un visage et la zone de lecture automatique.
            CardSide.PASSPORT_PAGE -> if (faceFound && machineZone) CardVerdict.ACCEPTED else CardVerdict.SHOW_PHOTO_PAGE
            CardSide.RECTO -> if (faceFound) CardVerdict.ACCEPTED else CardVerdict.SHOW_RECTO_FIRST
            CardSide.VERSO -> {
                val distance = rectoHash?.let { recto -> hashes.minOfOrNull { ImageHash.distance(it, recto) } }
                when {
                    distance == null -> CardVerdict.ACCEPTED
                    distance <= SAME_SIDE || (faceFound && distance <= SAME_SIDE_WITH_FACE) -> CardVerdict.STILL_RECTO
                    else -> CardVerdict.ACCEPTED
                }
            }
        }
}

/** La zone de lecture automatique de la page photo d'un passeport : deux
 * lignes de 44 signes (lettres, chiffres, « < »), la première commence par
 * « P ». Le texte lu sert seulement à reconnaître la page ; il n'est ni gardé
 * ni envoyé. */
object MachineZone {
    fun found(lines: List<String>): Boolean {
        val cleaned = lines.map { line -> line.uppercase().filterNot { it.isWhitespace() }.replace('«', '<') }
        fun machineLike(line: String): Boolean {
            if (line.length < 30) return false
            val allowed = line.count { (it in 'A'..'Z') || (it in '0'..'9') || it == '<' }
            return allowed.toDouble() / line.length >= 0.9 && '<' in line
        }
        val first = cleaned.indexOfFirst { it.startsWith("P") && machineLike(it) && "<<" in it }
        if (first < 0) return false
        return cleaned.indices.any { it != first && machineLike(cleaned[it]) }
    }
}

/** Empreinte « dHash » d'une image réduite à 9 × 8 niveaux de gris : un bit
 * par paire de pixels voisins sur chaque ligne. */
object ImageHash {
    const val WIDTH = 9
    const val HEIGHT = 8

    /** [gray] : 72 valeurs (0…255), ligne par ligne, de haut en bas. */
    fun dHash(gray: IntArray): Long {
        require(gray.size == WIDTH * HEIGHT)
        var hash = 0L
        for (row in 0 until HEIGHT) {
            for (column in 0 until WIDTH - 1) {
                hash = hash shl 1
                if (gray[row * WIDTH + column] < gray[row * WIDTH + column + 1]) hash = hash or 1L
            }
        }
        return hash
    }

    /** La même grille tournée d'un demi-tour (carte présentée à l'envers). */
    fun halfTurn(gray: IntArray): IntArray = gray.reversedArray()

    fun distance(a: Long, b: Long): Int = java.lang.Long.bitCount(a xor b)
}

// --- Vidéo guidée du visage ---

/** Ce que l'analyse voit sur une image de la caméra avant : image droite,
 * non inversée (telle que la caméra la voit, pas en miroir). */
data class FaceSample(
    val faceCount: Int,
    /** Centre du visage, 0…1, origine en haut à gauche. */
    val centerX: Double = 0.5,
    val centerY: Double = 0.45,
    /** Largeur du visage rapportée à la largeur de l'image. */
    val width: Double = 0.45,
    /** Angle de la tête, en degrés, sans le sens (null si inconnu). */
    val turnDegrees: Double? = null,
    /** Position du nez par rapport au centre du visage, en largeur de visage.
     * Positif : vers la droite de l'image, donc vers la gauche de la personne. */
    val noseOffset: Double = 0.0,
)

sealed interface HeadPosition {
    data object Ahead : HeadPosition
    data class Turned(val turn: HeadTurn) : HeadPosition
    data object Between : HeadPosition
}

object HeadPose {
    fun position(sample: FaceSample): HeadPosition {
        val offset = sample.noseOffset
        val degrees = sample.turnDegrees
        val turnedEnough: Boolean
        val ahead: Boolean
        if (degrees != null) {
            turnedEnough = degrees >= 20 && abs(offset) >= 0.03
            ahead = degrees <= 10 && abs(offset) < 0.08
        } else {
            turnedEnough = abs(offset) >= 0.14
            ahead = abs(offset) < 0.06
        }
        return when {
            turnedEnough -> HeadPosition.Turned(if (offset > 0) HeadTurn.LEFT else HeadTurn.RIGHT)
            ahead -> HeadPosition.Ahead
            else -> HeadPosition.Between
        }
    }

    /** Visage seul, de face, assez grand et au milieu du cercle. */
    fun isFramed(sample: FaceSample): Boolean =
        sample.faceCount == 1 && abs(sample.centerX - 0.5) <= 0.15 && abs(sample.centerY - 0.45) <= 0.18 &&
            sample.width in 0.28..0.85 && position(sample) == HeadPosition.Ahead
}

/** Les consignes de la vidéo, l'une après l'autre. Chacune doit être tenue sur
 * quelques images avant de passer à la suivante. */
class SelfieScript(
    /** Gauche et droite, dans un ordre tiré au sort. */
    val turns: List<HeadTurn> = HeadTurn.entries.shuffled(),
    val holdNeeded: Int = 5,
    /** Durée maximale de l'enregistrement, en secondes. */
    val timeLimit: Double = 20.0,
    /** Images sans visage tolérées pendant l'enregistrement. */
    val lostLimit: Int = 30,
) {
    sealed interface Step {
        data object FaceIn : Step
        data class Turn(val turn: HeadTurn) : Step
        data object LookAhead : Step
        data object Done : Step
    }

    enum class Event {
        NONE,

        /** Le visage est bien placé : l'enregistrement commence. */
        START_RECORDING,
        ADVANCED,
        FINISHED,

        /** Trop long ou visage perdu : on recommence au début. */
        RESTART,
    }

    init {
        require(turns.size == 2 && turns.toSet() == HeadTurn.entries.toSet())
    }

    var step: Step = Step.FaceIn
        private set
    var recordingStartedAt: Double? = null
        private set
    var finishedAt: Double? = null
        private set
    var severalFaces = false
        private set
    private var hold = 0
    private var lost = 0

    val steps: List<Step> get() = listOf(Step.FaceIn, Step.Turn(turns[0]), Step.Turn(turns[1]), Step.LookAhead)

    /** Numéro de la consigne en cours (1…4). */
    val number: Int
        get() = (steps.indexOf(step).takeIf { it >= 0 } ?: (steps.size - 1)) + 1

    val seconds: Int
        get() {
            val start = recordingStartedAt ?: return 0
            val end = finishedAt ?: return 0
            return maxOf(1, (end - start).roundToInt())
        }

    fun feed(sample: FaceSample, time: Double): Event {
        if (step == Step.Done) return Event.NONE
        recordingStartedAt?.let { if (time - it > timeLimit) return restart() }
        severalFaces = sample.faceCount > 1
        if (sample.faceCount != 1) {
            hold = 0
            if (recordingStartedAt != null) {
                lost += 1
                if (lost > lostLimit) return restart()
            }
            return Event.NONE
        }
        lost = 0
        val position = HeadPose.position(sample)
        val met = when (val current = step) {
            Step.FaceIn -> HeadPose.isFramed(sample)
            is Step.Turn -> position == HeadPosition.Turned(current.turn)
            Step.LookAhead -> position == HeadPosition.Ahead
            Step.Done -> false
        }
        if (!met) {
            hold = 0
            return Event.NONE
        }
        hold += 1
        if (hold < holdNeeded) return Event.NONE
        hold = 0
        return when (val current = step) {
            Step.FaceIn -> {
                step = Step.Turn(turns[0])
                recordingStartedAt = time
                Event.START_RECORDING
            }
            is Step.Turn -> {
                step = if (current.turn == turns[0]) Step.Turn(turns[1]) else Step.LookAhead
                Event.ADVANCED
            }
            Step.LookAhead -> {
                step = Step.Done
                finishedAt = time
                Event.FINISHED
            }
            Step.Done -> Event.NONE
        }
    }

    private fun restart(): Event {
        step = Step.FaceIn
        recordingStartedAt = null
        finishedAt = null
        hold = 0
        lost = 0
        return Event.RESTART
    }
}

