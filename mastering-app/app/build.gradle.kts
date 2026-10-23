plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}
// Release identities never fall back to a newly generated CI debug key.
val permanentKeyPath = System.getenv("MASTR_KEYSTORE_PATH")
val permanentKeyPassword = System.getenv("MASTR_KEYSTORE_PASSWORD")
val temporaryCiSigning = System.getenv("MASTR_ALLOW_TEMPORARY_SIGNING") == "true"
android {
    namespace = "app.mastr.studio"
    compileSdk = 35
    defaultConfig {
        applicationId = "app.mastr.studio"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildFeatures { compose = true; buildConfig = true }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    signingConfigs {
        if (permanentKeyPath != null) {
            create("permanent") {
                storeFile = file(permanentKeyPath)
                storeType = "PKCS12"
                storePassword = permanentKeyPassword
                keyAlias = "mastr-studio"
                keyPassword = permanentKeyPassword
            }
        }
    }
    buildTypes {
        getByName("release") {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // Throwaway signing is explicitly opt-in, for CI device tests ONLY.
            // ci/sign-mastering.py must apply the permanent identity before delivery.
            signingConfig = if (permanentKeyPath != null) signingConfigs.getByName("permanent")
                else if (temporaryCiSigning) signingConfigs.getByName("debug") else null
        }
    }
    packaging { jniLibs.useLegacyPackaging = true; resources.excludes += setOf("META-INF/DEPENDENCIES", "META-INF/LICENSE*", "META-INF/NOTICE*") }
}
tasks.matching { it.name == "packageRelease" }.configureEach {
    doFirst {
        check(permanentKeyPath != null || temporaryCiSigning) {
            "Permanent signing key missing. Restore the private backup; never generate a replacement. See SIGNING.md."
        }
    }
}
dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")
    implementation("com.github.wendykierp:JTransforms:3.1")
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation(platform("androidx.compose:compose-bom:2024.12.01"))
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
