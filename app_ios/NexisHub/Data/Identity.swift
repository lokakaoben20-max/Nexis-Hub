import CoreGraphics
import Foundation

// Étape « Pièce d'identité » de « Devenir prestataire » : ce qui est envoyé,
// et les règles qui guident la prise sur le téléphone.
//
// Exception à « pas d'IA avant le lancement » (AGENTS.md, décision de Ben du
// 2026-11-26) : l'analyse d'image du téléphone (Vision) guide la prise,
// rien de plus. Elle ne valide ni ne refuse personne : c'est l'équipe
// NexisHub qui vérifie la personne. Aucune image ne part vers un service
// d'IA extérieur.

/// Les deux faces de la pièce et la courte vidéo du visage (sans son).
struct IdentityCapture: Equatable {
    var recto: Data
    var verso: Data
    /// Vidéo H.264 sans piste audio.
    var video: Data
    var videoSeconds: Int
    /// Ordre des consignes données pendant la vidéo (tiré au sort), pour que
    /// l'équipe puisse le comparer à ce qu'elle voit.
    var headTurns: [HeadTurn]

    var isComplete: Bool {
        !recto.isEmpty && !verso.isEmpty && !video.isEmpty && videoSeconds > 0
            && headTurns.count == 2 && Set(headTurns) == Set(HeadTurn.allCases)
    }
}

enum CardSide: String, CaseIterable { case recto, verso }

/// Le sens dans lequel la personne tourne la tête (sa gauche, sa droite).
enum HeadTurn: String, CaseIterable { case left, right }

// MARK: - Recto ou verso

enum CardVerdict: Equatable {
    case accepted
    /// On attendait le recto et la carte ne porte pas de photo de visage.
    case showRectoFirst
    /// On attendait le verso et c'est encore le recto.
    case stillRecto
}

enum CardCheck {
    /// Écart (bits différents sur 64) en dessous duquel deux prises montrent
    /// la même face.
    static let sameSide = 10
    /// Écart plus large toléré quand un visage est aussi visible sur la prise.
    static let sameSideWithFace = 20

    /// Le recto porte la photo de la personne. Le verso ne doit pas être la
    /// même image que le recto (comparée dans les deux sens de lecture).
    static func verdict(expected: CardSide, faceFound: Bool,
                        hashes: [UInt64], rectoHash: UInt64?) -> CardVerdict {
        switch expected {
        case .recto:
            return faceFound ? .accepted : .showRectoFirst
        case .verso:
            guard let rectoHash, let distance = hashes.map({ ImageHash.distance($0, rectoHash) }).min() else {
                return .accepted
            }
            if distance <= sameSide || (faceFound && distance <= sameSideWithFace) { return .stillRecto }
            return .accepted
        }
    }
}

/// Empreinte « dHash » d'une image réduite à 9 × 8 niveaux de gris : un bit
/// par paire de pixels voisins sur chaque ligne.
enum ImageHash {
    static let width = 9
    static let height = 8

    /// `gray` : 72 valeurs, ligne par ligne, de haut en bas.
    static func dHash(_ gray: [UInt8]) -> UInt64 {
        precondition(gray.count == width * height)
        var hash: UInt64 = 0
        for row in 0..<height {
            for column in 0..<(width - 1) {
                hash <<= 1
                if gray[row * width + column] < gray[row * width + column + 1] { hash |= 1 }
            }
        }
        return hash
    }

    /// La même grille tournée d'un demi-tour (carte présentée à l'envers).
    static func halfTurn(_ gray: [UInt8]) -> [UInt8] { gray.reversed() }

    static func distance(_ a: UInt64, _ b: UInt64) -> Int { (a ^ b).nonzeroBitCount }
}

// MARK: - Carte immobile dans le cadre

/// Les quatre coins d'une carte, en coordonnées normalisées (0…1).
struct CardQuad: Equatable {
    var topLeft: CGPoint
    var topRight: CGPoint
    var bottomRight: CGPoint
    var bottomLeft: CGPoint

    var corners: [CGPoint] { [topLeft, topRight, bottomRight, bottomLeft] }

    /// Le plus grand déplacement d'un coin entre deux quadrilatères.
    func distance(to other: CardQuad) -> Double {
        zip(corners, other.corners).map { hypot(Double($0.x - $1.x), Double($0.y - $1.y)) }.max() ?? .infinity
    }
}

/// Déclenche la photo quand la carte reste immobile dans le cadre sur
/// plusieurs images de suite.
struct StableCardTracker {
    var needed = 12
    var tolerance = 0.02
    private(set) var recent: [CardQuad] = []

    /// Ajoute la carte vue sur une image (nil : aucune carte). Vrai quand elle
    /// est immobile depuis `needed` images.
    mutating func add(_ quad: CardQuad?) -> Bool {
        guard let quad else { recent.removeAll(); return false }
        if let last = recent.last, last.distance(to: quad) > tolerance * 2 { recent.removeAll() }
        recent.append(quad)
        if recent.count > needed { recent.removeFirst(recent.count - needed) }
        guard recent.count == needed else { return false }
        return recent.allSatisfy { $0.distance(to: quad) <= tolerance }
    }

    /// Une carte est vue, mais pas encore immobile assez longtemps.
    var isHolding: Bool { !recent.isEmpty }

    mutating func reset() { recent.removeAll() }
}

// MARK: - Vidéo guidée du visage

/// Ce que l'analyse voit sur une image de la caméra avant : image droite,
/// non inversée (telle que la caméra la voit, pas en miroir).
struct FaceSample: Equatable {
    var faceCount: Int
    /// Centre du visage, 0…1, origine en haut à gauche.
    var centerX: Double = 0.5
    var centerY: Double = 0.45
    /// Largeur du visage rapportée à la largeur de l'image.
    var width: Double = 0.45
    /// Angle de la tête, en degrés, sans le sens (nil si inconnu).
    var turnDegrees: Double?
    /// Position du nez par rapport au centre du visage, en largeur de visage.
    /// Positif : vers la droite de l'image, donc vers la gauche de la personne.
    var noseOffset: Double = 0
}

enum HeadPosition: Equatable { case ahead, turned(HeadTurn), between }

enum HeadPose {
    static func position(_ sample: FaceSample) -> HeadPosition {
        let offset = sample.noseOffset
        let turnedEnough: Bool
        let ahead: Bool
        if let degrees = sample.turnDegrees {
            turnedEnough = degrees >= 20 && abs(offset) >= 0.03
            ahead = degrees <= 10 && abs(offset) < 0.08
        } else {
            turnedEnough = abs(offset) >= 0.14
            ahead = abs(offset) < 0.06
        }
        if turnedEnough { return .turned(offset > 0 ? .left : .right) }
        return ahead ? .ahead : .between
    }

    /// Visage seul, de face, assez grand et au milieu du cercle.
    static func isFramed(_ sample: FaceSample) -> Bool {
        sample.faceCount == 1 && abs(sample.centerX - 0.5) <= 0.15 && abs(sample.centerY - 0.45) <= 0.18
            && (0.28...0.85).contains(sample.width) && position(sample) == .ahead
    }
}

/// Les consignes de la vidéo, l'une après l'autre. Chacune doit être tenue
/// sur quelques images avant de passer à la suivante.
struct SelfieScript {
    enum Step: Equatable { case faceIn, turn(HeadTurn), lookAhead, done }

    enum Event: Equatable {
        case none
        /// Le visage est bien placé : l'enregistrement commence.
        case startRecording
        case advanced
        case finished
        /// Trop long ou visage perdu : on recommence au début.
        case restart
    }

    /// Gauche et droite, dans un ordre tiré au sort.
    let turns: [HeadTurn]
    var holdNeeded = 5
    /// Durée maximale de l'enregistrement, en secondes.
    var timeLimit: TimeInterval = 20
    /// Images sans visage tolérées pendant l'enregistrement.
    var lostLimit = 30

    private(set) var step: Step = .faceIn
    private(set) var recordingStartedAt: TimeInterval?
    private(set) var finishedAt: TimeInterval?
    private(set) var severalFaces = false
    private var hold = 0
    private var lost = 0

    init(turns: [HeadTurn] = HeadTurn.allCases.shuffled()) {
        precondition(Set(turns) == Set(HeadTurn.allCases) && turns.count == 2)
        self.turns = turns
    }

    var steps: [Step] { [.faceIn, .turn(turns[0]), .turn(turns[1]), .lookAhead] }

    /// Numéro de la consigne en cours (1…4).
    var number: Int { min((steps.firstIndex(of: step) ?? steps.count - 1) + 1, steps.count) }

    var seconds: Int {
        guard let start = recordingStartedAt, let end = finishedAt else { return 0 }
        return max(1, Int((end - start).rounded()))
    }

    mutating func feed(_ sample: FaceSample, at time: TimeInterval) -> Event {
        guard step != .done else { return .none }
        if let start = recordingStartedAt, time - start > timeLimit { return restart() }
        severalFaces = sample.faceCount > 1
        guard sample.faceCount == 1 else {
            hold = 0
            if recordingStartedAt != nil {
                lost += 1
                if lost > lostLimit { return restart() }
            }
            return .none
        }
        lost = 0
        let position = HeadPose.position(sample)
        let met: Bool
        switch step {
        case .faceIn: met = HeadPose.isFramed(sample)
        case .turn(let turn): met = position == .turned(turn)
        case .lookAhead: met = position == .ahead
        case .done: met = false
        }
        guard met else { hold = 0; return .none }
        hold += 1
        guard hold >= holdNeeded else { return .none }
        hold = 0
        switch step {
        case .faceIn:
            step = .turn(turns[0])
            recordingStartedAt = time
            return .startRecording
        case .turn(let turn):
            step = turn == turns[0] ? .turn(turns[1]) : .lookAhead
            return .advanced
        case .lookAhead:
            step = .done
            finishedAt = time
            return .finished
        case .done:
            return .none
        }
    }

    private mutating func restart() -> Event {
        step = .faceIn
        recordingStartedAt = nil
        finishedAt = nil
        hold = 0
        lost = 0
        return .restart
    }
}
