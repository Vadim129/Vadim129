# Actual ACE-Step inference, operated by the agent

This workflow runs a real audio-conditioned generative music model. It does not
silently fall back to MIDI layering, EQ, or returning the supplied audio as if
it were generated. A Cover is a re-performance: vocal identity, pronunciation,
lyrics, and arrangement are not guaranteed to remain unchanged.

## Worker

- Standard `ubuntu-24.04` GitHub-hosted CPU runner; no paid larger runner.
- Pinned upstream code: `ace-step/ACE-Step-1.5` at
  `ca1e85fe9430179831e6bc6be790c332190a3866`.
- Official `ACE-Step/Ace-Step1.5` DiT Turbo, VAE, and text encoder weights.
  The separate planning LM is not loaded. Weight files are downloaded from
  the upstream model repository and are not stored in this Git repository.
- CPU DiT/text inference in bfloat16; VAE in CPU-safe float32.
- Cover strength 0.75, eight steps, seed 129, relaxed acoustic-pop/lullaby prompt.
- Full mode privately transcribes the source with faster-whisper small and
  provides the recognized Russian lyrics as additional conditioning.

The optional `music_task` workflow-dispatch input accepts `preview` or `full`.
Where the integration cannot dispatch workflows, a push to this session's
branch whose commit message contains `[music-ai:preview]` or `[music-ai:full]`
starts the corresponding job. Ordinary commits on this branch do not run the
legacy build script or another inference job. The previous build behavior on
its original configured branch is retained. A new marked inference request
cancels an older request on the same branch.

## Private transfer

No source recording, vocal transcript, generated plaintext audio, or private
key is intentionally published in the repository or public Actions artifacts.

1. The sandbox holds a private X25519 client key in ignored `music_private/`;
   only its public counterpart is committed.
2. Each temporary worker generates a new key pair and commits only the public
   key to this same working branch.
3. The agent encrypts the source to that worker key. Only authenticated
   ciphertext is sent through Git. The original Drive sharing is not changed.
4. The worker authenticates/decrypts the source in temporary storage, performs
   inference, then encrypts audio and diagnostics to the client's public key.
5. The agent retrieves the ciphertext through Git, decrypts locally, checks the
   result, and uploads the audio to the requested Google Drive destination.

The envelope uses X25519 + HKDF-SHA256 + AES-256-GCM with a fresh ephemeral key
and nonce for every message. Output archives authenticate before extraction;
archive paths are restricted to plain filenames. Encryption tests cover
roundtrips, tampering, wrong-recipient rejection, and invalid headers.

GitHub Secrets and write access to the Actions dispatch API are not required.
The music job itself needs `contents: write` solely to exchange public keys and
encrypted payloads on this working branch. It does not read repository secrets.
Azure-backed artifact download and raw workflow-log access are not needed.

## Checks and diagnostics

```sh
.venv/bin/python -m unittest discover -s music -p test_ai_artifacts.py
```

Private keys belong in ignored `music_private/`, never in Git. Decrypted audio,
model checkpoints, logs and generated assets belong in ignored/excluded `out/`
or temporary `runtime/`. Do not delete the client private key before receiving
the output. Treat `status.json` inside the decrypted result as authoritative;
a successful transfer alone is not proof that model inference succeeded.

Preview run `39882106087` completed actual 24-second Cover inference in 53.8
seconds, with exit code zero and non-silent finite stereo output. Full mode
also checks generated duration against the supplied source. Technical checks
are not a claim that a result has been subjectively listened to or matches
Suno in quality.

## Completed full run

Run `39882459862` completed successfully. The full 160.88-second Cover took
385.1 seconds of inference after the short test, used private source-lyric
conditioning, and produced finite, non-silent stereo audio at 48 kHz. Delivery
received only a 0.2 dB safety reduction and short boundary fades. The decoded
320 kbps MP3 measured −14.45 LUFS, −1.60 dBTP and LRA 8.50 LU. A 24-bit WAV
was also exported. Audio was delivered to Google Drive, not published as
plaintext in this repository. The original recording was not modified.

Temporary transport ciphertext and the expired worker public key are removed
from the branch's working tree after retrieval. Historical ciphertext remains
cryptographically protected. The client private key is not committed.
