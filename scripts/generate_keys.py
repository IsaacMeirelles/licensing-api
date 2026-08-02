"""Gera um par de chaves Ed25519 para assinatura de licencas.

Uso:
    uv run scripts/generate_keys.py

Cole as saidas (LICENSE_SIGNING_PRIVATE_KEY_B64 e
LICENSE_SIGNING_PUBLIC_KEY_B64) no arquivo .env. A privada fica SOMENTE
no servidor; a publica pode ser embutida no seu software (cliente) para
validacao offline.
"""
import base64

import nacl.signing


def main() -> None:
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    print("Copie estes valores para o seu .env:\n")
    print("LICENSE_SIGNING_PRIVATE_KEY_B64=" + base64.b64encode(bytes(signing_key)).decode())
    print("LICENSE_SIGNING_PUBLIC_KEY_B64=" + base64.b64encode(bytes(verify_key)).decode())


if __name__ == "__main__":
    main()
