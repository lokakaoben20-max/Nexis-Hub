package com.nexishub.app.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG
import androidx.biometric.BiometricPrompt
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import java.time.Duration
import java.time.Instant
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.Mac
import javax.crypto.SecretKey
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine

/** Règles du code NexisHub (6 chiffres), sans état : testées seules. */
object CodeRules {
    const val LENGTH = 6

    /** Après 5 erreurs, le téléphone est déconnecté du compte. */
    const val MAX_FAILURES = 5

    /** L'app se verrouille quand elle reste fermée au moins une minute. */
    val LOCK_AFTER: Duration = Duration.ofSeconds(60)

    /** Un code trop facile à deviner : un ou deux chiffres répétés (111111,
     * 121212), une suite (123456, 987654) ou deux moitiés pareilles (123123). */
    fun isWeak(code: String): Boolean {
        if (code.length != LENGTH || !code.all { it in '0'..'9' }) return true
        val digits = code.map { it - '0' }
        if (digits.toSet().size <= 2) return true
        val steps = digits.zipWithNext { a, b -> b - a }.toSet()
        if (steps == setOf(1) || steps == setOf(-1)) return true
        if (code.take(LENGTH / 2) == code.takeLast(LENGTH / 2)) return true
        return false
    }

    /** Verrouiller au retour, selon le temps passé hors de l'app. */
    fun shouldLock(leftAt: Instant?, now: Instant): Boolean =
        leftAt != null && Duration.between(leftAt, now) >= LOCK_AFTER

    /** Comparaison en temps constant. */
    fun same(a: ByteArray, b: ByteArray): Boolean = MessageDigest.isEqual(a, b)
}

/** Ce qui est gardé sur le téléphone. Le code lui-même n'est jamais gardé :
 * seulement son empreinte salée. */
data class CodeRecord(
    val salt: ByteArray,
    val digest: ByteArray,
    val failures: Int = 0,
    val biometrics: Boolean = false,
) {
    override fun equals(other: Any?): Boolean = other is CodeRecord && salt.contentEquals(other.salt) &&
        digest.contentEquals(other.digest) && failures == other.failures && biometrics == other.biometrics

    override fun hashCode(): Int = digest.contentHashCode()
}

interface CodeVault {
    fun load(): CodeRecord?
    fun save(record: CodeRecord)
    fun erase()

    /** Empreinte du code tapé. */
    fun digest(code: String, salt: ByteArray): ByteArray
}

/** Fichier privé de l'app (non sauvegardé : allowBackup="false"). L'empreinte
 * est un HMAC fait par une clé du Keystore d'Android, qui ne sort jamais du
 * téléphone : même copié, le fichier ne permet pas d'essayer des codes. */
class KeystoreCodeVault(context: Context) : CodeVault {
    private val prefs = context.getSharedPreferences("nexis_code", Context.MODE_PRIVATE)
    private val encoder = Base64.getEncoder()
    private val decoder = Base64.getDecoder()

    override fun load(): CodeRecord? {
        val salt = prefs.getString("salt", null) ?: return null
        val digest = prefs.getString("digest", null) ?: return null
        return CodeRecord(
            salt = decoder.decode(salt),
            digest = decoder.decode(digest),
            failures = prefs.getInt("failures", 0),
            biometrics = prefs.getBoolean("biometrics", false),
        )
    }

    override fun save(record: CodeRecord) {
        prefs.edit()
            .putString("salt", encoder.encodeToString(record.salt))
            .putString("digest", encoder.encodeToString(record.digest))
            .putInt("failures", record.failures)
            .putBoolean("biometrics", record.biometrics)
            .commit()
    }

    override fun erase() {
        prefs.edit().clear().commit()
    }

    override fun digest(code: String, salt: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(hmacKey())
        mac.update(salt)
        return mac.doFinal(code.toByteArray(Charsets.UTF_8))
    }

    private fun hmacKey(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(HMAC_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_HMAC_SHA256, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(HMAC_ALIAS, KeyProperties.PURPOSE_SIGN).build())
        return generator.generateKey()
    }

    private companion object {
        const val HMAC_ALIAS = "nexis_code_hmac"
    }
}

/** Pour les tests et les captures de la CI. */
class MemoryCodeVault(private var record: CodeRecord? = null) : CodeVault {
    override fun load(): CodeRecord? = record
    override fun save(record: CodeRecord) {
        this.record = record
    }
    override fun erase() {
        record = null
    }
    override fun digest(code: String, salt: ByteArray): ByteArray {
        val spec = PBEKeySpec(code.toCharArray(), salt, 100_000, 256)
        return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
    }
}

enum class BiometricResult { OK, FAILED, CHANGED }

/** L'empreinte (ou un autre capteur de classe « forte ») du téléphone. */
interface Biometrics {
    val available: Boolean

    /** Prépare une nouvelle clé liée aux empreintes enregistrées. */
    fun prepare()

    suspend fun authenticate(activity: FragmentActivity, title: String, negative: String): BiometricResult

    fun forget()
}

/** BiometricPrompt avec une clé du Keystore que tout ajout d'empreinte
 * invalide : une empreinte ajoutée après l'activation ne peut pas ouvrir
 * l'app, le code est redemandé. */
class AndroidBiometrics(private val context: Context) : Biometrics {
    override val available: Boolean
        get() = BiometricManager.from(context).canAuthenticate(BIOMETRIC_STRONG) == BiometricManager.BIOMETRIC_SUCCESS

    override fun prepare() {
        forget()
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setUserAuthenticationRequired(true)
                .setInvalidatedByBiometricEnrollment(true)
                .build(),
        )
        generator.generateKey()
    }

    override suspend fun authenticate(activity: FragmentActivity, title: String, negative: String): BiometricResult {
        val key = keyStore().getKey(KEY_ALIAS, null) as? SecretKey ?: return BiometricResult.CHANGED
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        try {
            cipher.init(Cipher.ENCRYPT_MODE, key)
        } catch (_: KeyPermanentlyInvalidatedException) {
            forget()
            return BiometricResult.CHANGED
        }
        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .setNegativeButtonText(negative)
            .setAllowedAuthenticators(BIOMETRIC_STRONG)
            .setConfirmationRequired(false)
            .build()
        return suspendCancellableCoroutine { continuation ->
            val prompt = BiometricPrompt(
                activity,
                ContextCompat.getMainExecutor(activity),
                object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                        // La clé ne sert que si l'empreinte a vraiment été reconnue.
                        val ok = runCatching { result.cryptoObject?.cipher?.doFinal(byteArrayOf(1)) }.getOrNull() != null
                        if (continuation.isActive) continuation.resume(if (ok) BiometricResult.OK else BiometricResult.FAILED)
                    }

                    override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                        if (continuation.isActive) continuation.resume(BiometricResult.FAILED)
                    }
                },
            )
            prompt.authenticate(info, BiometricPrompt.CryptoObject(cipher))
            continuation.invokeOnCancellation { prompt.cancelAuthentication() }
        }
    }

    override fun forget() {
        runCatching { keyStore().deleteEntry(KEY_ALIAS) }
    }

    private fun keyStore() = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

    private companion object {
        const val KEY_ALIAS = "nexis_empreinte"
    }
}

/** Le code NexisHub et l'empreinte de ce téléphone. C'est le téléphone qui
 * reconnaît la personne : l'app ne reçoit qu'un oui ou un non. */
class AppSecurity(private val vault: CodeVault, private val biometrics: Biometrics) {
    sealed interface Check {
        data object Ok : Check
        data class Wrong(val left: Int) : Check
        data object Blocked : Check
    }

    private var record by mutableStateOf(vault.load())

    /** Captures de la CI : l'émulateur n'a pas d'empreinte. */
    var biometryOverride: Boolean? = null

    val hasCode: Boolean get() = record != null
    val biometryAvailable: Boolean get() = biometryOverride ?: biometrics.available
    val biometricsOn: Boolean get() = record?.biometrics == true && biometryAvailable
    val failures: Int get() = record?.failures ?: 0

    /** Crée ou remplace le code. L'empreinte reste comme elle était. */
    fun setCode(code: String) {
        require(!CodeRules.isWeak(code)) { "code trop faible" }
        val salt = ByteArray(16).also { SecureRandom().nextBytes(it) }
        store(CodeRecord(salt, vault.digest(code, salt), biometrics = record?.biometrics ?: false))
    }

    /** Vérifie un code tapé. Le compteur d'erreurs est gardé avec le code :
     * fermer l'app ne le remet pas à zéro. */
    fun check(code: String): Check {
        val current = record ?: return Check.Blocked
        if (current.failures >= CodeRules.MAX_FAILURES) return Check.Blocked
        if (CodeRules.same(vault.digest(code, current.salt), current.digest)) {
            store(current.copy(failures = 0))
            return Check.Ok
        }
        val failures = current.failures + 1
        store(current.copy(failures = failures))
        val left = CodeRules.MAX_FAILURES - failures
        return if (left > 0) Check.Wrong(left) else Check.Blocked
    }

    /** Active l'empreinte après une reconnaissance réussie. */
    suspend fun enableBiometrics(activity: FragmentActivity?, title: String, negative: String): Boolean {
        val current = record ?: return false
        if (!biometryAvailable) return false
        if (biometryOverride != null) {
            store(current.copy(biometrics = true))
            return true
        }
        activity ?: return false
        val ok = runCatching {
            biometrics.prepare()
            biometrics.authenticate(activity, title, negative) == BiometricResult.OK
        }.getOrDefault(false)
        if (!ok) {
            biometrics.forget()
            return false
        }
        store((record ?: current).copy(biometrics = true, failures = 0))
        return true
    }

    fun disableBiometrics() {
        biometrics.forget()
        record?.let { store(it.copy(biometrics = false)) }
    }

    /** Ouvre avec l'empreinte. Si une empreinte a été ajoutée au téléphone
     * depuis l'activation, l'empreinte est coupée et le code est demandé. */
    suspend fun unlockWithBiometrics(activity: FragmentActivity?, title: String, negative: String): BiometricResult {
        val current = record ?: return BiometricResult.FAILED
        if (!biometricsOn || current.failures >= CodeRules.MAX_FAILURES || activity == null) return BiometricResult.FAILED
        val result = runCatching { biometrics.authenticate(activity, title, negative) }.getOrDefault(BiometricResult.FAILED)
        when (result) {
            BiometricResult.OK -> store((record ?: current).copy(failures = 0))
            BiometricResult.CHANGED -> disableBiometrics()
            BiometricResult.FAILED -> Unit
        }
        return result
    }

    /** Captures de la CI : un code déjà créé, et l'empreinte si demandé. */
    fun presetForCapture(code: String, biometricsOn: Boolean) {
        biometryOverride = true
        setCode(code)
        if (biometricsOn) record?.let { store(it.copy(biometrics = true)) }
    }

    /** Déconnexion : le code part avec la session. */
    fun erase() {
        vault.erase()
        biometrics.forget()
        record = null
    }

    private fun store(next: CodeRecord) {
        vault.save(next)
        record = next
    }
}
