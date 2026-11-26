import CommonCrypto
import Foundation
import LocalAuthentication
import Observation
import Security

/// Règles du code NexisHub (6 chiffres), sans état : testées seules.
enum CodeRules {
    static let length = 6
    /// Après 5 erreurs, le téléphone est déconnecté du compte.
    static let maxFailures = 5
    /// L'app se verrouille quand elle reste fermée au moins une minute.
    static let lockAfter: TimeInterval = 60
    /// PBKDF2-SHA256 : chaque essai coûte du temps à qui volerait le fichier.
    static let rounds: UInt32 = 100_000

    /// Un code trop facile à deviner : un ou deux chiffres répétés (111111,
    /// 121212), une suite (123456, 987654) ou deux moitiés pareilles (123123).
    static func isWeak(_ code: String) -> Bool {
        let digits = code.compactMap(\.wholeNumberValue)
        guard digits.count == length, digits.count == code.count else { return true }
        if Set(digits).count <= 2 { return true }
        let steps = Set(zip(digits, digits.dropFirst()).map { $1 - $0 })
        if steps == [1] || steps == [-1] { return true }
        if Array(digits.prefix(length / 2)) == Array(digits.suffix(length / 2)) { return true }
        return false
    }

    /// Verrouiller au retour, selon le temps passé hors de l'app.
    static func shouldLock(leftAt: Date?, now: Date) -> Bool {
        guard let leftAt else { return false }
        return now.timeIntervalSince(leftAt) >= lockAfter
    }

    static func digest(_ code: String, salt: Data) -> Data {
        var out = [UInt8](repeating: 0, count: 32)
        let status = salt.withUnsafeBytes { saltBytes in
            CCKeyDerivationPBKDF(CCPBKDFAlgorithm(kCCPBKDF2), code, code.utf8.count,
                                 saltBytes.bindMemory(to: UInt8.self).baseAddress, salt.count,
                                 CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256), rounds, &out, out.count)
        }
        precondition(status == kCCSuccess, "PBKDF2 a échoué")
        return Data(out)
    }

    /// Comparaison en temps constant.
    static func same(_ a: Data, _ b: Data) -> Bool {
        guard a.count == b.count else { return false }
        return zip(a, b).reduce(0) { $0 | ($1.0 ^ $1.1) } == 0
    }
}

/// Ce qui est gardé sur le téléphone. Le code lui-même n'est jamais gardé :
/// seulement son empreinte salée.
struct CodeRecord: Codable, Equatable {
    var salt: Data
    var digest: Data
    var failures = 0
    var biometrics = false
    /// État de Face ID / Touch ID quand il a été activé : s'il change (un
    /// visage ou un doigt ajouté), on redemande le code.
    var biometryState: Data?
}

protocol CodeVault {
    func load() -> CodeRecord?
    func save(_ record: CodeRecord)
    func erase()
}

/// Trousseau d'iOS, lisible seulement sur ce téléphone, une fois déverrouillé.
struct KeychainCodeVault: CodeVault {
    private let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: "com.nexishub.app.code",
        kSecAttrAccount as String: "nexis",
    ]

    func load() -> CodeRecord? {
        var search = query
        search[kSecReturnData as String] = true
        search[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(search as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return try? JSONDecoder().decode(CodeRecord.self, from: data)
    }

    func save(_ record: CodeRecord) {
        guard let data = try? JSONEncoder().encode(record) else { return }
        let update: [String: Any] = [kSecValueData as String: data]
        if SecItemUpdate(query as CFDictionary, update as CFDictionary) == errSecItemNotFound {
            var add = query
            add[kSecValueData as String] = data
            add[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            SecItemAdd(add as CFDictionary, nil)
        }
    }

    func erase() { SecItemDelete(query as CFDictionary) }
}

/// Pour les tests et les captures de la CI.
final class MemoryCodeVault: CodeVault {
    private var record: CodeRecord?
    init(_ record: CodeRecord? = nil) { self.record = record }
    func load() -> CodeRecord? { record }
    func save(_ record: CodeRecord) { self.record = record }
    func erase() { record = nil }
}

/// Le code NexisHub et Face ID / Touch ID de ce téléphone. C'est le
/// téléphone qui reconnaît la personne : l'app ne reçoit qu'un oui ou un non.
@MainActor
@Observable
final class AppSecurity {
    enum Biometry: Equatable { case none, faceID, touchID, opticID }
    enum Check: Equatable { case ok, wrong(left: Int), blocked }
    enum BiometricResult: Equatable { case ok, failed, changed }

    private let vault: CodeVault
    private var record: CodeRecord?
    /// Captures de la CI : le simulateur n'a pas Face ID.
    var biometryOverride: Biometry?

    init(vault: CodeVault) {
        self.vault = vault
        self.record = vault.load()
    }

    var hasCode: Bool { record != nil }
    var biometricsOn: Bool { record?.biometrics == true && biometry != .none }
    var failures: Int { record?.failures ?? 0 }

    var biometry: Biometry {
        if let biometryOverride { return biometryOverride }
        let context = LAContext()
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil) else { return .none }
        switch context.biometryType {
        case .faceID: return .faceID
        case .touchID: return .touchID
        case .opticID: return .opticID
        default: return .none
        }
    }

    /// Nom affiché : ce sont des marques d'Apple, jamais traduites.
    var biometryName: String {
        switch biometry {
        case .faceID: return "Face ID"
        case .touchID: return "Touch ID"
        case .opticID: return "Optic ID"
        case .none: return ""
        }
    }

    var biometrySymbol: String {
        switch biometry {
        case .touchID: return "touchid"
        case .opticID: return "opticid"
        default: return "faceid"
        }
    }

    /// Crée ou remplace le code. Face ID reste comme il était.
    func setCode(_ code: String) {
        precondition(!CodeRules.isWeak(code), "code trop faible")
        var salt = Data(count: 16)
        let status = salt.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 16, $0.baseAddress!) }
        precondition(status == errSecSuccess, "aléa indisponible")
        var next = CodeRecord(salt: salt, digest: CodeRules.digest(code, salt: salt))
        next.biometrics = record?.biometrics ?? false
        next.biometryState = record?.biometryState
        store(next)
    }

    /// Vérifie un code tapé. Le compteur d'erreurs est gardé avec le code :
    /// fermer l'app ne le remet pas à zéro.
    func check(_ code: String) -> Check {
        guard var current = record else { return .blocked }
        if current.failures >= CodeRules.maxFailures { return .blocked }
        if CodeRules.same(CodeRules.digest(code, salt: current.salt), current.digest) {
            current.failures = 0
            store(current)
            return .ok
        }
        current.failures += 1
        store(current)
        let left = CodeRules.maxFailures - current.failures
        return left > 0 ? .wrong(left: left) : .blocked
    }

    /// Active Face ID après une reconnaissance réussie.
    func enableBiometrics(reason: String, fallback: String) async -> Bool {
        guard var current = record, biometry != .none else { return false }
        if biometryOverride != nil {
            current.biometrics = true
            store(current)
            return true
        }
        let context = LAContext()
        context.localizedFallbackTitle = fallback
        guard (try? await context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason)) == true
        else { return false }
        current.biometrics = true
        current.biometryState = context.domainState.biometry.stateHash
        current.failures = 0
        store(current)
        return true
    }

    func disableBiometrics() {
        guard var current = record else { return }
        current.biometrics = false
        current.biometryState = nil
        store(current)
    }

    /// Ouvre avec Face ID. Si un visage ou un doigt a été ajouté au
    /// téléphone depuis l'activation, Face ID est coupé et le code est demandé.
    func unlockWithBiometrics(reason: String, fallback: String) async -> BiometricResult {
        guard biometricsOn, var current = record, current.failures < CodeRules.maxFailures else { return .failed }
        let context = LAContext()
        context.localizedFallbackTitle = fallback
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil) else { return .failed }
        if let saved = current.biometryState, let now = context.domainState.biometry.stateHash, saved != now {
            disableBiometrics()
            return .changed
        }
        guard (try? await context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason)) == true
        else { return .failed }
        current.failures = 0
        store(current)
        return .ok
    }

    #if DEBUG
    /// Captures de la CI : un code déjà créé, et Face ID si demandé.
    func presetForCapture(code: String, biometry: Biometry?, on: Bool) {
        biometryOverride = biometry
        setCode(code)
        if on, var current = record {
            current.biometrics = true
            store(current)
        }
    }
    #endif

    /// Déconnexion : le code part avec la session.
    func erase() {
        vault.erase()
        record = nil
    }

    private func store(_ next: CodeRecord) {
        vault.save(next)
        record = next
    }
}
