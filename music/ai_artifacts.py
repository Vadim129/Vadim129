"""Authenticated public-key encryption for remote audio transfer.

Only public keys and ciphertext cross the public GitHub repository/artifacts.
Private keys stay in ignored local storage or the temporary hosted worker.
No repository secrets, access tokens, or plaintext audio are published.
"""
import argparse
import io
import os
from pathlib import Path
import zipfile

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC=b'AMUS2'
AAD=b'arena-music-transfer-v2'


def derive(shared):
    return HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=AAD).derive(shared)


def seal(data,public):
    ephemeral=X25519PrivateKey.generate()
    recipient=X25519PublicKey.from_public_bytes(public)
    key=derive(ephemeral.exchange(recipient))
    pub=ephemeral.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    nonce=os.urandom(12)
    return MAGIC+pub+nonce+AESGCM(key).encrypt(nonce,data,AAD)


def unseal(data,private):
    if not data.startswith(MAGIC) or len(data)<65:
        raise ValueError('Invalid encrypted music payload')
    secret=X25519PrivateKey.from_private_bytes(private)
    key=derive(secret.exchange(X25519PublicKey.from_public_bytes(data[5:37])))
    return AESGCM(key).decrypt(data[37:49],data[49:],AAD)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=['keygen','seal','unseal','archive','extract'])
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--key',type=Path)
    args=parser.parse_args()
    if args.operation=='keygen':
        private=X25519PrivateKey.generate()
        args.source.parent.mkdir(parents=True,exist_ok=True)
        args.destination.parent.mkdir(parents=True,exist_ok=True)
        args.source.write_bytes(private.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()))
        args.source.chmod(0o600)
        args.destination.write_bytes(private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw))
    else:
        if args.key is None:
            parser.error('--key is required')
        key=args.key.read_bytes()
        if args.operation=='archive':
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
                for file in sorted(args.source.glob('*')):
                    if file.is_file() and file.suffix in ('.wav','.mp3','.json'):
                        z.write(file,file.name)
            output=seal(data.getvalue(),key)
        elif args.operation=='seal':
            output=seal(args.source.read_bytes(),key)
        elif args.operation=='unseal':
            output=unseal(args.source.read_bytes(),key)
        else:
            plain=unseal(args.source.read_bytes(),key)
            args.destination.mkdir(parents=True,exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(plain)) as z:
                for info in z.infolist():
                    if Path(info.filename).name!=info.filename:
                        raise ValueError('Unsafe archive member')
                    (args.destination/info.filename).write_bytes(z.read(info))
            print('Encrypted artifact extracted.')
            return
        args.destination.parent.mkdir(parents=True,exist_ok=True)
        args.destination.write_bytes(output)
    print(f'Transfer operation {args.operation} completed.')


if __name__=='__main__':
    main()
