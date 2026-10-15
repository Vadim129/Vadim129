# Third-party notices

## PDFBox-Android

The APK includes [PDFBox-Android](https://github.com/TomRoush/PdfBox-Android) solely to extract the embedded text from PDF books on-device for reading and speech synthesis.

- Maven artifact: `com.tom-roush:pdfbox-android:2.0.27.0`
- License: Apache License 2.0
- Upstream: Apache PDFBox / Tom Roush's Android port

## Sherpa-ONNX

The APK includes the prebuilt [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx) Android runtime to run the bundled Piper/VITS Russian neural voices locally.

- Release runtime: `sherpa-onnx-1.13.8.aar`
- License: Apache License 2.0
- Runtime integrity: SHA-256 pinned in `scripts/fetch-neural-tts-assets.sh`

## Piper Russian voices

- `ru_RU-irina-medium-int8`
- `ru_RU-dmitri-medium-int8`

The build downloads the upstream, checksum-pinned voice archives from the Sherpa-ONNX `tts-models` release. They are used exclusively for offline speech synthesis. Consult each upstream model card for model-specific attribution and licence information.

## Google Gemini API

Gemini is optional and is called directly by a user-provided API key. No Google SDK, Firebase SDK, tracker, advertisement SDK, shared key, or analytics SDK is included.
