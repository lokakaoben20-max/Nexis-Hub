plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.nexishub.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.nexishub.app"
        minSdk = 26
        targetSdk = 36
        // Numéro de version : celui de la compilation (CI), pour que chaque
        // nouvelle version s'installe par-dessus la précédente.
        versionCode = System.getenv("NEXIS_VERSION_CODE")?.toIntOrNull() ?: 1
        versionName = "1.0.0 ($versionCode)"
    }

    // Clé de signature fixe de Nexis Hub, fournie par la CI (secrets GitHub).
    // Sans elle (poste de développement), Android Studio signe avec sa clé de
    // débogage locale.
    val keystorePath = System.getenv("NEXIS_KEYSTORE_PATH")
    signingConfigs {
        if (keystorePath != null) {
            create("nexis") {
                storeFile = file(keystorePath)
                storeType = "pkcs12"
                storePassword = System.getenv("NEXIS_KEYSTORE_PASSWORD")
                keyAlias = "nexis"
                keyPassword = System.getenv("NEXIS_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            if (keystorePath != null) signingConfig = signingConfigs.getByName("nexis")
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.06.01")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // Étape « Pièce d'identité » : scanner de documents de ML Kit (galerie
    // désactivée), caméra avant et vidéo sans son (CameraX), visages et angle
    // de la tête (ML Kit, modèle dans l'app, rien n'est envoyé).
    implementation("com.google.android.gms:play-services-mlkit-document-scanner:16.0.0")
    implementation("com.google.mlkit:face-detection:16.1.7")
    // Page photo du passeport : lecture de la zone de lecture automatique, sur le téléphone.
    implementation("com.google.mlkit:text-recognition:16.0.1")
    val cameraX = "1.4.2"
    implementation("androidx.camera:camera-camera2:$cameraX")
    implementation("androidx.camera:camera-lifecycle:$cameraX")
    implementation("androidx.camera:camera-video:$cameraX")
    implementation("androidx.camera:camera-view:$cameraX")
    debugImplementation("androidx.compose.ui:ui-tooling")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20250517")
}
