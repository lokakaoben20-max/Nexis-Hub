import AVFoundation
import CoreImage
import CoreImage.CIFilterBuiltins
import SwiftUI
import UIKit
import Vision

// Caméras de l'étape « Pièce d'identité » : scanner de la carte (caméra
// arrière) et vidéo guidée du visage (caméra avant, sans micro). Tout se
// passe sur le téléphone, avec Vision ; aucune image ne part ailleurs.
// Aucune de ces caméras ne propose la galerie.

/// Une face de la pièce, redressée et réduite.
struct CardShot {
    let jpeg: Data
    let image: UIImage
    /// Empreintes de l'image (à l'endroit, puis tournée d'un demi-tour).
    let hashes: [UInt64]
    let faceFound: Bool
    /// Page de passeport : la zone de lecture automatique a été vue.
    var machineZone = false
}

/// La vidéo du visage, prête à être envoyée.
struct VideoShot {
    let data: Data
    let thumbnail: UIImage?
    let seconds: Int
    let turns: [HeadTurn]
}

/// Les images de la caméra arrivent droites, en portrait : l'app ne tourne
/// pas (portrait seulement). L'angle est fixe, même téléphone posé à plat
/// au-dessus d'une carte.
private let portraitAngle: CGFloat = 90

private func configure(_ connection: AVCaptureConnection?, mirrored: Bool = false) {
    guard let connection else { return }
    if connection.isVideoRotationAngleSupported(portraitAngle) { connection.videoRotationAngle = portraitAngle }
    if connection.isVideoMirroringSupported {
        connection.automaticallyAdjustsVideoMirroring = false
        connection.isVideoMirrored = mirrored
    }
}

enum CameraAccess {
    case granted, denied, missing

    /// Demande l'accès à l'appareil photo (jamais au micro).
    static func request(position: AVCaptureDevice.Position) async -> CameraAccess {
        guard AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: position) != nil else {
            return .missing
        }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: return .granted
        case .notDetermined: return await AVCaptureDevice.requestAccess(for: .video) ? .granted : .denied
        default: return .denied
        }
    }
}

/// L'image de la caméra, plein cadre.
struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    var mirrored = false

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }

    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        view.previewLayer.session = session
        view.previewLayer.videoGravity = .resizeAspectFill
        view.backgroundColor = .black
        configure(view.previewLayer.connection, mirrored: mirrored)
        return view
    }

    func updateUIView(_ view: PreviewView, context: Context) {
        configure(view.previewLayer.connection, mirrored: mirrored)
    }
}

/// Passe d'un point normalisé de Vision (origine en bas à gauche) à un point
/// de l'écran, pour une image `frame` remplissant `view` (aspect fill).
func screenPoint(_ point: CGPoint, frame: CGSize, in view: CGSize, mirrored: Bool = false) -> CGPoint {
    guard frame.width > 0, frame.height > 0 else { return .zero }
    let scale = max(view.width / frame.width, view.height / frame.height)
    let shown = CGSize(width: frame.width * scale, height: frame.height * scale)
    let x = mirrored ? 1 - point.x : point.x
    return CGPoint(x: x * shown.width - (shown.width - view.width) / 2,
                   y: (1 - point.y) * shown.height - (shown.height - view.height) / 2)
}

enum CardImages {
    static let context = CIContext()

    /// La grille 9 × 8 en niveaux de gris de l'empreinte.
    static func grayGrid(_ image: CGImage) -> [UInt8] {
        var pixels = [UInt8](repeating: 0, count: ImageHash.width * ImageHash.height)
        pixels.withUnsafeMutableBytes { buffer in
            guard let bitmap = CGContext(data: buffer.baseAddress, width: ImageHash.width, height: ImageHash.height,
                                         bitsPerComponent: 8, bytesPerRow: ImageHash.width,
                                         space: CGColorSpaceCreateDeviceGray(),
                                         bitmapInfo: CGImageAlphaInfo.none.rawValue) else { return }
            bitmap.interpolationQuality = .medium
            bitmap.draw(image, in: CGRect(x: 0, y: 0, width: ImageHash.width, height: ImageHash.height))
        }
        return pixels
    }

    static func hashes(_ image: CGImage) -> [UInt64] {
        let grid = grayGrid(image)
        return [ImageHash.dHash(grid), ImageHash.dHash(ImageHash.halfTurn(grid))]
    }

    /// Redresse la carte vue en perspective.
    static func straighten(_ image: CIImage, _ quad: CardQuad) -> CIImage {
        let extent = image.extent
        func point(_ p: CGPoint) -> CGPoint {
            CGPoint(x: extent.minX + p.x * extent.width, y: extent.minY + p.y * extent.height)
        }
        let filter = CIFilter.perspectiveCorrection()
        filter.inputImage = image
        filter.topLeft = point(quad.topLeft)
        filter.topRight = point(quad.topRight)
        filter.bottomRight = point(quad.bottomRight)
        filter.bottomLeft = point(quad.bottomLeft)
        return filter.outputImage ?? image
    }

    /// Cherche un visage dans les quatre sens de lecture. Renvoie l'image à
    /// l'endroit (visage droit, sinon carte en paysage) et si un visage a été vu.
    static func upright(_ card: CIImage) -> (image: CIImage, faceFound: Bool) {
        for orientation in [CGImagePropertyOrientation.up, .down, .right, .left] {
            let request = VNDetectFaceRectanglesRequest()
            try? VNImageRequestHandler(ciImage: card, orientation: orientation).perform([request])
            if let face = request.results?.first, face.boundingBox.width * face.boundingBox.height >= 0.01 {
                return (card.oriented(orientation), true)
            }
        }
        return (card.extent.height > card.extent.width ? card.oriented(.right) : card, false)
    }

    /// Cherche un visage dans les quatre sens (la page d'un passeport est
    /// tenue sur le côté). Renvoie le sens trouvé et le cadre du visage.
    static func face(in image: CIImage) -> (orientation: CGImagePropertyOrientation, box: CGRect)? {
        let placed = image.transformed(by: CGAffineTransform(translationX: -image.extent.minX, y: -image.extent.minY))
        for orientation in [CGImagePropertyOrientation.up, .right, .left, .down] {
            let request = VNDetectFaceRectanglesRequest()
            try? VNImageRequestHandler(ciImage: placed, orientation: orientation).perform([request])
            if let face = request.results?.first, face.boundingBox.width * face.boundingBox.height >= 0.01 {
                return (orientation, face.boundingBox)
            }
        }
        return nil
    }

    /// Lit les lignes de texte de la page, sur le téléphone, pour y chercher la
    /// zone de lecture automatique d'un passeport. Le texte n'est pas gardé.
    static func hasMachineZone(_ image: CIImage) -> Bool {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        let placed = image.transformed(by: CGAffineTransform(translationX: -image.extent.minX, y: -image.extent.minY))
        try? VNImageRequestHandler(ciImage: placed, orientation: .up).perform([request])
        let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
        return MachineZone.found(in: lines)
    }

    /// Réduit à 1 600 points au plus grand côté et encode en JPEG.
    static func finish(_ image: CIImage, faceFound: Bool, machineZone: Bool = false) -> CardShot? {
        let origin = image.transformed(by: CGAffineTransform(translationX: -image.extent.minX, y: -image.extent.minY))
        let longest = max(origin.extent.width, origin.extent.height)
        var scaled = origin
        if longest > 1600 {
            let filter = CIFilter.lanczosScaleTransform()
            filter.inputImage = origin
            filter.scale = Float(1600 / longest)
            filter.aspectRatio = 1
            scaled = filter.outputImage ?? origin
        }
        guard let cg = context.createCGImage(scaled, from: scaled.extent.integral) else { return nil }
        let image = UIImage(cgImage: cg)
        guard let jpeg = image.jpegData(compressionQuality: 0.8) else { return nil }
        return CardShot(jpeg: jpeg, image: image, hashes: hashes(cg), faceFound: faceFound, machineZone: machineZone)
    }

    static func rectangleRequest(minimumSize: Float = 0.3) -> VNDetectRectanglesRequest {
        let request = VNDetectRectanglesRequest()
        // Carte au format ID-1 (85,6 × 54 mm), vue un peu de biais.
        request.minimumAspectRatio = 0.5
        request.maximumAspectRatio = 0.8
        request.minimumSize = minimumSize
        request.quadratureTolerance = 20
        request.minimumConfidence = 0.8
        request.maximumObservations = 1
        return request
    }
}

private extension CardQuad {
    init(_ observation: VNRectangleObservation) {
        self.init(topLeft: observation.topLeft, topRight: observation.topRight,
                  bottomRight: observation.bottomRight, bottomLeft: observation.bottomLeft)
    }
}

// MARK: - Scanner de la carte

/// Caméra arrière : cherche la carte sur chaque image, prend la photo quand
/// elle reste immobile, puis la redresse. Tourne sur sa propre file.
final class CardEngine: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate, AVCapturePhotoCaptureDelegate,
    @unchecked Sendable {
    let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "com.nexishub.carte")
    private let videoOutput = AVCaptureVideoDataOutput()
    private let photoOutput = AVCapturePhotoOutput()
    private var tracker = StableCardTracker()
    private var passport = PassportTrigger()
    private var armed = false
    private var readsMachineZone = false
    /// Le cadre affiché et la taille de l'écran : le passeport est cherché
    /// dans ce cadre, et la photo y est recadrée.
    private var guide: CGRect = .zero
    private var viewSize: CGSize = .zero
    private var region: CGRect?
    private var passportFrames = 0
    private var busy = false
    private var lastQuad: CardQuad?
    private var frameCount = 0

    /// Carte vue (ou non), taille de l'image, carte en train d'être tenue.
    var onFrame: ((CardQuad?, CGSize, Bool) -> Void)?
    /// Photo prise et traitée (nil si elle n'a pas pu être lue).
    var onShot: ((CardShot?) -> Void)?

    func start() {
        queue.async { [self] in
            guard session.inputs.isEmpty else { if !session.isRunning { session.startRunning() }; return }
            guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
                  let input = try? AVCaptureDeviceInput(device: device) else { return }
            session.beginConfiguration()
            session.sessionPreset = .photo
            if session.canAddInput(input) { session.addInput(input) }
            videoOutput.alwaysDiscardsLateVideoFrames = true
            videoOutput.setSampleBufferDelegate(self, queue: queue)
            if session.canAddOutput(videoOutput) { session.addOutput(videoOutput) }
            if session.canAddOutput(photoOutput) { session.addOutput(photoOutput) }
            configure(videoOutput.connection(with: .video))
            configure(photoOutput.connection(with: .video))
            session.commitConfiguration()
            if (try? device.lockForConfiguration()) != nil {
                if device.isFocusModeSupported(.continuousAutoFocus) { device.focusMode = .continuousAutoFocus }
                device.unlockForConfiguration()
            }
            session.startRunning()
        }
    }

    func stop() {
        queue.async { [self] in
            armed = false
            if session.isRunning { session.stopRunning() }
        }
    }

    /// Autorise (ou non) la prochaine photo automatique. `machineZone` : page
    /// de passeport (visage et zone de lecture automatique dans le cadre).
    func arm(_ value: Bool, machineZone: Bool = false) {
        queue.async { [self] in
            armed = value
            readsMachineZone = machineZone
            busy = false
            tracker.reset()
            passport.reset()
        }
    }

    /// Le cadre de la pièce à l'écran (points), et la taille de l'écran.
    func setGuide(_ guide: CGRect, in view: CGSize) {
        queue.async { [self] in
            self.guide = guide
            viewSize = view
        }
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        frameCount += 1
        guard !busy, frameCount % 2 == 0, let pixels = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        let size = CGSize(width: CVPixelBufferGetWidth(pixels), height: CVPixelBufferGetHeight(pixels))
        if readsMachineZone {
            analyzePassport(pixels, size: size)
            return
        }
        let request = CardImages.rectangleRequest()
        try? VNImageRequestHandler(cvPixelBuffer: pixels, orientation: .up).perform([request])
        let quad = request.results?.first.map { CardQuad($0) }
        let stable = tracker.add(quad)
        if let quad { lastQuad = quad }
        if armed, stable {
            armed = false
            busy = true
            photoOutput.capturePhoto(with: AVCapturePhotoSettings(format: [AVVideoCodecKey: AVVideoCodecType.jpeg]),
                                     delegate: self)
        }
        onFrame?(quad, size, armed && tracker.isHolding)
    }

    /// Passeport : visage cherché dans le cadre (environ 5 fois par seconde),
    /// zone de lecture automatique une fois sur deux. Pas de contour cherché.
    private func analyzePassport(_ pixels: CVPixelBuffer, size: CGSize) {
        passportFrames += 1
        guard passportFrames % 3 == 0 else { return }
        guard let found = imageRegion(of: guide, frame: size, in: viewSize), !found.isNull, found.width > 0.1 else {
            onFrame?(nil, size, false)
            return
        }
        region = found
        let crop = CIImage(cvPixelBuffer: pixels).cropped(to: CGRect(
            x: found.minX * size.width, y: found.minY * size.height,
            width: found.width * size.width, height: found.height * size.height))
        let face = CardImages.face(in: crop)
        let zone = face.map { passportFrames % 6 == 0 && CardImages.hasMachineZone(crop.oriented($0.orientation)) } ?? false
        if armed, passport.add(face: face?.box, machineZone: zone) {
            armed = false
            busy = true
            photoOutput.capturePhoto(with: AVCapturePhotoSettings(format: [AVVideoCodecKey: AVVideoCodecType.jpeg]),
                                     delegate: self)
        }
        onFrame?(nil, size, armed && passport.isHolding)
    }

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto,
                     error: Error?) {
        let data = photo.fileDataRepresentation()
        queue.async { [self] in onShot?(process(data)) }
    }

    private func process(_ data: Data?) -> CardShot? {
        guard let data, let image = CIImage(data: data, options: [.applyOrientationProperty: true]) else { return nil }
        if readsMachineZone, let region {
            // Passeport : la photo est recadrée sur le cadre, mise à
            // l'endroit d'après le visage, puis revérifiée en pleine
            // résolution.
            let extent = image.extent
            let page = image.cropped(to: CGRect(
                x: extent.minX + region.minX * extent.width, y: extent.minY + region.minY * extent.height,
                width: region.width * extent.width, height: region.height * extent.height))
            let placed = page.transformed(by: CGAffineTransform(translationX: -page.extent.minX, y: -page.extent.minY))
            let card = CardImages.upright(placed)
            return CardImages.finish(card.image, faceFound: card.faceFound,
                                     machineZone: CardImages.hasMachineZone(card.image))
        }
        // La carte est cherchée de nouveau sur la photo, plus nette ; sinon
        // le cadre vu juste avant sert.
        let request = CardImages.rectangleRequest(minimumSize: 0.2)
        try? VNImageRequestHandler(ciImage: image, orientation: .up).perform([request])
        guard let quad = request.results?.first.map({ CardQuad($0) }) ?? lastQuad else { return nil }
        let card = CardImages.upright(CardImages.straighten(image, quad))
        let machineZone = readsMachineZone && CardImages.hasMachineZone(card.image)
        return CardImages.finish(card.image, faceFound: card.faceFound, machineZone: machineZone)
    }
}

// MARK: - Vidéo du visage

/// Caméra avant, sans micro : suit les consignes de `SelfieScript` image par
/// image et enregistre la vidéo entre la première et la dernière consigne.
final class SelfieEngine: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate, @unchecked Sendable {
    struct Status {
        var step: SelfieScript.Step
        var number: Int
        var recording: Bool
        var severalFaces: Bool
        var restarted: Bool
    }

    let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "com.nexishub.visage")
    private let output = AVCaptureVideoDataOutput()
    private var script = SelfieScript()
    private var writer: AVAssetWriter?
    private var input: AVAssetWriterInput?
    private var fileURL: URL?
    private var thumbnail: UIImage?
    private var frameCount = 0
    private var finishing = false

    var onStatus: ((Status) -> Void)?
    var onVideo: ((VideoShot?) -> Void)?


    func start() {
        queue.async { [self] in
            guard session.inputs.isEmpty else { if !session.isRunning { session.startRunning() }; return }
            guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front),
                  let camera = try? AVCaptureDeviceInput(device: device) else { return }
            session.beginConfiguration()
            session.sessionPreset = .hd1280x720
            if session.canAddInput(camera) { session.addInput(camera) }
            output.alwaysDiscardsLateVideoFrames = true
            output.setSampleBufferDelegate(self, queue: queue)
            if session.canAddOutput(output) { session.addOutput(output) }
            // Images non inversées : le sens de la tête se lit sans miroir.
            configure(output.connection(with: .video), mirrored: false)
            session.commitConfiguration()
            session.startRunning()
        }
    }

    func stop() {
        queue.async { [self] in
            if session.isRunning { session.stopRunning() }
            discard()
        }
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        guard !finishing, let pixels = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        let time = CMSampleBufferGetPresentationTimeStamp(sampleBuffer)
        if let input, input.isReadyForMoreMediaData { input.append(sampleBuffer) }
        frameCount += 1
        guard frameCount % 2 == 0 else { return }
        let sample = Self.sample(pixels)
        let event = script.feed(sample, at: time.seconds)
        switch event {
        case .startRecording:
            startWriting(pixels, at: time)
        case .restart:
            discard()
        case .finished:
            finishWriting()
        case .advanced, .none:
            break
        }
        onStatus?(Status(step: script.step, number: script.number, recording: writer != nil,
                         severalFaces: script.severalFaces, restarted: event == .restart))
    }

    private static func sample(_ pixels: CVPixelBuffer) -> FaceSample {
        let faces = VNDetectFaceRectanglesRequest()
        let handler = VNImageRequestHandler(cvPixelBuffer: pixels, orientation: .up)
        try? handler.perform([faces])
        let found = faces.results ?? []
        guard found.count == 1, let face = found.first else { return FaceSample(faceCount: found.count) }
        let landmarks = VNDetectFaceLandmarksRequest()
        landmarks.inputFaceObservations = [face]
        try? handler.perform([landmarks])
        let box = face.boundingBox
        var offset = 0.0
        if let nose = landmarks.results?.first?.landmarks?.nose?.normalizedPoints, !nose.isEmpty {
            offset = Double(nose.map(\.x).reduce(0, +)) / Double(nose.count) - 0.5
        }
        return FaceSample(faceCount: 1, centerX: Double(box.midX), centerY: Double(1 - box.midY),
                          width: Double(box.width),
                          turnDegrees: face.yaw.map { abs($0.doubleValue) * 180 / .pi },
                          noseOffset: offset)
    }

    private func startWriting(_ pixels: CVPixelBuffer, at time: CMTime) {
        discard()
        let width = CVPixelBufferGetWidth(pixels), height = CVPixelBufferGetHeight(pixels)
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("nexis-visage-\(UUID().uuidString).mp4")
        guard let writer = try? AVAssetWriter(outputURL: url, fileType: .mp4) else { return }
        let settings: [String: Any] = [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: width,
            AVVideoHeightKey: height,
            AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 2_000_000],
        ]
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
        input.expectsMediaDataInRealTime = true
        guard writer.canAdd(input) else { return }
        writer.add(input)
        writer.shouldOptimizeForNetworkUse = true
        guard writer.startWriting() else { return }
        writer.startSession(atSourceTime: time)
        self.writer = writer
        self.input = input
        fileURL = url
        // La vignette montre la personne comme elle se voyait (en miroir).
        let image = CIImage(cvPixelBuffer: pixels)
        if let cg = CardImages.context.createCGImage(image, from: image.extent) {
            thumbnail = UIImage(cgImage: cg, scale: 1, orientation: .upMirrored)
        }
    }

    private func finishWriting() {
        guard let writer, let input, let fileURL else {
            script = SelfieScript()
            onVideo?(nil)
            return
        }
        finishing = true
        let seconds = script.seconds, turns = script.turns, thumbnail = thumbnail
        input.markAsFinished()
        writer.finishWriting { [self] in
            queue.async { [self] in
                let data = writer.status == .completed ? try? Data(contentsOf: fileURL) : nil
                try? FileManager.default.removeItem(at: fileURL)
                self.writer = nil
                self.input = nil
                self.fileURL = nil
                guard let data, !data.isEmpty else {
                    // La vidéo n'a pas pu être lue : les consignes reprennent au début.
                    script = SelfieScript()
                    finishing = false
                    onVideo?(nil)
                    return
                }
                if session.isRunning { session.stopRunning() }
                onVideo?(VideoShot(data: data, thumbnail: thumbnail, seconds: seconds, turns: turns))
            }
        }
    }

    /// Abandonne l'enregistrement en cours et efface le fichier.
    private func discard() {
        writer?.cancelWriting()
        if let fileURL { try? FileManager.default.removeItem(at: fileURL) }
        writer = nil
        input = nil
        fileURL = nil
        thumbnail = nil
    }
}
