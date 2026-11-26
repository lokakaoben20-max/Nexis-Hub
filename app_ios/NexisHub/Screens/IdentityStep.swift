import AVFoundation
import SwiftUI
import UIKit

// Étape « Pièce d'identité » de « Devenir prestataire » : recto puis verso
// de la carte (ou page photo du passeport), pris par le scanner, et courte
// vidéo guidée du visage. Jamais
// de galerie. L'analyse sur le téléphone guide la prise ; c'est l'équipe
// NexisHub qui vérifie la personne.

/// Ce qui a été pris jusqu'ici.
struct IdentityDraft {
    /// Choisie par la personne avant la prise.
    var document: IdentityDocument?
    /// Recto de la carte, ou page photo du passeport.
    var recto: CardShot?
    var verso: CardShot?
    var video: VideoShot?

    var pieceDone: Bool {
        guard let document, recto != nil else { return false }
        return !document.needsVerso || verso != nil
    }

    var capture: IdentityCapture? {
        guard let document, let recto, let video, pieceDone else { return nil }
        let capture = IdentityCapture(document: document, recto: recto.jpeg,
                                      verso: document.needsVerso ? verso?.jpeg : nil, video: video.data,
                                      videoSeconds: video.seconds, headTurns: video.turns)
        return capture.isComplete ? capture : nil
    }

    /// Changer de pièce efface les faces déjà prises.
    mutating func choose(_ document: IdentityDocument) {
        guard document != self.document else { return }
        self.document = document
        recto = nil
        verso = nil
    }
}

/// Écrans figés pour les captures de la CI (pas d'appareil photo sur le
/// simulateur) : `become-identity`, `become-wrong-side`, `become-verso`,
/// `become-selfie`, `become-review`, `become-passport`, `become-wrong-page`.
enum IdentityDemo: String {
    case recto = "become-identity"
    case wrongSide = "become-wrong-side"
    case verso = "become-verso"
    case selfie = "become-selfie"
    case review = "become-review"
    case passport = "become-passport"
    case wrongPage = "become-wrong-page"

    static let captures: Set<String> = Set([recto, wrongSide, verso, selfie, review, passport, wrongPage].map(\.rawValue))
}

private struct ScanRequest: Identifiable {
    let sides: [CardSide]
    var id: String { sides.map(\.rawValue).joined() }
}

struct IdentityStep: View {
    @Environment(AppModel.self) private var app
    @Binding var draft: IdentityDraft
    @State private var scanning: ScanRequest?
    @State private var filming = false

    private var demo: IdentityDemo? { app.capture.flatMap(IdentityDemo.init(rawValue:)) }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            cardSection
            videoSection
            InfoNote(text: app.t("becomeGuideNote"), systemImage: "viewfinder")
            InfoNote(text: app.t("becomeIdentityHint"), systemImage: "lock.shield.fill")
            InfoNote(text: app.t("becomeDemoNote"), kind: .violet)
        }
        .fullScreenCover(item: $scanning) { request in
            CardScannerView(sides: request.sides, rectoHashes: request.sides.first == .verso ? draft.recto?.hashes : nil,
                            demo: demo) { shots in
                if let recto = shots[.recto] ?? shots[.passportPage] { draft.recto = recto }
                if let verso = shots[.verso] { draft.verso = verso }
            }
        }
        .fullScreenCover(isPresented: $filming) {
            SelfieVideoView(demo: demo == .selfie) { draft.video = $0 }
        }
        .onAppear(perform: openDemo)
    }

    private func openDemo() {
        switch demo {
        case .recto?, .wrongSide?:
            draft.choose(.voterCard)
            scanning = ScanRequest(sides: [.recto, .verso])
        case .verso?:
            draft.choose(.voterCard)
            scanning = ScanRequest(sides: [.verso])
        case .passport?, .wrongPage?:
            draft.choose(.passport)
            scanning = ScanRequest(sides: [.passportPage])
        case .selfie?: filming = true
        case .review?: draft = IdentityDemoImages.draft()
        case nil: break
        }
    }

    private var cardSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionLine(title: app.t("becomeIdDocument"), subtitle: app.t("becomeIdDocumentSub"),
                        systemImage: "person.text.rectangle", done: draft.pieceDone)
            Text(app.t("becomeDocChoose")).font(.body(13.5, .semibold, relativeTo: .subheadline)).foregroundStyle(Nexis.ink)
            ForEach(IdentityDocument.allCases, id: \.self) { document in
                ChoiceRow(title: app.t(document.labelKey),
                          subtitle: app.t(document.needsVerso ? "becomeCardSides" : "becomePassportSub"),
                          selected: draft.document == document) {
                    Image(systemName: document.symbol).font(.system(size: 18)).foregroundStyle(Nexis.softInk)
                        .frame(width: 36, height: 36)
                        .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                        .accessibilityHidden(true)
                } action: {
                    draft.choose(document)
                }
            }
            if let document = draft.document {
                if draft.recto != nil || draft.verso != nil {
                    HStack(alignment: .top, spacing: 10) {
                        if document.needsVerso {
                            FaceThumb(label: app.t("becomeRecto"), shot: draft.recto) { scanning = ScanRequest(sides: [.recto]) }
                            FaceThumb(label: app.t("becomeVerso"), shot: draft.verso) { scanning = ScanRequest(sides: [.verso]) }
                        } else {
                            FaceThumb(label: app.t("becomePhotoPage"), shot: draft.recto, ratio: CardSide.passportPage.ratio) {
                                scanning = ScanRequest(sides: [.passportPage])
                            }
                        }
                    }
                }
                if !draft.pieceDone {
                    Button {
                        scanning = ScanRequest(sides: draft.recto == nil ? document.sides : [.verso])
                    } label: {
                        Label(app.t("becomeScanCard"), systemImage: "viewfinder").font(.body(14.5, .semibold))
                    }
                    .buttonStyle(OutlineButtonStyle(tint: Nexis.accent))
                }
            }
        }
        .nxCard(padding: 14)
        .accessibilityElement(children: .contain)
    }

    private var videoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                Group {
                    if let thumbnail = draft.video?.thumbnail {
                        Image(uiImage: thumbnail).resizable().scaledToFill()
                    } else {
                        Image(systemName: "video").font(.system(size: 22)).foregroundStyle(Nexis.softInk)
                    }
                }
                .frame(width: 64, height: 64)
                .background(Nexis.soft)
                .clipShape(Circle())
                .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 3) {
                    Text(app.t("becomeSelfie")).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                    Text(draft.video.map { app.t("becomeVideoDone", ["seconds": String($0.seconds)]) } ?? app.t("becomeSelfieSub"))
                        .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                }
                Spacer(minLength: 8)
                if draft.video != nil {
                    Image(systemName: "checkmark.circle.fill").font(.system(size: 22)).foregroundStyle(Nexis.ok)
                        .accessibilityHidden(true)
                }
            }
            Button { filming = true } label: {
                Label(app.t(draft.video == nil ? "becomeRecordVideo" : "becomeRetake"),
                      systemImage: draft.video == nil ? "video" : "arrow.counterclockwise")
                    .font(.body(14.5, .semibold))
            }
            .buttonStyle(OutlineButtonStyle(tint: Nexis.accent))
        }
        .nxCard(padding: 14)
        .accessibilityElement(children: .contain)
    }
}

extension IdentityDocument {
    var labelKey: String {
        switch self {
        case .voterCard: return "docVoterCard"
        case .drivingLicence: return "docDrivingLicence"
        case .passport: return "docPassport"
        }
    }

    var symbol: String {
        switch self {
        case .voterCard: return "person.text.rectangle"
        case .drivingLicence: return "car"
        case .passport: return "book.closed"
        }
    }
}

extension CardSide {
    /// Format de la pièce : carte ID-1 (85,6 × 54 mm) ou page de passeport
    /// ID-3 (125 × 88 mm).
    var ratio: CGFloat { self == .passportPage ? 125 / 88 : 1.586 }
}

private struct SectionLine: View {
    let title: String
    let subtitle: String
    let systemImage: String
    let done: Bool

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: systemImage).font(.system(size: 22)).foregroundStyle(Nexis.softInk)
                .frame(width: 64, height: 64)
                .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                Text(subtitle).font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
            }
            Spacer(minLength: 8)
            if done {
                Image(systemName: "checkmark.circle.fill").font(.system(size: 22)).foregroundStyle(Nexis.ok)
                    .accessibilityHidden(true)
            }
        }
    }
}

/// Aperçu d'une face, avec « Reprendre ».
private struct FaceThumb: View {
    @Environment(AppModel.self) private var app
    let label: String
    let shot: CardShot?
    var ratio: CGFloat = CardSide.recto.ratio
    let retake: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Nexis.soft)
                .aspectRatio(ratio, contentMode: .fit)
                .overlay {
                    if let shot {
                        Image(uiImage: shot.image).resizable().scaledToFill()
                    } else {
                        Image(systemName: "rectangle.dashed").font(.system(size: 22)).foregroundStyle(Nexis.softInk)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Nexis.line, lineWidth: 0.5))
                .accessibilityHidden(true)
            HStack(spacing: 4) {
                Text(label).font(.body(13, .semibold, relativeTo: .footnote)).foregroundStyle(Nexis.ink)
                Spacer(minLength: 4)
                if shot != nil {
                    Button(app.t("becomeRetake"), action: retake)
                        .font(.body(13, .semibold, relativeTo: .footnote))
                        .tint(Nexis.accent)
                        .accessibilityLabel("\(app.t("becomeRetake")) · \(label)")
                }
            }
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Scanner de la carte

@MainActor
@Observable
final class CardScanner {
    enum Phase: Equatable {
        case starting, denied, missing
        case searching, holding, checking
        case wrong(CardVerdict)
        case taken, turnCard
    }

    private(set) var phase: Phase = .starting
    private(set) var side: CardSide = .recto
    private(set) var quad: CardQuad?
    private(set) var frameSize: CGSize = .zero
    private(set) var shots: [CardSide: CardShot] = [:]
    private(set) var finished = false
    @ObservationIgnored let engine = CardEngine()
    @ObservationIgnored private var sides: [CardSide] = []
    @ObservationIgnored private var rectoHashes: [UInt64]?
    /// Après « Retournez la carte », la carte encore visible est ignorée un instant.
    @ObservationIgnored private var ignoreUntil = Date.distantPast

    func start(sides: [CardSide], rectoHashes: [UInt64]?) async {
        self.sides = sides
        self.rectoHashes = rectoHashes
        side = sides.first ?? .recto
        switch await CameraAccess.request(position: .back) {
        case .denied: phase = .denied; return
        case .missing: phase = .missing; return
        case .granted: break
        }
        engine.onFrame = { [weak self] quad, size, holding in
            Task { @MainActor in self?.frame(quad, size, holding) }
        }
        engine.onShot = { [weak self] shot in
            Task { @MainActor in await self?.shot(shot) }
        }
        engine.start()
        phase = .searching
        armEngine()
    }

    /// Autorise la prochaine photo ; la page d'un passeport fait aussi lire
    /// la zone de lecture automatique (sur le téléphone, rien n'est gardé).
    private func armEngine() { engine.arm(true, machineZone: side == .passportPage) }

    func stop() { engine.stop() }

    /// Montre une étape figée, sans appareil photo (captures, simulateur).
    func show(_ phase: Phase, side: CardSide) {
        self.phase = phase
        self.side = side
        quad = nil
    }

    func record(_ shot: CardShot, for side: CardSide) { shots[side] = shot }
    func finish() { finished = true }

    private func frame(_ quad: CardQuad?, _ size: CGSize, _ holding: Bool) {
        frameSize = size
        guard phase == .searching || phase == .holding else { return }
        guard Date() >= ignoreUntil else { self.quad = nil; return }
        self.quad = quad
        phase = holding ? .holding : .searching
    }

    private func shot(_ shot: CardShot?) async {
        phase = .checking
        quad = nil
        guard let shot else { resume(after: 0); return }
        let rectoHash = side == .verso ? (shots[.recto]?.hashes.first ?? rectoHashes?.first) : nil
        let verdict = CardCheck.verdict(expected: side, faceFound: shot.faceFound, hashes: shot.hashes,
                                        rectoHash: rectoHash, machineZone: shot.machineZone)
        guard verdict == .accepted else {
            UINotificationFeedbackGenerator().notificationOccurred(.warning)
            phase = .wrong(verdict)
            resume(after: 2.5)
            return
        }
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        shots[side] = shot
        phase = .taken
        try? await Task.sleep(for: .seconds(1.1))
        guard let next = sides.drop(while: { $0 != side }).dropFirst().first else {
            engine.stop()
            finished = true
            return
        }
        side = next
        phase = .turnCard
        ignoreUntil = Date().addingTimeInterval(2.5)
        try? await Task.sleep(for: .seconds(2.2))
        phase = .searching
        armEngine()
    }

    private func resume(after seconds: Double) {
        Task {
            try? await Task.sleep(for: .seconds(seconds))
            phase = .searching
            armEngine()
        }
    }
}

struct CardScannerView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let sides: [CardSide]
    let rectoHashes: [UInt64]?
    var demo: IdentityDemo?
    let onFinish: ([CardSide: CardShot]) -> Void
    @State private var scanner = CardScanner()
    @State private var simulated = false

    var body: some View {
        GeometryReader { geometry in
            let guide = Self.guideRect(in: geometry.size, ratio: scanner.side.ratio)
            ZStack {
                Color.black
                if simulated || demo != nil {
                    // Démonstration « mauvaise face » : la caméra simulée montre le verso.
                    DemoCardBackdrop(side: demo == .wrongSide || demo == .wrongPage ? .verso : scanner.side,
                                     ratio: scanner.side.ratio, guide: guide)
                } else if scanner.phase != .denied && scanner.phase != .missing {
                    CameraPreview(session: scanner.engine.session)
                }
                GuideMask(guide: guide)
                    .fill(Color.black.opacity(0.55), style: FillStyle(eoFill: true))
                    .allowsHitTesting(false)
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .strokeBorder(guideColor, lineWidth: 3)
                    .frame(width: guide.width, height: guide.height)
                    .position(x: guide.midX, y: guide.midY)
                    .animation(.snappy, value: scanner.phase)
                    .accessibilityHidden(true)
                if let quad = scanner.quad {
                    QuadShape(points: quad.corners.map {
                        screenPoint($0, frame: scanner.frameSize, in: geometry.size)
                    })
                    .stroke(Nexis.halo, style: StrokeStyle(lineWidth: 2.5, lineJoin: .round))
                    .accessibilityHidden(true)
                }
                if scanner.phase == .turnCard {
                    TurnCardIcon(reduceMotion: reduceMotion)
                        .position(x: guide.midX, y: guide.midY)
                }
                overlay(guide: guide)
            }
        }
        .ignoresSafeArea()
        .statusBarHidden()
        .task { await start() }
        .onDisappear { scanner.stop() }
        .onChange(of: scanner.finished) { _, finished in
            if finished { onFinish(scanner.shots); dismiss() }
        }
        .onChange(of: scanner.phase) { _, _ in announce() }
    }

    /// Le cadre de la pièce (carte ID-1 ou page de passeport), au tiers haut de l'écran.
    static func guideRect(in size: CGSize, ratio: CGFloat) -> CGRect {
        let width = min(size.width * 0.86, 520)
        let height = width / ratio
        return CGRect(x: (size.width - width) / 2, y: size.height * 0.42 - height / 2, width: width, height: height)
    }

    private var guideColor: Color {
        switch scanner.phase {
        case .holding, .checking: return Nexis.halo
        case .taken: return Color(hex: 0x34C759)
        case .wrong: return Color(hex: 0xFF6B5E)
        default: return .white.opacity(0.9)
        }
    }

    private var title: String {
        switch scanner.side {
        case .recto: return app.t("scanRectoTitle")
        case .verso: return app.t("scanTurnTitle")
        case .passportPage: return app.t("scanPassportTitle")
        }
    }

    private var hint: String {
        switch scanner.side {
        case .recto: return app.t("scanRectoHint")
        case .verso: return app.t("scanVersoHint")
        case .passportPage: return app.t("scanPassportHint")
        }
    }

    private var sideLabel: String {
        switch scanner.side {
        case .recto: return app.t("becomeRecto")
        case .verso: return app.t("becomeVerso")
        case .passportPage: return app.t("becomePhotoPage")
        }
    }

    private var status: (text: String, icon: String, tone: Color)? {
        switch scanner.phase {
        case .starting, .turnCard: return nil
        case .denied: return (app.t("cameraDenied"), "video.slash", Color(hex: 0xFF6B5E))
        case .missing: return (app.t("cameraMissing"), "video.slash", Color(hex: 0xFF6B5E))
        case .searching: return (app.t("scanSearching"), "viewfinder", .white)
        case .holding: return (app.t("scanHold"), "hand.raised.fill", .white)
        case .checking: return (app.t("scanChecking"), "sparkle.magnifyingglass", .white)
        case .wrong(let verdict):
            let key: String
            switch verdict {
            case .stillRecto: key = "scanWrongRecto"
            case .showPhotoPage: key = "scanWrongPage"
            default: key = "scanWrongVerso"
            }
            return (app.t(key), "exclamationmark.triangle.fill", Color(hex: 0xFF6B5E))
        case .taken:
            return (sideLabel, "checkmark.circle.fill", Color(hex: 0x34C759))
        }
    }

    private func overlay(guide: CGRect) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Button { scanner.stop(); dismiss() } label: {
                    Image(systemName: "xmark").font(.system(size: 17, weight: .semibold)).foregroundStyle(.white)
                        .frame(width: 44, height: 44)
                        .nxGlass(in: Circle())
                }
                .accessibilityLabel(app.t("close"))
                Spacer()
                Text("\(min(sides.firstIndex(of: scanner.side).map { $0 + 1 } ?? 1, sides.count)) / \(sides.count)")
                    .font(.body(13, .semibold, relativeTo: .footnote)).foregroundStyle(.white)
                    .padding(.horizontal, 12).padding(.vertical, 7)
                    .nxGlass()
                    .accessibilityHidden(true)
            }
            .padding(.top, 54)
            VStack(alignment: .leading, spacing: 6) {
                Text(title).font(.title(22)).foregroundStyle(.white).accessibilityAddTraits(.isHeader)
                Text(hint).font(.body(15)).foregroundStyle(.white.opacity(0.82)).lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(.top, 14)
            .frame(maxHeight: max(guide.minY - 54 - 44, 0), alignment: .top)
            Spacer(minLength: 0)
            VStack(alignment: .leading, spacing: 12) {
                if let status {
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: status.icon).foregroundStyle(status.tone)
                        Text(status.text).font(.body(15, .semibold)).foregroundStyle(.white)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.horizontal, 16).padding(.vertical, 12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.black.opacity(0.55), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(.white.opacity(0.16)))
                    .accessibilityElement(children: .combine)
                }
                if scanner.phase == .denied, let url = URL(string: UIApplication.openSettingsURLString) {
                    Button { UIApplication.shared.open(url) } label: { WideLabel(text: app.t("notifOpenSettings")) }
                        .nxProminentButton()
                }
                if simulated {
                    Label(app.t("cameraSimulator"), systemImage: "desktopcomputer")
                        .font(.body(13, relativeTo: .footnote)).foregroundStyle(.white.opacity(0.75))
                }
            }
            .padding(.bottom, 40)
        }
        .padding(.horizontal, 20)
    }

    private func announce() {
        let text: String?
        switch scanner.phase {
        case .turnCard: text = app.t("scanTurnTitle")
        case .starting: text = nil
        default: text = status?.text
        }
        if let text { AccessibilityNotification.Announcement(text).post() }
    }

    private func start() async {
        if let demo {
            switch demo {
            case .recto: scanner.show(.holding, side: .recto)
            case .wrongSide: scanner.show(.wrong(.showRectoFirst), side: .recto)
            case .verso:
                scanner.record(IdentityDemoImages.shot(.recto), for: .recto)
                scanner.show(.searching, side: .verso)
            case .passport: scanner.show(.holding, side: .passportPage)
            case .wrongPage: scanner.show(.wrong(.showPhotoPage), side: .passportPage)
            default: break
            }
            return
        }
        #if targetEnvironment(simulator)
        simulated = true
        await simulate()
        #else
        await scanner.start(sides: sides, rectoHashes: rectoHashes)
        #endif
    }

    #if targetEnvironment(simulator)
    /// Simulateur (Appetize) : pas d'appareil photo, le parcours est joué.
    private func simulate() async {
        func wait(_ seconds: Double) async { try? await Task.sleep(for: .seconds(seconds)) }
        for (index, side) in sides.enumerated() {
            if index > 0 { scanner.show(.turnCard, side: side); await wait(2.2) }
            scanner.show(.searching, side: side)
            await wait(1.4)
            scanner.show(.holding, side: side)
            await wait(1)
            scanner.show(.checking, side: side)
            await wait(0.7)
            scanner.record(IdentityDemoImages.shot(side), for: side)
            scanner.show(.taken, side: side)
            await wait(1.1)
        }
        scanner.finish()
    }
    #endif
}

/// Tout l'écran sauf le cadre de la carte (assombri).
private struct GuideMask: Shape {
    let guide: CGRect

    func path(in rect: CGRect) -> Path {
        var path = Path(rect)
        path.addRoundedRect(in: guide, cornerSize: CGSize(width: 16, height: 16), style: .continuous)
        return path
    }
}

private struct QuadShape: Shape {
    let points: [CGPoint]

    func path(in rect: CGRect) -> Path {
        var path = Path()
        guard let first = points.first else { return path }
        path.move(to: first)
        points.dropFirst().forEach { path.addLine(to: $0) }
        path.closeSubpath()
        return path
    }
}

private struct TurnCardIcon: View {
    let reduceMotion: Bool
    @State private var flipped = false

    var body: some View {
        Image(systemName: "arrow.triangle.2.circlepath")
            .font(.system(size: 44, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: 104, height: 104)
            .background(Nexis.brand.opacity(0.9), in: Circle())
            .rotation3DEffect(.degrees(flipped ? 180 : 0), axis: (x: 0, y: 1, z: 0))
            .accessibilityHidden(true)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) { flipped = true }
            }
    }
}

// MARK: - Vidéo du visage

@MainActor
@Observable
final class SelfieRecorder {
    enum Phase: Equatable { case starting, denied, missing, running, finishing }

    private(set) var phase: Phase = .starting
    private(set) var step: SelfieScript.Step = .faceIn
    private(set) var number = 1
    private(set) var recording = false
    private(set) var severalFaces = false
    private(set) var tooSlow = false
    private(set) var failed = false
    private(set) var video: VideoShot?
    @ObservationIgnored let engine = SelfieEngine()


    func start() async {
        switch await CameraAccess.request(position: .front) {
        case .denied: phase = .denied; return
        case .missing: phase = .missing; return
        case .granted: break
        }
        engine.onStatus = { [weak self] status in Task { @MainActor in self?.update(status) } }
        engine.onVideo = { [weak self] video in Task { @MainActor in self?.done(video) } }
        engine.start()
        phase = .running
    }

    func stop() { engine.stop() }

    /// Montre une consigne figée, sans appareil photo (captures, simulateur).
    func show(step: SelfieScript.Step, number: Int, recording: Bool) {
        phase = .running
        self.step = step
        self.number = number
        self.recording = recording
    }

    func finish(with video: VideoShot) { self.video = video }

    private func update(_ status: SelfieEngine.Status) {
        if status.step != step && status.step != .faceIn { UISelectionFeedbackGenerator().selectionChanged() }
        step = status.step
        number = status.number
        recording = status.recording
        severalFaces = status.severalFaces
        if status.restarted {
            tooSlow = true
            UINotificationFeedbackGenerator().notificationOccurred(.warning)
            Task {
                try? await Task.sleep(for: .seconds(2.5))
                tooSlow = false
            }
        }
        if status.step == .done { phase = .finishing }
    }

    private func done(_ video: VideoShot?) {
        guard let video else {
            // L'enregistrement n'a pas pu être lu : les consignes reprennent.
            phase = .running
            step = .faceIn
            number = 1
            recording = false
            failed = true
            UINotificationFeedbackGenerator().notificationOccurred(.error)
            Task {
                try? await Task.sleep(for: .seconds(2.5))
                failed = false
            }
            return
        }
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        self.video = video
    }
}

struct SelfieVideoView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var demo = false
    let onFinish: (VideoShot) -> Void
    @State private var recorder = SelfieRecorder()
    @State private var simulated = false

    var body: some View {
        GeometryReader { geometry in
            let diameter = min(geometry.size.width * 0.78, 420)
            let center = CGPoint(x: geometry.size.width / 2, y: geometry.size.height * 0.42)
            ZStack {
                Color.black
                Group {
                    if simulated || demo {
                        DemoFace(step: recorder.step, reduceMotion: reduceMotion)
                    } else if recorder.phase == .running || recorder.phase == .finishing {
                        CameraPreview(session: recorder.engine.session, mirrored: true)
                    }
                }
                .frame(width: diameter, height: diameter)
                .clipShape(Circle())
                .position(center)
                StepRing(total: 4, done: recorder.step == .done ? 4 : recorder.number - 1, recording: recorder.recording)
                    .frame(width: diameter + 22, height: diameter + 22)
                    .position(center)
                if let arrow {
                    Image(systemName: arrow)
                        .font(.system(size: 30, weight: .bold))
                        .foregroundStyle(.white)
                        .frame(width: 58, height: 58)
                        .background(Nexis.brand, in: Circle())
                        .position(x: center.x + (arrow == "arrow.left" ? -1 : 1) * (diameter / 2 + 4), y: center.y)
                        .accessibilityHidden(true)
                }
                overlay(below: center.y + diameter / 2 + 26)
            }
        }
        .ignoresSafeArea()
        .statusBarHidden()
        .task { await start() }
        .onDisappear { recorder.stop() }
        .onChange(of: recorder.video != nil) { _, done in
            guard done, let video = recorder.video else { return }
            Task {
                try? await Task.sleep(for: .seconds(0.9))
                onFinish(video)
                dismiss()
            }
        }
        .onChange(of: instruction) { _, text in AccessibilityNotification.Announcement(text).post() }
    }

    /// La flèche montre le côté vers lequel tourner, dans l'image en miroir.
    private var arrow: String? {
        switch recorder.step {
        case .turn(.left): return "arrow.left"
        case .turn(.right): return "arrow.right"
        default: return nil
        }
    }

    private var instruction: String {
        switch recorder.phase {
        case .denied: return app.t("cameraDenied")
        case .missing: return app.t("cameraMissing")
        default: break
        }
        if recorder.failed { return app.t("actionFailed") }
        if recorder.tooSlow { return app.t("selfieTooSlow") }
        if recorder.severalFaces { return app.t("selfieOneFace") }
        switch recorder.step {
        case .faceIn: return app.t("selfieFaceIn")
        case .turn(.left): return app.t("selfieTurnLeft")
        case .turn(.right): return app.t("selfieTurnRight")
        case .lookAhead: return app.t("selfieLookAhead")
        case .done: return app.t("selfieDone")
        }
    }

    private func overlay(below top: CGFloat) -> some View {
        ZStack(alignment: .top) {
            VStack(spacing: 8) {
                HStack {
                    Button { recorder.stop(); dismiss() } label: {
                        Image(systemName: "xmark").font(.system(size: 17, weight: .semibold)).foregroundStyle(.white)
                            .frame(width: 44, height: 44)
                            .nxGlass(in: Circle())
                    }
                    .accessibilityLabel(app.t("close"))
                    Spacer()
                    if recorder.recording {
                        HStack(spacing: 6) {
                            Circle().fill(Color(hex: 0xFF3B30)).frame(width: 9, height: 9)
                            Text(app.t("selfieRecording")).font(.body(13, .semibold, relativeTo: .footnote))
                        }
                        .foregroundStyle(.white)
                        .padding(.horizontal, 12).padding(.vertical, 7)
                        .nxGlass()
                    }
                }
                Text(app.t("selfieTitle")).font(.title(19)).foregroundStyle(.white)
                    .accessibilityAddTraits(.isHeader)
            }
            .padding(.top, 54)
            VStack(spacing: 10) {
                Text(app.t("selfieStep", ["step": String(recorder.number), "total": "4"]))
                    .font(.body(13, .semibold, relativeTo: .footnote)).foregroundStyle(Nexis.halo)
                Text(instruction)
                    .font(.title(23))
                    .foregroundStyle(recorder.tooSlow || recorder.failed || recorder.severalFaces || recorder.phase == .denied
                                     ? Color(hex: 0xFF8A80) : .white)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .contentTransition(.opacity)
                    .animation(.snappy, value: instruction)
                if recorder.step == .faceIn && !recorder.tooSlow && recorder.phase == .running {
                    Text(app.t("selfieIntro")).font(.body(14.5)).foregroundStyle(.white.opacity(0.78))
                        .multilineTextAlignment(.center).lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if recorder.phase == .denied, let url = URL(string: UIApplication.openSettingsURLString) {
                    Button { UIApplication.shared.open(url) } label: { WideLabel(text: app.t("notifOpenSettings")) }
                        .nxProminentButton()
                        .padding(.top, 6)
                }
                if simulated {
                    Label(app.t("cameraSimulator"), systemImage: "desktopcomputer")
                        .font(.body(13, relativeTo: .footnote)).foregroundStyle(.white.opacity(0.75))
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.top, top)
        }
        .padding(.horizontal, 22)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
    }

    private func start() async {
        if demo {
            recorder.show(step: .turn(.left), number: 2, recording: true)
            return
        }
        #if targetEnvironment(simulator)
        simulated = true
        func wait(_ seconds: Double) async { try? await Task.sleep(for: .seconds(seconds)) }
        let turns: [HeadTurn] = HeadTurn.allCases.shuffled()
        recorder.show(step: .faceIn, number: 1, recording: false)
        await wait(1.8)
        recorder.show(step: .turn(turns[0]), number: 2, recording: true)
        await wait(2)
        recorder.show(step: .turn(turns[1]), number: 3, recording: true)
        await wait(2)
        recorder.show(step: .lookAhead, number: 4, recording: true)
        await wait(1.5)
        recorder.show(step: .done, number: 4, recording: false)
        recorder.finish(with: IdentityDemoImages.video(turns: turns))
        #else
        await recorder.start()
        #endif
    }
}

/// Anneau autour du visage : une part par consigne faite.
private struct StepRing: View {
    let total: Int
    let done: Int
    let recording: Bool

    var body: some View {
        ZStack {
            ForEach(0..<total, id: \.self) { index in
                let gap = 0.012
                Circle()
                    .trim(from: Double(index) / Double(total) + gap, to: Double(index + 1) / Double(total) - gap)
                    .stroke(index < done ? Color(hex: 0x34C759) : Color.white.opacity(recording ? 0.45 : 0.28),
                            style: StrokeStyle(lineWidth: 6, lineCap: .round))
                    .rotationEffect(.degrees(-90))
            }
        }
        .animation(.snappy, value: done)
        .accessibilityHidden(true)
    }
}

// MARK: - Démonstration (simulateur et captures de la CI)

/// Fond dessiné à la place de la caméra : une carte posée sur une table.
private struct DemoCardBackdrop: View {
    let side: CardSide
    let ratio: CGFloat
    let guide: CGRect

    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(hex: 0x2A2F38), Color(hex: 0x14171C)], startPoint: .top, endPoint: .bottom)
            SpecimenCard(side: side, ratio: ratio)
                .frame(width: guide.width * 0.94, height: guide.height * 0.94)
                .rotationEffect(.degrees(-2))
                .shadow(color: .black.opacity(0.5), radius: 18, y: 10)
                .position(x: guide.midX, y: guide.midY)
        }
        .accessibilityHidden(true)
    }
}

/// Une pièce d'identité dessinée, sans aucun texte : le recto porte un
/// visage, le verso des lignes et un code, la page du passeport un visage et
/// deux lignes de lecture automatique.
struct SpecimenCard: View {
    let side: CardSide
    var ratio: CGFloat?

    var body: some View {
        GeometryReader { geometry in
            let w = geometry.size.width, h = geometry.size.height
            ZStack(alignment: .topLeading) {
                RoundedRectangle(cornerRadius: w * 0.045, style: .continuous)
                    .fill(LinearGradient(colors: [Color(hex: 0xEAF1FB), Color(hex: 0xD6E4F5)],
                                         startPoint: .topLeading, endPoint: .bottomTrailing))
                Rectangle().fill(Color(hex: 0x0A63F0).opacity(0.85)).frame(height: h * 0.16)
                    .clipShape(UnevenRoundedRectangle(topLeadingRadius: w * 0.045, topTrailingRadius: w * 0.045))
                if side != .verso {
                    RoundedRectangle(cornerRadius: w * 0.02)
                        .fill(Color(hex: 0xB9C9DE))
                        .overlay(Image(systemName: "person.fill").resizable().scaledToFit()
                            .foregroundStyle(Color(hex: 0x6F84A3)).padding(w * 0.03).offset(y: w * 0.02))
                        .clipShape(RoundedRectangle(cornerRadius: w * 0.02))
                        .frame(width: w * 0.26, height: h * (side == .passportPage ? 0.46 : 0.56))
                        .offset(x: w * 0.06, y: h * 0.24)
                    lines(x: w * 0.38, y: h * 0.26, width: w * 0.54, height: h, count: side == .passportPage ? 4 : 5)
                    if side == .passportPage {
                        // Les deux lignes de lecture automatique, dessinées en blocs.
                        VStack(alignment: .leading, spacing: h * 0.035) {
                            ForEach(0..<2, id: \.self) { _ in
                                HStack(spacing: w * 0.006) {
                                    ForEach(0..<30, id: \.self) { i in
                                        RoundedRectangle(cornerRadius: 1).fill(Color(hex: 0x24344D).opacity(i % 7 == 3 ? 0.35 : 0.85))
                                            .frame(width: w * 0.024, height: h * 0.055)
                                    }
                                }
                            }
                        }
                        .offset(x: w * 0.05, y: h * 0.76)
                    }
                } else {
                    lines(x: w * 0.06, y: h * 0.26, width: w * 0.6, height: h, count: 4)
                    HStack(spacing: w * 0.008) {
                        ForEach(0..<34, id: \.self) { i in
                            Rectangle().fill(Color(hex: 0x24344D)).frame(width: w * (i % 3 == 0 ? 0.008 : 0.004))
                        }
                    }
                    .frame(height: h * 0.2)
                    .offset(x: w * 0.06, y: h * 0.72)
                    RoundedRectangle(cornerRadius: w * 0.015).fill(Color(hex: 0xC7D3E3))
                        .frame(width: w * 0.2, height: w * 0.2)
                        .offset(x: w * 0.74, y: h * 0.3)
                }
            }
        }
        .aspectRatio(ratio ?? side.ratio, contentMode: .fit)
    }

    private func lines(x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat, count: Int) -> some View {
        VStack(alignment: .leading, spacing: height * 0.06) {
            ForEach(0..<count, id: \.self) { i in
                Capsule().fill(Color(hex: 0x8FA3BF)).frame(width: width * (i % 2 == 0 ? 1 : 0.7), height: height * 0.045)
            }
        }
        .offset(x: x, y: y)
    }
}

/// Visage dessiné à la place de la caméra avant.
private struct DemoFace: View {
    let step: SelfieScript.Step
    let reduceMotion: Bool

    private var angle: Double {
        switch step {
        case .turn(.left): return -28
        case .turn(.right): return 28
        default: return 0
        }
    }

    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(hex: 0x3A4250), Color(hex: 0x1C2129)], startPoint: .top, endPoint: .bottom)
            Image(systemName: "person.fill")
                .resizable().scaledToFit()
                .foregroundStyle(Color(hex: 0x8C99AD))
                .padding(.horizontal, 40)
                .offset(y: 46)
                .rotation3DEffect(.degrees(angle), axis: (x: 0, y: 1, z: 0))
                .animation(reduceMotion ? nil : .easeInOut(duration: 0.6), value: angle)
        }
        .accessibilityHidden(true)
    }
}

/// Images de démonstration (dessinées par l'app, pas des photos).
@MainActor
enum IdentityDemoImages {
    static func shot(_ side: CardSide) -> CardShot {
        let renderer = ImageRenderer(content: SpecimenCard(side: side).frame(width: 428, height: 428 / side.ratio))
        renderer.scale = 2
        let image = renderer.uiImage ?? UIImage()
        let jpeg = image.jpegData(compressionQuality: 0.8) ?? Data([1])
        let hashes = image.cgImage.map(CardImages.hashes) ?? [side == .verso ? 2 : 1]
        return CardShot(jpeg: jpeg, image: image, hashes: hashes, faceFound: side != .verso,
                        machineZone: side == .passportPage)
    }

    static func video(turns: [HeadTurn]) -> VideoShot {
        let renderer = ImageRenderer(content: DemoFace(step: .lookAhead, reduceMotion: true).frame(width: 160, height: 160))
        renderer.scale = 2
        return VideoShot(data: Data("aperçu".utf8), thumbnail: renderer.uiImage, seconds: 7, turns: turns)
    }

    static func draft() -> IdentityDraft {
        IdentityDraft(document: .voterCard, recto: shot(.recto), verso: shot(.verso), video: video(turns: [.left, .right]))
    }
}
