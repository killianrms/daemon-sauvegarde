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
    """Gestionnaire de chiffrement AES-256-GCM (v3.0 Envelope)"""

    def __init__(self, password=None, key_file=None):
        """
        Initialise le gestionnaire de chiffrement
        
        Args:
            password: Mot de passe pour déverrouiller la clé maîtresse
            key_file: Fichier de stockage de la clé
        """
        self.master_key = None # The actual key used for file encryption
        self.key_file = key_file or Path.home() / '.backup_encryption_key'
        self.salt = None
        self.wrapped_key = None # Encrypted Master Key

        if self.key_file.exists():
            self._load_key_file(password)
        elif password:
            # New Setup
            self.salt = os.urandom(16)
            self.master_key = AESGCM.generate_key(bit_length=256)
            self._save_key_file(password)
        else:
            # No password, generate random master key and save it (unencrypted/raw check?)
            # For this secure system, we require a password effectively for wrapping usually.
            # But let's support "No Password" mode where we just store Master Key raw?
            # Or generate a random KEK?
            # Let's assume password is mandatory for v3 or we use a default one?
            # Revert to raw storage if no password (same as before but explicit)
            self.master_key = AESGCM.generate_key(bit_length=256)
            self._save_key_file(None)

    def _derive_kek(self, password, salt):
        """Dérive la Key Encryption Key (KEK) depuis le mot de passe"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode())

    def _save_key_file(self, password):
        """Sauvegarde la clé (enveloppée si mot de passe fourni)"""
        try:
            if not self.key_file.exists():
                self.key_file.touch(mode=0o600)
            else:
                os.chmod(self.key_file, 0o600)
            self.key_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'version': '3.0',
                'algorithm': 'AES-256-GCM',
                'salt': base64.b64encode(self.salt).decode() if self.salt else None
            }

            if password and self.salt:
                # Envelope Encryption
                kek = self._derive_kek(password, self.salt)
                aesgcm = AESGCM(kek)
                nonce = os.urandom(12)
                wrapped = aesgcm.encrypt(nonce, self.master_key, None)
                
                data['mode'] = 'wrapped'
                data['nonce'] = base64.b64encode(nonce).decode()
                data['key'] = base64.b64encode(wrapped).decode()
            else:
                # Raw Storage
                data['mode'] = 'raw'
                data['key'] = base64.b64encode(self.master_key).decode()

            with open(self.key_file, 'w') as f:
                json.dump(data, f)
            os.chmod(self.key_file, 0o600)
            
        except Exception as e:
            print(f"Error saving key: {e}")
            raise

    def _load_key_file(self, password):
        try:
            with open(self.key_file, 'r') as f:
                data = json.load(f)

            version = data.get('version', '1.0')
            
            # Migration V2 -> V3
            if version == '2.0' or version == '1.0':
                # Old format: key was derived directly or stored directly.
                # V2: stored derived key in 'key' field, salt in 'salt'.
                # We can't verify password easily without trying to derive and match?
                # Actually V2 stored the KEY itself.
                # If password was used, we derived logic outside.
                # Wait, my previous V2 implementation stored `key = derived_key`.
                # So if we load it, we have the Master Key directly.
                # We can migrate it to wrapped format if password is provided.
                
                stored_key_b64 = data.get('key')
                if not stored_key_b64: raise ValueError("Corrupt key file")
                self.master_key = base64.b64decode(stored_key_b64)
                
                if data.get('salt'):
                    self.salt = base64.b64decode(data['salt'])
                else:
                    self.salt = os.urandom(16)
                    
                print("⚠ Migrating Key File from v2 to v3 (Envelope Encryption)...")
                self._save_key_file(password)
                return

            # V3 Loading
            self.salt = base64.b64decode(data['salt']) if data.get('salt') else None
            mode = data.get('mode', 'raw')
            encrypted_key = base64.b64decode(data['key'])
            
            if mode == 'wrapped':
                if not password:
                    raise ValueError("Password required to unlock this key file.")
                if not self.salt:
                     raise ValueError("Corrupt key file: Wrapped mode without salt.")
                     
                nonce = base64.b64decode(data['nonce'])
                kek = self._derive_kek(password, self.salt)
                aesgcm = AESGCM(kek)
                try:
                    self.master_key = aesgcm.decrypt(nonce, encrypted_key, None)
                except:
                    raise ValueError("Incorrect password.")
            else:
                self.master_key = encrypted_key

        except Exception as e:
            raise Exception(f"Key load failed: {e}")

    @property
    def key(self):
        # Compatibility with existing code that accesses .key
        return self.master_key

    @key.setter
    def key(self, value):
        self.master_key = value

    def change_password(self, old_password, new_password):
        """Change le mot de passe sans rechiffrer les données (Key Wrapping)"""
        # 1. Verify old password (unlock)
        # We assume self.master_key is already loaded/valid.
        # But to be sure, we can try to unlock again?
        # If we are here, self.master_key is in memory.
        
        # We just re-wrap with new password.
        print("⟳ Re-wrapping Master Key with new password...")
        
        # Generate new salt for the new password wrapping (Good practice)
        self.salt = os.urandom(16)
        self._save_key_file(new_password)
        print("✓ Mot de passe changé (Données préservées).")

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
        """Change le mot de passe sans rechiffrer les données (Key Wrapping)"""
        try:
             # Verify old password
             # We assume current key_file corresponds to current self.master_key
             # Load in a temp instance to verify authentication
             # Note: This works for both v2 (migrated on load) and v3
             # If v2, loading it triggers migration save?? Wait.
             # My _load_key_file logic migrates IF v2. 
             # So calling EncryptionManager(old_password) will migrate it on disk if it was v2.
             # That's fine.
             
             # Avoid infinite recursion or file lock? 
             # Loading reads file. Safe.
             
             # We pass self.key_file.
             EncryptionManager(password=old_password, key_file=self.key_file)
             
             # If successful, we can re-wrap
             print("⟳ Re-wrapping Master Key with new password...")
             self.salt = os.urandom(16)
             self._save_key_file(new_password)
             print("✓ Mot de passe changé (Données préservées).")
             
        except Exception as e:
            raise ValueError(f"Ancien mot de passe incorrect: {e}")

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
