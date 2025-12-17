#!/usr/bin/env python3
"""
Module de chiffrement pour les sauvegardes
Fournit un chiffrement AES-256-GCM pour protéger les données au repos
"""

import os
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import json

class EncryptionManager:
    """Gestionnaire de chiffrement AES-256-GCM"""

    def __init__(self, password=None, key_file=None):
        """
        Initialise le gestionnaire de chiffrement

        Args:
            password: Mot de passe pour dériver la clé
            key_file: Fichier contenant la clé (alternative au password)
        """
        self.key = None
        self.key_file = key_file or Path.home() / '.backup_encryption_key'

        if password:
            self.key = self._derive_key(password)
        elif self.key_file.exists():
            self.key = self._load_key()
        else:
            # Générer une nouvelle clé si aucune n'existe
            self.key = AESGCM.generate_key(bit_length=256)
            self._save_key()

    def _derive_key(self, password, salt=None):
        """Dérive une clé de 256 bits depuis un mot de passe"""
        if salt is None:
            salt = b'backup_system_salt_v1'  # Salt fixe (idéalement stocké séparément)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode())

    def _save_key(self):
        """Sauvegarde la clé de chiffrement"""
        self.key_file.parent.mkdir(parents=True, exist_ok=True)

        # Encoder en base64 pour stockage
        key_b64 = base64.b64encode(self.key).decode()

        with open(self.key_file, 'w') as f:
            json.dump({
                'key': key_b64,
                'version': '1.0',
                'algorithm': 'AES-256-GCM'
            }, f)

        # Permissions restrictives
        os.chmod(self.key_file, 0o600)
        print(f"✓ Clé de chiffrement sauvegardée: {self.key_file}")

    def _load_key(self):
        """Charge la clé de chiffrement depuis le fichier"""
        try:
            with open(self.key_file, 'r') as f:
                data = json.load(f)
                return base64.b64decode(data['key'])
        except Exception as e:
            raise Exception(f"Impossible de charger la clé de chiffrement: {e}")

    def encrypt_file(self, input_file, output_file):
        """
        Chiffre un fichier avec AES-256-GCM

        Args:
            input_file: Chemin du fichier à chiffrer
            output_file: Chemin du fichier chiffré de sortie

        Returns:
            dict: Métadonnées du chiffrement (nonce, tag, size)
        """
        try:
            # Lire le fichier
            with open(input_file, 'rb') as f:
                plaintext = f.read()

            # Générer un nonce aléatoire (96 bits pour GCM)
            nonce = os.urandom(12)

            # Chiffrer avec AES-256-GCM
            aesgcm = AESGCM(self.key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)

            # Sauvegarder (nonce + ciphertext)
            with open(output_file, 'wb') as f:
                f.write(nonce + ciphertext)

            # Calculer hash du texte clair pour vérification
            plaintext_hash = hashlib.sha256(plaintext).hexdigest()

            metadata = {
                'nonce': base64.b64encode(nonce).decode(),
                'original_size': len(plaintext),
                'encrypted_size': len(ciphertext) + 12,  # +12 pour le nonce
                'plaintext_hash': plaintext_hash,
                'algorithm': 'AES-256-GCM'
            }

            return metadata

        except Exception as e:
            raise Exception(f"Erreur lors du chiffrement: {e}")

    def decrypt_file(self, input_file, output_file):
        """
        Déchiffre un fichier AES-256-GCM

        Args:
            input_file: Chemin du fichier chiffré
            output_file: Chemin du fichier déchiffré de sortie

        Returns:
            bool: True si succès
        """
        try:
            # Lire le fichier chiffré
            with open(input_file, 'rb') as f:
                encrypted_data = f.read()

            # Extraire nonce et ciphertext
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]

            # Déchiffrer
            aesgcm = AESGCM(self.key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)

            # Sauvegarder
            with open(output_file, 'wb') as f:
                f.write(plaintext)

            return True

        except Exception as e:
            raise Exception(f"Erreur lors du déchiffrement: {e}")

    def encrypt_stream(self, data):
        """Chiffre des données en mémoire"""
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def decrypt_stream(self, encrypted_data):
        """Déchiffre des données en mémoire"""
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        aesgcm = AESGCM(self.key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    def change_password(self, old_password, new_password):
        """Change le mot de passe de chiffrement"""
        old_key = self._derive_key(old_password)

        # Vérifier que l'ancien mot de passe est correct
        if old_key != self.key:
            raise ValueError("Ancien mot de passe incorrect")

        # Dériver nouvelle clé
        new_key = self._derive_key(new_password)

        # TODO: Rechiffrer tous les fichiers avec la nouvelle clé
        # Pour l'instant, juste sauvegarder la nouvelle clé
        self.key = new_key
        self._save_key()

        print("✓ Mot de passe changé avec succès")

    def get_info(self):
        """Retourne les informations sur la configuration de chiffrement"""
        return {
            'algorithm': 'AES-256-GCM',
            'key_size': 256,
            'key_file': str(self.key_file),
            'key_exists': self.key_file.exists(),
            'encryption_enabled': self.key is not None
        }


def test_encryption():
    """Teste le chiffrement/déchiffrement"""
    import tempfile

    print("\n=== Test du chiffrement ===\n")

    # Créer un gestionnaire avec mot de passe
    enc = EncryptionManager(password="test_password_123")

    # Créer un fichier de test
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        test_file = f.name
        f.write("Ceci est un test de chiffrement AES-256-GCM\n" * 100)

    try:
        # Chiffrer
        encrypted_file = test_file + '.enc'
        metadata = enc.encrypt_file(test_file, encrypted_file)

        print(f"✓ Fichier chiffré")
        print(f"  Taille originale: {metadata['original_size']} bytes")
        print(f"  Taille chiffrée: {metadata['encrypted_size']} bytes")
        print(f"  Hash: {metadata['plaintext_hash'][:16]}...")

        # Déchiffrer
        decrypted_file = test_file + '.dec'
        enc.decrypt_file(encrypted_file, decrypted_file)

        # Vérifier
        with open(test_file, 'rb') as f1, open(decrypted_file, 'rb') as f2:
            if f1.read() == f2.read():
                print(f"✓ Déchiffrement réussi - fichiers identiques")
            else:
                print(f"✗ Erreur - fichiers différents")

        # Nettoyer
        os.unlink(test_file)
        os.unlink(encrypted_file)
        os.unlink(decrypted_file)

        print("\n✓ Test terminé avec succès\n")

    except Exception as e:
        print(f"✗ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_encryption()
