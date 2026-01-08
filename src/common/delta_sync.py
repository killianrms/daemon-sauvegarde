#!/usr/bin/env python3
"""
Module de synchronisation incrémentale (Delta Sync)
Envoie seulement les différences entre fichiers pour économiser bande passante
Inspiré de rsync
"""

import hashlib
import os
from pathlib import Path
import struct

class DeltaSync:
    """Gestionnaire de synchronisation incrémentale"""

    BLOCK_SIZE = 4096  # Taille des blocs pour la signature
    
    def __init__(self, block_size=None):
        self.block_size = block_size or self.BLOCK_SIZE
        self.signatures_cache = {}

    def calculate_signature(self, file_path, block_size=None):
        """
        Calcule la signature d'un fichier (liste de hash des blocs)

        Args:
            file_path: Chemin du fichier
            block_size: Taille des blocs (défaut: 4096)

        Returns:
            dict: Signature du fichier
        """
        block_size = block_size or self.block_size
        blocks = []

        try:
            with open(file_path, 'rb') as f:
                block_num = 0
                while True:
                    data = f.read(block_size)
                    if not data:
                        break

                    # Hash SHA256 du bloc
                    block_hash = hashlib.sha256(data).digest()

                    # Hash faible (rolling hash) pour performance
                    weak_hash = self._rolling_hash(data)

                    blocks.append({
                        'num': block_num,
                        'weak_hash': weak_hash,
                        'strong_hash': block_hash,
                        'size': len(data)
                    })

                    block_num += 1

            file_hash = hashlib.sha256(open(file_path, 'rb').read()).digest()

            signature = {
                'file_size': os.path.getsize(file_path),
                'block_size': block_size,
                'block_count': len(blocks),
                'blocks': blocks,
                'file_hash': file_hash
            }

            return signature

        except Exception as e:
            raise Exception(f"Erreur lors du calcul de signature: {e}")

    def _rolling_hash(self, data):
        """Calcule un hash rapide (weak hash) pour comparaison rapide"""
        # Simple somme des bytes (peut être amélioré avec Adler-32)
        return sum(data) % (2**32)

    def generate_delta(self, source_file, signature):
        """
        Génère les instructions delta basées sur une signature

        Args:
            source_file: Fichier source (nouvelle version)
            signature: Signature de l'ancien fichier

        Returns:
            dict: Instructions delta
        """
        block_size = signature['block_size']
        old_blocks = {(b['weak_hash'], b['strong_hash']): b['num']
                      for b in signature['blocks']}

        delta_ops = []
        matched_blocks = 0
        new_data_size = 0

        try:
            with open(source_file, 'rb') as f:
                position = 0
                buffer = b''

                while True:
                    # Lire un bloc
                    chunk = f.read(block_size)
                    if not chunk:
                        break

                    buffer += chunk

                    # Essayer de matcher avec un bloc existant
                    if len(buffer) >= block_size:
                        block_data = buffer[:block_size]
                        weak = self._rolling_hash(block_data)
                        strong = hashlib.sha256(block_data).digest()

                        # Vérifier si ce bloc existe déjà
                        if (weak, strong) in old_blocks:
                            # Bloc trouvé ! Envoyer juste une référence
                            if len(delta_ops) > 0 and delta_ops[-1]['type'] == 'data':
                                # Envoyer d'abord les données accumulées
                                pass

                            delta_ops.append({
                                'type': 'block',
                                'block_num': old_blocks[(weak, strong)],
                                'position': position
                            })

                            matched_blocks += 1
                            buffer = buffer[block_size:]
                            position += block_size
                        else:
                            # Nouveau bloc - accumuler les données
                            if len(delta_ops) == 0 or delta_ops[-1]['type'] != 'data':
                                delta_ops.append({
                                    'type': 'data',
                                    'data': b'',
                                    'position': position
                                })

                            delta_ops[-1]['data'] += block_data
                            new_data_size += len(block_data)
                            buffer = buffer[block_size:]
                            position += block_size

                # Données restantes
                if buffer:
                    if len(delta_ops) == 0 or delta_ops[-1]['type'] != 'data':
                        delta_ops.append({
                            'type': 'data',
                            'data': buffer,
                            'position': position
                        })
                    else:
                        delta_ops[-1]['data'] += buffer
                    new_data_size += len(buffer)

            # Statistiques
            total_blocks = signature['block_count']
            match_ratio = (matched_blocks / total_blocks * 100) if total_blocks > 0 else 0

            delta = {
                'operations': delta_ops,
                'matched_blocks': matched_blocks,
                'new_data_size': new_data_size,
                'match_ratio': match_ratio,
                'total_ops': len(delta_ops)
            }

            return delta

        except Exception as e:
            raise Exception(f"Erreur lors de la génération du delta: {e}")

    def apply_delta(self, base_file, delta, output_file):
        """
        Applique les instructions delta pour reconstruire le fichier

        Args:
            base_file: Fichier de base (ancienne version)
            delta: Instructions delta
            output_file: Fichier de sortie (nouvelle version)

        Returns:
            bool: True si succès
        """
        try:
            # Lire les blocs du fichier de base
            signature = self.calculate_signature(base_file)
            blocks = {}

            with open(base_file, 'rb') as f:
                for block_info in signature['blocks']:
                    f.seek(block_info['num'] * signature['block_size'])
                    data = f.read(block_info['size'])
                    blocks[block_info['num']] = data

            # Appliquer les opérations delta
            with open(output_file, 'wb') as f:
                for op in delta['operations']:
                    if op['type'] == 'block':
                        # Copier un bloc existant
                        f.write(blocks[op['block_num']])
                    elif op['type'] == 'data':
                        # Écrire de nouvelles données
                        f.write(op['data'])

            return True

        except Exception as e:
            raise Exception(f"Erreur lors de l'application du delta: {e}")

    def calculate_transfer_size(self, delta):
        """Calcule la taille des données à transférer"""
        total_size = 0

        for op in delta['operations']:
            if op['type'] == 'block':
                # Référence de bloc : seulement 8 bytes (numéro du bloc)
                total_size += 8
            elif op['type'] == 'data':
                # Données réelles
                total_size += len(op['data'])

        return total_size

    def get_efficiency(self, original_size, delta):
        """Calcule l'efficacité du delta sync"""
        transfer_size = self.calculate_transfer_size(delta)
        reduction = (1 - transfer_size / original_size) * 100 if original_size > 0 else 0

        return {
            'original_size': original_size,
            'transfer_size': transfer_size,
            'reduction_percent': reduction,
            'bandwidth_saved': original_size - transfer_size
        }


def test_delta_sync():
    """Teste le delta sync"""
    import tempfile

    print("\n=== Test du Delta Sync ===\n")

    ds = DeltaSync()

    # Créer un fichier original
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_v1.txt') as f:
        original_file = f.name
        # Écrire du contenu
        content = "Ligne originale\n" * 1000
        f.write(content)

    # Créer une version modifiée (quelques changements)
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_v2.txt') as f:
        modified_file = f.name
        # Garder 80% du contenu, modifier 20%
        lines = content.split('\n')
        lines[100] = "LIGNE MODIFIÉE"
        lines[200] = "AUTRE MODIFICATION"
        lines[500:520] = ["NOUVELLES LIGNES\n"] * 20
        f.write('\n'.join(lines))

    try:
        # Calculer signature de l'original
        print("1. Calcul de la signature de l'original...")
        signature = ds.calculate_signature(original_file)
        print(f"   ✓ {signature['block_count']} blocs de {signature['block_size']} bytes")

        # Générer le delta
        print("\n2. Génération du delta...")
        delta = ds.generate_delta(modified_file, signature)
        print(f"   ✓ {delta['matched_blocks']} blocs matchés ({delta['match_ratio']:.1f}%)")
        print(f"   ✓ {delta['new_data_size']} bytes de nouvelles données")
        print(f"   ✓ {delta['total_ops']} opérations")

        # Calculer l'efficacité
        print("\n3. Calcul de l'efficacité...")
        original_size = os.path.getsize(modified_file)
        efficiency = ds.get_efficiency(original_size, delta)
        print(f"   Taille originale: {efficiency['original_size']} bytes")
        print(f"   Taille à transférer: {efficiency['transfer_size']} bytes")
        print(f"   Réduction: {efficiency['reduction_percent']:.1f}%")
        print(f"   Bande passante économisée: {efficiency['bandwidth_saved']} bytes")

        # Appliquer le delta
        print("\n4. Application du delta...")
        reconstructed_file = modified_file + '.reconstructed'
        ds.apply_delta(original_file, delta, reconstructed_file)

        # Vérifier
        with open(modified_file, 'rb') as f1, open(reconstructed_file, 'rb') as f2:
            if f1.read() == f2.read():
                print("   ✓ Reconstruction réussie - fichiers identiques")
            else:
                print("   ✗ Erreur - fichiers différents")

        # Nettoyer
        os.unlink(original_file)
        os.unlink(modified_file)
        os.unlink(reconstructed_file)

        print("\n✓ Test terminé avec succès\n")

    except Exception as e:
        print(f"✗ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_delta_sync()
