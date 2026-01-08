from setuptools import setup, find_packages

setup(
    name="daemon-sauvegarde",
    version="2.0.0",
    description="Secure, Delta-Sync capable Backup System",
    author="DepInfo Omega Team",
    packages=find_packages(),
    install_requires=[
        "watchdog>=3.0.0",
        "paramiko>=3.0.0",
        "scp>=0.14.5",
        "flask>=3.0.0",
        "cryptography>=41.0.0",
        "pytest>=7.0.0"
    ],
    entry_points={
        'console_scripts': [
            'backup-client=src.client.daemon:main',
            'backup-status=src.client.status:main',
            'backup-admin=src.client.manage:main',
            'backup-server-agent=src.server.agent:main', # Usually internal
            'backup-gc=src.server.gc:main'
        ],
    },
    python_requires='>=3.8',
)
